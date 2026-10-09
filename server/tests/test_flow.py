#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""随便吃服务端 · 主链路自测。

覆盖：健康检查 → 注册登录 → 设备免验证码登录 → 档案与忌口 → 热量检索
      → 识别 → 确认入库 → 记录查询 → 推荐 → 对话 → 报告 → 分享

运行（在 server 目录下）：
    python tests/test_flow.py
"""

import sys
import json
import os
import time
from pathlib import Path

# 自测固定走本地规则引擎，不消耗 DeepSeek 额度
os.environ["SHIJI_AI_PROVIDER"] = "mock"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app, on_startup  # noqa: E402
from app import db  # noqa: E402

client = TestClient(app)

# TestClient 仅在上下文管理器内触发 lifespan，这里显式初始化一次
on_startup()
PHONE = "13800001234"
PASSWORD = "test-pass-123"


def check(name, condition, extra=""):
    mark = "PASS" if condition else "FAIL"
    print(f"[{mark}] {name} {extra}")
    if not condition:
        raise SystemExit(1)


def wait_estimated(client, headers, meal_id, timeout=120):
    """热量是后台估算的，轮询到不再是 estimating 为止。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/api/v1/meals/{meal_id}", headers=headers)
        if r.status_code == 200 and r.json().get("status") != "estimating":
            return r.json()
        time.sleep(2)
    return None


def main():
    r = client.get("/health")
    health = r.json()
    check("健康检查", r.status_code == 200, f"热量索引 {health['heat_index_count']} 条")
    check("热量索引已导入", health["heat_index_count"] >= 1190, f"实际 {health['heat_index_count']} 条")

    r = client.post("/api/v1/auth/sms/send", json={"phone": PHONE})
    code = r.json().get("code")
    check("发送验证码（开发模式返回验证码）", r.status_code == 200 and bool(code))

    r = client.post("/api/v1/auth/sms/verify", json={"phone": PHONE, "code": code, "password": PASSWORD})
    body = r.json()
    check("注册 / 登录并设置密码", r.status_code == 200 and "access_token" in body)
    token = body["access_token"]
    device_token = body["device_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post("/api/v1/auth/device/login", json={"device_token": device_token})
    check("设备免验证码登录", r.status_code == 200 and "access_token" in r.json())

    r = client.post("/api/v1/auth/login/password", json={"phone": PHONE, "password": PASSWORD})
    check("密码登录", r.status_code == 200)

    r = client.put(
        "/api/v1/profile",
        json={"city": "杭州", "goals": ["减盐", "控肉", "减糖"]},
        headers=headers,
    )
    check("保存膳食目标（多选）", r.status_code == 200 and "减盐" in r.json()["goals"])

    r = client.post(
        "/api/v1/profile/restrictions",
        json={"type": "allergen", "keyword": "花生", "source": "manual"},
        headers=headers,
    )
    check("写入忌口（硬约束）", r.status_code == 200 and r.json()["confirmed"] == 1)

    r = client.get("/api/v1/foods/search", params={"q": "米饭"})
    foods = r.json()["items"]
    check("热量索引检索", len(foods) > 0, f"命中 {len(foods)} 条，首条 {foods[0]['food_name']} {foods[0]['energy_kcal']} kcal")

    r = client.post(
        "/api/v1/recognition",
        json={"image_keys": [], "text": "午饭吃了小白菜、鲈鱼和米饭", "meal_slot": "lunch", "source": "diy"},
        headers=headers,
    )
    job = r.json()
    items = job["result"]["items"]
    check(
        "识别只出名称、不带热量",
        r.status_code == 200 and len(items) >= 2 and all(i.get("energy_kcal") is None for i in items),
        f"{len(items)} 个食材，带热量 {sum(1 for i in items if i.get('energy_kcal') is not None)} 条",
    )

    r = client.post(f"/api/v1/recognition/{job['job_id']}/confirm", json={}, headers=headers)
    meal = r.json()
    check(
        "确认即刻入库（热量估算中）",
        r.status_code == 200 and meal["status"] == "estimating",
        f"状态 {meal['status']}",
    )

    # 识别任务里存着上传图片的 base64：确认入库后必须立刻清掉，不然库会一直涨
    job_row = db.query_one("SELECT payload FROM recognition_jobs WHERE id=?", (job["job_id"],))
    payload_after = json.loads(job_row["payload"])
    check(
        "确认后识别任务里的图片被清掉",
        "images_base64" not in payload_after,
        f"剩下的字段 {list(payload_after.keys())}",
    )

    # 过期任务会被定时清理
    uid = db.query_one("SELECT id FROM users ORDER BY id LIMIT 1")["id"]
    db.execute(
        "INSERT INTO recognition_jobs(id, user_id, payload, result, status, created_at) "
        "VALUES(?,?,?,?,?,?)",
        (
            "expiredjob00000000001", uid, "{}", "{}", "pending",
            "2000-01-01T00:00:00+00:00",
        ),
    )
    from app.main import _cleanup_recognition_jobs  # noqa: E402

    deleted = _cleanup_recognition_jobs(force=True)
    left = db.query_one("SELECT id FROM recognition_jobs WHERE id=?", ("expiredjob00000000001",))
    check("过期识别任务被清理", deleted >= 1 and left is None, f"删了 {deleted} 条")

    filled = wait_estimated(client, headers, meal["id"])
    check(
        "后台估算回填热量",
        filled is not None and filled["status"] == "confirmed" and filled["total_energy_kcal"] > 0,
        f"合计 {filled['total_energy_kcal'] if filled else '-'} kcal",
    )

    r = client.post(
        "/api/v1/meals",
        json={"meal_slot": "dinner", "source": "takeout", "note": "少盐", "items": [{"food_name": "小白菜"}, {"food_name": "鲈鱼"}]},
        headers=headers,
    )
    check("手工新建一餐（先入库）", r.status_code == 200 and r.json()["status"] == "estimating")
    created = r.json()
    filled = wait_estimated(client, headers, created["id"])
    check(
        "手工新建一餐后自动补热量",
        r.status_code == 200 and filled is not None and filled["total_energy_kcal"] > 0,
        f"合计 {filled['total_energy_kcal'] if filled else '-'} kcal",
    )

    r = client.post(
        "/api/v1/estimates",
        json={"meal_slot": "lunch", "items": [{"food_name": "小白菜"}, {"food_name": "鲈鱼"}]},
        headers=headers,
    )
    check("单独估算接口可用", r.status_code == 200, f"合计 {r.json().get('energy_total_kcal')} kcal")

    r = client.get("/api/v1/meals", headers=headers)
    check("历史记录查询", len(r.json()["items"]) >= 2)

    # 列表也必须带 items / photos：客户端是 Gson 反序列化，JSON 里缺键会变 null
    listed = r.json()["items"]
    check(
        "列表每条都带 items 字段",
        all(isinstance(m.get("items"), list) for m in listed),
        str(list(listed[0].keys())),
    )
    check(
        "列表每条都带 photos 字段",
        all(isinstance(m.get("photos"), list) for m in listed),
        str(list(listed[0].keys())),
    )

    r = client.post("/api/v1/recommendations", json={"scene": "diy"}, headers=headers)
    plans = r.json()["plans"]
    forbidden = [p for p in plans if any("花生" in i["food_name"] for p in plans for i in p["items"])]
    check("生成推荐方案", len(plans) >= 1, f"{len(plans)} 套")
    check("忌口硬约束生效（未出现花生）", not forbidden)

    r = client.post("/api/v1/recommendations", json={"scene": "takeout", "lat": 30.25, "lng": 120.15}, headers=headers)
    check("外卖场景附带附近店铺", len(r.json().get("stores", [])) > 0)

    r = client.post("/api/v1/chat/sessions", headers=headers)
    # 忌口现在按关键词去重，先清掉历史同名记录，保证这条用例可重复跑
    uid = client.get("/api/v1/profile", headers=headers).json()["user_id"]
    db.execute("DELETE FROM restrictions WHERE user_id=? AND keyword=?", (uid, "香菜"))

    sid = r.json()["session_id"]
    check("创建对话会话", r.status_code == 200 and bool(r.json()["notice"]))

    r = client.post(
        f"/api/v1/chat/sessions/{sid}/messages",
        json={"content": "我不吃香菜"},
        headers=headers,
    )
    extracted = r.json()["extracted"]
    check("对话抽取忌口且需用户确认", any(e["needs_confirm"] for e in extracted), str(extracted))

    r = client.post(f"/api/v1/chat/sessions/{sid}/end", headers=headers)
    check("结束对话即清空", r.json().get("cleared") is True)

    r = client.get("/api/v1/reports", params={"period": "week"}, headers=headers)
    rep = r.json()
    check("周报告统计", r.status_code == 200 and len(rep["category_share"]) > 0, f"覆盖 {rep['meal_items']} 个食材条目")

    r = client.post("/api/v1/shares", json={"type": "weekly"}, headers=headers)
    share = r.json()
    check("生成一周分享（文字/图表，无照片）", r.status_code == 200 and share["payload"]["has_photo"] is False)

    r = client.get(f"/api/v1/shares/{share['share_id']}")
    check("分享可访问", r.status_code == 200)

    print("\n--- 同一餐再记一次：追加 vs 覆盖 ---")
    stamp = "2026-10-05T18:30:00+00:00"

    def confirm_meal(text, mode=None, note=None):
        r = client.post(
            "/api/v1/recognition",
            json={"text": text, "meal_slot": "dinner", "source": "diy"},
            headers=headers,
        )
        job = r.json()
        body = {"meal_slot": "dinner", "eaten_at": stamp}
        if mode:
            body["mode"] = mode
        if note is not None:
            body["note"] = note
        r = client.post(
            f"/api/v1/recognition/{job['job_id']}/confirm", json=body, headers=headers
        )
        return r.json()

    first = confirm_meal("米饭 青菜", note="第一轮")
    first_id = first["id"]
    check("先建一条晚餐记录", first_id > 0 and len(first["items"]) >= 2, f"id={first_id}")

    merged = confirm_meal("紫菜蛋花汤", mode="append")
    names = [i["food_name"] for i in merged["items"]]
    check("追加不会丢掉原来的食材", "米饭" in names and "青菜" in names, str(names))
    check("追加把新内容接上了", len(names) >= 3, str(names))
    check("追加标记正确", merged.get("appended") is True, str(merged.get("appended")))
    check("追加后还是同一条记录", merged["id"] == first_id, f"{merged['id']} vs {first_id}")
    check("追加保留了原备注", "第一轮" in (merged.get("note") or ""), str(merged.get("note")))

    replaced = confirm_meal("面条", mode="replace", note="第二轮")
    names2 = [i["food_name"] for i in replaced["items"]]
    check("覆盖会换掉旧内容", "米饭" not in names2, str(names2))
    check("覆盖标记正确", replaced.get("replaced") is True, str(replaced.get("replaced")))

    print("\n全部主链路自测通过。")


if __name__ == "__main__":
    main()
