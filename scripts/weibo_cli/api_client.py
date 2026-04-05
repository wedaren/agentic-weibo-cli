"""微博 HTTP 客户端。"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from .session import CookieRecord, SessionData, SessionStore, merge_cookies, now_iso, normalize_optional
from .logger import get_logger

log = get_logger(__name__)


class WeiboApiError(RuntimeError):
    def __init__(self, message: str, url: str, status: int | None = None, details: str | None = None):
        super().__init__(message)
        self.url = url
        self.status = status
        self.details = details


class WeiboAuthError(WeiboApiError):
    pass


class WeiboNetworkError(WeiboApiError):
    pass


@dataclass(slots=True)
class SessionProbeResult:
    ok: bool
    url: str
    login: bool | None
    uid: str | None


class WeiboApiClient:
    def __init__(self, session: SessionData, store: SessionStore | None = None, base_url: str | None = None, min_interval_ms: int = 250):
        self.session = session
        self.store = store
        self.base_url = normalize_base_url(base_url)
        self.min_interval_ms = max(0, min_interval_ms)
        self.http = requests.Session()
        self.user_agent = (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) "
            "Version/17.0 Mobile/15E148 Safari/604.1 weibo-cli/2.0"
        )
        self.last_request_at = 0.0

    def validate_session(self) -> SessionProbeResult:
        payload = self.request_json("/api/config", method="GET")
        data = payload.get("data") or {}
        login = data.get("login")
        uid = normalize_optional(data.get("uid"))
        if login is False:
            raise WeiboAuthError(
                "微博登录态已失效。请先执行 status 确认状态，再按需执行 login 或 login --force。",
                self.build_url("/api/config"),
            )
        if uid and uid != self.session.uid:
            self.session = self.session.with_updates(uid=uid)
            self._persist_session()
        return SessionProbeResult(ok=True, url=self.build_url("/api/config"), login=login, uid=uid)

    def request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        query: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: Any = None,
        auth_required: bool = True,
    ) -> dict[str, Any]:
        response = self.request(path, method=method, query=query, headers=headers, data=data, auth_required=auth_required)
        text = response.text.strip()
        if not text:
            return {}
        try:
            payload = response.json()
        except ValueError as error:
            raise WeiboApiError(f"微博接口返回了非 JSON 响应，无法解析：{error}", response.url, response.status_code, text[:400]) from error
        self.raise_for_application_auth_error(payload, response.url)
        return payload

    def request(
        self,
        path: str,
        *,
        method: str = "GET",
        query: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        data: Any = None,
        auth_required: bool = True,
    ) -> requests.Response:
        self.wait_for_rate_limit()
        url = self.build_url(path, query)
        log.debug("HTTP %s %s", method, url)
        try:
            response = self.http.request(
                method=method,
                url=url,
                headers=self.build_headers(headers, auth_required=auth_required),
                data=data,
                allow_redirects=True,
                timeout=30,
            )
        except requests.RequestException as error:
            log.warning("网络请求失败: %s %s — %s", method, url, error)
            raise WeiboNetworkError(
                f"微博接口网络请求失败：{error}",
                url,
            ) from error
        log.debug("HTTP %d %s", response.status_code, url)
        self.last_request_at = time.time()
        self._merge_response_cookies(response.cookies)

        if response.status_code in (401, 403):
            raise WeiboAuthError(
                "微博登录态无效或已失效。请先执行 status 确认状态，再按需执行 login 或 login --force。",
                response.url,
                response.status_code,
                response.text[:400],
            )
        if not response.ok:
            raise WeiboApiError(f"微博接口请求失败（HTTP {response.status_code}）。", response.url, response.status_code, response.text[:400])
        return response

    def build_headers(self, extra_headers: dict[str, str] | None, *, auth_required: bool) -> dict[str, str]:
        headers = {k.lower(): v for k, v in (extra_headers or {}).items()}
        headers.setdefault("accept", "application/json, text/plain, */*")
        headers.setdefault("user-agent", self.user_agent)
        headers.setdefault("x-requested-with", "XMLHttpRequest")
        if auth_required:
            headers.setdefault("cookie", self.session.cookie_header())
            headers.setdefault("origin", "https://m.weibo.cn")
            csrf_token = self.session.csrf_token()
            if csrf_token:
                headers.setdefault("x-xsrf-token", csrf_token)
                headers.setdefault("x-csrf-token", csrf_token)
        return headers

    def raise_for_application_auth_error(self, payload: dict[str, Any], url: str) -> None:
        if not isinstance(payload, dict):
            return
        if ((payload.get("data") or {}).get("login") is False):
            raise WeiboAuthError(
                "微博登录态已失效。请先执行 status 确认状态，再按需执行 login 或 login --force。",
                url,
                details=str(payload)[:400],
            )
        ok = payload.get("ok")
        redirect_url = str(payload.get("url") or "").strip()
        if ok == -100 or "passport.weibo.com" in redirect_url:
            raise WeiboAuthError(
                "微博登录态无效或已失效。请先执行 status 确认状态，再按需执行 login 或 login --force。",
                url,
                details=str(payload)[:400],
            )

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

    def _merge_response_cookies(self, response_cookies: requests.cookies.RequestsCookieJar) -> None:
        incoming: list[CookieRecord] = []
        for cookie in response_cookies:
            incoming.append(
                CookieRecord(
                    name=cookie.name,
                    value=cookie.value,
                    domain=cookie.domain or None,
                    path=cookie.path or "/",
                    expires=int(cookie.expires) if cookie.expires is not None else None,
                    secure=bool(cookie.secure),
                    http_only=bool(cookie._rest.get("HttpOnly")),
                )
            )
        if not incoming:
            return
        self.session = self.session.with_updates(cookies=merge_cookies(self.session.cookies, tuple(incoming)), updated_at=now_iso())
        self._persist_session()

    def _persist_session(self) -> None:
        if self.store is None or self.session.source != "local":
            return
        self.store.save(self.session)


def normalize_base_url(base_url: str | None) -> str:
    resolved = (base_url or os.environ.get("WEIBO_API_BASE_URL") or "https://m.weibo.cn").strip()
    return resolved if resolved.endswith("/") else f"{resolved}/"