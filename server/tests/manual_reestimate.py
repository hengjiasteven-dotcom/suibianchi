"""手工验证：提交后热量由后台估算并回填，手动重算接口可用。"""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"


def req(method, path, body=None, token=None):
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        BASE + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    if token:
        request.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(request, timeout=180) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    token = req(
        "POST", "/auth/login/password", {"phone": "13900001111", "password": "test1234"}
    )["access_token"]

    meals = req("GET", "/meals", None, token)["items"]
    if not meals:
        print("没有可用的记录")
        return
    meal = meals[0]
    print("目标记录", meal["id"], meal["status"], meal["total_energy_kcal"])

    started = req("POST", "/meals/%d/estimate" % meal["id"], {}, token)
    print("触发重算 ->", started["status"], started["total_energy_kcal"])
    if started["status"] != "estimating":
        print("预期是 estimating，实际不是")
        sys.exit(1)

    for _ in range(30):
        time.sleep(3)
        rows = req("GET", "/meals", None, token)["items"]
        cur = [x for x in rows if x["id"] == meal["id"]][0]
        if cur["status"] != "estimating":
            print("回填完成", cur["status"], cur["total_energy_kcal"])
            return
    print("超时：一直停在 estimating")
    sys.exit(1)


if __name__ == "__main__":
    main()
