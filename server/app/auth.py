"""管理后台认证：HMAC 签名的无状态 token，够用且不引入额外依赖。"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import Depends, Header, HTTPException, status

from .config import get_settings


def _sign(payload: bytes) -> str:
    secret = get_settings().admin_secret.encode()
    digest = hmac.new(secret, payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode().rstrip("=")


def issue_token(subject: str = "admin") -> tuple[str, int]:
    settings = get_settings()
    exp = int(time.time()) + settings.admin_token_ttl
    body = {"sub": subject, "exp": exp}
    raw = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    token = f"{base64.urlsafe_b64encode(raw).decode().rstrip('=')}.{_sign(raw)}"
    return token, exp


def verify_password(password: str) -> bool:
    expected = get_settings().admin_password
    return hmac.compare_digest(password.encode(), expected.encode())


def verify_token(token: str) -> dict:
    try:
        encoded, signature = token.split(".", 1)
        padded = encoded + "=" * (-len(encoded) % 4)
        raw = base64.urlsafe_b64decode(padded)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录状态无效，请重新登录") from exc

    if not hmac.compare_digest(signature, _sign(raw)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录状态无效，请重新登录")

    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录状态无效，请重新登录") from exc

    if int(body.get("exp", 0)) < int(time.time()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已过期，请重新登录")
    return body


def require_admin(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "需要管理员登录")
    return verify_token(authorization.split(" ", 1)[1].strip())


AdminUser = Depends(require_admin)
