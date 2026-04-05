"""命令行入口。"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .auth import LoginResult, WeiboAuthService
from .browser_login import DEFAULT_LOGIN_URL, assert_browser_automation_available, run_browser_login
from .local_config import get_local_config_path
from .output import format_action_result, format_comment_result, format_comments, format_post_result, format_reposts, format_session_status, format_weibo_detail, format_weibo_list
from .service import WeiboService
from .session import SessionData, SessionStatus
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
    login_parser.add_argument("--browser-user-data-dir", help="浏览器持久化资料目录；默认复用 .local/browser-profile")
    login_parser.add_argument("--timeout-sec", default="180")
    login_parser.add_argument("--manual", action="store_true")
    login_parser.add_argument("--check-browser", action="store_true")
    login_parser.add_argument("--from-env", action="store_true")
    login_parser.add_argument("--prompt", action="store_true", help="仅在显式指定时进入交互式输入模式")
    login_parser.add_argument("--force", action="store_true", help="忽略当前本地登录态，强制重新执行登录流程")
    login_parser.set_defaults(prompt=False, handler=handle_login)

    status_parser = subparsers.add_parser("status", help="查看当前登录态状态")
    status_parser.set_defaults(handler=handle_status)

    post_parser = subparsers.add_parser("post", help="发布一条微博")
    post_parser.add_argument("--text", required=True)
    post_parser.set_defaults(handler=handle_post)

    show_parser = subparsers.add_parser("show", help="查看指定微博的详情")
    show_parser.add_argument("--weibo-id", required=True)
    show_parser.set_defaults(handler=handle_show)

    list_parser = subparsers.add_parser("list", help="查看当前账号最近发布的微博")
    list_parser.add_argument("--limit", default="10")
    list_parser.add_argument("--page", default="1")
    list_parser.add_argument("--only-reposts", action="store_true", help="只返回转发微博")
    list_parser.add_argument("--only-originals", action="store_true", help="只返回原创微博")
    list_parser.set_defaults(handler=handle_list)

    comments_parser = subparsers.add_parser("comments", help="查看指定微博的评论")
    comments_parser.add_argument("--weibo-id", required=True)
    comments_parser.add_argument("--limit", default="20")
    comments_parser.add_argument("--page", default="1")
    comments_parser.set_defaults(handler=handle_comments)

    comment_parser = subparsers.add_parser("comment", help="对指定微博发表评论")
    comment_parser.add_argument("--weibo-id", required=True)
    comment_parser.add_argument("--text", required=True)
    comment_parser.set_defaults(handler=handle_comment)

    like_parser = subparsers.add_parser("like", help="给指定微博点赞")
    like_parser.add_argument("--weibo-id", required=True)
    like_parser.set_defaults(handler=handle_like)

    unlike_parser = subparsers.add_parser("unlike", help="取消点赞指定微博")
    unlike_parser.add_argument("--weibo-id", required=True)
    unlike_parser.set_defaults(handler=handle_unlike)

    delete_parser = subparsers.add_parser("delete", help="删除自己发布的微博")
    delete_parser.add_argument("--weibo-id", required=True)
    delete_parser.set_defaults(handler=handle_delete)

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
    return Path(__file__).resolve().parents[2]


def handle_login(args: argparse.Namespace) -> int:
    auth = WeiboAuthService()
    timeout_ms = parse_timeout_ms(args.timeout_sec)
    cookie = (args.cookie or "").strip() or ((os.environ.get("WEIBO_COOKIE") or "").strip() if args.from_env else None)
    uid = (args.uid or "").strip() or ((os.environ.get("WEIBO_UID") or "").strip() if args.from_env else None)

    if args.check_browser:
        executable_path = assert_browser_automation_available(args.browser_path)
        sys.stdout.write(f"浏览器自动化可用：{executable_path}\n")
        return 0

    explicit_login_request = bool(cookie or args.manual or args.prompt or args.from_env)
    if not args.force and not explicit_login_request:
        current_status = auth.inspect()
        if current_status.usable:
            sys.stdout.write(format_session_status(current_status))
            sys.stdout.write("当前登录态有效，无需重复登录。若需刷新登录态，请追加 --force。\n")
            return 0

    if cookie:
        result = auth.persist_cookie_header(cookie_header=cookie, uid=uid, login_url=args.login_url, source_label="显式提供")
        sys.stdout.write(format_login_result(result))
        return 0

    if args.prompt or args.manual:
        render_manual_login_instructions(args.login_url)
        manual_cookie = prompt_input("请输入登录成功后的完整 cookie：")
        manual_uid = uid or prompt_input("如已知账号 UID，请输入（可直接回车跳过）：", optional=True)
        if not manual_cookie:
            raise RuntimeError(f"未获取到可持久化的微博 cookie。默认本地文件路径：{get_local_config_path()}")
        result = auth.persist_cookie_header(cookie_header=manual_cookie, uid=manual_uid, login_url=args.login_url, source_label="手动录入")
        sys.stdout.write(format_login_result(result))
        return 0

    render_browser_login_instructions(args.login_url, timeout_ms, args.browser_user_data_dir)
    try:
        result = auth.persist_browser_login(
            login_url=args.login_url,
            browser_path=args.browser_path,
            timeout_ms=timeout_ms,
            user_data_dir=args.browser_user_data_dir,
        )
    except Exception as error:  # noqa: BLE001
        sys.stdout.write(f"浏览器扫码登录未成功：{error}\n\n")
        raise RuntimeError(
            "未获取到可持久化的微博 cookie。"
            f"请重试浏览器扫码，或使用 --cookie / --from-env / --prompt 进入手动粘贴模式。默认本地文件路径：{get_local_config_path()}"
        ) from error
    sys.stdout.write(format_login_result(result))
    return 0


def handle_status(args: argparse.Namespace) -> int:
    sys.stdout.write(format_session_status(WeiboAuthService().inspect()))
    return 0


def _recover_session(auth: WeiboAuthService) -> WeiboService | None:
    """当登录态已配置但失效时，尝试通过环境变量或交互式扫码恢复。

    成功返回新的 WeiboService；无法恢复时向 stderr 写错误信息并返回 None。
    """
    status = auth.inspect()
    if not status.configured or status.usable:
        return None

    cookie_env = os.environ.get("WEIBO_COOKIE") or None
    if cookie_env:
        try:
            result = auth.persist_cookie_header(
                cookie_header=cookie_env,
                uid=os.environ.get("WEIBO_UID"),
                login_url=None,
                source_label="env:WEIBO_COOKIE",
            )
            sys.stdout.write(format_login_result(result))
            return WeiboService.create_default()
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"使用 WEIBO_COOKIE 恢复登录失败：{e}\n")
            return None

    if sys.stdin and sys.stdin.isatty():
        answer = prompt_input("检测到已配置登录态但已失效，是否现在打开浏览器扫码登录以继续？(Y/n): ", optional=True)
        if answer is None or answer.strip().lower() in ("y", "yes", ""):
            try:
                result = auth.persist_browser_login(
                    login_url=DEFAULT_LOGIN_URL,
                    browser_path=None,
                    timeout_ms=180000,
                    user_data_dir=None,
                )
                sys.stdout.write(format_login_result(result))
                return WeiboService.create_default()
            except Exception as e:  # noqa: BLE001
                sys.stderr.write(f"扫码登录失败：{e}\n")
                return None
        else:
            sys.stderr.write("已取消登录。请先执行 scripts/weibo-cli login 再重试。\n")
            return None

    sys.stderr.write("当前会话已过期。请执行 `scripts/weibo-cli login` 或 `scripts/weibo-cli login --force`。\n")
    return None


def handle_post(args: argparse.Namespace) -> int:
    result = WeiboService.create_default().post_weibo(args.text)
    sys.stdout.write(format_post_result(result))
    return 0


def handle_show(args: argparse.Namespace) -> int:
    result = WeiboService.create_default().show_weibo(args.weibo_id)
    sys.stdout.write(format_weibo_detail(result))
    return 0


def handle_list(args: argparse.Namespace) -> int:
    if args.only_reposts and args.only_originals:
        raise RuntimeError("--only-reposts 和 --only-originals 不能同时使用。")
    try:
        service = WeiboService.create_default()
    except RuntimeError:
        auth = WeiboAuthService()
        service = _recover_session(auth)
        if service is None:
            return 1

    items_all = service.list_own_weibos(
        limit=parse_positive_integer_option(args.limit, "--limit"),
        page=parse_positive_integer_option(args.page, "--page"),
    )

    if args.only_reposts:
        repost_items = [item for item in items_all if item.reposted_status is not None]
        if not repost_items:
            sys.stdout.write(f"未查询到转发，回退显示最近 {len(items_all)} 条微博。\n")
            sys.stdout.write(format_weibo_list(items_all))
            return 0
        service.expand_reposted_status(repost_items)
        sys.stdout.write(format_weibo_list(repost_items))
        return 0

    if args.only_originals:
        items_all = [item for item in items_all if item.reposted_status is None]

    sys.stdout.write(format_weibo_list(items_all))
    return 0


def handle_comments(args: argparse.Namespace) -> int:
    items = WeiboService.create_default().get_comments(
        weibo_id=args.weibo_id,
        limit=parse_positive_integer_option(args.limit, "--limit"),
        page=parse_positive_integer_option(args.page, "--page"),
    )
    sys.stdout.write(format_comments(items))
    return 0


def handle_comment(args: argparse.Namespace) -> int:
    result = WeiboService.create_default().create_comment(args.weibo_id, args.text)
    sys.stdout.write(format_comment_result(result))
    return 0


def handle_like(args: argparse.Namespace) -> int:
    result = WeiboService.create_default().like_weibo(args.weibo_id)
    sys.stdout.write(format_action_result(result))
    return 0


def handle_unlike(args: argparse.Namespace) -> int:
    result = WeiboService.create_default().unlike_weibo(args.weibo_id)
    sys.stdout.write(format_action_result(result))
    return 0


def handle_delete(args: argparse.Namespace) -> int:
    result = WeiboService.create_default().delete_weibo(args.weibo_id)
    sys.stdout.write(format_action_result(result))
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


def render_browser_login_instructions(login_url: str, timeout_ms: int, user_data_dir: str | None = None) -> None:
    profile_dir = resolve_profile_dir_for_display(user_data_dir)
    sys.stdout.write("即将自动打开本地浏览器，请在浏览器里完成微博扫码登录。\n")
    sys.stdout.write(f"登录页：{login_url}\n")
    sys.stdout.write(f"浏览器 profile：{profile_dir}\n")
    sys.stdout.write("启动时会先尝试复用这个 profile 中已有的微博登录态；只有复用失败时才需要扫码。\n")
    sys.stdout.write(f"等待时间：{round(timeout_ms / 1000)} 秒\n\n")


def render_manual_login_instructions(login_url: str) -> None:
    sys.stdout.write("当前使用交互式手动模式。请在浏览器中打开下面登录页，完成登录后把完整 cookie 粘贴回终端。\n")
    sys.stdout.write(f"登录页：{login_url}\n\n")
    sys.stdout.write("也可以直接重新执行：WEIBO_COOKIE='你的cookie' scripts/weibo-cli login --from-env\n\n")


def resolve_profile_dir_for_display(user_data_dir: str | None) -> str:
    from .browser_login import resolve_browser_profile_dir

    return str(resolve_browser_profile_dir(user_data_dir))


def format_login_result(result: LoginResult) -> str:
    lines = [
        f"登录态已写入 {result.persisted_path}",
        f"来源：{result.source_label}",
        f"UID：{result.session.uid or '未提供'}",
        f"更新时间：{result.session.updated_at}",
    ]
    if result.profile_dir:
        lines.append(f"浏览器 profile：{result.profile_dir}")
        if result.reused_existing_login:
            lines.append("复用结果：已复用当前 profile 中已有的微博登录态。")
        else:
            lines.append("复用结果：当前 profile 中没有可用微博登录态，本次已通过扫码获取。")
    if result.final_url:
        lines.append(f"最终页面：{result.final_url}")
    if result.cookie_names:
        lines.append(f"Cookie 摘要：{len(result.cookie_names)} 个键")
    lines.append(format_login_persistence_report(result.session).rstrip())
    return "\n".join(lines) + "\n"


def prompt_input(prompt: str, optional: bool = False) -> str | None:
    value = input(prompt).strip()
    if optional:
        return value or None
    return value or None


def format_login_persistence_report(session: SessionData) -> str:
    lines = ["登录后校验: 已通过"]
    if session.uid:
        lines.append(f"校验 UID: {session.uid}")
    cookie_count = len(session.cookies)
    if cookie_count <= 0:
        lines.append("持久化质量: 当前仅保存 cookie header，后续若微博刷新更细粒度 cookie，建议优先使用浏览器扫码登录。")
        return "\n".join(lines) + "\n"
    with_domain = sum(1 for cookie in session.cookies if cookie.domain)
    with_path = sum(1 for cookie in session.cookies if cookie.path)
    lines.append(f"持久化质量: 已保存 cookieJar {cookie_count} 条，其中带 domain 的 {with_domain} 条，带 path 的 {with_path} 条。")
    if with_domain == 0:
        lines.append("提示: 当前 cookieJar 仍缺少 domain 信息，稳定性会弱于浏览器扫码直接采集的登录态。")
    return "\n".join(lines) + "\n"


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