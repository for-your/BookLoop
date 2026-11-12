"""
微信扫码免密登录（需求："支持微信扫码免密（绑定后）"）。

- 生产：配置 WECHAT_APPID / WECHAT_SECRET 后走真实 OAuth2：
    mp_h5  公众号网页授权（微信内置浏览器，scope=snsapi_userinfo）
    open_qr 开放平台网站应用扫码登录（scope=snsapi_login）
- 演示：未配置时自动进入 mock 模式，code="demo" 映射到预置 openid
  （见 services/wechat.py 的 DEMO_OPENID，由 init_data.py 绑定到演示账号）。

零依赖：真实调用仅使用标准库 urllib，不引入 requests/httpx。
"""
from __future__ import annotations

import hashlib
import json
from urllib.parse import urlencode
from urllib.request import urlopen

from ..core.config import (
    WECHAT_APPID,
    WECHAT_MOCK,
    WECHAT_MODE,
    WECHAT_REDIRECT_URI,
    WECHAT_SECRET,
)

# 演示模式预置 openid（init_data.py 会绑定到学生 20230001）
DEMO_OPENID = "mock_demo_openid"


def oauth_url(redirect_uri: str = "", state: str = "") -> str:
    """生成微信 OAuth 授权地址（公众号网页授权 / 开放平台二维码）"""
    redirect_uri = redirect_uri or WECHAT_REDIRECT_URI
    base = (
        "https://open.weixin.qq.com/connect/qrconnect"
        if WECHAT_MODE == "open_qr"
        else "https://open.weixin.qq.com/connect/oauth2/authorize"
    )
    params = {
        "appid": WECHAT_APPID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "snsapi_login" if WECHAT_MODE == "open_qr" else "snsapi_userinfo",
        "state": state,
    }
    url = f"{base}?{urlencode(params)}"
    return url + ("#wechat_redirect" if WECHAT_MODE == "open_qr" else "")


def _get_json(url: str) -> dict:
    with urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))


def code2session(code: str) -> dict:
    """用授权 code 换取微信身份。返回 {openid, unionid, nickname, avatar}"""
    if WECHAT_MOCK:
        openid = DEMO_OPENID if code == "demo" else "mock_" + hashlib.md5(code.encode()).hexdigest()[:16]
        return {"openid": openid, "unionid": "", "nickname": "微信演示用户", "avatar": ""}

    # code → access_token + openid
    token_url = "https://api.weixin.qq.com/sns/oauth2/access_token?" + urlencode(
        {"appid": WECHAT_APPID, "secret": WECHAT_SECRET, "code": code, "grant_type": "authorization_code"}
    )
    data = _get_json(token_url)
    if "errcode" in data:
        raise RuntimeError(f"微信登录失败：{data.get('errmsg', data['errcode'])}")

    openid = data.get("openid", "")
    unionid = data.get("unionid", "")
    access_token = data.get("access_token", "")
    nickname = avatar = ""
    # scope=snsapi_userinfo 时补充昵称头像
    if access_token and data.get("scope") == "snsapi_userinfo":
        try:
            info = _get_json(
                "https://api.weixin.qq.com/sns/userinfo?"
                + urlencode({"access_token": access_token, "openid": openid, "lang": "zh_CN"})
            )
            nickname, avatar = info.get("nickname", ""), info.get("headimgurl", "")
        except Exception:
            pass
    return {"openid": openid, "unionid": unionid, "nickname": nickname, "avatar": avatar}
