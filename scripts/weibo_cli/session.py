"""会话模型与本地存储。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from .local_config import get_browser_profile_dir, get_local_config_path, read_local_config, write_local_config

AUTH_COOKIE_KEYS = ("SUB", "SUBP", "SCF")
EXPIRY_COOKIE_KEY = "ALF"
DOMAIN_PRIORITY = ("m.weibo.cn", ".m.weibo.cn", "weibo.com", ".weibo.com", "passport.weibo.com", ".passport.weibo.com")


@dataclass(frozen=True, slots=True)
class CookieRecord:
    name: str
    value: str
    domain: str | None = None
    path: str = "/"
    expires: int | None = None
    secure: bool = False
    http_only: bool = False


@dataclass(frozen=True, slots=True)
class SessionData:
    uid: str | None
    login_url: str | None
    updated_at: str
    source: Literal["env", "local"]
    cookies: tuple[CookieRecord, ...]

    def cookie_header(self) -> str:
        cookies_by_name = {cookie.name: cookie.value for cookie in select_cookie_header_cookies(self.cookies)}
        return "; ".join(f"{name}={value}" for name, value in cookies_by_name.items())

    def cookie_names(self) -> tuple[str, ...]:
        return tuple(cookie.name for cookie in select_cookie_header_cookies(self.cookies))

    def csrf_token(self) -> str | None:
        for key in ("XSRF-TOKEN", "X-CSRF-TOKEN"):
            for cookie in select_cookie_header_cookies(self.cookies):
                if cookie.name == key:
                    return cookie.value
        return None

    def assert_auth_cookies(self) -> None:
        cookie_names = {cookie.name for cookie in self.cookies}
        if not any(key in cookie_names for key in AUTH_COOKIE_KEYS):
            raise RuntimeError(
                f"微博登录态缺少核心鉴权 cookie。至少需要包含 {'/'.join(AUTH_COOKIE_KEYS)} 之一。"
                "请先执行 status 确认状态，再按需执行 login 或 login --force。"
            )
        expires = next((cookie.expires for cookie in self.cookies if cookie.name == EXPIRY_COOKIE_KEY and cookie.expires is not None), None)
        if expires is not None and expires <= int(datetime.now(timezone.utc).timestamp()):
            expires_at = datetime.fromtimestamp(expires, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            raise RuntimeError(
                f"微博登录态已过期（ALF={expires_at}）。请先执行 status 确认状态，再按需执行 login 或 login --force。"
            )

    def with_updates(
        self,
        *,
        uid: str | None | object = None,
        login_url: str | None | object = None,
        updated_at: str | None | object = None,
        source: Literal["env", "local"] | object = None,
        cookies: tuple[CookieRecord, ...] | object = None,
    ) -> "SessionData":
        resolved_uid = self.uid if uid is None else uid
        resolved_login_url = self.login_url if login_url is None else login_url
        resolved_updated_at = self.updated_at if updated_at is None else updated_at
        resolved_source = self.source if source is None else source
        resolved_cookies = self.cookies if cookies is None else cookies
        return SessionData(
            uid=resolved_uid,
            login_url=resolved_login_url,
            updated_at=resolved_updated_at,
            source=resolved_source,
            cookies=resolved_cookies,
        )


@dataclass(slots=True)
class SessionStatus:
    configured: bool
    usable: bool
    source: str | None
    uid: str | None
    updated_at: str | None
    message: str
    session: SessionData | None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_optional(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def parse_cookie_header(cookie_header: str) -> tuple[CookieRecord, ...]:
    cookies: list[CookieRecord] = []
    for segment in cookie_header.split(";"):
        part = segment.strip()
        if not part or "=" not in part:
            continue
        name, value = part.split("=", 1)
        normalized_name = normalize_optional(name)
        if not normalized_name:
            continue
        cookies.append(CookieRecord(name=normalized_name, value=value.strip()))
    return tuple(cookies)


def merge_cookies(existing: tuple[CookieRecord, ...], incoming: tuple[CookieRecord, ...]) -> tuple[CookieRecord, ...]:
    ordered: list[CookieRecord] = list(existing)
    index_by_key = {cookie_identity(cookie): index for index, cookie in enumerate(ordered)}
    for cookie in incoming:
        key = cookie_identity(cookie)
        if key in index_by_key:
            ordered[index_by_key[key]] = cookie
            continue
        index_by_key[key] = len(ordered)
        ordered.append(cookie)
    return tuple(ordered)


def select_cookie_header_cookies(cookies: tuple[CookieRecord, ...]) -> tuple[CookieRecord, ...]:
    selected: dict[str, CookieRecord] = {}
    for cookie in cookies:
        current = selected.get(cookie.name)
        if current is None or compare_cookie_priority(cookie, current) > 0:
            selected[cookie.name] = cookie
    return tuple(selected[name] for name in sorted(selected.keys()))


def serialize_cookies(cookies: tuple[CookieRecord, ...]) -> list[dict[str, Any]]:
    return [
        {
            "name": cookie.name,
            "value": cookie.value,
            "domain": cookie.domain,
            "path": cookie.path,
            "expires": cookie.expires,
            "secure": cookie.secure,
            "http_only": cookie.http_only,
        }
        for cookie in cookies
    ]


def deserialize_cookies(raw_cookies: Any) -> tuple[CookieRecord, ...]:
    if not isinstance(raw_cookies, list):
        return ()
    cookies: list[CookieRecord] = []
    for row in raw_cookies:
        if not isinstance(row, dict):
            continue
        name = normalize_optional(row.get("name"))
        value = normalize_optional(row.get("value"))
        if not name or value is None:
            continue
        expires = normalize_expires(row.get("expires"))
        cookies.append(
            CookieRecord(
                name=name,
                value=value,
                domain=normalize_optional(row.get("domain")),
                path=normalize_optional(row.get("path")) or "/",
                expires=expires,
                secure=bool(row.get("secure")),
                http_only=bool(row.get("http_only") or row.get("httpOnly")),
            )
        )
    return tuple(cookies)


def normalize_expires(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    normalized = normalize_optional(value)
    if normalized is None:
        return None
    try:
        return int(float(normalized))
    except ValueError:
        return None


def cookie_identity(cookie: CookieRecord) -> tuple[str, str | None, str]:
    return (cookie.name, cookie.domain, cookie.path)


def compare_cookie_priority(candidate: CookieRecord, current: CookieRecord) -> int:
    domain_score = score_domain(candidate.domain) - score_domain(current.domain)
    if domain_score:
        return domain_score
    path_score = len(candidate.path or "") - len(current.path or "")
    if path_score:
        return path_score
    return (candidate.expires or 0) - (current.expires or 0)


def score_domain(domain: str | None) -> int:
    if not domain:
        return 0
    try:
        index = DOMAIN_PRIORITY.index(domain)
    except ValueError:
        return 0
    return len(DOMAIN_PRIORITY) - index


class SessionStore:
    def __init__(self):
        self.session_path = get_local_config_path()
        self.browser_profile_dir = get_browser_profile_dir()

    def load(self) -> SessionData | None:
        env_cookie = normalize_optional(os.environ.get("WEIBO_COOKIE"))
        env_uid = normalize_optional(os.environ.get("WEIBO_UID"))
        if env_cookie:
            return SessionData(
                uid=env_uid,
                login_url=None,
                updated_at=now_iso(),
                source="env",
                cookies=parse_cookie_header(env_cookie),
            )

        config = read_local_config()
        if config is None:
            return None
        return self._deserialize_local_session(config)

    def save(self, session: SessionData) -> str:
        payload = {
            "version": 2,
            "uid": session.uid,
            "login_url": session.login_url,
            "updated_at": session.updated_at,
            "cookies": serialize_cookies(session.cookies),
        }
        return str(write_local_config(payload))

    def _deserialize_local_session(self, config: dict[str, Any]) -> SessionData | None:
        cookies = deserialize_cookies(config.get("cookies"))
        if not cookies:
            cookies = deserialize_cookies(config.get("cookieJar"))
        if not cookies:
            cookie_header = normalize_optional(config.get("cookie"))
            if cookie_header:
                cookies = parse_cookie_header(cookie_header)
        if not cookies:
            return None
        return SessionData(
            uid=normalize_optional(config.get("uid")),
            login_url=normalize_optional(config.get("login_url") or config.get("loginUrl")),
            updated_at=normalize_optional(config.get("updated_at") or config.get("updatedAt")) or now_iso(),
            source="local",
            cookies=cookies,
        )