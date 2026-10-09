"""方案 C · 账号打通：短信与密码校验全部委托给 xiaodaidai.site 的后端。

我们只调用站点已有的 HTTP 接口，不修改它的代码和数据库：

  POST /api/v1/auth/phone/send-code   发验证码（阿里云号码认证服务）
  POST /api/v1/auth/phone/verify      校验验证码并登录/自动建号
  POST /api/v1/auth/password/login    手机号 + 密码登录
  POST /api/v1/auth/password/reset    短信找回密码

站点返回格式：成功 {ok: true, data: {...}}，失败 {ok: false, error: "..."}。
拿到站点用户后，我们在自己的库里按 site_user_id 做映射（见 db.find_or_create_site_user）。
"""

from typing import Dict, Optional

import httpx

from .config import SITE_API_BASE, SITE_AUTH_ENABLED, SITE_AUTH_TIMEOUT


class SiteAuthError(Exception):
    """站点账号服务返回的错误（消息可直接给用户看）。"""


def enabled() -> bool:
    return SITE_AUTH_ENABLED


def _post(path: str, payload: Dict, client_ip: str = "") -> Dict:
    url = f"{SITE_API_BASE}{path}"
    try:
        # 把 App 用户的真实 IP 透传给站点，否则站点的“每 IP 限流”会被所有用户共用
        headers = {"X-Forwarded-For": client_ip, "X-Real-IP": client_ip} if client_ip else {}
        response = httpx.post(url, json=payload, headers=headers, timeout=SITE_AUTH_TIMEOUT)
    except httpx.HTTPError as exc:  # 站点服务没起来 / 网络不通
        raise SiteAuthError("账号服务暂时不可用，请稍后再试") from exc

    try:
        body = response.json()
    except Exception:  # noqa: BLE001
        body = {}

    if response.status_code >= 400 or body.get("ok") is False:
        message = body.get("error") or f"账号服务返回 {response.status_code}"
        raise SiteAuthError(str(message))
    return body.get("data") or {}


def _pick_user(data: Dict, phone: str) -> Dict:
    """从站点响应里取出我们需要的用户信息。"""
    user = data.get("user") or {}
    site_id = user.get("id")
    if site_id is None:
        raise SiteAuthError("账号服务没有返回用户信息")
    return {
        "site_user_id": int(site_id),
        "phone": str(user.get("phone") or phone),
        "nickname": str(user.get("nickname") or ""),
        "avatar": str(user.get("avatar") or ""),
    }


def send_code(phone: str, purpose: str = "login", client_ip: str = "") -> Dict:
    """发短信验证码。purpose: login / register / reset / change。"""
    return _post(
        "/api/v1/auth/phone/send-code",
        {"phone": phone, "purpose": purpose},
        client_ip,
    )


def login_with_code(
    phone: str, code: str, purpose: str = "login", client_ip: str = ""
) -> Dict:
    """校验验证码；站点侧会自动建号，返回统一后的用户信息。"""
    data = _post(
        "/api/v1/auth/phone/verify",
        {"phone": phone, "code": code, "purpose": purpose},
        client_ip,
    )
    return _pick_user(data, phone)


def login_with_password(phone: str, password: str, client_ip: str = "") -> Dict:
    data = _post(
        "/api/v1/auth/password/login",
        {"phone": phone, "password": password},
        client_ip,
    )
    return _pick_user(data, phone)


def reset_password(phone: str, code: str, new_password: str) -> Dict:
    data = _post(
        "/api/v1/auth/password/reset",
        {"phone": phone, "code": code, "password": new_password},
    )
    user = data.get("user")
    return _pick_user(data, phone) if user else {}
