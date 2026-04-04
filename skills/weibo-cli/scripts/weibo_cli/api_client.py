"""微博 HTTP 客户端。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from .session import WeiboSession, assert_session_configured


class WeiboApiError(RuntimeError):
    def __init__(self, message: str, url: str, status: int | None = None, details: str | None = None):
        super().__init__(message)
        self.url = url
        self.status = status
        self.details = details


class WeiboAuthError(WeiboApiError):
    pass


@dataclass(slots=True)
class SessionProbeResult:
    ok: bool
    url: str
    login: bool | None
    uid: str | None


class WeiboApiClient:
    def __init__(self, session: WeiboSession, base_url: str | None = None, min_interval_ms: int = 250):
        self.session = session
        self.base_url = normalize_base_url(base_url)
        self.min_interval_ms = max(0, min_interval_ms)
        self.user_agent = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1 weibo-cli/0.1.0"
        )
        self.last_request_at = 0.0

    @classmethod
    def from_configured_session(cls) -> "WeiboApiClient":
        return cls(assert_session_configured())

    def validate_session(self) -> SessionProbeResult:
        payload = self.request_json("/api/config", method="GET")
        data = payload.get("data") or {}
        login = data.get("login")
        uid = normalize_uid(data.get("uid"))
        if login is False:
            raise WeiboAuthError("微博登录态已失效，请重新运行 login 更新 cookie。", self.build_url("/api/config"))
        return SessionProbeResult(ok=True, url=self.build_url("/api/config"), login=login, uid=uid)

    def request_json(self, path: str, *, method: str = "GET", query: dict[str, Any] | None = None,
                     headers: dict[str, str] | None = None, data: Any = None,
                     auth_required: bool = True) -> dict[str, Any]:
        response = self.request(path, method=method, query=query, headers=headers, data=data, auth_required=auth_required)
        text = response.text.strip()
        if not text:
            return {}
        try:
            return response.json()
        except ValueError as error:
            raise WeiboApiError(f"微博接口返回了非 JSON 响应，无法解析：{error}", response.url, response.status_code, text[:400]) from error

    def request(self, path: str, *, method: str = "GET", query: dict[str, Any] | None = None,
                headers: dict[str, str] | None = None, data: Any = None, auth_required: bool = True) -> requests.Response:
        self.wait_for_rate_limit()
        url = self.build_url(path, query)
        merged_headers = self.build_headers(headers, auth_required=auth_required)
        response = requests.request(method=method, url=url, headers=merged_headers, data=data, allow_redirects=True, timeout=30)
        self.last_request_at = time.time()

        if response.status_code in (401, 403):
            raise WeiboAuthError("微博登录态无效或已失效，请重新运行 login 更新 cookie。", response.url, response.status_code, response.text[:400])
        if not response.ok:
            raise WeiboApiError(f"微博接口请求失败（HTTP {response.status_code}）。", response.url, response.status_code, response.text[:400])
        return response

    def build_headers(self, extra_headers: dict[str, str] | None, *, auth_required: bool) -> dict[str, str]:
        headers = {k.lower(): v for k, v in (extra_headers or {}).items()}
        csrf_token = extract_cookie_value(self.session.cookie, "XSRF-TOKEN") or extract_cookie_value(self.session.cookie, "X-CSRF-TOKEN")
        headers.setdefault("accept", "application/json, text/plain, */*")
        headers.setdefault("user-agent", self.user_agent)
        headers.setdefault("x-requested-with", "XMLHttpRequest")
        if auth_required:
            headers.setdefault("cookie", self.session.cookie)
            headers.setdefault("origin", "https://m.weibo.cn")
        if csrf_token:
            headers.setdefault("x-xsrf-token", csrf_token)
            headers.setdefault("x-csrf-token", csrf_token)
        return headers

    def build_url(self, path: str, query: dict[str, Any] | None = None) -> str:
        base = self.base_url[:-1] if self.base_url.endswith("/") else self.base_url
        url = f"{base}{path}"
        if not query:
            return url
        filtered = {key: str(value) for key, value in query.items() if value is not None}
        if not filtered:
            return url
        return f"{url}?{requests.compat.urlencode(filtered)}"

    def wait_for_rate_limit(self) -> None:
        wait_seconds = (self.last_request_at + self.min_interval_ms / 1000) - time.time()
        if wait_seconds > 0:
            time.sleep(wait_seconds)


def normalize_base_url(base_url: str | None) -> str:
    resolved = (base_url or os.environ.get("WEIBO_API_BASE_URL") or "https://m.weibo.cn").strip()
    return resolved if resolved.endswith("/") else f"{resolved}/"


def normalize_uid(uid: Any) -> str | None:
    if uid is None:
        return None
    normalized = str(uid).strip()
    return normalized or None


def extract_cookie_value(cookie_header: str, key: str) -> str | None:
    for segment in cookie_header.split(";"):
        part = segment.strip()
        if not part or "=" not in part:
            continue
        current_key, value = part.split("=", 1)
        if current_key.strip() == key:
            return value.strip()
    return None