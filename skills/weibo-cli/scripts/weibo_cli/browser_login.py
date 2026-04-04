"""浏览器扫码登录。"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from .api_client import WeiboApiClient
from .session import now_iso

DEFAULT_LOGIN_URL = "https://passport.weibo.com/sso/signin?entry=wapsso&source=wapssowb&url=https%3A%2F%2Fweibo.com"
AUTH_COOKIE_KEYS = ("SUB", "SUBP", "SCF")
BUSINESS_ORIGINS = ("https://weibo.com", "https://m.weibo.cn")
DOMAIN_PRIORITY = ("m.weibo.cn", ".m.weibo.cn", "weibo.com", ".weibo.com", "passport.weibo.com", ".passport.weibo.com")


def find_browser_executable(browser_path: str | None = None) -> str:
    candidates = [
        (browser_path or "").strip() or None,
        os.environ.get("WEIBO_CHROME_PATH", "").strip() or None,
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    raise RuntimeError("未找到可用的 Chrome/Chromium 浏览器。请安装 Google Chrome，或通过 --browser-path / WEIBO_CHROME_PATH 指定浏览器路径。")


def assert_browser_automation_available(browser_path: str | None = None) -> str:
    from playwright.sync_api import sync_playwright

    executable_path = find_browser_executable(browser_path)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=executable_path, headless=True)
        browser.close()
    return executable_path


def run_browser_login(login_url: str | None = None, browser_path: str | None = None, timeout_ms: int = 180000) -> dict[str, object]:
    from playwright.sync_api import sync_playwright

    executable_path = find_browser_executable(browser_path)
    resolved_login_url = (login_url or "").strip() or DEFAULT_LOGIN_URL
    poll_interval_ms = 2000
    profile_dir = tempfile.mkdtemp(prefix="weibo-cli-login-")

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(profile_dir, executable_path=executable_path, headless=False, viewport=None)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(resolved_login_url, wait_until="domcontentloaded")
            deadline = time.time() + timeout_ms / 1000
            while time.time() < deadline:
                current_url = page.url
                on_business_domain = any(current_url.startswith(origin) for origin in BUSINESS_ORIGINS)
                if on_business_domain:
                    hydrate_business_cookies(page)
                extracted = extract_cookie_header(context)
                if extracted:
                    refreshed = extract_cookie_header(context) or extracted
                    probe = probe_uid(refreshed["cookie"])
                    if on_business_domain and (probe.get("uid") or probe.get("login") is not False):
                        return {
                            "cookie": refreshed["cookie"],
                            "uid": probe.get("uid"),
                            "login_url": resolved_login_url,
                            "final_url": page.url,
                            "cookie_keys": refreshed["cookie_keys"],
                            "updated_at": now_iso(),
                        }
                page.wait_for_timeout(poll_interval_ms)
        finally:
            context.close()
    raise RuntimeError(f"等待扫码登录超时（{round(timeout_ms / 1000)} 秒）。请确认你已在浏览器中完成微博登录。")


def hydrate_business_cookies(page: object) -> None:
    for target_url in BUSINESS_ORIGINS:
        page.goto(target_url, wait_until="domcontentloaded", timeout=15000)


def extract_cookie_header(context: object) -> dict[str, object] | None:
    cookies = context.cookies(["https://m.weibo.cn", "https://weibo.com", "https://passport.weibo.com"])
    relevant = [cookie for cookie in cookies if "weibo" in cookie.get("domain", "")]
    deduped = dedupe_cookies(relevant)
    entries = [f"{cookie['name']}={cookie['value']}" for cookie in deduped]
    if not any(any(entry.startswith(f"{key}=") for entry in entries) for key in AUTH_COOKIE_KEYS):
        return None
    return {"cookie": "; ".join(entries), "cookie_keys": sorted(entry.split("=", 1)[0] for entry in entries)}


def dedupe_cookies(cookies: list[dict[str, object]]) -> list[dict[str, object]]:
    selected: dict[str, dict[str, object]] = {}
    for cookie in cookies:
        current = selected.get(str(cookie["name"]))
        if current is None or compare_cookie_priority(cookie, current) > 0:
            selected[str(cookie["name"])] = cookie
    return sorted(selected.values(), key=lambda item: str(item["name"]))


def compare_cookie_priority(candidate: dict[str, object], current: dict[str, object]) -> int:
    domain_score = score_domain(str(candidate.get("domain", ""))) - score_domain(str(current.get("domain", "")))
    if domain_score:
        return domain_score
    path_score = len(str(candidate.get("path", ""))) - len(str(current.get("path", "")))
    if path_score:
        return path_score
    return int(candidate.get("expires", 0)) - int(current.get("expires", 0))


def score_domain(domain: str) -> int:
    try:
        index = DOMAIN_PRIORITY.index(domain)
    except ValueError:
        return 0
    return len(DOMAIN_PRIORITY) - index


def probe_uid(cookie: str) -> dict[str, object]:
    client = WeiboApiClient(
        session=type("Session", (), {"cookie": cookie, "uid": None, "login_url": None, "updated_at": now_iso(), "source": "local"})()
    )
    result = client.validate_session()
    return {"uid": result.uid, "login": result.login}