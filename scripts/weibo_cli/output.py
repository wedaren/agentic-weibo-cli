"""终端输出格式化。"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .models import CommentItem, FollowItem, ListWeiboItem, PostWeiboResult, RepostItem, UserProfile, WeiboActionResult
from .session import SessionStatus


def format_json_output(payload: Any) -> str:
    return json.dumps({"ok": True, "data": normalize_json_value(payload)}, ensure_ascii=False, indent=2) + "\n"


def normalize_json_value(value: Any) -> Any:
    if is_dataclass(value):
        return normalize_json_value(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize_json_value(item) for item in value]
    return value


def format_session_status(status: SessionStatus) -> str:
    lines = ["登录态状态"]
    lines.append(f"已配置: {'是' if status.configured else '否'}")
    lines.append(f"可直接使用: {'是' if status.usable else '否'}")
    if status.source:
        lines.append(f"来源: {status.source}")
    if status.uid:
        lines.append(f"UID: {status.uid}")
    if status.updated_at:
        lines.append(f"更新时间: {status.updated_at}")
    if status.message:
        lines.append(f"说明: {status.message}")
    return "\n".join(lines) + "\n"


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


def format_weibo_detail(item: ListWeiboItem) -> str:
    lines = [f"微博 ID: {item.id}"]
    if item.bid:
        lines.append(f"微博 BID: {item.bid}")
    if item.user_name or item.user_id:
        lines.append(f"作者: {item.user_name or '未知用户'}{f' ({item.user_id})' if item.user_id else ''}")
    if item.created_at:
        lines.append(f"时间: {item.created_at}")
    if item.source:
        lines.append(f"来源: {item.source}")
    lines.append(
        f"互动: 转发 {item.reposts_count or 0} | 评论 {item.comments_count or 0} | 点赞 {item.attitudes_count or 0}"
    )
    lines.extend(_format_repost_block(item))
    return "\n".join(lines) + "\n"


def format_comments(items: list[CommentItem]) -> str:
    if not items:
        return "该微博当前没有可返回的评论记录。\n"
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        lines.extend(_format_comment_item(item, index))
    return "\n".join(lines) + "\n"


def format_comment_result(item: CommentItem) -> str:
    lines = ["评论成功", f"评论 ID: {item.id}"]
    if item.user_name or item.user_id:
        lines.append(f"用户: {item.user_name or '未知用户'}{f' ({item.user_id})' if item.user_id else ''}")
    if item.created_at:
        lines.append(f"时间: {item.created_at}")
    if item.source:
        lines.append(f"来源: {item.source}")
    lines.extend(["正文:", item.text or "(空正文)"])
    return "\n".join(lines) + "\n"


def format_action_result(result: WeiboActionResult) -> str:
    lines = [result.action, f"微博 ID: {result.weibo_id}"]
    if result.url:
        lines.append(f"访问链接: {result.url}")
    if result.message:
        lines.append(f"说明: {result.message}")
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
    lines.extend(_format_repost_block(item))
    return lines


def _format_repost_block(item: ListWeiboItem) -> list[str]:
    """格式化转发区块，供 format_weibo_detail 和 _format_list_item 共用。"""
    if item.reposted_status:
        lines = ["转发内容:", item.text or "(无转发文案)"]
        header_parts = ["原微博:"]
        if item.reposted_status.user_name:
            header_parts.append(f"@{item.reposted_status.user_name}")
        if item.reposted_status.id:
            header_parts.append(f"({item.reposted_status.id})")
        lines.append(" ".join(header_parts))
        lines.append(item.reposted_status.text or "(原微博正文为空)")
        return lines
    return [item.text or "(空正文)"]


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


def _format_comment_item(item: CommentItem, index: int) -> list[str]:
    lines = [f"[{index}] {item.id}"]
    if item.user_name or item.user_id:
        lines.append(f"用户: {item.user_name or '未知用户'}{f' ({item.user_id})' if item.user_id else ''}")
    if item.created_at:
        lines.append(f"时间: {item.created_at}")
    if item.source:
        lines.append(f"来源: {item.source}")
    if item.like_count is not None:
        lines.append(f"点赞: {item.like_count}")
    lines.append(item.text or "(空正文)")
    return lines


def format_user_profile(profile: UserProfile) -> str:
    """格式化用户主页信息。"""
    lines = [f"用户: {profile.screen_name or '未知用户'} ({profile.uid})"]
    if profile.description:
        lines.append(f"简介: {profile.description}")
    if profile.location:
        lines.append(f"地区: {profile.location}")
    if profile.verified and profile.verified_reason:
        lines.append(f"认证: {profile.verified_reason}")
    elif profile.verified:
        lines.append("认证: 已认证")
    counts = []
    if profile.followers_count is not None:
        counts.append(f"粉丝 {profile.followers_count}")
    if profile.friends_count is not None:
        counts.append(f"关注 {profile.friends_count}")
    if profile.statuses_count is not None:
        counts.append(f"微博 {profile.statuses_count}")
    if counts:
        lines.append(" | ".join(counts))
    if profile.profile_url:
        lines.append(f"主页: {profile.profile_url}")
    return "\n".join(lines) + "\n"


def format_search_results(items: list[ListWeiboItem], keyword: str, *, following_only: bool = False) -> str:
    """格式化微博搜索结果，包含作者信息。"""
    if not items:
        scope = "你关注的用户中" if following_only else "全网"
        return f"未找到{scope}包含「{keyword}」的微博。\n"
    scope = "关注用户" if following_only else "全网"
    lines: list[str] = [f"搜索「{keyword}」（{scope}），共 {len(items)} 条："]
    for index, item in enumerate(items, start=1):
        lines.extend(_format_search_item(item, index))
    return "\n".join(lines) + "\n"


def _format_search_item(item: ListWeiboItem, index: int) -> list[str]:
    lines = [f"[{index}] {item.id}"]
    if item.user_name or item.user_id:
        lines.append(f"作者: {item.user_name or '未知用户'}{f' ({item.user_id})' if item.user_id else ''}")
    if item.created_at:
        lines.append(f"时间: {item.created_at}")
    lines.append(
        f"互动: 转发 {item.reposts_count or 0} | 评论 {item.comments_count or 0} | 点赞 {item.attitudes_count or 0}"
    )
    lines.extend(_format_repost_block(item))
    return lines


def format_follow_list(items: list[FollowItem], *, label: str = "列表") -> str:
    """格式化关注或粉丝列表。"""
    if not items:
        return f"未获取到{label}记录（列表可能为空，或该用户已将{label}设为仅自己可见）。\n"
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        lines.extend(_format_follow_item(item, index))
    return "\n".join(lines) + "\n"


def _format_follow_item(item: FollowItem, index: int) -> list[str]:
    lines = [f"[{index}] {item.screen_name or '未知用户'} ({item.uid})"]
    if item.description:
        lines.append(f"  简介: {item.description}")
    if item.verified and item.verified_reason:
        lines.append(f"  认证: {item.verified_reason}")
    counts = []
    if item.followers_count is not None:
        counts.append(f"粉丝 {item.followers_count}")
    if item.friends_count is not None:
        counts.append(f"关注 {item.friends_count}")
    if item.statuses_count is not None:
        counts.append(f"微博 {item.statuses_count}")
    if counts:
        lines.append(f"  {' | '.join(counts)}")
    return lines