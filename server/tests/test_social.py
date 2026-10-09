#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""广场功能自测：6 位用户码、加好友申请、朋友圈、一对一分享。

覆盖：
- 每个用户拿到唯一的 6 位字母数字码
- 按码查名片 / 按码申请加好友
- 加好友必须对方同意；拒绝后不是好友
- 互相申请时直接成为好友
- 朋友圈公开发布与读取
- 一对一分享只能收发双方看到
- 公开名片只有昵称/签名/城市/性别

跑法：cd server && python tests/test_social.py
"""

import os
import re
import sys
import tempfile
from pathlib import Path

os.environ["SHIJI_AI_PROVIDER"] = "mock"
os.environ["SHIJI_SMS_DEV_MODE"] = "1"
os.environ["SHIJI_SITE_AUTH"] = "0"
os.environ["SHIJI_DB_PATH"] = os.path.join(tempfile.mkdtemp(), "social-test.db")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app, on_startup  # noqa: E402
from app import db  # noqa: E402

client = TestClient(app)
on_startup()

checks = []


def check(name, ok, detail=""):
    checks.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}  {detail}")


def login(phone):
    sent = client.post("/api/v1/auth/sms/send", json={"phone": phone}).json()
    tokens = client.post(
        "/api/v1/auth/sms/verify",
        json={"phone": phone, "code": sent["code"], "password": "test1234"},
    ).json()
    row = db.query_one("SELECT id, public_id FROM users WHERE phone=?", (phone,))
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    return row["id"], row["public_id"], headers


def main():
    alice_id, alice_code, alice = login("13700000001")
    bob_id, bob_code, bob = login("13700000002")
    carol_id, carol_code, carol = login("13700000003")

    print("--- 6 位用户码 ---")
    codes = [alice_code, bob_code, carol_code]
    check("每位用户都分到 6 位码", all(c and len(c) == 6 for c in codes), str(codes))
    check("码只含小写字母和数字", all(re.fullmatch(r"[0-9a-z]{6}", c or "") for c in codes))
    check("码互不相同", len(set(codes)) == 3)
    profile = client.get("/api/v1/profile", headers=alice).json()
    check("个人档案里能拿到自己的码", profile["code"] == alice_code, str(profile.get("code")))

    print("\n--- 内置头像 ---")
    r = client.put("/api/v1/profile", json={"avatar": "avatar_3"}, headers=alice)
    check("能设置内置头像", r.status_code == 200 and r.json().get("avatar") == "avatar_3", r.text[:120])
    r = client.put("/api/v1/profile", json={"avatar": "../etc/passwd"}, headers=alice)
    check("非法头像编号被拒", r.status_code == 400, r.text[:80])
    r = client.put("/api/v1/profile", json={}, headers=alice)
    check("不传头像时保持原值", r.json().get("avatar") == "avatar_3", str(r.json().get("avatar")))

    print("\n--- 自定义 ID ---")
    # 先试非法的：这时还没改过，才能拿到格式/占用的真实错误
    r = client.put("/api/v1/profile/code", json={"code": "abc"}, headers=alice)
    check("长度不对被拒", r.status_code == 400, r.text[:80])
    r = client.put("/api/v1/profile/code", json={"code": "a-b_12"}, headers=alice)
    check("非法字符被拒", r.status_code == 400, r.text[:80])
    r = client.put("/api/v1/profile/code", json={"code": bob_code}, headers=alice)
    check("别人的 ID 不能占", r.status_code == 409, r.text[:80])
    r = client.get("/api/v1/profile", headers=alice)
    check("没改过时标记为可改", r.json().get("code_changeable") is True)

    old_code = alice_code
    r = client.put("/api/v1/profile/code", json={"code": "iloveu"}, headers=alice)
    check("能把自己的 ID 改成 iloveu", r.status_code == 200 and r.json()["code"] == "iloveu", r.text[:140])
    check("旧 ID 立刻失效", client.get("/api/v1/users/" + old_code, headers=bob).status_code == 404)
    check("新 ID 能查到", client.get("/api/v1/users/iloveu", headers=bob).status_code == 200)
    alice_code = "iloveu"

    # 改过一次就锁死
    r = client.put("/api/v1/profile/code", json={"code": "lockme"}, headers=alice)
    check("再改一次被拒（已锁死）", r.status_code == 409, r.text[:80])
    r = client.get("/api/v1/profile", headers=alice)
    check("档案里标记为不可再改", r.json().get("code_changeable") is False)

    # 给 alice 造一条记录，方便生成分享内容
    client.post(
        "/api/v1/meals",
        json={
            "meal_slot": "lunch",
            "eaten_at": "2026-10-09T12:00:00+00:00",
            "source": "diy",
            "note": "",
            "items": [
                {
                    "food_name": "米饭",
                    "dish_name": "黄炆鸡米饭",
                    "energy_kcal": 200,
                    "match_status": "manual",
                },
                {
                    "food_name": "西兰花",
                    "dish_name": "清炒西兰花",
                    "energy_kcal": 50,
                    "match_status": "manual",
                },
            ],
        },
        headers=alice,
    )
    alice_meal_id = db.query_one(
        "SELECT id FROM meals WHERE user_id=? ORDER BY id DESC LIMIT 1", (alice_id,)
    )["id"]

    print("\n--- 按码看名片 ---")
    r = client.get("/api/v1/users/" + alice_code, headers=bob)
    card = r.json()
    check("能按码查到名片", r.status_code == 200 and card["code"] == alice_code, str(card))
    check("名片不含饮食数据", "meals" not in card and "restrictions" not in card, str(list(card.keys())))
    check("初始关系是 none", card.get("friend_status") == "none", str(card.get("friend_status")))
    check("乱码查不到人", client.get("/api/v1/users/zzzzzz", headers=bob).status_code == 404)

    print("\n--- 加好友要对方同意 ---")
    r = client.post("/api/v1/friends", json={"code": alice_code}, headers=bob)
    check("bob 申请加 alice", r.status_code == 200 and r.json()["status"] == "pending", r.text[:120])

    r = client.get("/api/v1/friends", headers=bob)
    check("还没同意时不是好友", len(r.json()["items"]) == 0, str(r.json()))

    r = client.get("/api/v1/users/" + alice_code, headers=bob)
    check("申请人看到 pending_out", r.json().get("friend_status") == "pending_out")

    r = client.get("/api/v1/friends/requests", headers=alice)
    inbox = r.json()["items"]
    check("alice 收到一行提醒", len(inbox) == 1 and inbox[0]["from"]["code"] == bob_code, str(inbox)[:160])
    request_id = inbox[0]["request_id"]

    r = client.get("/api/v1/users/" + bob_code, headers=alice)
    check("被申请方看到 pending_in", r.json().get("friend_status") == "pending_in")

    print("\n--- 同意 / 拒绝 ---")
    r = client.post(f"/api/v1/friends/requests/{request_id}/accept", headers=carol)
    check("别人不能替你同意", r.status_code == 404, r.text[:80])

    r = client.post(f"/api/v1/friends/requests/{request_id}/accept", headers=alice)
    check("alice 同意申请", r.status_code == 200 and r.json()["ok"], r.text[:80])

    r = client.get("/api/v1/friends", headers=alice)
    check("同意后 alice 有 bob", bob_id in [f["user_id"] for f in r.json()["items"]])
    r = client.get("/api/v1/friends", headers=bob)
    check("同意后 bob 有 alice", alice_id in [f["user_id"] for f in r.json()["items"]])
    # alice 前面已经把 ID 改成了 iloveu，bob 这边应该看到新 ID 而不是旧的
    check(
        "好友改 ID 后我这边同步成新 ID",
        any(f["code"] == "iloveu" for f in r.json()["items"]),
        str(r.json())[:160],
    )

    r = client.get("/api/v1/friends/requests", headers=alice)
    check("处理过的申请不再出现在提醒里", len(r.json()["items"]) == 0)

    # 拒绝流程
    client.post("/api/v1/friends", json={"code": bob_code}, headers=carol)
    inbox = client.get("/api/v1/friends/requests", headers=bob).json()["items"]
    check("bob 收到 carol 的申请", len(inbox) == 1, str(inbox)[:140])
    r = client.post(f"/api/v1/friends/requests/{inbox[0]['request_id']}/reject", headers=bob)
    check("bob 拒绝 carol", r.status_code == 200)
    r = client.get("/api/v1/friends", headers=bob)
    check("拒绝后不是好友", carol_id not in [f["user_id"] for f in r.json()["items"]])

    # 互相申请直接互加
    client.post("/api/v1/friends", json={"code": carol_code}, headers=carol)
    client.post("/api/v1/friends", json={"code": bob_code}, headers=carol)
    r = client.post("/api/v1/friends", json={"code": carol_code}, headers=bob)
    check("互相申请直接成为好友", r.json().get("status") == "friends", r.text[:120])

    print("\n--- 朋友圈 ---")
    r = client.post("/api/v1/feed/moments", json={"kind": "latest"}, headers=alice)
    check("发最近一餐成功", r.status_code == 200 and r.json()["payload"].get("meals"), r.text[:140])
    latest_meal = r.json()["payload"]["meals"][0]
    check("最近一餐分享带餐名", "黄炆鸡米饭" in latest_meal.get("dishes", []), str(latest_meal)[:160])
    check("最近一餐分享也带食材", "米饭" in latest_meal.get("foods", []), str(latest_meal.get("foods")))

    print("\n--- 分享带照片 ---")
    # 测试环境没配七牛，直接塞一条照片记录，只验字段流转和签名时机
    db.execute(
        "INSERT INTO meal_photos(meal_id, object_key, created_at) VALUES(?,?,?)",
        (alice_meal_id, "meals/test/sample.jpg", "2026-10-09T00:00:00+00:00"),
    )
    r = client.post("/api/v1/feed/moments", json={"kind": "latest"}, headers=alice)
    photo_payload = r.json()["payload"]
    check("有照片时 has_photo 为真", photo_payload.get("has_photo") is True, str(photo_payload)[:160])
    check(
        "发布时就带上了照片记录",
        bool(photo_payload["meals"][0].get("photo_keys")),
        str(photo_payload["meals"][0])[:160],
    )

    r = client.get("/api/v1/feed/moments", headers=alice)
    items_with_photo = [i for i in r.json()["items"] if i["payload"].get("has_photo")]
    check("读动态时带回 photos 字段", bool(items_with_photo))
    check(
        "对外不暴露 object_key",
        all(
            "photo_keys" not in m
            for i in r.json()["items"]
            for m in (i["payload"].get("meals") or [])
        ),
        "photo_keys 已经被换成 photos",
    )

    r = client.post("/api/v1/feed/moments", json={"kind": "weekly"}, headers=alice)
    weekly = r.json()["payload"]
    check("发周占比成功", r.status_code == 200 and len(weekly["category_share"]) > 0, str(weekly)[:120])

    r = client.get("/api/v1/feed/moments", headers=carol)
    items = r.json()["items"]
    check("非好友也能看到朋友圈", len(items) >= 2, f"看到 {len(items)} 条")
    check("朋友圈带作者码", items[0]["author"]["code"] == alice_code, str(items[0]["author"]))
    # 现在分享最近一餐会带照片了，未配七牛/无图的那些仍是 False，两种都要能共存
    check(
        "朋友圈里带图与不带图共存",
        any(i["payload"].get("has_photo") for i in items)
        and any(not i["payload"].get("has_photo") for i in items),
        str([i["payload"].get("has_photo") for i in items]),
    )
    check("别人看时 mine 为假", all(not i["mine"] for i in items))
    r = client.get("/api/v1/feed/moments", headers=alice)
    check("作者自己看时 mine 为真", all(i["mine"] for i in r.json()["items"]))

    print("\n--- 一对一分享 ---")
    r = client.post(f"/api/v1/feed/direct/{bob_id}", json={"kind": "latest"}, headers=alice)
    check("给好友分享今天吃的", r.status_code == 200, r.text[:100])
    r = client.post(f"/api/v1/feed/direct/{bob_id}", json={"kind": "weekly"}, headers=alice)
    check("给好友分享一周占比", r.status_code == 200, r.text[:100])

    r = client.get(f"/api/v1/feed/direct/{alice_id}", headers=bob)
    check("bob 收到两条", len(r.json()["items"]) == 2, f"共 {len(r.json()['items'])} 条")
    r = client.get(f"/api/v1/feed/direct/{bob_id}", headers=alice)
    check("alice 也能看到同一段", len(r.json()["items"]) == 2)

    _, _, dave = login("13700000004")
    r = client.get(f"/api/v1/feed/direct/{alice_id}", headers=dave)
    check("第三方看不到别人的私聊", len(r.json()["items"]) == 0)
    r = client.post(f"/api/v1/feed/direct/{carol_id}", json={"kind": "latest"}, headers=dave)
    check("非好友不能直接分享", r.status_code == 403, r.text[:80])
    r = client.post(f"/api/v1/feed/direct/{alice_id}", json={"kind": "latest"}, headers=alice)
    check("不能分享给自己", r.status_code == 400, r.text[:80])

    print()
    if all(checks):
        print("广场功能自测全部通过")
        return 0
    print(f"有失败项（共 {len(checks)} 项）")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
