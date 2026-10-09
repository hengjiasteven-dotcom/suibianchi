"""随便吃服务端 · 数据库（SQLite，标准库实现，便于先跑通主链路）。

生产环境把 DB_PATH 指向 PostgreSQL 时，只需替换本模块的实现。
"""

from typing import Dict
import sqlite3
from contextlib import contextmanager


from .security import now_iso
from .config import DB_PATH
from .security import new_public_id

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    -- 对外展示的 6 位码，加好友、名片用的都是它，不是自增 id
    public_id TEXT,
    -- 6 位码只能自己改一次，改过就锁死
    code_changed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    last_login_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id INTEGER PRIMARY KEY,
    gender TEXT,
    -- 头像只存内置头像的编号（avatar_1 ... avatar_7），不存图片本身
    avatar TEXT,
    name TEXT,
    signature TEXT,
    city TEXT,
    goals TEXT NOT NULL DEFAULT '[]',
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS restrictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    keyword TEXT NOT NULL,
    level INTEGER NOT NULL DEFAULT 3,
    confirmed INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    keyword TEXT NOT NULL,
    weight REAL NOT NULL DEFAULT 1.0,
    confirmed INTEGER NOT NULL DEFAULT 1,
    source TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    meal_slot TEXT NOT NULL,
    meal_date TEXT,
    eaten_at TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'unknown',
    note TEXT,
    status TEXT NOT NULL DEFAULT 'confirmed',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meal_photos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_id INTEGER NOT NULL,
    object_key TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meal_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    meal_id INTEGER NOT NULL,
    food_name TEXT NOT NULL,
    dish_name TEXT,
    food_code TEXT,
    energy_kcal REAL,
    amount_text TEXT,
    cooking TEXT,
    match_status TEXT NOT NULL DEFAULT 'unmatched',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS recognition_jobs (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    payload TEXT NOT NULL,
    result TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS heat_index (
    food_code TEXT PRIMARY KEY,
    food_name TEXT NOT NULL,
    energy_kcal REAL NOT NULL,
    energy_kj REAL,
    water_g REAL,
    protein_g REAL,
    fat_g REAL,
    carb_g REAL,
    search_keys TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS shares (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT
);

-- 好友关系：加好友时双向写两行，查询只按 user_id 取
CREATE TABLE IF NOT EXISTS friend_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    friend_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, friend_id)
);

-- 加好友申请：对方同意后才写入 friend_links（双向同意）
CREATE TABLE IF NOT EXISTS friend_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL,
    to_user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(from_user_id, to_user_id)
);

-- 广场动态：channel=moments 是公开朋友圈，channel=direct 是一对一分享
CREATE TABLE IF NOT EXISTS feed_posts (
    id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    channel TEXT NOT NULL,
    recipient_id INTEGER,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sms_codes (
    phone TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

-- 索引没收录、关键词也认不出来的食材，让模型定一次类别后缓存下来
CREATE TABLE IF NOT EXISTS food_categories (
    food_name TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'ai',
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_meals_user_time ON meals(user_id, eaten_at);
CREATE INDEX IF NOT EXISTS idx_items_meal ON meal_items(meal_id);
CREATE INDEX IF NOT EXISTS idx_restrictions_user ON restrictions(user_id);
CREATE INDEX IF NOT EXISTS idx_friends_user ON friend_links(user_id);
CREATE INDEX IF NOT EXISTS idx_friend_requests_to ON friend_requests(to_user_id, status);
CREATE INDEX IF NOT EXISTS idx_feed_moments ON feed_posts(channel, created_at);
CREATE INDEX IF NOT EXISTS idx_feed_direct ON feed_posts(channel, recipient_id, created_at);
"""


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()


def _migrate(conn):
    """老库补列：SQLite 没有 ADD COLUMN IF NOT EXISTS，只能自己查一遍。"""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(meal_items)").fetchall()}
    if "dish_name" not in cols:
        conn.execute("ALTER TABLE meal_items ADD COLUMN dish_name TEXT")
    # 一天四餐，每餐只能有一条记录：用 meal_date + meal_slot 定位
    meal_cols = {r["name"] for r in conn.execute("PRAGMA table_info(meals)").fetchall()}
    if "meal_date" not in meal_cols:
        conn.execute("ALTER TABLE meals ADD COLUMN meal_date TEXT")
    conn.execute(
        "UPDATE meals SET meal_date=substr(eaten_at,1,10) WHERE meal_date IS NULL OR meal_date=''"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_meals_day_slot ON meals(user_id, meal_date, meal_slot)"
    )
    # 个人主页：名字 / 个性签名
    profile_cols = {r["name"] for r in conn.execute("PRAGMA table_info(profiles)").fetchall()}
    if "name" not in profile_cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN name TEXT")
    if "signature" not in profile_cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN signature TEXT")
    if "gender" not in profile_cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN gender TEXT")
    # 头像编号：老用户留空就用默认首字头像
    if "avatar" not in profile_cols:
        conn.execute("ALTER TABLE profiles ADD COLUMN avatar TEXT")
    # 爱好也要经过用户确认（对话里抽出来的是待确认）
    pref_cols = {r["name"] for r in conn.execute("PRAGMA table_info(preferences)").fetchall()}
    if "confirmed" not in pref_cols:
        conn.execute("ALTER TABLE preferences ADD COLUMN confirmed INTEGER NOT NULL DEFAULT 1")
    if "source" not in pref_cols:
        conn.execute("ALTER TABLE preferences ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
    # 忌口分三档：1 不太喜欢 / 2 感觉很难吃 / 3 完全不接受
    res_cols = {r["name"] for r in conn.execute("PRAGMA table_info(restrictions)").fetchall()}
    if "level" not in res_cols:
        conn.execute("ALTER TABLE restrictions ADD COLUMN level INTEGER NOT NULL DEFAULT 3")
    # 方案 C：和站点账号打通，记录站点的用户 id
    user_cols = {r["name"] for r in conn.execute("PRAGMA table_info(users)").fetchall()}
    if "site_user_id" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN site_user_id INTEGER")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_site_id ON users(site_user_id)"
    )
    # 对外 6 位用户码：老用户也要补上
    if "public_id" not in user_cols:
        conn.execute("ALTER TABLE users ADD COLUMN public_id TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_public_id ON users(public_id)"
    )
    if "code_changed" not in user_cols:
        conn.execute(
            "ALTER TABLE users ADD COLUMN code_changed INTEGER NOT NULL DEFAULT 0"
        )
    _backfill_public_ids(conn)



def new_unique_public_id() -> str:
    """建新用户时用的对外 6 位码（每次开自己的连接查重）。"""
    for _ in range(50):
        code = new_public_id()
        if not query_one("SELECT 1 FROM users WHERE public_id=?", (code,)):
            return code
    raise RuntimeError("生成用户 ID 失败，请重试")


def _unique_public_id(conn) -> str:
    """生成一个没用过的 6 位码。

    36^6 的空间下撞车概率极低，但还是查一下库，保证唯一。
    """
    for _ in range(50):
        code = new_public_id()
        if not conn.execute("SELECT 1 FROM users WHERE public_id=?", (code,)).fetchone():
            return code
    raise RuntimeError("生成用户 ID 失败，请重试")


def _backfill_public_ids(conn):
    rows = conn.execute(
        "SELECT id FROM users WHERE public_id IS NULL OR public_id=''"
    ).fetchall()
    for row in rows:
        conn.execute(
            "UPDATE users SET public_id=? WHERE id=?", (_unique_public_id(conn), row["id"])
        )

@contextmanager
def connect():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def query_all(sql, params=()):
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def query_one(sql, params=()):
    with connect() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def execute(sql, params=()):
    with connect() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.lastrowid


def execute_rowcount(sql, params=()) -> int:
    """执行写操作并返回影响行数（清理任务要报“删了几条”）。"""
    with connect() as conn:
        cur = conn.execute(sql, params)
        conn.commit()
        return cur.rowcount


def find_or_create_site_user(site_user_id: int, phone: str, nickname: str = "") -> Dict:
    """方案 C：把站点用户映射成本地用户。

    先按 site_user_id 找；没有就按手机号认领（老用户升级）；再没有才新建。
    """
    row = query_one("SELECT * FROM users WHERE site_user_id=?", (site_user_id,))
    if row:
        return row
    row = query_one("SELECT * FROM users WHERE phone=?", (phone,))
    if row:
        execute("UPDATE users SET site_user_id=? WHERE id=?", (site_user_id, row["id"]))
        return query_one("SELECT * FROM users WHERE id=?", (row["id"],))
    user_id = execute(
        "INSERT INTO users(phone, password_hash, status, created_at, site_user_id, public_id) "
        "VALUES(?,?,?,?,?,?)",
        (phone, None, "active", now_iso(), site_user_id, new_unique_public_id()),
    )
    profile = query_one("SELECT * FROM profiles WHERE user_id=?", (user_id,))
    if not profile:
        execute(
            "INSERT INTO profiles(user_id, name, city, goals, updated_at) VALUES(?,?,?,?,?)",
            (user_id, nickname or None, None, "[]", now_iso()),
        )
    return query_one("SELECT * FROM users WHERE id=?", (user_id,))
