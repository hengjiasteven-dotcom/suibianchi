"""随便吃服务端 · 配置。"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """读取 server/.env，把密钥放环境变量里，避免写进代码或提交到仓库。"""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('\"').strip("'"))




_load_dotenv(BASE_DIR / ".env")
DATA_DIR = Path(os.environ.get("SHIJI_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = Path(os.environ.get("SHIJI_DB_PATH", DATA_DIR / "shiji.db"))
HEAT_INDEX_PATH = Path(
    os.environ.get(
        "SHIJI_HEAT_INDEX",
        BASE_DIR.parent / "output" / "heat_index" / "app" / "app_heat_index.jsonl",
    )
)

# 认证
JWT_SECRET = os.environ.get("SHIJI_JWT_SECRET", "dev-secret-change-me")
JWT_TTL_SECONDS = int(os.environ.get("SHIJI_JWT_TTL", 7 * 24 * 3600))
SMS_CODE_TTL_SECONDS = int(os.environ.get("SHIJI_SMS_TTL", 300))
SMS_DEV_MODE = os.environ.get("SHIJI_SMS_DEV_MODE", "1") == "1"

# 对话会话（进程内，带 TTL；生产替换为 Redis）
# 站点账号体系（方案 C）：短信与密码校验委托给 xiaodaidai.site 的后端，
# 我们只调它的 HTTP 接口，不改它的代码与数据库。
SITE_API_BASE = os.environ.get("SHIJI_SITE_API_BASE", "http://127.0.0.1:4300").rstrip("/")
SITE_AUTH_ENABLED = os.environ.get("SHIJI_SITE_AUTH", "0") == "1"
SITE_AUTH_TIMEOUT = float(os.environ.get("SHIJI_SITE_AUTH_TIMEOUT", "20"))
CHAT_TTL_SECONDS = int(os.environ.get("SHIJI_CHAT_TTL", 600))

# AI
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DEEPSEEK_MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-flash")
AI_PROVIDER = os.environ.get("SHIJI_AI_PROVIDER", "deepseek" if DEEPSEEK_API_KEY else "mock")

# 是否把本地热量索引作为提示词前缀：默认 0，热量完全交给 AI 估算
AI_INCLUDE_INDEX = os.environ.get("SHIJI_AI_INCLUDE_INDEX", "0") == "1"

# 七牛云
QINIU_ACCESS_KEY = os.environ.get("QINIU_ACCESS_KEY", "")
QINIU_SECRET_KEY = os.environ.get("QINIU_SECRET_KEY", "")
QINIU_BUCKET = os.environ.get("QINIU_BUCKET", "shiji-meals")
QINIU_DOMAIN = os.environ.get("QINIU_DOMAIN", "")
# 客户端直传时用的上传入口；服务端中转上传走 SDK 默认值，不依赖这项
QINIU_UPLOAD_HOST = os.environ.get("QINIU_UPLOAD_HOST", "https://up.qiniup.com")
# 空间是私有读时返回签名 URL；签名有效期默认 6 小时
QINIU_PRIVATE = os.environ.get("QINIU_PRIVATE", "0") == "1"
QINIU_URL_TTL = int(os.environ.get("QINIU_URL_TTL", "21600"))

# 地图
MAP_PROVIDER = os.environ.get("SHIJI_MAP_PROVIDER", "mock")
BAIDU_MAP_AK = os.environ.get("BAIDU_MAP_AK", "")

# AI 调用配额：防止有人拿接口白嫖你的 DeepSeek 额度
AI_DAILY_PER_USER = int(os.environ.get("SHIJI_AI_DAILY_PER_USER", 100))

# 识别任务（里面存着上传图片的 base64）保留多少天，超期就删
RECOGNITION_KEEP_DAYS = int(os.environ.get("SHIJI_RECOGNITION_KEEP_DAYS", "7"))

# 客户端版本信息：发版脚本 tools/publish_apk.py 会更新这个文件
RELEASE_FILE = Path(os.environ.get("SHIJI_RELEASE_FILE", BASE_DIR / "release.json"))
AI_DAILY_TOTAL = int(os.environ.get("SHIJI_AI_DAILY_TOTAL", 2000))
