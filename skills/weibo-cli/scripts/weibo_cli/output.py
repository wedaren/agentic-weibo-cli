"""终端输出格式化。"""

from __future__ import annotations

from .service import ListWeiboItem, PostWeiboResult, RepostItem


def format_post_result(result: PostWeiboResult) -> str:
    lines = ["发布成功", f"微博 ID: {result.id}"]
    if result.bid:
        lines.append(f"微博 BID: {result.bid}")
    if result.created_at:
        lines.append(f"发布时间: {result.created_at}")
    if result.url:
        lines.append(f"访问链接: {result.url}")
    lines.extend(["正文:", result.text])
    return "\n".join(lines) + "\n"


def format_weibo_list(items: list[ListWeiboItem]) -> str:
    if not items:
        return "未查询到微博记录。\n"
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        lines.extend(_format_list_item(item, index))
    return "\n".join(lines) + "\n"


def format_reposts(items: list[RepostItem]) -> str:
    if not items:
        return "该微博当前没有可返回的转发记录。\n"
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        lines.extend(_format_repost_item(item, index))
    return "\n".join(lines) + "\n"


def _format_list_item(item: ListWeiboItem, index: int) -> list[str]:
    lines = [f"[{index}] {item.id}"]
    if item.created_at:
        lines.append(f"时间: {item.created_at}")
    if item.source:
        lines.append(f"来源: {item.source}")
    lines.append(
        f"互动: 转发 {item.reposts_count or 0} | 评论 {item.comments_count or 0} | 点赞 {item.attitudes_count or 0}"
    )
    if item.reposted_status:
        lines.append("转发内容:")
        lines.append(item.text or "(无转发文案)")
        header_parts = ["原微博:"]
        if item.reposted_status.user_name:
            header_parts.append(f"@{item.reposted_status.user_name}")
        if item.reposted_status.id:
            header_parts.append(f"({item.reposted_status.id})")
        lines.append(" ".join(header_parts))
        lines.append(item.reposted_status.text or "(原微博正文为空)")
    else:
        lines.append(item.text or "(空正文)")
    return lines


def _format_repost_item(item: RepostItem, index: int) -> list[str]:
    lines = [f"[{index}] {item.id}"]
    if item.user_name or item.user_id:
        lines.append(f"用户: {item.user_name or '未知用户'}{f' ({item.user_id})' if item.user_id else ''}")
    if item.created_at:
        lines.append(f"时间: {item.created_at}")
    if item.source:
        lines.append(f"来源: {item.source}")
    lines.append(item.text or "(空正文)")
    return lines