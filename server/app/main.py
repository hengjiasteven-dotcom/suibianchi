"""随便吃服务端 · FastAPI 应用入口。

启动：
    uvicorn app.main:app --reload --port 8000
接口文档：
    http://127.0.0.1:8000/docs
"""

import json
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from . import db, services
from .config import (
    AI_DAILY_PER_USER,
    AI_DAILY_TOTAL,
    CHAT_TTL_SECONDS,
    RECOGNITION_KEEP_DAYS,
    SMS_CODE_TTL_SECONDS,
    SMS_DEV_MODE,
)
from . import site_auth
from .site_auth import SiteAuthError
from .security import (
    create_access_token,
    decode_access_token,
    hash_device_token,
    hash_password,
    new_device_token,
    new_id,
    new_sms_code,
    now_iso,
    verify_password,
)

app = FastAPI(title="随便吃 API", version="0.1.0")
bearer = HTTPBearer(auto_error=False)

# 对话会话保存在进程内存，带 TTL；生产环境替换为 Redis
CHAT_SESSIONS: Dict[str, Dict] = {}

# AI 调用计数（进程内，按天重置；多实例部署时换成 Redis）
AI_USAGE: Dict = {"date": "", "total": 0, "by_user": {}}


def check_ai_quota(user_id: int) -> None:
    """限制单用户与全站的 AI 调用量，避免接口被人白嫖。"""
    today = datetime.now(timezone.utc).date().isoformat()
    if AI_USAGE["date"] != today:
        AI_USAGE["date"] = today
        AI_USAGE["total"] = 0
        AI_USAGE["by_user"] = {}
    used = AI_USAGE["by_user"].get(user_id, 0)
    if used >= AI_DAILY_PER_USER:
        raise HTTPException(status_code=429, detail=f"今日 AI 调用已达上限（{AI_DAILY_PER_USER} 次），请明天再试")
    if AI_USAGE["total"] >= AI_DAILY_TOTAL:
        raise HTTPException(status_code=503, detail="服务今日 AI 额度已用完，请联系管理员")
    AI_USAGE["by_user"][user_id] = used + 1
    AI_USAGE["total"] += 1


def import_heat_index_file() -> int:
    """首次启动时，把导出的热量索引导入数据库。"""
    from .config import HEAT_INDEX_PATH

    if not HEAT_INDEX_PATH.exists():
        return 0
    inserted = 0
    with open(HEAT_INDEX_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            db.execute(
                "INSERT OR REPLACE INTO heat_index(food_code, food_name, energy_kcal, energy_kj, water_g, protein_g, fat_g, carb_g, search_keys) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    row["food_code"],
                    row["food_name"],
                    row["energy_kcal"],
                    row.get("energy_kj"),
                    row.get("water_g"),
                    row.get("protein_g"),
                    row.get("fat_g"),
                    row.get("carb_g"),
                    "",
                ),
            )
            inserted += 1
    return inserted


@app.on_event("startup")
def on_startup():
    db.init_db()
    # 每次启动都与索引文件对齐，保证名称/数值与导出版本一致
    import_heat_index_file()
    count = services.load_heat_index()
    app.state.heat_index_count = count
    # 启动时清一次过期的识别任务（里面存着图片 base64，不清理会一直涨）
    _cleanup_recognition_jobs(force=True)


# ------------------------------------------------------------------ 依赖

def current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer)) -> int:
    if credentials is None:
        raise HTTPException(status_code=401, detail="未登录")
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise HTTPException(status_code=401, detail="登录已失效")
    user = db.query_one("SELECT * FROM users WHERE id=? AND status='active'", (user_id,))
    if not user:
        raise HTTPException(status_code=401, detail="账号不可用")
    return user_id


def _level_value(raw, default: int = 3) -> int:
    """把模型给的档位（数字或中文说法）归一成 1~3。"""
    if raw is None or raw == "":
        return default
    if isinstance(raw, (int, float)):
        return max(1, min(3, int(raw)))
    text = str(raw).strip()
    if text.isdigit():
        return max(1, min(3, int(text)))
    for token, level in (
        ("完全", 3), ("绝不", 3), ("过敏", 3), ("一口都不", 3),
        ("很难吃", 2), ("难吃", 2), ("恶心", 2), ("受不了", 2), ("讨厌", 2),
        ("最爱", 3), ("最喜欢", 3), ("超爱", 3), ("非常喜欢", 3),
        ("很喜欢", 2), ("喜欢", 2), ("好吃", 2), ("很香", 2),
        ("不太", 1), ("还行", 1), ("一般", 1), ("勉强", 1),
    ):
        if token in text:
            return level
    return default


def profile_context(user_id: int) -> Dict:
    profile = db.query_one("SELECT * FROM profiles WHERE user_id=?", (user_id,)) or {}
    account = db.query_one("SELECT * FROM users WHERE id=?", (user_id,)) or {}
    restrictions = db.query_all("SELECT * FROM restrictions WHERE user_id=?", (user_id,))
    preferences = db.query_all("SELECT * FROM preferences WHERE user_id=?", (user_id,))
    goals = json.loads(profile.get("goals") or "[]")
    phone = account.get("phone") or ""
    masked = f"{phone[:3]}****{phone[-4:]}" if len(phone) == 11 else phone
    return {
        "user_id": user_id,
        "name": profile.get("name") or "",
        # 对外展示和加好友用的 6 位码
        "code": account.get("public_id") or "",
        # 6 位码只能自己改一次，false 表示已经锁死
        "code_changeable": not account.get("code_changed"),
        "signature": profile.get("signature") or "",
        "avatar": profile.get("avatar") or "",
        "gender": profile.get("gender") or "",
        "phone": masked,
        "city": profile.get("city"),
        "goals": goals,
        "restrictions": [r for r in restrictions if r["confirmed"]],
        # 只有确认过的爱好才参与后续推荐
        "preferences": [p for p in preferences if p["confirmed"]],
    }


# ------------------------------------------------------------------ 基础模型

class SmsSendIn(BaseModel):
    phone: str = Field(min_length=11, max_length=11)


class SmsVerifyIn(BaseModel):
    phone: str
    code: str
    password: Optional[str] = None


class PasswordLoginIn(BaseModel):
    phone: str
    password: str


class DeviceLoginIn(BaseModel):
    device_token: str


# 内置头像编号：客户端把这几张图打进包里，服务端只存编号
ALLOWED_AVATARS = {f"avatar_{i}" for i in range(1, 8)}


class CodeIn(BaseModel):
    """改自己的对外 ID：6 位小写字母或数字。"""
    code: str


class ProfileIn(BaseModel):
    # 内置头像编号：avatar_1 ... avatar_7；传空字符串表示换回默认首字头像
    avatar: Optional[str] = None
    gender: Optional[str] = None
    name: Optional[str] = None
    signature: Optional[str] = None
    city: Optional[str] = None
    # 膳食目标与忌口属于用餐习惯，放在以后的报告里维护，个人主页不展示
    goals: Optional[List[str]] = None


class RestrictionIn(BaseModel):
    type: str = "dislike"
    keyword: str
    # 1 不太喜欢 / 2 感觉很难吃 / 3 完全不接受
    level: int = 3
    source: str = "manual"


class PreferenceIn(BaseModel):
    keyword: str
    # 1 有点喜欢 / 2 很喜欢 / 3 最爱吃
    weight: float = 3.0


class MealItemIn(BaseModel):
    food_name: str
    dish_name: str = ""
    food_code: Optional[str] = None
    energy_kcal: Optional[float] = None
    amount_text: str = ""
    cooking: str = ""
    match_status: str = "manual"


class MealCreateIn(BaseModel):
    meal_slot: str
    meal_date: Optional[str] = None
    eaten_at: Optional[str] = None
    source: str = "unknown"
    note: str = ""
    items: List[MealItemIn] = Field(default_factory=list)


class MealPatchIn(BaseModel):
    meal_slot: Optional[str] = None
    meal_date: Optional[str] = None
    eaten_at: Optional[str] = None
    source: Optional[str] = None
    note: Optional[str] = None
    items: Optional[List[MealItemIn]] = None


class PhotoIn(BaseModel):
    count: int = 1


class EstimateIn(BaseModel):
    items: List[MealItemIn] = Field(default_factory=list)
    meal_slot: str = "lunch"


class RecognitionIn(BaseModel):
    image_keys: List[str] = Field(default_factory=list)
    images_base64: List[str] = Field(default_factory=list, description="base64 或 data URL 形式的图片，直接传给 DeepSeek")
    text: str = ""
    meal_slot: str = "lunch"
    source: str = "unknown"


class RecognitionConfirmIn(BaseModel):
    meal_slot: Optional[str] = None
    eaten_at: Optional[str] = None
    source: Optional[str] = None
    note: Optional[str] = None
    items: Optional[List[MealItemIn]] = None
    # 同一格已经有记录时：replace 整体替换（旧行为）/ append 并到原记录上
    mode: str = "replace"


class RecommendIn(BaseModel):
    scene: str = Field(default="diy", description="diy 或 takeout")
    lat: Optional[float] = None
    lng: Optional[float] = None
    keyword: Optional[str] = None


class ChatMessageIn(BaseModel):
    content: str
    nearby_mode: bool = False
    nearby_page: int = 0
    lat: Optional[float] = None
    lng: Optional[float] = None
    keyword: Optional[str] = None


class NearbyModeIn(BaseModel):
    enabled: bool = True
    lat: Optional[float] = None
    lng: Optional[float] = None


class ShareIn(BaseModel):
    type: str = Field(default="daily", description="daily 或 weekly")
    date: Optional[str] = None


class MomentIn(BaseModel):
    """广场里发一条分享：kind 决定是“最近一餐”还是“本周占比”。"""
    kind: str = Field(default="daily", description="daily 或 weekly")
    date: Optional[str] = None


class FriendIn(BaseModel):
    """加好友时填对方的 6 位用户码。"""
    code: str = Field(min_length=6, max_length=6)


# ------------------------------------------------------------------ 元信息

@app.get("/health")
def health():
    return {
        "status": "ok",
        "heat_index_count": getattr(app.state, "heat_index_count", 0),
        "sms_dev_mode": SMS_DEV_MODE,
        "ai_provider": services.AI_PROVIDER,
        # 只报提供方，不暴露空间名/密钥；用来确认图片存储是否真的接上了
        "storage": "qiniu" if services.qiniu_enabled() else "mock",
        "storage_configured": bool(services.QINIU_DOMAIN),
    }


def _read_release() -> Dict:
    """读发版信息（server/release.json）。文件不存在或坏了都不报错，当没发过版。"""
    try:
        from .config import RELEASE_FILE

        if not RELEASE_FILE.exists():
            return {}
        return json.loads(RELEASE_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


@app.get("/api/v1/app/version")
def app_version():
    """客户端检查更新：最新版本号 + 现签的下载地址。

    不需登录也能看：更新提示要在登录页就能弹。下载地址指向七牛私有空间，
    所以每次请求现签一次，有效期跟 QINIU_URL_TTL 一致。
    """
    info = _read_release()
    if not info:
        return {
            "version_code": 0,
            "version_name": "",
            "notes": "",
            "force": False,
            "download_url": "",
        }

    key = (info.get("object_key") or "").strip()
    return {
        "version_code": int(info.get("version_code") or 0),
        "version_name": info.get("version_name") or "",
        "notes": info.get("notes") or "",
        "force": bool(info.get("force")),
        "download_url": services.public_url(key) if key else "",
    }


# ------------------------------------------------------------------ 认证

def _client_ip(request: Request) -> str:
    """取真实客户端 IP：优先 Cloudflare/代理头，再退回直连地址。

    转发给站点账号服务，让它的“每 IP 限流”按真实用户算，而不是全部算在 127.0.0.1 上。
    """
    for header in ("cf-connecting-ip", "true-client-ip", "x-real-ip"):
        value = (request.headers.get(header) or "").strip()
        if value:
            return value
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128


def _check_password(password: str) -> str:
    """和站点保持一致：8~128 位，不能只有空格。"""
    value = password or ""
    if not value.strip():
        raise HTTPException(status_code=400, detail="密码不能全是空格")
    if len(value) < PASSWORD_MIN_LENGTH or len(value) > PASSWORD_MAX_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=f"密码需要 {PASSWORD_MIN_LENGTH}~{PASSWORD_MAX_LENGTH} 位",
        )
    return value


def _issue_tokens(user_id: int) -> Dict:
    """登录成功：登记这台设备 + 发访问令牌（站点登录与本地登录共用）。"""
    device_token = new_device_token()
    db.execute(
        "INSERT INTO devices(user_id, token_hash, created_at, last_login_at) VALUES(?,?,?,?)",
        (user_id, hash_device_token(device_token), now_iso(), now_iso()),
    )
    return {"access_token": create_access_token(user_id), "device_token": device_token}

@app.post("/api/v1/auth/sms/send")
def send_sms(payload: SmsSendIn, request: Request):
    # 方案 C：短信走站点账号体系（阿里云号码认证），我们不再自己发
    if site_auth.enabled():
        try:
            site_auth.send_code(payload.phone, purpose="login", client_ip=_client_ip(request))
        except SiteAuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"sent": True, "dev_mode": False}
    code = new_sms_code()
    expires = (datetime.now(timezone.utc) + timedelta(seconds=SMS_CODE_TTL_SECONDS)).isoformat()
    db.execute(
        "INSERT INTO sms_codes(phone, code, expires_at) VALUES(?,?,?) "
        "ON CONFLICT(phone) DO UPDATE SET code=excluded.code, expires_at=excluded.expires_at",
        (payload.phone, code, expires),
    )
    return services.send_sms_code(payload.phone, code)


@app.post("/api/v1/auth/sms/verify")
def verify_sms(payload: SmsVerifyIn, request: Request):
    # 方案 C：验证码由站点校验（通过即自动建号），我们只负责发自己的登录令牌
    if site_auth.enabled():
        try:
            identity = site_auth.login_with_code(
                payload.phone, payload.code, client_ip=_client_ip(request)
            )
        except SiteAuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        # 站点的注册接口只认验证码、没地方存密码。所以两件事自己做：
        #   1. 是不是新用户由我们判断（站点不会告诉我们）
        #   2. 新用户必须设密码，密码存在我们本地
        known = db.query_one(
            "SELECT id FROM users WHERE site_user_id=?", (identity["site_user_id"],)
        ) or db.query_one("SELECT id FROM users WHERE phone=?", (identity["phone"],))

        password = payload.password or ""
        if not known:
            # 不给密码注册，这个号以后就只能靠短信进来，直接拦住
            if not password:
                raise HTTPException(
                    status_code=400,
                    detail=f"首次注册请设置密码（{PASSWORD_MIN_LENGTH} 位以上）",
                )
            password = _check_password(password)

        user = db.find_or_create_site_user(
            identity["site_user_id"], identity["phone"], identity.get("nickname", "")
        )
        # 本地留一份密码（站点存不了）；已经有密码的不覆盖
        if password and not user.get("password_hash"):
            db.execute(
                "UPDATE users SET password_hash=? WHERE id=?",
                (hash_password(password), user["id"]),
            )
        return _issue_tokens(user["id"])

    row = db.query_one("SELECT * FROM sms_codes WHERE phone=?", (payload.phone,))
    if not row or row["code"] != payload.code:
        raise HTTPException(status_code=400, detail="验证码不正确")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="验证码已过期")

    user = db.query_one("SELECT * FROM users WHERE phone=?", (payload.phone,))
    if not user:
        if not payload.password:
            raise HTTPException(
                status_code=400,
                detail=f"首次注册请设置密码（{PASSWORD_MIN_LENGTH} 位以上）",
            )
        password = _check_password(payload.password)
        user_id = db.execute(
            "INSERT INTO users(phone, password_hash, created_at, public_id) VALUES(?,?,?,?)",
            (payload.phone, hash_password(password), now_iso(), db.new_unique_public_id()),
        )
        db.execute(
            "INSERT INTO profiles(user_id, city, goals, updated_at) VALUES(?,?,?,?)",
            (user_id, None, "[]", now_iso()),
        )
    else:
        user_id = user["id"]
        if payload.password and not user["password_hash"]:
            db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(payload.password), user_id))

    db.execute("DELETE FROM sms_codes WHERE phone=?", (payload.phone,))
    device_token = new_device_token()
    db.execute(
        "INSERT INTO devices(user_id, token_hash, created_at, last_login_at) VALUES(?,?,?,?)",
        (user_id, hash_device_token(device_token), now_iso(), now_iso()),
    )
    return {"access_token": create_access_token(user_id), "device_token": device_token}


@app.post("/api/v1/auth/login/password")
def login_password(payload: PasswordLoginIn, request: Request):
    # 密码有两个来源，两边都要试：
    #   1. App 内注册时我们把密码存在自己库里（站点存不了）
    #   2. 网站注册的老账号，密码在站点那边
    local = db.query_one("SELECT * FROM users WHERE phone=?", (payload.phone,))
    if local and local.get("password_hash") and verify_password(
        payload.password, local["password_hash"]
    ):
        return _issue_tokens(local["id"])

    if site_auth.enabled():
        try:
            identity = site_auth.login_with_password(
                payload.phone, payload.password, client_ip=_client_ip(request)
            )
        except SiteAuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
        user = db.find_or_create_site_user(
            identity["site_user_id"], identity["phone"], identity.get("nickname", "")
        )
        return _issue_tokens(user["id"])
    raise HTTPException(status_code=401, detail="手机号或密码不正确")


@app.post("/api/v1/auth/device/login")
def login_device(payload: DeviceLoginIn):
    row = db.query_one("SELECT * FROM devices WHERE token_hash=?", (hash_device_token(payload.device_token),))
    if not row:
        raise HTTPException(status_code=401, detail="设备令牌无效")
    db.execute("UPDATE devices SET last_login_at=? WHERE id=?", (now_iso(), row["id"]))
    return {"access_token": create_access_token(row["user_id"])}


@app.post("/api/v1/auth/password/reset")
def reset_password(payload: SmsVerifyIn):
    # 方案 C：找回密码走站点的重置接口，密码存在同一套账号里
    if site_auth.enabled():
        if not payload.password:
            raise HTTPException(status_code=400, detail="请提供新密码")
        try:
            site_auth.reset_password(payload.phone, payload.code, payload.password)
        except SiteAuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}
    row = db.query_one("SELECT * FROM sms_codes WHERE phone=?", (payload.phone,))
    if not row or row["code"] != payload.code:
        raise HTTPException(status_code=400, detail="验证码不正确")
    if not payload.password:
        raise HTTPException(status_code=400, detail="请提供新密码")
    user = db.query_one("SELECT * FROM users WHERE phone=?", (payload.phone,))
    if not user:
        raise HTTPException(status_code=404, detail="账号不存在")
    db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(payload.password), user["id"]))
    db.execute("DELETE FROM sms_codes WHERE phone=?", (payload.phone,))
    return {"ok": True}


@app.delete("/api/v1/account")
def delete_account(user_id: int = Depends(current_user)):
    """合规通道：注销账号并删除个人数据（日常记录不提供删除入口）。"""
    db.execute("DELETE FROM meal_items WHERE meal_id IN (SELECT id FROM meals WHERE user_id=?)", (user_id,))
    db.execute("DELETE FROM meal_photos WHERE meal_id IN (SELECT id FROM meals WHERE user_id=?)", (user_id,))
    for table in ("meals", "restrictions", "preferences", "profiles", "devices", "shares", "recognition_jobs"):
        db.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    return {"ok": True, "deleted": True}


# ------------------------------------------------------------------ 档案

@app.get("/api/v1/profile")
def get_profile(user_id: int = Depends(current_user)):
    return profile_context(user_id)


@app.put("/api/v1/profile")
def put_profile(payload: ProfileIn, user_id: int = Depends(current_user)):
    # 没传的字段保持原值，不清空
    current = db.query_one("SELECT * FROM profiles WHERE user_id=?", (user_id,)) or {}
    name = payload.name if payload.name is not None else current.get("name")
    signature = payload.signature if payload.signature is not None else current.get("signature")
    avatar = payload.avatar if payload.avatar is not None else current.get("avatar")
    # 只接受内置头像编号，别的值一律拒掉
    if avatar and avatar not in ALLOWED_AVATARS:
        raise HTTPException(status_code=400, detail="头像编号不对")
    gender = payload.gender if payload.gender is not None else current.get("gender")
    city = payload.city if payload.city is not None else current.get("city")
    goals = (
        payload.goals
        if payload.goals is not None
        else json.loads(current.get("goals") or "[]")
    )
    db.execute(
        "INSERT INTO profiles(user_id, name, signature, avatar, gender, city, goals, updated_at) "
        "VALUES(?,?,?,?,?,?,?,?) "
        "ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, signature=excluded.signature, "
        "avatar=excluded.avatar, gender=excluded.gender, city=excluded.city, "
        "goals=excluded.goals, updated_at=excluded.updated_at",
        (
            user_id, name, signature, avatar, gender, city,
            json.dumps(goals, ensure_ascii=False), now_iso(),
        ),
    )
    return profile_context(user_id)


@app.put("/api/v1/profile/code")
def change_public_code(payload: CodeIn, user_id: int = Depends(current_user)):
    """改自己的对外 ID。

    只允许 6 位小写字母或数字，且不能和别人重。改完旧 ID 立刻失效。
    只能改一次：改完 code_changed 置 1，以后再请求一律 409。
    """
    code = (payload.code or "").strip().lower()
    account = db.query_one(
        "SELECT public_id, code_changed FROM users WHERE id=?", (user_id,)
    ) or {}
    # 改过一次就锁死，防止反复改名让人找不着
    if account.get("code_changed"):
        raise HTTPException(status_code=409, detail="ID 只能改一次，已经锁定了")

    # 先看有没有锁死，再看格式：锁死的用户无论传什么都应该拿到同一个提示
    if not re.fullmatch(r"[0-9a-z]{6}", code):
        raise HTTPException(status_code=400, detail="ID 只能是 6 位小写字母或数字")

    owner = db.query_one("SELECT id FROM users WHERE public_id=?", (code,))
    if owner and owner["id"] != user_id:
        raise HTTPException(status_code=409, detail="这个 ID 已经有人用了")

    db.execute(
        "UPDATE users SET public_id=?, code_changed=1 WHERE id=?",
        (code, user_id),
    )
    return profile_context(user_id)


@app.get("/api/v1/profile/restrictions")
def list_restrictions(user_id: int = Depends(current_user)):
    return db.query_all("SELECT * FROM restrictions WHERE user_id=? ORDER BY id", (user_id,))


@app.post("/api/v1/profile/restrictions")
def add_restriction(payload: RestrictionIn, user_id: int = Depends(current_user)):
    rid = db.execute(
        "INSERT INTO restrictions(user_id, type, keyword, level, confirmed, source, created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (
            user_id,
            payload.type,
            payload.keyword,
            max(1, min(3, payload.level)),
            1 if payload.source == "manual" else 0,
            payload.source,
            now_iso(),
        ),
    )
    return db.query_one("SELECT * FROM restrictions WHERE id=?", (rid,))


@app.patch("/api/v1/profile/restrictions/{rid}")
def confirm_restriction(
    rid: int,
    confirmed: bool = True,
    level: Optional[int] = None,
    user_id: int = Depends(current_user),
):
    row = db.query_one("SELECT * FROM restrictions WHERE id=? AND user_id=?", (rid, user_id))
    if not row:
        raise HTTPException(status_code=404, detail="忌口条目不存在")
    if not confirmed:
        # 拒绝就直接丢掉这条候选
        db.execute("DELETE FROM restrictions WHERE id=?", (rid,))
        return {"id": rid, "rejected": True}
    # 报告里也能改程度：只传 level 就是单纯调档
    fixed = level if level is not None else int(row.get("level") or 3)
    db.execute(
        "UPDATE restrictions SET confirmed=1, level=? WHERE id=?", (max(1, min(3, int(fixed))), rid)
    )
    return db.query_one("SELECT * FROM restrictions WHERE id=?", (rid,))


@app.get("/api/v1/profile/preferences")
def list_preferences(user_id: int = Depends(current_user)):
    return db.query_all("SELECT * FROM preferences WHERE user_id=? ORDER BY id", (user_id,))


@app.post("/api/v1/profile/preferences")
def add_preference(payload: PreferenceIn, user_id: int = Depends(current_user)):
    pid = db.execute(
        "INSERT INTO preferences(user_id, keyword, weight, created_at) VALUES(?,?,?,?)",
        (user_id, payload.keyword, payload.weight, now_iso()),
    )
    return db.query_one("SELECT * FROM preferences WHERE id=?", (pid,))


@app.patch("/api/v1/profile/preferences/{pid}")
def confirm_preference(
    pid: int,
    confirmed: bool = True,
    weight: Optional[float] = None,
    user_id: int = Depends(current_user),
):
    row = db.query_one("SELECT * FROM preferences WHERE id=? AND user_id=?", (pid, user_id))
    if not row:
        raise HTTPException(status_code=404, detail="爱好条目不存在")
    if not confirmed:
        db.execute("DELETE FROM preferences WHERE id=?", (pid,))
        return {"id": pid, "rejected": True}
    fixed = weight if weight is not None else (row.get("weight") or 3.0)
    # 同样只传 weight 就是改程度：1 有点喜欢 / 2 很喜欢 / 3 最爱吃
    db.execute(
        "UPDATE preferences SET confirmed=1, weight=? WHERE id=?", (max(1.0, min(3.0, float(fixed))), pid)
    )
    return db.query_one("SELECT * FROM preferences WHERE id=?", (pid,))


@app.get("/api/v1/profile/pending")
def pending_facts(user_id: int = Depends(current_user)):
    """对话里抽到、还没经用户确认的爱好与忌口。"""
    return {
        "preferences": db.query_all(
            "SELECT * FROM preferences WHERE user_id=? AND confirmed=0 ORDER BY id DESC", (user_id,)
        ),
        "restrictions": db.query_all(
            "SELECT * FROM restrictions WHERE user_id=? AND confirmed=0 ORDER BY id DESC", (user_id,)
        ),
    }


# ------------------------------------------------------------------ 热量索引

@app.get("/api/v1/foods/search")
def foods_search(q: str = Query(..., min_length=1), limit: int = 20):
    return {"items": services.search_foods(q, limit)}


# ------------------------------------------------------------------ 餐食记录

MAX_BACKFILL_DAYS = 2


def _check_backfill(eaten_at: Optional[str]):
    if not eaten_at:
        return
    try:
        ts = datetime.fromisoformat(eaten_at)
    except ValueError:
        raise HTTPException(status_code=400, detail="用餐时间格式不正确")
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) - ts > timedelta(days=MAX_BACKFILL_DAYS):
        raise HTTPException(status_code=400, detail="最多只能补录两天内的记录")


def _save_items(meal_id: int, items: List[MealItemIn], index_fallback: bool = True):
    for item in items:
        energy = item.energy_kcal
        status = item.match_status
        if energy is None:
            # 两步识别流程把热量交给后台 AI 估算，不用本地索引抢答
            row = services.match_food(item.food_name) if index_fallback else None
            if row:
                energy = row["energy_kcal"]
                status = "matched"
            else:
                status = "unmatched" if index_fallback else "pending_estimate"
        code = item.food_code
        if not code:
            row = services.match_food(item.food_name)
            code = row["food_code"] if row else None
        db.execute(
            "INSERT INTO meal_items(meal_id, food_name, dish_name, food_code, energy_kcal, amount_text, cooking, match_status, created_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                meal_id,
                item.food_name,
                item.dish_name or "",
                code,
                energy,
                item.amount_text,
                item.cooking,
                status,
                now_iso(),
            ),
        )


# 估算超过这个时长还没回填，视为卡住，下次查询时自动收尾
STALE_ESTIMATE_MINUTES = 10


def _needs_estimation(items: List[MealItemIn]) -> bool:
    return any(item.energy_kcal is None and item.food_name.strip() for item in items)


def _resolve_meal_date(payload) -> str:
    """这条记录算哪一天：优先用客户端给的本机日期，否则退回时间戳里的日期。"""
    given = getattr(payload, "meal_date", None)
    if given:
        return given
    return (getattr(payload, "eaten_at", None) or now_iso())[:10]


def _insert_meal(payload: MealCreateIn, user_id: int, mode: str = "replace"):
    """一天四餐、每餐只留一条。

    mode="replace"：这一格已有记录就整体替换（旧行为）。
    mode="append" ：把这次的并进已有记录，不覆盖；同菜同食材的不重复加。

    返回 (meal_id, 是否还要估算, 是不是覆盖了旧的, 是不是追加到旧的)。
    """
    meal_date = _resolve_meal_date(payload)
    existing = db.query_one(
        "SELECT * FROM meals WHERE user_id=? AND meal_date=? AND meal_slot=? AND status<>'deleted'",
        (user_id, meal_date, payload.meal_slot),
    )

    if existing and mode == "append":
        meal_id = existing["id"]
        merged: List[MealItemIn] = []
        seen = set()
        # 先把原有的排前面，并保留它们已经算好的热量
        for row in db.query_all(
            "SELECT * FROM meal_items WHERE meal_id=? ORDER BY id", (meal_id,)
        ):
            key = ((row["food_name"] or "").strip(), (row["dish_name"] or "").strip())
            seen.add(key)
            merged.append(
                MealItemIn(
                    food_name=row["food_name"],
                    dish_name=row["dish_name"] or "",
                    food_code=row["food_code"],
                    energy_kcal=row["energy_kcal"],
                    amount_text=row["amount_text"] or "",
                    cooking=row["cooking"] or "",
                    match_status=row["match_status"] or "kept",
                )
            )
        # 再把这次新加的接上；完全一样的（同食材同菜）不重复加
        for item in payload.items:
            key = (item.food_name.strip(), (item.dish_name or "").strip())
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)

        needs = _needs_estimation(merged)
        status = "estimating" if needs else "confirmed"
        old_note = (existing.get("note") or "").strip()
        new_note = (payload.note or "").strip()
        note = "；".join(n for n in (old_note, new_note) if n)
        # 追加不改这顿饭原本的时间，也不动来源
        db.execute(
            "UPDATE meals SET note=?, status=?, updated_at=? WHERE id=?",
            (note, status, now_iso(), meal_id),
        )
        db.execute("DELETE FROM meal_items WHERE meal_id=?", (meal_id,))
        _save_items(meal_id, merged, index_fallback=not needs)
        return meal_id, needs, False, True

    needs = _needs_estimation(payload.items)
    status = "estimating" if needs else "confirmed"
    eaten_at = payload.eaten_at or now_iso()
    if existing:
        meal_id = existing["id"]
        db.execute(
            "UPDATE meals SET eaten_at=?, source=?, note=?, status=?, updated_at=? WHERE id=?", 
            (eaten_at, payload.source, payload.note, status, now_iso(), meal_id),
        )
        db.execute("DELETE FROM meal_items WHERE meal_id=?", (meal_id,))
    else:
        meal_id = db.execute(
            "INSERT INTO meals(user_id, meal_slot, meal_date, eaten_at, source, note, status, created_at, updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (
                user_id,
                payload.meal_slot,
                meal_date,
                eaten_at,
                payload.source,
                payload.note,
                status,
                now_iso(),
                now_iso(),
            ),
        )
    _save_items(meal_id, payload.items, index_fallback=not needs)
    return meal_id, needs, existing is not None, False


def _store_meal_photos(meal_id: int, user_id: int, images: List[str], append: bool = False):
    """把这一餐的照片传到七牛，成功的那些把 object_key 记到 meal_photos。

    跑在后台任务里：图片在识别阶段已经进过服务端，这里只负责落库存档，不让用户等。
    append=False 时先清空旧照片再写（换了一顿就不该留着上一顿的图）；
    append=True 时保留旧图，只往后追加。
    """
    if not append:
        db.execute("DELETE FROM meal_photos WHERE meal_id=?", (meal_id,))
    for seq, raw in enumerate(images):
        data = services.decode_image_payload(raw)
        if not data:
            continue
        object_key = services.upload_meal_photo(user_id, data, seq)
        if object_key:
            db.execute(
                "INSERT INTO meal_photos(meal_id, object_key, created_at) VALUES(?,?,?)",
                (meal_id, object_key, now_iso()),
            )


def _run_estimation(meal_id: int):
    """后台任务：调 AI 逐项估算热量并回填；失败或算不出时用本地索引兜底。"""
    meal = db.query_one("SELECT * FROM meals WHERE id=?", (meal_id,))
    if not meal:
        return
    rows = db.query_all("SELECT * FROM meal_items WHERE meal_id=? ORDER BY id", (meal_id,))
    payload = [
        {
            "food_name": r["food_name"],
            "dish_name": r.get("dish_name") or "",
            "amount_text": r.get("amount_text") or "",
            "cooking": r.get("cooking") or "",
        }
        for r in rows
        if r["food_name"]
    ]
    estimates = []
    if payload:
        try:
            estimates = services.get_ai().estimate(payload, meal["meal_slot"]).get("items", [])
        except Exception:  # noqa: BLE001
            estimates = []
    by_name: Dict[str, Dict] = {}
    for est in estimates:
        key = (est.get("food_name") or "").strip()
        if key and key not in by_name:
            by_name[key] = est
    for row in rows:
        est = by_name.get(row["food_name"])
        energy = est.get("energy_kcal") if est else None
        status = "ai_estimated" if energy is not None else "unmatched"
        if energy is None:
            fallback = services.match_food(row["food_name"])
            if fallback:
                energy = fallback["energy_kcal"]
                status = "index_estimated"
        db.execute(
            "UPDATE meal_items SET energy_kcal=?, match_status=? WHERE id=?", (energy, status, row["id"])
        )
    db.execute(
        "UPDATE meals SET status='confirmed', updated_at=? WHERE id=?", (now_iso(), meal_id)
    )


@app.post("/api/v1/meals")
def create_meal(
    payload: MealCreateIn,
    background: BackgroundTasks,
    user_id: int = Depends(current_user),
):
    if payload.meal_slot not in ("breakfast", "lunch", "dinner", "supper"):
        raise HTTPException(status_code=400, detail="餐次只能是 breakfast / lunch / dinner / supper")
    _check_backfill(payload.eaten_at)
    meal_id, needs, replaced, _appended = _insert_meal(payload, user_id)
    if needs:
        background.add_task(_run_estimation, meal_id)
    result = get_meal(meal_id, user_id)
    result["replaced"] = replaced
    return result


def _is_stale(updated_at: Optional[str]) -> bool:
    if not updated_at:
        return True
    try:
        stamp = datetime.fromisoformat(updated_at)
    except ValueError:
        return True
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - stamp > timedelta(minutes=STALE_ESTIMATE_MINUTES)


def _attach_meal_detail(meal: Dict) -> Dict:
    """给一条记录补上食材、照片、总能量。列表和详情共用，保证两边的字段一致。

    这里必须把所有字段都填上：客户端是 Gson 反序列化，JSON 里缺键会变成 null。
    """
    meal["items"] = db.query_all(
        "SELECT * FROM meal_items WHERE meal_id=? ORDER BY id", (meal["id"],)
    )
    photos = db.query_all(
        "SELECT * FROM meal_photos WHERE meal_id=? ORDER BY id", (meal["id"],)
    )
    for photo in photos:
        # 库里只存 object_key，对外给完整地址，换域名/加签名都不影响历史数据
        photo["url"] = services.public_url(photo["object_key"])
    meal["photos"] = photos
    meal["total_energy_kcal"] = round(
        sum(i["energy_kcal"] or 0 for i in meal["items"]), 1
    )
    return meal


@app.get("/api/v1/meals")
def list_meals(
    start: Optional[str] = None,
    end: Optional[str] = None,
    user_id: int = Depends(current_user),
):
    sql = "SELECT * FROM meals WHERE user_id=?"
    params: List = [user_id]
    if start:
        sql += " AND eaten_at>=?"
        params.append(start)
    if end:
        sql += " AND eaten_at<=?"
        params.append(end)
    sql += " ORDER BY eaten_at DESC"
    meals = db.query_all(sql, tuple(params))
    for meal in meals:
        # 估算中卡住超过阈值就收尾，避免一直显示“估算中”
        if meal["status"] == "estimating" and _is_stale(meal["updated_at"]):
            db.execute("UPDATE meals SET status='confirmed' WHERE id=?", (meal["id"],))
            meal["status"] = "confirmed"
        meal["items"] = db.query_all("SELECT * FROM meal_items WHERE meal_id=? ORDER BY id", (meal["id"],))
        _attach_meal_detail(meal)
    return {"items": meals}


@app.get("/api/v1/meals/{meal_id}")
def get_meal(meal_id: int, user_id: int = Depends(current_user)):
    meal = db.query_one("SELECT * FROM meals WHERE id=? AND user_id=?", (meal_id, user_id))
    if not meal:
        raise HTTPException(status_code=404, detail="记录不存在")
    return _attach_meal_detail(meal)


@app.patch("/api/v1/meals/{meal_id}")
def patch_meal(
    meal_id: int,
    payload: MealPatchIn,
    background: BackgroundTasks,
    user_id: int = Depends(current_user),
):
    meal = db.query_one("SELECT * FROM meals WHERE id=? AND user_id=?", (meal_id, user_id))
    if not meal:
        raise HTTPException(status_code=404, detail="记录不存在")
    _check_backfill(payload.eaten_at)
    # 一天四餐、每餐只留一条：换餐次时不能撞到当天已有的那条
    new_slot = payload.meal_slot or meal["meal_slot"]
    new_date = (
        payload.meal_date
        or meal.get("meal_date")
        or (payload.eaten_at or meal["eaten_at"])[:10]
    )
    clash = db.query_one(
        "SELECT id FROM meals WHERE user_id=? AND meal_date=? AND meal_slot=? AND id<>?",
        (user_id, new_date, new_slot, meal_id),
    )
    if clash:
        raise HTTPException(
            status_code=409,
            detail="这一餐当天已经有记录了，直接改那一条就行",
        )
    fields, params = [], []
    if payload.meal_slot is not None:
        if payload.meal_slot not in ("breakfast", "lunch", "dinner", "supper"):
            raise HTTPException(status_code=400, detail="餐次只能是 breakfast / lunch / dinner / supper")
        fields.append("meal_slot=?")
        params.append(payload.meal_slot)
    for key, value in (
        ("eaten_at", payload.eaten_at),
        ("source", payload.source),
        ("note", payload.note),
        ("meal_date", payload.meal_date),
    ):
        if value is not None:
            fields.append(f"{key}=?")
            params.append(value)
    if fields:
        fields.append("updated_at=?")
        params.append(now_iso())
        params.extend([meal_id, user_id])
        db.execute(f"UPDATE meals SET {', '.join(fields)} WHERE id=? AND user_id=?", tuple(params))
    if payload.items is not None:
        needs = _needs_estimation(payload.items)
        db.execute("DELETE FROM meal_items WHERE meal_id=?", (meal_id,))
        _save_items(meal_id, payload.items, index_fallback=not needs)
        # 改过名的食材没有热量：标成估算中，丢后台重算
        db.execute(
            "UPDATE meals SET status=?, updated_at=? WHERE id=?",
            ("estimating" if needs else "confirmed", now_iso(), meal_id),
        )
        if needs:
            background.add_task(_run_estimation, meal_id)
    return get_meal(meal_id, user_id)


@app.post("/api/v1/meals/{meal_id}/estimate")
def estimate_meal(
    meal_id: int,
    background: BackgroundTasks,
    user_id: int = Depends(current_user),
):
    """重算某一餐的热量：先前台标成估算中，再丢给后台任务。"""
    meal = db.query_one("SELECT * FROM meals WHERE id=? AND user_id=?", (meal_id, user_id))
    if not meal:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.execute(
        "UPDATE meals SET status='estimating', updated_at=? WHERE id=?", (now_iso(), meal_id)
    )
    background.add_task(_run_estimation, meal_id)
    return get_meal(meal_id, user_id)


@app.post("/api/v1/meals/{meal_id}/photos")
def add_photos(meal_id: int, payload: PhotoIn, user_id: int = Depends(current_user)):
    meal = db.query_one("SELECT * FROM meals WHERE id=? AND user_id=?", (meal_id, user_id))
    if not meal:
        raise HTTPException(status_code=404, detail="记录不存在")
    token = services.create_upload_token(user_id, payload.count)
    return token


# ------------------------------------------------------------------ 识别

# 识别任务里存着上传图片的 base64，是库里最大的一块垃圾。两头都要收：
#   1. 用户确认入库后立刻把图片丢掉（这时照片已经传七牛了）
#   2. 整条任务也只留 RECOGNITION_KEEP_DAYS 天
_JOB_CLEANUP: Dict[str, Optional[datetime]] = {"at": None}


def _shrink_job_payload(job_id: str) -> None:
    """把识别任务里的图片 base64 清掉，只留文字信息。"""
    job = db.query_one("SELECT payload FROM recognition_jobs WHERE id=?", (job_id,))
    if not job:
        return
    try:
        original = json.loads(job["payload"])
    except Exception:  # noqa: BLE001
        original = {}
    slim = {k: v for k, v in original.items() if k != "images_base64"}
    slim["images_count"] = len(original.get("images_base64") or [])
    db.execute(
        "UPDATE recognition_jobs SET payload=? WHERE id=?",
        (json.dumps(slim, ensure_ascii=False), job_id),
    )


def _cleanup_recognition_jobs(force: bool = False) -> int:
    """删掉过期的识别任务，返回删了几条。

    最多一小时真扫一次表，不然每个识别请求都删一遍太浪费。
    """
    now = datetime.now(timezone.utc)
    last = _JOB_CLEANUP["at"]
    if not force and last is not None and (now - last).total_seconds() < 3600:
        return 0
    _JOB_CLEANUP["at"] = now
    cutoff = (now - timedelta(days=RECOGNITION_KEEP_DAYS)).isoformat()
    return db.execute_rowcount(
        "DELETE FROM recognition_jobs WHERE created_at < ?", (cutoff,)
    )

@app.post("/api/v1/recognition")
def recognize(payload: RecognitionIn, user_id: int = Depends(current_user)):
    check_ai_quota(user_id)
    # 顺手清一次过期的识别任务（内部限流，不会每个请求都真删）
    _cleanup_recognition_jobs()
    ai = services.get_ai()
    result = ai.recognize(
        payload.image_keys, payload.text, payload.meal_slot, payload.source, payload.images_base64
    )
    job_id = new_id()
    db.execute(
        "INSERT INTO recognition_jobs(id, user_id, payload, result, status, created_at) VALUES(?,?,?,?,?,?)",
        (
            job_id,
            user_id,
            json.dumps(payload.dict(), ensure_ascii=False),
            json.dumps(result, ensure_ascii=False),
            "pending",
            now_iso(),
        ),
    )
    return {"job_id": job_id, "result": result}


@app.post("/api/v1/recognition/{job_id}/confirm")
def confirm_recognition(
    job_id: str,
    payload: RecognitionConfirmIn,
    background: BackgroundTasks,
    user_id: int = Depends(current_user),
):
    job = db.query_one("SELECT * FROM recognition_jobs WHERE id=? AND user_id=?", (job_id, user_id))
    if not job:
        raise HTTPException(status_code=404, detail="识别任务不存在")
    result = json.loads(job["result"])
    items = payload.items or [
        MealItemIn(
            food_name=item.get("food_name", ""),
            dish_name=item.get("dish_name", ""),
            food_code=item.get("food_code"),
            energy_kcal=item.get("energy_kcal"),
            amount_text=item.get("amount_text", ""),
            cooking=item.get("cooking", ""),
            match_status=item.get("match_status", "ai_estimated"),
        )
        for item in result.get("items", [])
    ]
    meal_payload = MealCreateIn(
        meal_slot=payload.meal_slot or result.get("meal_slot", "lunch"),
        eaten_at=payload.eaten_at,
        # 用户界面不再问来源：优先用识别推断出来的
        source=(
            payload.source
            if payload.source in ("diy", "takeout")
            else result.get("source") or payload.source or "unknown"
        ),
        note=payload.note if payload.note is not None else result.get("note", ""),
        items=items,
    )
    # 同一格已经有记录时：用户选“并进去”就 append，否则按老行为整体替换
    mode = payload.mode if payload.mode in ("replace", "append") else "replace"
    meal_id, needs, replaced, appended = _insert_meal(meal_payload, user_id, mode)
    db.execute("UPDATE recognition_jobs SET status='confirmed' WHERE id=?", (job_id,))
    # 照片存档：有图就丢给后台传七牛
    images = json.loads(job["payload"]).get("images_base64") or []
    # 图片已经交给后台传七牛了，任务里那份 base64 马上清掉，不然库会一直涨
    _shrink_job_payload(job_id)
    if images:
        # 追加时保留旧图，只往后加
        background.add_task(_store_meal_photos, meal_id, user_id, images, mode == "append")
    elif mode != "append":
        # 覆盖式记录又没带新图：旧图应该清掉；追加时不动旧图
        db.execute("DELETE FROM meal_photos WHERE meal_id=?", (meal_id,))
    # 用户确认完就立刻返回，热量由后台估算完成后再回填
    if needs:
        background.add_task(_run_estimation, meal_id)
    result = get_meal(meal_id, user_id)
    result["replaced"] = replaced
    result["appended"] = appended
    return result


@app.post("/api/v1/estimates")
def estimates(payload: EstimateIn, user_id: int = Depends(current_user)):
    """用户确认食材后，再单独估算热量（识别阶段只出名称，不算热量）。"""
    check_ai_quota(user_id)
    ai = services.get_ai()
    raw_items = [item.dict() for item in payload.items]
    return ai.estimate(raw_items, payload.meal_slot)


# ------------------------------------------------------------------ 推荐

@app.post("/api/v1/recommendations")
def recommendations(payload: RecommendIn, user_id: int = Depends(current_user)):
    check_ai_quota(user_id)
    context = profile_context(user_id)
    context["scene"] = "takeout" if payload.scene == "takeout" else "diy"
    context["gaps"] = _recent_gaps(user_id)
    ai = services.get_ai()
    result = ai.recommend(context)
    if context["scene"] == "takeout" and payload.lat is not None and payload.lng is not None:
        result["stores"] = services.nearby_stores(payload.lat, payload.lng, payload.keyword or "餐厅")["stores"]
    result["disclaimer"] = "热量为依据食材索引的估算参考值，不做每日目标提醒"
    return result


@app.get("/api/v1/stores/nearby")
def stores(lat: float, lng: float, keyword: str = "餐厅", limit: int = 5):
    return services.nearby_stores(lat, lng, keyword, limit)


def _recent_summary(user_id: int, days: int = 7) -> Dict:
    """最近吃过的菜品和高频食材，给对话当上下文。"""
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.query_all(
        "SELECT mi.food_name, mi.dish_name FROM meal_items mi "
        "JOIN meals m ON m.id=mi.meal_id WHERE m.user_id=? AND m.eaten_at>=?",
        (user_id, since),
    )
    dishes = []
    for row in rows:
        dish = (row.get("dish_name") or "").strip()
        if dish and dish not in dishes:
            dishes.append(dish)
    counter = Counter(r["food_name"] for r in rows if r.get("food_name"))
    return {
        "dishes": dishes[:20],
        "top_foods": [name for name, _ in counter.most_common(10)],
        "item_count": len(rows),
    }


def _recent_gaps(user_id: int, days: int = 7) -> List[str]:
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    rows = db.query_all(
        "SELECT mi.food_name, mi.food_code FROM meal_items mi JOIN meals m ON m.id=mi.meal_id "
        "WHERE m.user_id=? AND m.eaten_at>=?",
        (user_id, since),
    )
    counter = Counter(
        services.resolve_category(r["food_name"], r["food_code"]) for r in rows
    )
    expected = ["蔬菜类及制品", "水果类及制品", "鱼虾蟹贝类", "乳类及制品"]
    return [name for name in expected if counter.get(name, 0) == 0]


# ------------------------------------------------------------------ 对话

@app.post("/api/v1/chat/sessions")
def chat_start(user_id: int = Depends(current_user)):
    sid = new_id()
    CHAT_SESSIONS[sid] = {
        "user_id": user_id,
        "messages": [],
        "created_at": datetime.now(timezone.utc),
        "notice": "退出 App 超过 10 分钟将自动结束并清空本次对话",
    }
    return {"session_id": sid, "notice": CHAT_SESSIONS[sid]["notice"]}


def _get_session(sid: str, user_id: int) -> Dict:
    session = CHAT_SESSIONS.get(sid)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="会话不存在或已结束")
    if (datetime.now(timezone.utc) - session["created_at"]).total_seconds() > CHAT_TTL_SECONDS:
        CHAT_SESSIONS.pop(sid, None)
        raise HTTPException(status_code=410, detail="会话已超时结束")
    return session



def _nearby_keyword(content: str) -> str:
    """把「我想吃牛肉」这类问题压成百度地点检索能用的关键词。"""
    text = content or ""
    for word in (
        "我想吃", "想吃", "来点", "有没有", "推荐", "附近", "周边",
        "换一换", "换一批", "换一家", "其他", "还有", "别的", "再来",
        "外卖", "点个", "点份", "吃", "的", "店", "吧", "呢",
    ):
        text = text.replace(word, " ")
    text = "".join(text.split())
    return text or "美食"


@app.post("/api/v1/chat/sessions/{sid}/nearby")
def chat_nearby(sid: str, payload: NearbyModeIn, user_id: int = Depends(current_user)):
    """进入/退出附近模式：进入时并发建立上百家店的缓存。"""
    session = _get_session(sid, user_id)
    if not payload.enabled:
        session.pop("nearby_cache", None)
        session["nearby_mode"] = False
        return {"enabled": False, "count": 0, "stores": []}
    if payload.lat is None or payload.lng is None:
        raise HTTPException(status_code=400, detail="需要定位")
    stores = services.nearby_catalog(payload.lat, payload.lng, 120)
    session["nearby_cache"] = stores
    session["nearby_mode"] = True
    session["nearby_center"] = (payload.lat, payload.lng)
    session["nearby_cached_at"] = now_iso()
    return {"enabled": True, "count": len(stores), "stores": stores[:20]}


@app.post("/api/v1/chat/sessions/{sid}/messages")
def chat_message(sid: str, payload: ChatMessageIn, user_id: int = Depends(current_user)):
    session = _get_session(sid, user_id)
    check_ai_quota(user_id)
    context = profile_context(user_id)
    # 口味只在本次对话里生效，不落库
    context["session_likes"] = session.get("likes", [])
    # 让 AI 知道最近吃了什么、缺什么，才好给建议
    context["gaps"] = _recent_gaps(user_id)
    context["recent"] = _recent_summary(user_id)
    if (
        payload.nearby_mode
        and payload.lat is not None
        and payload.lng is not None
    ):
        keyword = _nearby_keyword(payload.content)
        nearby_page = max(0, payload.nearby_page)
        precise = services.nearby_stores(
            payload.lat, payload.lng, keyword, 20, nearby_page
        ).get("stores", [])
        cached = session.get("nearby_cache") or []
        merged: Dict[str, Dict] = {}
        for store in precise:
            name = (store.get("name") or "").strip()
            if name:
                merged[name] = store
        for store in cached:
            name = (store.get("name") or "").strip()
            if name and name not in merged:
                merged[name] = store
        context["nearby_stores"] = list(merged.values())[:80]
        session["nearby_page"] = nearby_page
    ai = services.get_ai()
    result = ai.chat(payload.content, context)
    stores = context.get("nearby_stores") or []
    if stores:
        names = [s.get("name") or "" for s in stores[:5] if s.get("name")]
        reply_now = result.get("reply") or ""
        if names and not any(name in reply_now for name in names):
            result["reply"] = reply_now.rstrip() + "\n附近可参考：" + "、".join(names) + "。"
    session["messages"].append({"role": "user", "content": payload.content})
    session["messages"].append({"role": "assistant", "content": result["reply"]})

    saved = []
    # 同一样东西只在一处：已存在忌口或爱好里的关键词，不再重复提醒
    blocked = {
        row["keyword"].strip()
        for table in ("restrictions", "preferences")
        for row in db.query_all(f"SELECT keyword FROM {table} WHERE user_id=?", (user_id,))
    }
    for fact in result.get("facts", []):
        if fact["type"] == "restriction":
            keyword = (fact.get("keyword") or "").strip()
            if not keyword or keyword in blocked:
                continue
            level = _level_value(fact.get("level"), 3)
            rid = db.execute(
                "INSERT INTO restrictions(user_id, type, keyword, level, confirmed, source, created_at) "
                "VALUES(?,?,?,?,?,?,?)",
                (user_id, "dislike", keyword, level, 0, "chat", now_iso()),
            )
            blocked.add(keyword)
            # 之前当爱好聊过、现在改口说不能接受：把会话里的同名项撤掉
            session_likes_now = session.setdefault("likes", [])
            if keyword in session_likes_now:
                session_likes_now.remove(keyword)
            saved.append(
                {
                    "id": rid,
                    "type": "restriction",
                    "needs_confirm": True,
                    "keyword": keyword,
                    "level": level,
                }
            )
        else:
            # 爱好也分三档，同样要用户确认后才进档案
            keyword = (fact.get("keyword") or "").strip()
            if not keyword or keyword in blocked:
                continue
            level = _level_value(fact.get("level") or fact.get("weight"), 2)
            pid = db.execute(
                "INSERT INTO preferences(user_id, keyword, weight, confirmed, source, created_at) "
                "VALUES(?,?,?,?,?,?)",
                (user_id, keyword, float(level), 0, "chat", now_iso()),
            )
            blocked.add(keyword)
            # 会话里也留一份，本次对话的上下文用得上
            likes = session.setdefault("likes", [])
            if keyword not in likes:
                likes.append(keyword)
            saved.append(
                {
                    "id": pid,
                    "type": "preference",
                    "needs_confirm": True,
                    "keyword": keyword,
                    "level": level,
                }
            )
    return {
        "reply": result["reply"],
        "extracted": saved,
        "likes": session.get("likes", []),
        "finished": result.get("finished", False),
        "nearby_page": session.get("nearby_page", 0),
        "stores": stores,
    }


@app.post("/api/v1/chat/sessions/{sid}/end")
def chat_end(sid: str, user_id: int = Depends(current_user)):
    _get_session(sid, user_id)
    CHAT_SESSIONS.pop(sid, None)
    return {"ok": True, "cleared": True}


# ------------------------------------------------------------------ 报告

PERIOD_DAYS = {"3d": 3, "week": 7, "month": 30, "quarter": 90}


@app.get("/api/v1/reports")
def report(period: str = "week", user_id: int = Depends(current_user)):
    days = PERIOD_DAYS.get(period)
    if not days:
        raise HTTPException(status_code=400, detail="period 只能是 3d / week / month / quarter")
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    items = db.query_all(
        "SELECT mi.*, m.eaten_at, m.meal_slot FROM meal_items mi JOIN meals m ON m.id=mi.meal_id "
        "WHERE m.user_id=? AND m.eaten_at>=?",
        (user_id, since),
    )
    category_counter = Counter()
    # 规则也认不出来的食材：让模型定一次类别并缓存，保证每条都能归到类
    unknown_names = sorted({
        (i.get("food_name") or "").strip()
        for i in items
        if services.resolve_category(i.get("food_name"), i.get("food_code")) == "其他"
    })
    if unknown_names:
        services.learn_categories(unknown_names)
    food_counter = Counter()
    for item in items:
        # 索引没收录的（比如黄瓜/鸡蛋）按关键词兜底归类，不再出现“未匹配”
        category = services.resolve_category(item.get("food_name"), item.get("food_code"))
        category_counter[category] += 1
        food_counter[item["food_name"]] += 1
    total = sum(category_counter.values()) or 1
    shares = [
        {"category": name, "count": count, "percent": round(count / total * 100, 1)}
        for name, count in category_counter.most_common()
    ]
    expected = ["蔬菜类及制品", "水果类及制品", "鱼虾蟹贝类", "乳类及制品"]
    gaps = [name for name in expected if category_counter.get(name, 0) == 0]
    return {
        "period": period,
        "days": days,
        "meal_items": len(items),
        "category_share": shares,
        "top_foods": [{"name": name, "count": count} for name, count in food_counter.most_common(10)],
        "gaps": gaps,
        "suggestions": [f"接下来可增加{food}的摄入" for food in gaps],
        "note": "按出现频次统计，不代表食用量",
    }


# ------------------------------------------------------------------ 分享

def _public_user(target_id: int) -> Dict:
    """对外的用户名片：只给昵称/签名/城市/性别和 ID，不含任何饮食记录。"""
    row = db.query_one("SELECT * FROM profiles WHERE user_id=?", (target_id,)) or {}
    return {
        "user_id": target_id,
        # 6 位对外码：名片上显示、加好友时输入的都是它
        "code": (db.query_one("SELECT public_id FROM users WHERE id=?", (target_id,)) or {}).get("public_id") or "",
        "name": row.get("name") or f"用户{target_id}",
        "avatar": row.get("avatar") or "",
        "signature": row.get("signature") or "",
        "city": row.get("city") or "",
        "gender": row.get("gender") or "",
    }


def _share_meal_entry(meal: Dict) -> Dict:
    """一餐在分享里的样子：先给餐名，再给食材。

    餐名是用户真正想说的"我吃了什么"，食材列表是补充。
    """
    rows = db.query_all(
        "SELECT food_name, dish_name FROM meal_items WHERE meal_id=? ORDER BY id",
        (meal["id"],),
    )
    dishes: List[str] = []
    for row in rows:
        name = (row.get("dish_name") or "").strip()
        if name and name not in dishes:
            dishes.append(name)

    entry = {
        "meal_slot": meal["meal_slot"],
        "eaten_at": meal.get("eaten_at") or "",
        "foods": [r["food_name"] for r in rows if r.get("food_name")],
    }
    if dishes:
        entry["dishes"] = dishes
    if meal.get("meal_date"):
        entry["meal_date"] = meal["meal_date"]
    # 照片只存 object_key：签名有有效期，存库会过期，等读的时候再现签
    keys = [
        p["object_key"]
        for p in db.query_all(
            "SELECT object_key FROM meal_photos WHERE meal_id=? ORDER BY id", (meal["id"],)
        )
    ]
    if keys:
        entry["photo_keys"] = keys
    return entry


def _build_share_payload(user_id: int, kind: str, date: Optional[str] = None) -> Dict:
    """latest = 最近的一餐；daily = 某一天吃了什么；weekly = 最近 7 天占比。

    分享内容只有文字与类别占比，不带照片，也不含任何其他隐私。
    """
    if kind == "latest":
        meal = db.query_one(
            "SELECT * FROM meals WHERE user_id=? AND status<>'deleted' "
            "ORDER BY eaten_at DESC, id DESC LIMIT 1",
            (user_id,),
        )
        content = []
        if meal:
            content.append(_share_meal_entry(meal))
        return {
            "type": "latest",
            "meals": content,
            "has_photo": any(e.get("photo_keys") for e in content),
        }

    if kind == "daily":
        target = date or datetime.now(timezone.utc).date().isoformat()
        meals = db.query_all(
            "SELECT * FROM meals WHERE user_id=? AND substr(eaten_at,1,10)=? ORDER BY eaten_at",
            (user_id, target),
        )
        content = []
        for meal in meals:
            content.append(_share_meal_entry(meal))
        return {
            "type": "daily",
            "date": target,
            "meals": content,
            "has_photo": any(e.get("photo_keys") for e in content),
        }

    rep = report("week", user_id)
    return {
        "type": "weekly",
        "category_share": rep["category_share"],
        "title": "最近 7 天食物类别占比",
        "has_photo": False,
    }


@app.post("/api/v1/shares")
def create_share(payload: ShareIn, user_id: int = Depends(current_user)):
    if payload.type not in ("latest", "daily", "weekly"):
        raise HTTPException(status_code=400, detail="type 只能是 latest / daily / weekly")
    sid = new_id()
    payload_json = _build_share_payload(user_id, payload.type, payload.date)
    db.execute(
        "INSERT INTO shares(id, user_id, type, payload, created_at) VALUES(?,?,?,?,?)",
        (sid, user_id, payload.type, json.dumps(payload_json, ensure_ascii=False), now_iso()),
    )
    return {"share_id": sid, "payload": payload_json}


@app.get("/api/v1/shares/{share_id}")
def get_share(share_id: str):
    row = db.query_one("SELECT * FROM shares WHERE id=?", (share_id,))
    if not row:
        raise HTTPException(status_code=404, detail="分享不存在")
    return {"share_id": share_id, "type": row["type"], "payload": json.loads(row["payload"])}


# ------------------------------------------------------------------ 广场

def _resolve_share_photos(payload: Dict) -> None:
    """把 payload 里的 photo_keys 换成本次请求新签的 URL。

    签名有有效期（QINIU_URL_TTL），所以不能存进库，只能每次读的时候现签。
    就地改 payload，顺便把 photo_keys 去掉——外部只要能直接用的地址。
    """
    for meal in payload.get("meals") or []:
        keys = meal.pop("photo_keys", None)
        if not keys:
            continue
        meal["photos"] = [
            {"url": u} for u in (services.public_url(k) for k in keys) if u
        ]


def _feed_item(row, viewer_id: int) -> Dict:
    payload = json.loads(row["payload"])
    _resolve_share_photos(payload)
    return {
        "post_id": row["id"],
        "kind": row["kind"],
        "payload": payload,
        "created_at": row["created_at"],
        "author": _public_user(row["user_id"]),
        "mine": row["user_id"] == viewer_id,
    }


@app.post("/api/v1/feed/moments")
def post_moment(payload: MomentIn, user_id: int = Depends(current_user)):
    """发到朋友圈：所有人都能看到。"""
    if payload.kind not in ("latest", "daily", "weekly"):
        raise HTTPException(status_code=400, detail="kind 只能是 latest / daily / weekly")
    body = _build_share_payload(user_id, payload.kind, payload.date)
    pid = new_id()
    db.execute(
        "INSERT INTO feed_posts(id, user_id, channel, recipient_id, kind, payload, created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (pid, user_id, "moments", None, payload.kind, json.dumps(body, ensure_ascii=False), now_iso()),
    )
    return {"post_id": pid, "payload": body}


@app.get("/api/v1/feed/moments")
def list_moments(
    limit: int = Query(50, ge=1, le=200),
    user_id: int = Depends(current_user),
):
    """朋友圈：所有人发的都在这里，倒序。"""
    rows = db.query_all(
        "SELECT * FROM feed_posts WHERE channel='moments' "
        "ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (limit,),
    )
    return {"items": [_feed_item(r, user_id) for r in rows]}


@app.post("/api/v1/feed/direct/{friend_id}")
def send_direct(friend_id: int, payload: MomentIn, user_id: int = Depends(current_user)):
    """把一餐或一周占比单独分享给某个好友。"""
    if friend_id == user_id:
        raise HTTPException(status_code=400, detail="不能分享给自己")
    if payload.kind not in ("latest", "daily", "weekly"):
        raise HTTPException(status_code=400, detail="kind 只能是 latest / daily / weekly")
    if not db.query_one(
        "SELECT 1 FROM friend_links WHERE user_id=? AND friend_id=?", (user_id, friend_id)
    ):
        raise HTTPException(status_code=403, detail="还不是好友")
    body = _build_share_payload(user_id, payload.kind, payload.date)
    pid = new_id()
    db.execute(
        "INSERT INTO feed_posts(id, user_id, channel, recipient_id, kind, payload, created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (
            pid, user_id, "direct", friend_id, payload.kind,
            json.dumps(body, ensure_ascii=False), now_iso(),
        ),
    )
    return {"post_id": pid, "payload": body}


@app.get("/api/v1/feed/direct/{friend_id}")
def list_direct(friend_id: int, user_id: int = Depends(current_user)):
    """只返回我和这位好友之间的分享往来，按时间正序。"""
    rows = db.query_all(
        "SELECT * FROM feed_posts WHERE channel='direct' AND "
        "((user_id=? AND recipient_id=?) OR (user_id=? AND recipient_id=?)) "
        "ORDER BY created_at ASC, rowid ASC",
        (user_id, friend_id, friend_id, user_id),
    )
    return {"items": [_feed_item(r, user_id) for r in rows]}


def _are_friends(a: int, b: int) -> bool:
    return bool(
        db.query_one("SELECT 1 FROM friend_links WHERE user_id=? AND friend_id=?", (a, b))
    )


def _accept_request(request_id: int, receiver_id: int) -> bool:
    """同意加好友：双方各写一行 friend_links，并把申请标成已同意。"""
    row = db.query_one(
        "SELECT * FROM friend_requests WHERE id=? AND to_user_id=? AND status='pending'",
        (request_id, receiver_id),
    )
    if not row:
        return False

    stamp = now_iso()
    pairs = ((row["from_user_id"], row["to_user_id"]), (row["to_user_id"], row["from_user_id"]))
    for a, b in pairs:
        db.execute(
            "INSERT INTO friend_links(user_id, friend_id, created_at) VALUES(?,?,?) "
            "ON CONFLICT(user_id, friend_id) DO NOTHING",
            (a, b, stamp),
        )
    db.execute(
        "UPDATE friend_requests SET status='accepted', updated_at=? WHERE id=?",
        (stamp, request_id),
    )
    return True


@app.post("/api/v1/friends")
def add_friend(payload: FriendIn, user_id: int = Depends(current_user)):
    """按 ID 申请加好友：对方同意后才互为好友。

    对方同时也在申请你（互相申请）时直接互加，不用再手工同意。
    """
    code = (payload.code or "").strip().lower()
    target_row = db.query_one(
        "SELECT id FROM users WHERE public_id=? AND status='active'", (code,)
    )
    if not target_row:
        raise HTTPException(status_code=404, detail="没有这个用户码")
    target = target_row["id"]
    if target == user_id:
        raise HTTPException(status_code=400, detail="不能加自己")

    if _are_friends(user_id, target):
        return {"ok": True, "status": "friends", "message": "你们已经是好友"}

    # 对方已经申请过我：这次申请等于同意
    reverse = db.query_one(
        "SELECT id FROM friend_requests WHERE from_user_id=? AND to_user_id=? AND status='pending'",
        (target, user_id),
    )
    if reverse and _accept_request(reverse["id"], user_id):
        return {"ok": True, "status": "friends", "message": "互相申请，已成为好友"}

    existing = db.query_one(
        "SELECT * FROM friend_requests WHERE from_user_id=? AND to_user_id=?", (user_id, target)
    )
    if existing and existing["status"] == "pending":
        return {"ok": True, "status": "pending", "message": "已经申请过了，等对方同意"}

    stamp = now_iso()
    if existing:
        # 之前被拒过：复用这条记录重新申请
        db.execute(
            "UPDATE friend_requests SET status='pending', created_at=?, updated_at=? WHERE id=?",
            (stamp, stamp, existing["id"]),
        )
    else:
        db.execute(
            "INSERT INTO friend_requests(from_user_id, to_user_id, status, created_at, updated_at) "
            "VALUES(?,?,?,?,?)",
            (user_id, target, "pending", stamp, stamp),
        )
    return {"ok": True, "status": "pending", "message": "申请已发出，等对方同意"}


@app.get("/api/v1/friends")
def list_friends(user_id: int = Depends(current_user)):
    rows = db.query_all(
        "SELECT friend_id, created_at FROM friend_links WHERE user_id=? ORDER BY created_at DESC",
        (user_id,),
    )
    items = []
    for row in rows:
        card = _public_user(row["friend_id"])
        card["since"] = row["created_at"]
        items.append(card)
    return {"items": items}


@app.delete("/api/v1/friends/{friend_id}")
def remove_friend(friend_id: int, user_id: int = Depends(current_user)):
    db.execute("DELETE FROM friend_links WHERE user_id=? AND friend_id=?", (user_id, friend_id))
    db.execute("DELETE FROM friend_links WHERE user_id=? AND friend_id=?", (friend_id, user_id))
    return {"ok": True}


@app.get("/api/v1/friends/requests")
def list_friend_requests(user_id: int = Depends(current_user)):
    """别人发给我、还没处理的加好友申请（广场里的提醒行）。"""
    rows = db.query_all(
        "SELECT * FROM friend_requests WHERE to_user_id=? AND status='pending' "
        "ORDER BY created_at DESC",
        (user_id,),
    )
    return {
        "items": [
            {
                "request_id": r["id"],
                "from": _public_user(r["from_user_id"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    }


@app.post("/api/v1/friends/requests/{request_id}/accept")
def accept_friend_request(request_id: int, user_id: int = Depends(current_user)):
    if not _accept_request(request_id, user_id):
        raise HTTPException(status_code=404, detail="这条申请不存在或已处理")
    return {"ok": True}


@app.post("/api/v1/friends/requests/{request_id}/reject")
def reject_friend_request(request_id: int, user_id: int = Depends(current_user)):
    row = db.query_one(
        "SELECT id FROM friend_requests WHERE id=? AND to_user_id=? AND status='pending'",
        (request_id, user_id),
    )
    if not row:
        raise HTTPException(status_code=404, detail="这条申请不存在或已处理")
    db.execute(
        "UPDATE friend_requests SET status='rejected', updated_at=? WHERE id=?",
        (now_iso(), request_id),
    )
    return {"ok": True}


@app.get("/api/v1/users/{code}")
def get_public_user(code: str, user_id: int = Depends(current_user)):
    """按 6 位码看别人的名片：只给昵称/签名/城市/性别，以及关系状态。"""
    row = db.query_one(
        "SELECT id FROM users WHERE public_id=? AND status='active'", (code.strip().lower(),)
    )
    if not row:
        raise HTTPException(status_code=404, detail="没有这个用户码")
    target_id = row["id"]
    card = _public_user(target_id)
    card["is_friend"] = _are_friends(user_id, target_id)
    # 用于名片上决定显示“加好友 / 等待对方同意 / 同意对方申请 / 已是好友”
    if card["is_friend"]:
        card["friend_status"] = "friends"
    elif db.query_one(
        "SELECT 1 FROM friend_requests WHERE from_user_id=? AND to_user_id=? AND status='pending'",
        (user_id, target_id),
    ):
        card["friend_status"] = "pending_out"
    elif db.query_one(
        "SELECT 1 FROM friend_requests WHERE from_user_id=? AND to_user_id=? AND status='pending'",
        (target_id, user_id),
    ):
        card["friend_status"] = "pending_in"
    else:
        card["friend_status"] = "none"
    card["is_me"] = target_id == user_id
    return card
