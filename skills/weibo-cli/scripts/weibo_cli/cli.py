"""命令行入口。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .api_client import WeiboApiClient
from .browser_login import DEFAULT_LOGIN_URL, assert_browser_automation_available, run_browser_login
from .local_config import get_local_config_path
from .output import format_post_result, format_reposts, format_weibo_list
from .service import WeiboService
from .session import now_iso, persist_session
from .skill_catalog import format_skill_document, format_skill_list, format_skill_prompt_xml, format_skill_validation, load_skills


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="weibo-cli", description="面向个人账号的微博命令行工具")
    parser.add_argument("--version", action="version", version="0.1.0")
    subparsers = parser.add_subparsers(dest="command")

    login_parser = subparsers.add_parser("login", help="通过本地扫码流程登录微博并保存登录态")
    login_parser.add_argument("--cookie")
    login_parser.add_argument("--uid")
    login_parser.add_argument("--login-url", default=DEFAULT_LOGIN_URL)
    login_parser.add_argument("--browser-path")
    login_parser.add_argument("--timeout-sec", default="180")
    login_parser.add_argument("--manual", action="store_true")
    login_parser.add_argument("--check-browser", action="store_true")
    login_parser.add_argument("--from-env", action="store_true")
    login_parser.add_argument("--no-prompt", dest="prompt", action="store_false")
    login_parser.set_defaults(prompt=True, handler=handle_login)

    post_parser = subparsers.add_parser("post", help="发布一条微博")
    post_parser.add_argument("--text", required=True)
    post_parser.set_defaults(handler=handle_post)

    list_parser = subparsers.add_parser("list", help="查看当前账号最近发布的微博")
    list_parser.add_argument("--limit", default="10")
    list_parser.add_argument("--page", default="1")
    list_parser.set_defaults(handler=handle_list)

    reposts_parser = subparsers.add_parser("reposts", help="获取指定微博的转发信息")
    reposts_parser.add_argument("--weibo-id", required=True)
    reposts_parser.add_argument("--limit", default="20")
    reposts_parser.add_argument("--page", default="1")
    reposts_parser.set_defaults(handler=handle_reposts)

    skills_parser = subparsers.add_parser("skills", help="列出或查看当前仓库提供的 skills")
    skills_subparsers = skills_parser.add_subparsers(dest="skills_command")
    skills_parser.set_defaults(handler=handle_skills_list)
    show_parser = skills_subparsers.add_parser("show", help="显示某个 skill 的完整文档")
    show_parser.add_argument("name")
    show_parser.set_defaults(handler=handle_skills_show)
    prompt_parser = skills_subparsers.add_parser("prompt", help="输出可直接提供给 agent 的 <available_skills> XML")
    prompt_parser.set_defaults(handler=handle_skills_prompt)
    validate_parser = skills_subparsers.add_parser("validate", help="校验 skills 的 YAML frontmatter 与目录规范")
    validate_parser.set_defaults(handler=handle_skills_validate)

    return parser


def repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def handle_login(args: argparse.Namespace) -> int:
    timeout_ms = parse_timeout_ms(args.timeout_sec)
    cookie = (args.cookie or "").strip() or ((os.environ.get("WEIBO_COOKIE") or "").strip() if args.from_env else None)
    uid = (args.uid or "").strip() or ((os.environ.get("WEIBO_UID") or "").strip() if args.from_env else None)
    source_label = "显式提供" if cookie else "浏览器扫码"
    browser_diagnostics = ""

    if args.check_browser:
        executable_path = assert_browser_automation_available(args.browser_path)
        sys.stdout.write(f"浏览器自动化可用：{executable_path}\n")
        return 0

    if not cookie and not args.manual:
        render_browser_login_instructions(args.login_url, timeout_ms)
        try:
            browser_login = run_browser_login(login_url=args.login_url, browser_path=args.browser_path, timeout_ms=timeout_ms)
            cookie = str(browser_login["cookie"])
            uid = uid or (browser_login.get("uid") or None)
            browser_diagnostics = (
                f"最终页面：{browser_login.get('final_url') or args.login_url}\n"
                f"捕获到的 cookie 键：{', '.join(browser_login.get('cookie_keys') or [])}\n"
            )
        except Exception as error:  # noqa: BLE001
            sys.stdout.write(f"浏览器扫码登录不可用，已降级到手动模式：{error}\n\n")

    if not cookie:
        render_manual_login_instructions(args.login_url)
        if args.prompt:
            cookie = prompt_input("请输入登录成功后的完整 cookie：")
            uid = uid or prompt_input("如已知账号 UID，请输入（可直接回车跳过）：", optional=True)
        source_label = "手动录入"

    if not cookie:
        raise RuntimeError(
            f"未提供可持久化的微博 cookie。请通过浏览器扫码、--cookie、--from-env 或手动模式写入本地文件：{get_local_config_path()}"
        )

    validated = validate_session_before_persist(cookie, uid)
    uid = validated.get("uid") or uid
    path, session = persist_session(cookie, uid=uid, login_url=args.login_url)
    sys.stdout.write(f"登录态已写入 {path}\n")
    sys.stdout.write(f"来源：{source_label}\n")
    sys.stdout.write(f"UID：{session.uid or '未提供'}\n")
    sys.stdout.write(f"更新时间：{session.updated_at}\n")
    if browser_diagnostics:
        sys.stdout.write(browser_diagnostics)
    return 0


def handle_post(args: argparse.Namespace) -> int:
    result = WeiboService.create_default().post_weibo(args.text)
    sys.stdout.write(format_post_result(result))
    return 0


def handle_list(args: argparse.Namespace) -> int:
    items = WeiboService.create_default().list_own_weibos(
        limit=parse_positive_integer_option(args.limit, "--limit"),
        page=parse_positive_integer_option(args.page, "--page"),
    )
    sys.stdout.write(format_weibo_list(items))
    return 0


def handle_reposts(args: argparse.Namespace) -> int:
    items = WeiboService.create_default().get_reposts(
        weibo_id=args.weibo_id,
        limit=parse_positive_integer_option(args.limit, "--limit"),
        page=parse_positive_integer_option(args.page, "--page"),
    )
    sys.stdout.write(format_reposts(items))
    return 0


def handle_skills_list(args: argparse.Namespace) -> int:
    skills, issues = load_skills(repo_root())
    if issues:
        raise RuntimeError(format_skill_validation(issues).rstrip())
    sys.stdout.write(format_skill_list(skills))
    return 0


def handle_skills_show(args: argparse.Namespace) -> int:
    skills, issues = load_skills(repo_root())
    if issues:
        raise RuntimeError(format_skill_validation(issues).rstrip())
    for skill in skills:
        if skill.name == args.name.strip().lower():
            sys.stdout.write(format_skill_document(skill))
            return 0
    raise RuntimeError(f"未找到名为 {args.name} 的 skill。可用 skill：{', '.join(skill.name for skill in skills)}")


def handle_skills_prompt(args: argparse.Namespace) -> int:
    skills, issues = load_skills(repo_root())
    if issues:
        raise RuntimeError(format_skill_validation(issues).rstrip())
    sys.stdout.write(format_skill_prompt_xml(skills))
    return 0


def handle_skills_validate(args: argparse.Namespace) -> int:
    _, issues = load_skills(repo_root())
    output = format_skill_validation(issues)
    sys.stdout.write(output)
    return 1 if issues else 0


def parse_positive_integer_option(value: str, option_name: str) -> int:
    try:
        parsed = int(value)
    except ValueError as error:
        raise RuntimeError(f"{option_name} 必须是大于 0 的整数。") from error
    if parsed <= 0:
        raise RuntimeError(f"{option_name} 必须是大于 0 的整数。")
    return parsed


def parse_timeout_ms(raw_value: str) -> int:
    try:
        seconds = int(raw_value)
    except ValueError as error:
        raise RuntimeError("--timeout-sec 必须是大于 0 的整数。") from error
    if seconds <= 0:
        raise RuntimeError("--timeout-sec 必须是大于 0 的整数。")
    return seconds * 1000


def render_browser_login_instructions(login_url: str, timeout_ms: int) -> None:
    sys.stdout.write("即将自动打开本地浏览器，请在浏览器里完成微博扫码登录。\n")
    sys.stdout.write(f"登录页：{login_url}\n")
    sys.stdout.write(f"等待时间：{round(timeout_ms / 1000)} 秒\n\n")


def render_manual_login_instructions(login_url: str) -> None:
    sys.stdout.write("当前使用手动模式。请在浏览器中打开下面登录页，完成登录后把完整 cookie 粘贴回终端。\n")
    sys.stdout.write(f"登录页：{login_url}\n\n")
    sys.stdout.write("也可以直接重新执行：WEIBO_COOKIE='你的cookie' scripts/weibo-cli login --from-env\n\n")


def prompt_input(prompt: str, optional: bool = False) -> str | None:
    value = input(prompt).strip()
    if optional:
        return value or None
    return value or None


def validate_session_before_persist(cookie: str, uid: str | None) -> dict[str, str | None]:
    client = WeiboApiClient(
        session=type("Session", (), {"cookie": cookie, "uid": uid, "login_url": None, "updated_at": now_iso(), "source": "local"})()
    )
    try:
        result = client.validate_session()
        if result.login is False:
            raise RuntimeError("微博业务接口确认当前 cookie 未登录。")
        return {"uid": result.uid or uid}
    except Exception as error:  # noqa: BLE001
        raise RuntimeError(f"获取到的 cookie 尚未通过微博业务接口校验，请重新登录。详细原因：{error}") from error


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 0
    return int(args.handler(args) or 0)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:  # noqa: BLE001
        sys.stderr.write(f"{error}\n")
        raise SystemExit(1)