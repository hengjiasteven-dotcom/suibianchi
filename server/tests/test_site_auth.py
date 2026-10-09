"""方案 C（账号打通）对接测试。

用一个假的站点账号服务顶替 xiaodaidai.site 的后端，验证：
- 发验证码走站点接口（不再回显验证码）
- 验证码登录 → 站点返回用户 → 本地建立 site_user_id 映射 → 发我们自己的令牌
- 密码登录 / 找回密码同样走站点
不真发短信，也不碰站点。

跑法：cd server && python tests/test_site_auth.py
"""

import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 必须在导入 app 之前设置：config 是导入时读环境变量的
_TMP = tempfile.mkdtemp()
os.environ["SHIJI_SITE_AUTH"] = "1"
STUB_PORT = 18081
os.environ["SHIJI_SITE_API_BASE"] = f"http://127.0.0.1:{STUB_PORT}"
os.environ["SHIJI_DB_PATH"] = os.path.join(_TMP, "site-auth-test.db")
os.environ["SHIJI_SMS_DEV_MODE"] = "0"

SITE_USER_ID = 777
PHONE = "13800001234"
SENT = {"count": 0}


class StubSite(BaseHTTPRequestHandler):
    """假装是站点的 /api/v1/auth/* 接口。"""

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        payload = json.loads(raw or b"{}")
        phone = str(payload.get("phone") or PHONE)

        SENT["last_xff"] = self.headers.get("X-Forwarded-For", "")
        if self.path.endswith("/phone/send-code"):
            SENT["count"] += 1
            self._json(200, {"ok": True, "data": {"sent": True, "phone": phone, "expiresIn": 300}})
        elif self.path.endswith("/phone/verify"):
            if payload.get("code") == "000000":
                self._json(400, {"ok": False, "error": "验证码不正确"})
                return
            self._json(200, {"ok": True, "data": {
                "authenticated": True,
                "role": "visitor",
                "user": {"id": SITE_USER_ID, "phone": phone, "nickname": "站点用户"},
            }})
        elif self.path.endswith("/password/login"):
            if payload.get("password") == "good-pass":
                self._json(200, {"ok": True, "data": {
                    "authenticated": True,
                    "user": {"id": SITE_USER_ID, "phone": phone, "nickname": "站点用户"},
                }})
            else:
                self._json(401, {"ok": False, "error": "手机号或密码不正确"})
        elif self.path.endswith("/password/reset"):
            self._json(200, {"ok": True, "data": {"user": {"id": SITE_USER_ID, "phone": phone}}})
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def _json(self, status, body):
        data = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):  # 静音
        return


def main() -> int:
    server = HTTPServer(("127.0.0.1", STUB_PORT), StubSite)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    from fastapi.testclient import TestClient

    from app import db, main

    checks = []

    def check(name, ok, extra=""):
        checks.append(ok)
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  {extra}"))

    with TestClient(main.app) as client:
        # 1) 发验证码：走站点，不回显验证码
        resp = client.post(
            "/api/v1/auth/sms/send",
            json={"phone": PHONE},
            headers={"X-Forwarded-For": "203.0.113.9"},
        )
        check("把用户真实 IP 透传给站点", SENT.get("last_xff") == "203.0.113.9", SENT)
        body = resp.json()
        check("发验证码走站点接口", resp.status_code == 200 and body.get("dev_mode") is False and "code" not in body, body)
        check("站点确实被调用了一次", SENT["count"] == 1, SENT)

        # 2) 错误验证码 → 站点返回错误 → 我们翻译成 400
        resp = client.post("/api/v1/auth/sms/verify", json={"phone": PHONE, "code": "000000"})
        check("验证码错误被拦下", resp.status_code == 400 and "验证码" in resp.text, resp.text)

        # 3) 正确验证码 → 自动建号并映射 site_user_id → 发我们的令牌
        # 3) 正确验证码但没给密码：首次注册必须拦住，不允许出现无密码账号
        resp = client.post("/api/v1/auth/sms/verify", json={"phone": PHONE, "code": "123456"})
        check(
            "首次注册不给密码被拦下",
            resp.status_code == 400 and "设置密码" in resp.text,
            resp.text,
        )
        check(
            "被拦下时没有偷偷建号",
            db.query_one("SELECT id FROM users WHERE phone=?", (PHONE,)) is None,
            "",
        )

        # 4) 带上密码再注册 → 自动建号并映射 site_user_id → 发我们的令牌
        resp = client.post(
            "/api/v1/auth/sms/verify",
            json={"phone": PHONE, "code": "123456", "password": "app-pass-123"},
        )
        body = resp.json()
        token = body.get("access_token")
        check(
            "带密码注册拿到令牌",
            resp.status_code == 200 and bool(token) and bool(body.get("device_token")),
            body,
        )

        row = db.query_one("SELECT * FROM users WHERE phone=?", (PHONE,))
        check("本地用户映射到站点 id", bool(row) and row.get("site_user_id") == SITE_USER_ID, row)
        check("密码在本地留了一份", bool(row and row.get("password_hash")), str(row))

        # 5) 用注册时设的密码能直接登录（走本地那份，不依赖站点）
        resp = client.post(
            "/api/v1/auth/login/password",
            json={"phone": PHONE, "password": "app-pass-123"},
        )
        check(
            "能用注册时设的密码登录",
            resp.status_code == 200 and bool(resp.json().get("access_token")),
            resp.text,
        )

        resp = client.post(
            "/api/v1/auth/login/password",
            json={"phone": PHONE, "password": "app-pass-999"},
        )
        check("本地密码不对时不会误放行", resp.status_code in (401, 400), resp.text)

        # 4) 用令牌访问自己的档案（说明登录态真的可用）
        resp = client.get("/api/v1/profile", headers={"Authorization": f"Bearer {token}"})
        check("令牌可以访问接口", resp.status_code == 200 and resp.json().get("user_id") == row["id"], resp.text)

        # 5) 密码登录 / 找回密码也走站点
        resp = client.post("/api/v1/auth/login/password", json={"phone": PHONE, "password": "good-pass"})
        check("密码登录走站点", resp.status_code == 200 and bool(resp.json().get("access_token")), resp.text)

        resp = client.post("/api/v1/auth/login/password", json={"phone": PHONE, "password": "wrong-pass"})
        check("密码错误被拦下", resp.status_code == 401, resp.text)

        resp = client.post("/api/v1/auth/password/reset", json={"phone": PHONE, "code": "123456", "password": "new-pass"})
        check("找回密码走站点", resp.status_code == 200 and resp.json().get("ok") is True, resp.text)

    server.shutdown()

    if all(checks):
        print("\n方案 C 对接全部通过")
        return 0
    print("\n有失败项")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
