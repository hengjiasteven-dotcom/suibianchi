"""随便吃服务端 · 领域服务层。

包含：热量索引匹配、AI 能力（识别 / 推荐 / 对话）、短信、对象存储、地图检索。
所有外部依赖都做成可替换的 provider，默认 mock，配置好密钥后自动切换真实实现。
"""

from datetime import datetime, timezone
import hashlib
import difflib
import base64
import json
import re
from urllib.parse import quote_plus
from typing import Dict, List, Optional

from . import db
from .config import (
    AI_INCLUDE_INDEX,
    AI_PROVIDER,
    BAIDU_MAP_AK,
    BAIDU_MAP_SK,
    DEEPSEEK_API_KEY,
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL,
    MAP_PROVIDER,
    QINIU_BUCKET,
    QINIU_ACCESS_KEY,
    QINIU_DOMAIN,
    QINIU_PRIVATE,
    QINIU_SECRET_KEY,
    QINIU_UPLOAD_HOST,
    QINIU_URL_TTL,
)
from .security import new_id

# ---------------------------------------------------------------- 热量索引

_INDEX: List[Dict] = []
_BY_KEY: Dict[str, Dict] = {}
_PRIMARY: Dict[str, Dict] = {}
_BY_CODE: Dict[str, Dict] = {}

# 食物编码前两位 → 类别名（用于统计与缺口分析）
CATEGORY_NAMES = {
    "01": "谷类及制品",
    "02": "薯类淀粉及制品",
    "03": "干豆类及制品",
    "04": "蔬菜类及制品",
    "05": "菌藻类",
    "06": "水果类及制品",
    "07": "坚果种子类",
    "08": "畜肉类及制品",
    "09": "禽肉类及制品",
    "10": "乳类及制品",
    "11": "蛋类及制品",
    "12": "鱼虾蟹贝类",
    "13": "小吃甜饼类",
    "19": "油脂类",
    "21": "调味品类",
}


def normalize_name(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r"[\[\]（）()【】〔〕\s·,，、。]", "", name)
    return name.lower()


# 加工/制品类词汇：同名情况下优先选未加工的原食材
PROCESSED_MARKERS = (
    "脱水", "干", "油", "松", "罐头", "烤", "炸", "腌", "酱", "卤", "熏",
    "蜜饯", "丝", "脯", "粉", "饮料", "汁", "罐头", "糕", "饼",
)


def processed_score(name: str) -> int:
    return sum(1 for marker in PROCESSED_MARKERS if marker in (name or ""))


def primary_name(name: str) -> str:
    """去掉括号别名后的主名称：小白菜[青菜] → 小白菜。"""
    return re.sub(r"[\[【（(].*?[\]】）)]", "", name or "").strip() or (name or "")


def make_aliases(name: str) -> List[str]:
    """从名称中生成检索别名，例如「大麦[元麦]」→ 大麦 / 元麦。"""
    aliases = {name}
    # 只有方括号里的内容算同义词；圆括号是限定词（如“龙须面（鸡蛋）”）
    for part in re.findall(r"[\[【]([^\]】]+)[\]】]", name):
        for piece in re.split(r"[，,、/]", part):
            piece = piece.strip()
            if piece:
                aliases.add(piece)
    aliases.add(re.sub(r"[\[【（(].*?[\]】）)]", "", name).strip())
    return [a for a in aliases if a]


def load_heat_index() -> int:
    """把数据库里的热量索引加载进内存。"""
    global _INDEX, _BY_KEY, _PRIMARY, _BY_CODE
    rows = db.query_all("SELECT * FROM heat_index")
    _INDEX = rows
    _BY_KEY = {}
    _PRIMARY = {}
    _BY_CODE = {}
    for row in rows:
        _BY_CODE[str(row["food_code"])] = row
        key_primary = normalize_name(primary_name(row["food_name"]))
        if key_primary:
            old = _PRIMARY.get(key_primary)
            if old is None or processed_score(row["food_name"]) < processed_score(old["food_name"]):
                _PRIMARY[key_primary] = row
        keys = {normalize_name(row["food_name"])}
        keys.update(normalize_name(a) for a in make_aliases(row["food_name"]))
        for extra in (row.get("search_keys") or "").split("|"):
            if extra.strip():
                keys.add(normalize_name(extra))
        for key in keys:
            if key:
                _BY_KEY.setdefault(key, row)
    return len(_INDEX)


def index_size() -> int:
    return len(_INDEX)


def category_of(food_code: Optional[str]) -> Optional[str]:
    if not food_code:
        return None
    return CATEGORY_NAMES.get(str(food_code)[:2])


# 索引没收录的常见食物用关键词兜底归类。
# 统计、占比、缺什么都按类别算，宁可粗一点，也不要出现一大块未匹配。
CATEGORY_KEYWORDS = (
    (("米饭", "米线", "米粉", "粥", "面条", "挂面", "拉面", "馒头", "包子", "饺子", "馄饨",
      "螺蛳粉", "酸辣粉", "河粉", "凉皮", "肠粉", "米皮", "意大利面",
      "花卷", "烧饼", "油条", "面包", "吐司", "麦片", "燕麦", "玉米", "藜麦", "方便面", "面"),
     "谷类及制品"),
    (("土豆", "马铃薯", "红薯", "地瓜", "紫薯", "芋头", "山药", "粉条", "粉丝", "藕粉", "淀粉"),
     "薯类淀粉及制品"),
    (("蛋糕", "巧克力", "冰淇淋", "冰激凌", "布丁", "月饼", "汤圆", "饼干", "糖果", "薯片"),
     "小吃甜饼类"),
    (("香菇", "蘑菇", "平菇", "金针菇", "杏鲍菇", "木耳", "银耳", "海带", "紫菜", "裙带菜", "菌", "菇", "藻"),
     "菌藻类"),
    (("青菜", "白菜", "菠菜", "生菜", "油麦菜", "芹菜", "韭菜", "西兰花", "花菜", "花椰菜", "卷心菜",
      "娃娃菜", "空心菜", "苋菜", "茼蒿", "黄瓜", "冬瓜", "南瓜", "丝瓜", "苦瓜", "茄子", "番茄",
      "西红柿", "辣椒", "青椒", "彩椒", "胡萝卜", "萝卜", "洋葱", "莴笋", "竹笋", "芦笋", "豆角",
      "四季豆", "豌豆", "荷兰豆", "毛豆", "莲藕", "藕", "秋葵", "葱", "姜", "蒜", "香菜", "菜"),
     "蔬菜类及制品"),
    (("苹果", "香蕉", "橙", "橘", "柚", "柠檬", "梨", "桃", "葡萄", "提子", "西瓜", "哈密瓜", "草莓",
      "蓝莓", "猕猴桃", "奇异果", "芒果", "菠萝", "荔枝", "龙眼", "樱桃", "石榴", "柿子", "枣", "火龙果",
      "牛油果", "椰子", "山楂", "水果"),
     "水果类及制品"),
    # 蛋类要排在肉类前面，不然“鸡蛋”会被“鸡”抢先归到禽肉
    (("鸡蛋", "鸭蛋", "鹌鹑蛋", "皮蛋", "咸蛋", "蛋"),
     "蛋类及制品"),
    (("猪肉", "牛肉", "羊肉", "猪", "牛", "羊", "排骨", "五花", "里脊", "腊肉", "火腿", "香肠", "培根",
      "肉末", "肉丝", "肉片", "肉"),
     "畜肉类及制品"),
    (("鸡肉", "鸡胸", "鸡腿", "鸡翅", "鸡爪", "鸡", "鸭", "鹅", "烤鸡", "炸鸡"),
     "禽肉类及制品"),
    (("鱼", "虾", "蟹", "贝", "蛤", "蚝", "牡蛎", "鱿鱼", "章鱼", "海参", "鲍", "海鲜"),
     "鱼虾蟹贝类"),
    (("牛奶", "酸奶", "奶粉", "奶酪", "芝士", "黄油", "奶油", "炼乳"),
     "乳类及制品"),
    (("豆腐", "豆浆", "豆干", "豆皮", "腐竹", "豆芽", "黄豆", "绿豆", "红豆", "黑豆", "芸豆", "豆"),
     "干豆类及制品"),
    (("花生", "核桃", "杏仁", "腰果", "瓜子", "开心果", "榛子", "松子", "芝麻", "坚果"),
     "坚果种子类"),
    (("食用油", "植物油", "橄榄油", "花生油", "菜籽油", "大豆油", "香油", "猪油", "油"),
     "油脂类"),
    (("盐", "酱油", "醋", "味精", "鸡精", "蚝油", "豆瓣酱", "甜面酱", "番茄酱", "花椒", "八角",
      "料酒", "孜然", "胡椒", "咖喱", "糖", "酱"),
     "调味品类"),
    (("奶茶", "可乐", "雪碧", "芬达", "汽水", "气泡水", "苏打水", "果汁", "果茶", "咖啡", "美式",
      "拿铁", "卡布奇诺", "摩卡", "浓缩", "豆浆", "豆奶", "椰汁", "椰奶", "乳酸菌", "养乐多",
      "酸梅汤", "凉茶", "啤酒", "白酒", "红酒", "葡萄酒", "黄酒", "清酒", "米酒", "矿泉水",
      "纯净水", "饮料", "茶"),
     "饮料类"),
)


def guess_category(name: str) -> Optional[str]:
    """按关键词给个粗略类别（索引里没有的食材走这里）。"""
    text = (name or "").strip()
    if not text:
        return None
    for keywords, category in CATEGORY_KEYWORDS:
        if any(word in text for word in keywords):
            return category
    return None


def resolve_category(food_name: Optional[str], food_code: Optional[str] = None) -> str:
    """统计口径：先看编码，再回索引找同名，再关键词兜底，最后才归到其他。"""
    by_code = category_of(food_code)
    if by_code:
        return by_code
    name = (food_name or "").strip()
    if name:
        hit = match_food_strict(name)
        if hit:
            by_index = category_of(hit.get("food_code"))
            if by_index:
                return by_index
        by_keyword = guess_category(name)
        if by_keyword:
            return by_keyword
        by_cache = cached_category(name)
        if by_cache:
            return by_cache
    return "其他"


def cached_category(name: str) -> Optional[str]:
    """之前让模型定过的类别，直接复用。"""
    key = (name or "").strip()
    if not key:
        return None
    row = db.query_one("SELECT category FROM food_categories WHERE food_name=?", (key,))
    return row["category"] if row else None


def remember_category(name: str, category: str, source: str = "ai") -> None:
    key = (name or "").strip()
    if not key or category not in set(CATEGORY_NAMES.values()):
        return
    db.execute(
        "INSERT OR REPLACE INTO food_categories(food_name, category, source, updated_at) VALUES(?,?,?,?)",
        (key, category, source, datetime.now(timezone.utc).isoformat()),
    )


def learn_categories(names: List[str]) -> Dict[str, str]:
    """规则认不出来的食材：先查缓存，剩下的一次性问模型，然后写进缓存。"""
    result: Dict[str, str] = {}
    todo: List[str] = []
    for name in names:
        key = (name or "").strip()
        if not key or key in result or key in todo:
            continue
        hit = cached_category(key)
        if hit:
            result[key] = hit
        else:
            todo.append(key)
    if todo:
        try:
            got = get_ai().classify_items(todo)
        except Exception:  # noqa: BLE001
            got = {}
        for key, category in (got or {}).items():
            if category in set(CATEGORY_NAMES.values()):
                remember_category(key, category)
                result[key] = category
    return result


def find_by_code(code: str) -> Optional[Dict]:
    return _BY_CODE.get(str(code or "").strip())


def index_prompt_block() -> str:
    """把热量索引整理成稳定文本，作为提示词的固定前缀。

    索引内容稳定，可命中 DeepSeek 的上下文缓存，重复请求成本极低。
    """
    lines = ["食物编码\t食物名称"]
    for row in sorted(_INDEX, key=lambda r: str(r["food_code"])):
        lines.append(f'{row["food_code"]}\t{row["food_name"]}')
    return "\n".join(lines)


def search_foods(keyword: str, limit: int = 20) -> List[Dict]:
    key = normalize_name(keyword)
    if not key:
        return []
    exact = _BY_KEY.get(key)
    scored = []
    for row in _INDEX:
        name = normalize_name(row["food_name"])
        if key in name:
            scored.append((0, len(name), row))
        else:
            ratio = difflib.SequenceMatcher(None, key, name).ratio()
            if ratio >= 0.6:
                scored.append((1, -ratio, row))
    scored.sort(key=lambda x: (x[0], x[1]))
    results = []
    if exact:
        results.append(exact)
    for _, _, row in scored:
        if row not in results:
            results.append(row)
    return results[:limit]


def match_food(name: str) -> Optional[Dict]:
    """识别结果 → 热量索引匹配：精确 → 别名 → 模糊 → 最长前缀。"""
    key = normalize_name(name)
    if not key:
        return None
    if key in _BY_KEY:
        return _BY_KEY[key]

    if key in _PRIMARY:
        return _PRIMARY[key]

    # 受控包含：查询与主名互为包含且长度接近（米饭 → 粳米饭）
    contained = []
    for row in _INDEX:
        primary = normalize_name(primary_name(row["food_name"]))
        if not primary:
            continue
        # 只允许“索引名包含查询”（米饭 → 粳米饭）；反向包含会误伤（鸡蛋 → 鸡）
        if key in primary and len(primary) - len(key) <= 2:
            contained.append((processed_score(row["food_name"]), len(primary) - len(key), row))
    if contained:
        contained.sort(key=lambda x: (x[0], x[1]))
        return contained[0][2]

    # 模糊匹配收紧到 0.85，避免“鸡蛋”被误匹配成“龙须面（鸡蛋）”
    best, best_ratio = None, 0.0
    for row in _INDEX:
        primary = normalize_name(primary_name(row["food_name"]))
        ratio = difflib.SequenceMatcher(None, key, primary).ratio()
        if ratio > best_ratio:
            best, best_ratio = row, ratio
    if best is not None and best_ratio >= 0.85:
        return best

    # 菜品名降级：番茄炒蛋 → 番茄
    for cut in range(len(key), 1, -1):
        prefix = key[:cut]
        if prefix in _BY_KEY:
            return _BY_KEY[prefix]
    return None


def match_food_strict(name: str) -> Optional[Dict]:
    """分类专用：只认精确/别名/主名/受控包含，不做模糊和前缀截断。

    避免把复合菜名糊到无关食材上（“牛油果奶昔”不该命中“牛油”）。
    """
    key = normalize_name(name)
    if not key:
        return None
    if key in _BY_KEY:
        return _BY_KEY[key]
    if key in _PRIMARY:
        return _PRIMARY[key]
    contained = []
    for row in _INDEX:
        primary = normalize_name(primary_name(row["food_name"]))
        if not primary:
            continue
        if key in primary and len(primary) - len(key) <= 2:
            contained.append((processed_score(row["food_name"]), len(primary) - len(key), row))
    if contained:
        contained.sort(key=lambda x: (x[0], x[1]))
        return contained[0][2]
    return None


# ---------------------------------------------------------------- AI provider

def to_image_url(image: str) -> str:
    """把客户端传来的图片转成 DeepSeek 能识别的 image_url。

    支持三种输入：完整 data URL、http(s) 链接、裸 base64（按文件头推断类型）。
    """
    if not image:
        return ""
    if image.startswith(("data:", "http://", "https://")):
        return image
    head = image[:16]
    try:
        raw = base64.b64decode(head + "=" * (-len(head) % 4))
    except Exception:  # noqa: BLE001
        raw = b""
    return f"data:{sniff_image_mime(raw)};base64,{image}"


def _to_float(value):
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def build_ai_item(raw: Dict) -> Dict:
    """规整模型返回的单条食材，并用「克数 × 每百克热量」交叉校验。

    模型偶尔会把整道菜的热量写进单条食材，这里以分量推算值为准。
    """
    name = (raw.get("food_name") or "").strip()
    grams = _to_float(raw.get("grams"))
    per100 = _to_float(raw.get("kcal_per_100g"))
    kcal = _to_float(raw.get("kcal"))
    corrected = False
    if grams is not None and per100 is not None and grams > 0:
        derived = grams * per100 / 100.0
        if kcal is None or abs(kcal - derived) > max(20.0, derived * 0.25):
            kcal = derived
            corrected = True
    amount_text = raw.get("amount_text") or (f"约{grams:.0f}克" if grams else "")
    return {
        "food_name": name,
        "dish_name": (raw.get("dish_name") or "").strip(),
        "food_code": None,
        "matched_name": None,
        "energy_kcal": round(kcal, 1) if kcal is not None else None,
        "energy_source": "ai_estimate",
        "grams": grams,
        "kcal_per_100g": per100,
        "amount_text": amount_text,
        "cooking": raw.get("cooking", ""),
        "match_status": "ai_estimated" if kcal is not None else "unknown",
        "calorie_corrected": corrected,
    }


def _pick_source(value, fallback: str) -> str:
    """用模型看出来的来源；它认不出来就沿用请求里带的值。"""
    text = (value or "").strip().lower()
    if text in ("diy", "takeout", "unknown"):
        return text
    return fallback


# 忌口三档：1 不太喜欢 / 2 感觉很难吃 / 3 完全不接受
RESTRICTION_LEVELS = {1: "不太喜欢", 2: "感觉很难吃", 3: "完全不接受"}
# 爱好三档：1 有点喜欢 / 2 很喜欢 / 3 最爱吃
PREFERENCE_LEVELS = {1: "有点喜欢", 2: "很喜欢", 3: "最爱吃"}


def restriction_label(level) -> str:
    try:
        return RESTRICTION_LEVELS.get(int(level or 3), RESTRICTION_LEVELS[3])
    except (TypeError, ValueError):
        return RESTRICTION_LEVELS[3]


def preference_label(weight) -> str:
    try:
        return PREFERENCE_LEVELS.get(int(round(float(weight or 2))), PREFERENCE_LEVELS[2])
    except (TypeError, ValueError):
        return PREFERENCE_LEVELS[2]


class MockAI:
    """无密钥时的本地实现：从文字里抽取食材，按规则给推荐。"""

    DISH_HINTS = {
        "番茄炒蛋": ["番茄", "鸡蛋"],
        "西红柿炒鸡蛋": ["番茄", "鸡蛋"],
        "青椒肉丝": ["青椒", "猪肉"],
        "宫保鸡丁": ["鸡肉", "花生"],
        "鱼香肉丝": ["猪肉", "木耳"],
        "蛋炒饭": ["米饭", "鸡蛋"],
        "小米粥": ["小米"],
        "白粥": ["稻米"],
        "牛奶": ["牛乳"],
    }

    STOPWORDS = ["今天", "昨天", "早上", "中午", "晚上", "午饭", "晚饭", "早饭", "吃了", "喝了", "一份", "一碗", "还有", "外加", "和", "了", "的"]

    def recognize(
        self,
        image_keys: List[str],
        text: str,
        meal_slot: str,
        source: str,
        images_base64: Optional[List[str]] = None,
    ) -> Dict:
        raw = (text or "").strip()
        candidates: List[str] = []
        for dish, parts in self.DISH_HINTS.items():
            if dish in raw:
                candidates.extend(parts)
                raw = raw.replace(dish, " ")
        cleaned = raw
        for word in self.STOPWORDS:
            cleaned = cleaned.replace(word, " ")
        for piece in re.split(r"[，,。；;、\s+/和与]+", cleaned):
            piece = piece.strip()
            if len(piece) >= 1:
                candidates.append(piece)

        items = []
        # 只识别名字，不算热量；热量等用户确认后在 estimate() 里做
        seen = set()
        for candidate in candidates:
            if candidate in seen or not candidate:
                continue
            seen.add(candidate)
            items.append(
                {
                    "food_name": candidate,
                    "dish_name": "",
                    "amount_text": "",
                    "cooking": "",
                    "match_status": "recognized",
                }
            )
        if not items:
            items = [
                {
                    "food_name": "未识别食材",
                    "dish_name": "",
                    "amount_text": "",
                    "cooking": "",
                    "match_status": "unmatched",
                }
            ]
        return {
            "meal_slot": meal_slot,
            "source": source,
            "items": items,
            "confidence": 0.6 if items and items[0]["match_status"] == "recognized" else 0.2,
            "note": text or "",
            "engine_note": "本地规则引擎：只识别食材名称，热量在确认后估算",
        }

    def estimate(self, items: List[Dict], meal_slot: str) -> Dict:
        """按食材名估算热量（未接 DeepSeek 时用本地索引兜底）。"""
        result = []
        for item in items:
            name = (item.get("food_name") or "").strip()
            row = match_food(name) if name else None
            energy = row["energy_kcal"] if row else None
            result.append(
                {
                    "food_name": name,
                    "dish_name": item.get("dish_name", ""),
                    "amount_text": item.get("amount_text", "") or ("约100克" if row else ""),
                    "grams": 100.0 if row else None,
                    "kcal_per_100g": energy,
                    "energy_kcal": energy,
                    "cooking": item.get("cooking", ""),
                    "match_status": "index_estimated" if row else "unknown",
                }
            )
        return {
            "items": result,
            "energy_total_kcal": round(sum(i["energy_kcal"] or 0 for i in result), 1),
            "engine_note": "本地索引估算（未接入 DeepSeek）",
        }


    def classify_items(self, names: List[str]) -> Dict[str, str]:
        """没接模型时补不了分类：返回空，让规则兜底。"""
        return {}


    def recommend(self, context: Dict) -> Dict:
        restrictions = context.get("restrictions", [])
        # 「很难吃」和「完全不接受」不进候选；「不太喜欢」只是少推，仍可能出现在备选里
        avoided = [r["keyword"] for r in restrictions if int(r.get("level") or 3) >= 2]
        goals = context.get("goals", [])
        gaps = context.get("gaps", [])
        scene = context.get("scene", "diy")

        pool = [
            row
            for row in _INDEX
            if not any(word and word in row["food_name"] for word in avoided)
        ]
        if not pool:
            pool = list(_INDEX)

        def pick(category_prefixes, count, used):
            chosen = []
            for row in pool:
                if str(row["food_code"])[:2] in category_prefixes and row["food_name"] not in used:
                    chosen.append(row)
                    used.add(row["food_name"])
                    if len(chosen) >= count:
                        break
            return chosen

        used = set()
        plans = []
        for idx, style in enumerate(["快手", "清淡", "家常"], start=1):
            proteins = pick(["08", "09", "12", "11"], 1, used)
            veggies = pick(["04", "05"], 2, used)
            staples = pick(["01", "02"], 1, used)
            if not (proteins and veggies):
                break
            items = proteins + veggies + staples
            kcal = sum(item["energy_kcal"] or 0 for item in items)
            plans.append(
                {
                    "title": f"方案{chr(64 + idx)}｜{'下厨' if scene == 'diy' else '外卖'}·{style}",
                    "items": [
                        {
                            "food_name": item["food_name"],
                            "food_code": item["food_code"],
                            "energy_kcal": item["energy_kcal"],
                        }
                        for item in items
                    ],
                    "energy_kcal_estimate": round(kcal, 1),
                    "reason": self._reason(goals, gaps, restrictions),
                    "scene": scene,
                }
            )
        return {
            "plans": plans,
            "note": "本地规则引擎生成的方案（未接入 DeepSeek），热量为原料热量参考值",
        }

    @staticmethod
    def _reason(goals, gaps, restrictions):
        parts = []
        if goals:
            parts.append("已按你的膳食目标：" + "、".join(goals))
        if gaps:
            parts.append("补充近期较少摄入的类别：" + "、".join(gaps))
        if restrictions:
            parts.append(
                "已避开忌口："
                + "、".join(f"{r['keyword']}（{restriction_label(r.get('level'))}）" for r in restrictions)
            )
        return "；".join(parts) if parts else "按均衡膳食原则搭配"

    def chat(self, message: str, context: Dict) -> Dict:
        facts = []
        for match in re.finditer(r"(不吃|忌口|过敏|讨厌)\s*([\u4e00-\u9fa5]{1,6})", message):
            level = 3 if match.group(1) in ("忌口", "过敏") else 2
            facts.append(
                {"type": "restriction", "keyword": match.group(2), "level": level, "needs_confirm": True}
            )
        for match in re.finditer(r"(爱吃|喜欢|最爱)\s*([\u4e00-\u9fa5]{1,6})", message):
            facts.append(
                {
                    "type": "preference",
                    "keyword": match.group(2),
                    "level": 3 if match.group(1) == "最爱" else 2,
                    "needs_confirm": True,
                }
            )
        reply = "我记下了。" if facts else ""
        reply += "根据你最近记录和当前想法，建议先考虑清淡的蛋白质搭配一份深色蔬菜。"
        if context.get("restrictions"):
            reply += "（已避开：" + "、".join(
                f"{r['keyword']}·{restriction_label(r.get('level'))}" for r in context["restrictions"][:5]
            ) + "）"
        nearby = context.get("nearby_stores") or []
        names = "、".join(s.get("name") for s in nearby[:5] if s.get("name"))
        if names:
            reply += f" 附近可参考：{names}。"
        return {"reply": reply, "facts": facts, "finished": False}


class DeepSeekAI(MockAI):
    """接入 DeepSeek 后启用；未配置密钥时不会被实例化。"""

    def chat(self, message: str, context: Dict) -> Dict:  # pragma: no cover
        """真正的对话式推荐：结合最近吃了什么、缺什么、爱好与忌口。"""
        restrictions = "、".join(r["keyword"] for r in context.get("restrictions", [])) or "无"
        # 会话里刚聊到的口味 + 档案里已确认的爱好，两边都参考
        likes = "、".join(context.get("session_likes") or []) or "暂无"
        saved_likes = "、".join(
            f"{p['keyword']}（{preference_label(p.get('weight'))}）"
            for p in context.get("preferences", [])
        ) or "暂无"
        goals = "、".join(context.get("goals") or []) or "无"
        gaps = "、".join(context.get("gaps") or []) or "无"
        recent = context.get("recent") or {}
        recent_text = "、".join(recent.get("dishes") or recent.get("top_foods") or []) or "最近没有记录"
        nearby = context.get("nearby_stores") or []
        nearby_parts = []
        for item in nearby[:6]:
            name = item.get("name")
            if not name:
                continue
            distance = item.get("distance_m")
            nearby_parts.append(f"{name}（约{distance}米）" if distance else name)
        nearby_text = "、".join(nearby_parts) or "无"
        prompt = (
            "用户在「随便吃」里问该吃什么，请像朋友一样用中文回答。要求："
            "① 先用一句话回应用户当下的想法，不要一上来就报菜单；"
            "② 给 2~3 个具体可执行的选择（家常做法或外卖怎么点都行），每个都说明为什么适合他；"
            "③ 忌口是硬约束，绝对不能出现任何一条；"
            "④ 参考他最近吃过的，别推刚吃过的同类，优先补上最近缺的类别；"
            "⑤ 留意用户对某道菜或某种食材的评价，抽成候选（没评价就别编）："
            "负面评价（难吃、太油、太辣、受不了、不想吃、恶心）→ restriction；"
            "正面评价（好吃、喜欢、想再吃、很香）→ preference；keyword 只写具体菜品或食材；"
            "⑥ 每条候选都要带 level，只能填 1 / 2 / 3："
            "restriction：1 不太喜欢 / 2 感觉很难吃 / 3 完全不接受；"
            "preference：1 有点喜欢 / 2 很喜欢 / 3 最爱吃；"
            "⑦ 只输出 JSON，不要额外解释："
            '{"reply":"","facts":[{"type":"preference","keyword":"","level":2},'
            '{"type":"restriction","keyword":"","level":3}],"finished":false}'
            "⑧ 回复控制在 150 字以内，facts 最多 3 条；"
            "⑨ 如果提供了附近店铺，推荐外卖时只能从这些店铺里选名字，回复里只写店铺名，不要提数据来源；"
            f"\n忌口（硬约束）：{restrictions}"
            f"\n长期档案里的爱好：{saved_likes}"
            f"\n本次对话聊到的口味：{likes}"
            f"\n膳食目标：{goals}"
            f"\n最近缺的类别：{gaps}"
            f"\n城市：{context.get('city') or '未知'}\n最近 7 天吃过：{recent_text}"
            f"\n附近店铺：{nearby_text}"
            f"\n用户这次说：{message}"
        )
        try:
            content = self._call(
                [
                    {"role": "system", "content": "你是饮食参谋，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.6,
                max_tokens=600,
            )
            data = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
            reply = (data.get("reply") or "").strip()
            if not reply:
                raise ValueError("empty reply")
            facts = []
            for raw in data.get("facts", []):
                keyword = (raw.get("keyword") or "").strip()
                if not keyword:
                    continue
                if raw.get("type") == "restriction":
                    facts.append(
                        {
                            "type": "restriction",
                            "keyword": keyword,
                            "level": raw.get("level"),
                            "needs_confirm": True,
                        }
                    )
                else:
                    facts.append(
                        {
                            "type": "preference",
                            "keyword": keyword,
                            "level": raw.get("level") or raw.get("weight") or 2,
                            "needs_confirm": True,
                        }
                    )
            return {
                "reply": reply,
                "facts": facts,
                "finished": bool(data.get("finished")),
            }
        except Exception:  # noqa: BLE001
            return super().chat(message, context)

    def _call(self, messages, temperature=0.3, max_tokens=800):
        import httpx

        response = httpx.post(
            f"{DEEPSEEK_BASE_URL}/chat/completions",
            headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}"},
            json={
                "model": DEEPSEEK_MODEL,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=httpx.Timeout(45.0, connect=8.0),
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]

    def recognize(self, image_keys, text, meal_slot, source, images_base64=None):  # pragma: no cover
        # 有图时文字只是补充；没图时那句话就是全部信息，必须从文字里拆出菜品
        if images_base64:
            task = (
                "请识别这一餐实际吃到的食材和菜品，只列出名称，不要估算热量。要求："
                "注意：可能一次发来多张照片（全景、特写、订单截图等），它们拍的是同一餐，"
                "请合成一份清单，同一样东西不要重复计数；"
                "① 每种食材单独列出，不要合成一盘菜；"
                "② 如果图是外卖订单、菜单或小票截图，先读出上面的菜名和份数，"
                "再把每道菜拆成食材，并在 dish_name 里标出它属于哪道菜；份数是 2 就按两份写；"
                "③ 图上有备注（如「少辣」「不要香菜」）时，放进 note 字段；"
                "④ 顺手判断这一餐是外卖还是自己做的：外卖订单、外卖包装、一次性餐具→takeout；"
                "自家做的饭菜→diy；判断不了就写 unknown；"
                "⑤ 判断不出的不要写。只输出 JSON，不要解释："
                '{"items":[{"food_name":"","dish_name":"","amount_text":"","cooking":""}],"note":"","source":""}'
                f"\n餐次：{meal_slot}；来源：{source}；用户补充的文字：{text}"
            )
        else:
            # 纯文字：这句话就是全部信息，别把它当成备注忽略掉
            task = (
                "用户没有发图片，只写了一句吃了什么，这句话就是全部信息。"
                "请把这句话拆成菜品和食材，只列名称，不要估算热量。要求："
                "① 先认出提到的菜品名（如「黄焖鸡米饭」），填进 dish_name；"
                "② 再把每道菜拆成具体食材（鸡腿肉、香菇、米饭……），"
                "每种单独一行，food_name 填食材；"
                "③ 用户没提到的不要编；④ 只输出 JSON，不要解释："
                '{"items":[{"food_name":"","dish_name":"","amount_text":"","cooking":""}],"note":"","source":""}'
                f"\n餐次：{meal_slot}；来源：{source}；用户原话（这就是全部信息）：{text}"
            )

        prompt = task
        blocks: List[Dict] = [{"type": "text", "text": prompt}]
        for image in images_base64 or []:
            url = to_image_url(image)
            blocks.append({"type": "image_url", "image_url": {"url": url}})
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "你是饮食记录助手。这一轮只负责认食材名称，热量留到用户确认后再算。"
                    ),
                },
                {"role": "user", "content": blocks},
            ]
            # temperature=0：识别结果要尽量稳定，同一张图不要每次都给出不同份量
            content = self._call(messages, temperature=0.0, max_tokens=1000)
            data = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
        except Exception:  # noqa: BLE001
            return super().recognize(image_keys, text, meal_slot, source, images_base64)
        items = []
        for raw in data.get("items", []):
            name = (raw.get("food_name") or "").strip()
            if not name:
                continue
            items.append(
                {
                    "food_name": name,
                    "dish_name": (raw.get("dish_name") or "").strip(),
                    "amount_text": raw.get("amount_text", ""),
                    "cooking": raw.get("cooking", ""),
                    "match_status": "recognized",
                }
            )
        # 图片里读到的备注（如「少辣」「不要香菜」）才是这条记录的备注；
        # 引擎说明放在 engine_note，不写进用户记录。
        note_text = (data.get("note") or "").strip()
        if text.strip() and note_text:
            note_text = f"{text.strip()}；{note_text}"
        elif text.strip():
            note_text = text.strip()
        # 模型偶尔会返回空清单：退回本地关键词拆分，至少不能什么都不给
        if not items and text.strip():
            fallback = super().recognize(image_keys, text, meal_slot, source, images_base64)
            if fallback.get("items"):
                fallback["engine_note"] = "模型没拆出来，已按文字关键词兜底"
                return fallback
        return {
            "meal_slot": meal_slot,
            "source": _pick_source(data.get("source"), source),
            "items": items,
            "confidence": 0.8,
            "note": note_text,
            "engine_note": "DeepSeek 识别：只产出食材名称与备注，热量待用户确认后估算",
        }


    def estimate(self, items: List[Dict], meal_slot: str) -> Dict:  # pragma: no cover
        """用户确认食材后，再单独调一次模型估算热量。"""
        lines = []
        for item in items:
            name = (item.get("food_name") or "").strip()
            if not name:
                continue
            dish = (item.get("dish_name") or "").strip()
            amount = (item.get("amount_text") or "").strip()
            if amount in ("未知", "unknown"):
                amount = ""
            tail = []
            if dish:
                tail.append(f"来自：{dish}")
            if amount:
                tail.append(f"份量：{amount}")
            lines.append(f"- {name}（{'；'.join(tail)}）" if tail else f"- {name}")
        prompt = (
            "请给下面这些食材估算热量。要求："
            "① 每种食材单独给出，不要合并；"
            "② 给出这一份的大致质量（克），拿不准就按常见一份的量估；"
            "③ 给出每 100 克的热量和这一份的热量（均为 kcal）；"
            "④ 炒、煎、炸类必须计入烹调油，每道菜按 10~15 克食用油估；凉拌、清蒸类不计或按 3~5 克；"
            "⑤ food_name、dish_name、amount_text、cooking 必须原样照抄上面清单，不要自己改写、补写或填占位词；"
            "⑥ 只输出 JSON，不要解释："
            '{"items":[{"food_name":"","dish_name":"","amount_text":"","grams":0,"kcal_per_100g":0,"kcal":0,"cooking":""}]}'
            f"\n餐次：{meal_slot}\n食材清单：\n" + "\n".join(lines)
        )
        try:
            content = self._call(
                [
                    {"role": "system", "content": "你是饮食记录助手，负责按食材估算热量，只给估算值。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=800,
            )
            data = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
        except Exception:  # noqa: BLE001
            return super().estimate(items, meal_slot)
        result = [build_ai_item(raw) for raw in data.get("items", [])]
        # 菜品归属以用户确认过的输入为准，丢弃模型可能回填的占位词
        dish_by_name = {
            (i.get("food_name") or "").strip(): (i.get("dish_name") or "").strip() for i in items
        }
        cooking_by_name = {
            (i.get("food_name") or "").strip(): (i.get("cooking") or "").strip() for i in items
        }
        for item in result:
            src_dish = dish_by_name.get((item.get("food_name") or "").strip(), "")
            item["dish_name"] = src_dish or (item.get("dish_name") or "").strip()
            src_cooking = cooking_by_name.get((item.get("food_name") or "").strip(), "")
            item["cooking"] = src_cooking or (item.get("cooking") or "").strip()
        return {
            "items": result,
            "energy_total_kcal": round(sum(i["energy_kcal"] or 0 for i in result), 1),
            "engine_note": "DeepSeek 估算：热量按食材逐项上报，服务端汇总",
        }

    def classify_items(self, names: List[str]) -> Dict[str, str]:  # pragma: no cover
        """把规则认不出来的食材名归到固定类别（只分类，不算热量）。"""
        if not names:
            return {}
        all_categories = "、".join(CATEGORY_NAMES.values())
        lines = "\n".join(f"- {n}" for n in names)
        prompt = (
            "把下面这些食物或饮品归到类别里，只能从给定类别中选一个最贴近的："
            f"{all_categories}。要求："
            "① 每一条都必须给类别，不能留空、不能自造类别；"
            "② 按主要原料判断，例如奶茶→饮料类、牛腩→畜肉类及制品、豆腐→干豆类及制品；"
            "③ 拿不准就选最接近的那一类，不要写解释；"
            "④ 只输出 JSON："
            '{"items":[{"food_name":"","category":""}]}'
            f"\n食物清单：\n{lines}"
        )
        try:
            content = self._call(
                [
                    {"role": "system", "content": "你是食物分类助手，只输出 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=600,
            )
            data = json.loads(re.search(r"\{.*\}", content, re.S).group(0))
        except Exception:  # noqa: BLE001
            return {}
        valid = set(CATEGORY_NAMES.values())
        out: Dict[str, str] = {}
        for raw in data.get("items", []):
            name = (raw.get("food_name") or "").strip()
            category = (raw.get("category") or "").strip()
            if name and category in valid:
                out[name] = category
        return out


def get_ai():
    if AI_PROVIDER == "deepseek" and DEEPSEEK_API_KEY:
        return DeepSeekAI()
    return MockAI()


# ---------------------------------------------------------------- 短信

def send_sms_code(phone: str, code: str) -> Dict:
    from .config import SMS_DEV_MODE

    if SMS_DEV_MODE:
        return {"sent": True, "dev_mode": True, "code": code}
    # 生产：在此调用短信服务商 SDK
    return {"sent": True, "dev_mode": False}


# ---------------------------------------------------------------- 对象存储

IMAGE_MIME_EXT = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/gif": "gif",
    "image/webp": "webp",
}


def qiniu_enabled() -> bool:
    """AK / SK / 空间名都配齐才算启用；否则退回 mock，方便本地联调。"""
    return bool(QINIU_ACCESS_KEY and QINIU_SECRET_KEY and QINIU_BUCKET)


def public_url(object_key: str) -> str:
    """object_key → 对外可访问的完整地址。

    私有空间返回带签名的临时 URL（有效期 QINIU_URL_TTL）；公开空间直接拼域名。
    每次请求记录都重新签一次，所以过期不影响使用。
    """
    if not object_key or not QINIU_DOMAIN:
        return ""
    url = f"{QINIU_DOMAIN.rstrip('/')}/{object_key.lstrip('/')}"
    if not QINIU_PRIVATE or not qiniu_enabled():
        return url
    try:
        return _qiniu_auth().private_download_url(url, expires=QINIU_URL_TTL)
    except Exception:  # noqa: BLE001
        return url


def sniff_image_mime(data: bytes) -> str:
    """按文件头判断图片类型，认不出来就按 JPEG 处理（与识别那条链一致）。"""
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def decode_image_payload(image: str) -> Optional[bytes]:
    """把 data URL / 裸 base64 解成原始字节；解不开返回 None。"""
    if not image:
        return None
    payload = image
    if image.startswith("data:"):
        _, _, payload = image.partition(",")
    payload = payload.strip()
    if not payload:
        return None
    try:
        return base64.b64decode(payload)
    except Exception:  # noqa: BLE001
        return None


def _qiniu_auth():
    from qiniu import Auth

    return Auth(QINIU_ACCESS_KEY, QINIU_SECRET_KEY)


def upload_meal_photo(user_id: int, data: bytes, seq: int = 0) -> Optional[str]:
    """把一餐的照片传到七牛，返回 object_key。

    没配七牛、或上传失败都返回 None（不抛异常），让调用方安静地跳过这张图。
    """
    if not qiniu_enabled() or not data:
        return None
    mime = sniff_image_mime(data)
    ext = IMAGE_MIME_EXT.get(mime, "jpg")
    suffix = f"-{seq}" if seq else ""
    object_key = f"meals/{user_id}/{new_id()}{suffix}.{ext}"
    try:
        from qiniu import put_data

        token = _qiniu_auth().upload_token(QINIU_BUCKET, object_key, 3600)
        result, info = put_data(token, object_key, data, mime_type=mime)
        if getattr(info, "status_code", 0) != 200 or not result:
            return None
        return object_key
    except Exception:  # noqa: BLE001
        return None


def create_upload_token(user_id: int, count: int = 1) -> Dict:
    """给客户端直传七牛用的上传凭证。

    当前主流程是服务端中转上传（见 upload_meal_photo），这个接口保留给直传方案用。
    """
    count = max(1, min(int(count or 1), 9))
    keys = [f"meals/{user_id}/{new_id()}.jpg" for _ in range(count)]
    if not qiniu_enabled():
        return {
            "provider": "mock",
            "upload_token": "mock-token",
            "tokens": ["mock-token"] * count,
            "keys": keys,
            "bucket": QINIU_BUCKET,
            "domain": QINIU_DOMAIN,
            "upload_host": "",
        }
    auth = _qiniu_auth()
    tokens = [auth.upload_token(QINIU_BUCKET, key, 3600) for key in keys]
    return {
        "provider": "qiniu",
        "upload_token": tokens[0],
        "tokens": tokens,
        "keys": keys,
        "bucket": QINIU_BUCKET,
        "domain": QINIU_DOMAIN,
        "upload_host": QINIU_UPLOAD_HOST,
    }


# ---------------------------------------------------------------- 地图检索


def _baidu_query(params: List[tuple]) -> str:
    """按百度官方规则：每个 value 做一次 UTF-8 URL 编码，按参数顺序拼接。"""
    return "&".join(
        f"{key}={quote_plus(str(value), safe='')}" for key, value in params
    )


def _baidu_sn(path: str, query: str, sk: str) -> str:
    """百度 SN 签名：path?query + SK 整体再做一次 URL 编码，最后 MD5。"""
    whole = path + "?" + query + sk
    return hashlib.md5(quote_plus(whole, safe="").encode("utf-8")).hexdigest()


def nearby_stores(lat: float, lng: float, keyword: str = "餐厅", limit: int = 5) -> Dict:
    if MAP_PROVIDER == "mock" or not BAIDU_MAP_AK:
        demo = [
            {"name": "巷口家常菜", "distance_m": 320, "type": "家常菜"},
            {"name": "轻食沙拉工坊", "distance_m": 480, "type": "轻食"},
            {"name": "老城面馆", "distance_m": 650, "type": "面食"},
        ]
        return {"provider": "mock", "stores": demo[:limit]}
    # 生产：按需调用百度地点检索，只查这一次，不建全量商家库；结果用后即弃
    import httpx

    try:
        path = "/place/v2/search"
        params = [
            ("query", keyword),
            ("location", f"{lat},{lng}"),
            ("radius", "3000"),
            ("output", "json"),
            ("scope", "2"),
            ("page_size", str(max(1, min(limit, 20)))),
            ("page_num", "0"),
            ("ak", BAIDU_MAP_AK),
        ]
        query = _baidu_query(params)
        if BAIDU_MAP_SK:
            query += "&sn=" + _baidu_sn(path, query, BAIDU_MAP_SK)
        url = f"https://api.map.baidu.com{path}?{query}"
        # 百度域名同时有 IPv6 记录，服务器也有 IPv6；绑定 IPv4 本地地址，
        # 确保请求从白名单里的 IPv4 出口出去。
        transport = httpx.HTTPTransport(local_address="0.0.0.0")
        with httpx.Client(transport=transport, timeout=8.0) as client:
            response = client.get(url)
        data = response.json()
        if data.get("status") != 0:
            return {"provider": "baidu", "stores": [], "error": data.get("message") or "百度地点检索失败"}
        stores = []
        for item in data.get("results", [])[:limit]:
            detail = item.get("detail_info") or {}
            distance = detail.get("distance")
            try:
                distance = int(distance) if distance is not None else None
            except (TypeError, ValueError):
                distance = None
            stores.append(
                {
                    "name": item.get("name") or "",
                    "distance_m": distance,
                    "type": item.get("type") or "",
                }
            )
        return {"provider": "baidu", "stores": stores}
    except Exception as exc:  # noqa: BLE001
        return {"provider": "baidu", "stores": [], "error": str(exc)}
