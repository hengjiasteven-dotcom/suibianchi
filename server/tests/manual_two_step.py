"""手工验证：识别只出名称，确认后才估算热量。"""
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def post(path, payload, token=None):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}
    )
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    login = post("/auth/login/password", {"phone": "13900001111", "password": "test1234"})
    token = login["access_token"]

    text = sys.argv[1] if len(sys.argv) > 1 else "外卖：宫保鸡丁、番茄炒蛋、清炒油麦菜、米饭两份，备注少辣不要香菜"
    rec = post(
        "/recognition",
        {"text": text, "meal_slot": "lunch", "source": "takeout", "image_keys": []},
        token,
    )
    result = rec["result"]
    print("== 第一步：识别 ==")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    leaked = [i for i in result["items"] if i.get("energy_kcal") is not None]
    print("热量字段泄漏条数:", len(leaked))

    est = post(
        "/estimates",
        {"meal_slot": "lunch", "items": result["items"]},
        token,
    )
    print("== 第二步：确认后估算 ==")
    print(json.dumps(est, ensure_ascii=False, indent=2))
    print("合计 kcal:", est["energy_total_kcal"])
    print("菜品归属:", sorted({i.get("dish_name") or "(空)" for i in est["items"]}))


if __name__ == "__main__":
    main()
