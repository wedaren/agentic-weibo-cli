"""登录态加载、校验与持久化。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from .local_config import get_local_config_path, read_local_config, write_local_config

AUTH_COOKIE_KEYS = ("SUB", "SUBP", "SCF")
EXPIRY_COOKIE_KEY = "ALF"


@dataclass(slots=True)
class WeiboSession:
    cookie: str
    uid: str | None
    login_url: str | None
    updated_at: str
    source: Literal["env", "local"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def looks_like_cookie(cookie: str) -> bool:
    return "=" in cookie and ";" in cookie


def normalize_cookie(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized if normalized and looks_like_cookie(normalized) else None


def normalize_optional(value: str | None) -> str | None:
    normalized = (value or "").strip()
    return normalized or None


def parse_cookie_header(cookie: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for segment in cookie.split(";"):
        part = segment.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        if key:
            result[key] = value.strip()
    return result


def read_cookie_expiry(raw_expiry: str | None) -> str | None:
    if not raw_expiry:
        return None
    try:
        seconds = int(raw_expiry)
    except ValueError:
        return None
    if seconds <= 0:
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def load_session() -> WeiboSession | None:
    env_cookie = normalize_cookie(os.environ.get("WEIBO_COOKIE"))
    env_uid = normalize_optional(os.environ.get("WEIBO_UID"))
    if env_cookie:
        return WeiboSession(cookie=env_cookie, uid=env_uid, login_url=None, updated_at=now_iso(), source="env")

    local_config = read_local_config() or {}
    local_cookie = normalize_cookie(local_config.get("cookie"))
    if not local_cookie:
        return None

    return WeiboSession(
        cookie=local_cookie,
        uid=normalize_optional(local_config.get("uid")),
        login_url=normalize_optional(local_config.get("loginUrl")),
        updated_at=normalize_optional(local_config.get("updatedAt")) or now_iso(),
        source="local",
    )


def validate_session(session: WeiboSession) -> WeiboSession:
    normalized_cookie = normalize_cookie(session.cookie)
    if not normalized_cookie:
        raise RuntimeError("微博登录态格式无效。cookie 必须是浏览器导出的完整请求头字符串。")

    cookies = parse_cookie_header(normalized_cookie)
    auth_cookie_keys = [key for key in AUTH_COOKIE_KEYS if key in cookies]
    if not auth_cookie_keys:
        raise RuntimeError(
            f"微博登录态缺少核心鉴权 cookie。至少需要包含 {'/'.join(AUTH_COOKIE_KEYS)} 之一，请重新执行 login。"
        )

    expires_at = read_cookie_expiry(cookies.get(EXPIRY_COOKIE_KEY))
    if expires_at:
        expires_ts = datetime.fromisoformat(expires_at.replace("Z", "+00:00")).timestamp()
        if expires_ts <= datetime.now(timezone.utc).timestamp():
            raise RuntimeError(f"微博登录态已过期（ALF={expires_at}）。请重新运行 login 更新本地登录态。")

    return WeiboSession(
        cookie=normalized_cookie,
        uid=normalize_optional(session.uid),
        login_url=normalize_optional(session.login_url),
        updated_at=normalize_optional(session.updated_at) or now_iso(),
        source=session.source,
    )


def assert_session_configured() -> WeiboSession:
    env_cookie = os.environ.get("WEIBO_COOKIE")
    if env_cookie and not looks_like_cookie(env_cookie.strip()):
        raise RuntimeError("环境变量 WEIBO_COOKIE 格式无效。cookie 至少应包含一个分号分隔的键值对。")

    local_config = read_local_config() or {}
    local_cookie = local_config.get("cookie")
    if local_cookie and not looks_like_cookie(str(local_cookie).strip()):
        raise RuntimeError(f"本地登录态文件 {get_local_config_path()} 格式无效。")

    session = load_session()
    if session is None:
        raise RuntimeError(
            f"微博登录态尚未配置。请先运行 login，或通过环境变量 WEIBO_COOKIE/WEIBO_UID 提供登录态。默认本地文件路径：{get_local_config_path()}"
        )
    return validate_session(session)


def persist_session(cookie: str, uid: str | None = None, login_url: str | None = None) -> tuple[str, WeiboSession]:
    normalized_cookie = normalize_cookie(cookie)
    if not normalized_cookie:
        raise RuntimeError("微博 cookie 为空。请在扫码登录成功后粘贴浏览器中的完整 cookie 字符串。")

    config = {
        "cookie": normalized_cookie,
        "uid": normalize_optional(uid),
        "loginUrl": normalize_optional(login_url),
        "updatedAt": now_iso(),
    }
    path = write_local_config(config)
    session = WeiboSession(
        cookie=normalized_cookie,
        uid=config["uid"],
        login_url=config["loginUrl"],
        updated_at=config["updatedAt"],
        source="local",
    )
    return str(path), session