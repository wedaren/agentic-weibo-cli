"""鉴权编排。"""

from __future__ import annotations

from dataclasses import dataclass

from .api_client import WeiboApiClient, WeiboAuthError
from .browser_login import BrowserLoginResult, run_browser_login
from .session import SessionData, SessionStatus, SessionStore, now_iso, parse_cookie_header


@dataclass(slots=True)
class LoginResult:
    session: SessionData
    persisted_path: str
    source_label: str
    reused_existing_login: bool
    profile_dir: str | None
    final_url: str | None
    cookie_names: tuple[str, ...]


class WeiboAuthService:
    def __init__(self, store: SessionStore | None = None, base_url: str | None = None):
        self.store = store or SessionStore()
        self.base_url = base_url

    def inspect(self) -> SessionStatus:
        session = self.store.load()
        if session is None:
            return SessionStatus(
                configured=False,
                usable=False,
                source=None,
                uid=None,
                updated_at=None,
                message=f"未检测到本地登录态。默认路径：{self.store.session_path}",
                session=None,
            )

        try:
            session.assert_auth_cookies()
        except RuntimeError as error:
            return SessionStatus(
                configured=True,
                usable=False,
                source=session.source,
                uid=session.uid,
                updated_at=session.updated_at,
                message=str(error),
                session=session,
            )

        client = WeiboApiClient(session=session, store=self.store, base_url=self.base_url)
        try:
            probe = client.validate_session()
        except WeiboAuthError:
            return SessionStatus(
                configured=True,
                usable=False,
                source=session.source,
                uid=session.uid,
                updated_at=session.updated_at,
                message="检测到已配置登录态，但当前已失效。请按需执行 login；如果你明确要刷新现有登录态，再使用 login --force。",
                session=session,
            )

        validated_session = client.session.with_updates(uid=probe.uid or client.session.uid)
        return SessionStatus(
            configured=True,
            usable=True,
            source=validated_session.source,
            uid=validated_session.uid,
            updated_at=validated_session.updated_at,
            message="当前登录态有效，可以直接执行 list、reposts、post 等命令。",
            session=validated_session,
        )

    def require_valid_session(self) -> SessionData:
        status = self.inspect()
        if not status.usable or status.session is None:
            raise RuntimeError(status.message)
        return status.session

    def persist_browser_login(
        self,
        *,
        login_url: str,
        browser_path: str | None,
        timeout_ms: int,
        user_data_dir: str | None,
    ) -> LoginResult:
        browser_result = run_browser_login(
            login_url=login_url,
            browser_path=browser_path,
            timeout_ms=timeout_ms,
            user_data_dir=user_data_dir,
        )
        session = SessionData(
            uid=browser_result.uid,
            login_url=browser_result.login_url,
            updated_at=now_iso(),
            source="local",
            cookies=browser_result.cookies,
        )
        return self._persist_validated_session(
            session=session,
            source_label="浏览器扫码",
            reused_existing_login=browser_result.reused_existing_login,
            profile_dir=browser_result.profile_dir,
            final_url=browser_result.final_url,
            cookie_names=browser_result.cookie_names,
        )

    def persist_cookie_header(self, *, cookie_header: str, uid: str | None, login_url: str | None, source_label: str) -> LoginResult:
        session = SessionData(
            uid=uid,
            login_url=login_url,
            updated_at=now_iso(),
            source="local",
            cookies=parse_cookie_header(cookie_header),
        )
        return self._persist_validated_session(
            session=session,
            source_label=source_label,
            reused_existing_login=False,
            profile_dir=None,
            final_url=None,
            cookie_names=session.cookie_names(),
        )

    def _persist_validated_session(
        self,
        *,
        session: SessionData,
        source_label: str,
        reused_existing_login: bool,
        profile_dir: str | None,
        final_url: str | None,
        cookie_names: tuple[str, ...],
    ) -> LoginResult:
        client = WeiboApiClient(session=session, store=self.store, base_url=self.base_url)
        probe = client.validate_session()
        validated_session = client.session.with_updates(uid=probe.uid or client.session.uid, updated_at=now_iso(), source="local")
        persisted_path = str(self.store.save(validated_session))
        return LoginResult(
            session=validated_session,
            persisted_path=persisted_path,
            source_label=source_label,
            reused_existing_login=reused_existing_login,
            profile_dir=profile_dir,
            final_url=final_url,
            cookie_names=cookie_names,
        )