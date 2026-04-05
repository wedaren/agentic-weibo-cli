"""终端输出格式化。"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from .models import CommentItem, FollowItem, ListWeiboItem, PostWeiboResult, RepostItem, SyncResult, UserProfile, WeiboActionResult
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


def format_follow_list(items: list[FollowItem], *, label: str = "列表", has_more: bool = False, total: int | None = None) -> str:
    """格式化关注或粉丝列表。

    has_more=True 时末尾追加翻页提示；total 非 None 时显示合计条数（全量拉取时使用）。
    """
    if not items:
        return f"未获取到{label}记录（列表可能为空，或该用户已将{label}设为仅自己可见）。\n"
    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        lines.extend(_format_follow_item(item, index))
    if total is not None:
        lines.append(f"\n共 {total} 条{label}记录（全量）。")
    elif has_more:
        lines.append(f"\n当前显示 {len(items)} 条，可能还有更多。使用 --all-pages 一次性拉取全量，或追加 --page N 翻页。")
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


def format_sync_result(result: SyncResult) -> str:
    """格式化增量同步结果。"""
    lines = [
        "同步完成",
        f"新增: {result.added} 条",
        f"跳过（已存在）: {result.skipped} 条",
        f"过期清理: {result.purged} 条",
        f"数据库总计: {result.total} 条",
        f"请求页数: {result.pages_fetched}",
        f"数据库路径: {result.db_path}",
    ]
    return "\n".join(lines) + "\n"


def format_local_stats(stats: dict[str, Any]) -> str:
    """格式化本地数据库统计信息。"""
    lines = [
        "本地 feed 数据库统计",
        f"总条数: {stats.get('total', 0)}",
        f"覆盖用户数: {stats.get('user_count', 0)}",
    ]
    if stats.get("oldest_synced_at"):
        lines.append(f"最早同步: {stats['oldest_synced_at']}")
    if stats.get("newest_synced_at"):
        lines.append(f"最新同步: {stats['newest_synced_at']}")
    lines.append(f"保留天数: {stats.get('retention_days', 7)} 天")
    lines.append(f"数据库路径: {stats.get('db_path', '未知')}")
    return "\n".join(lines) + "\n"


def format_local_posts(rows: list[dict[str, Any]], *, keyword: str | None = None) -> str:
    """格式化本地数据库查询结果（含 synced_at）。"""
    if not rows:
        scope = f"「{keyword}」" if keyword else ""
        return f"本地数据库中未找到{scope}相关微博。\n"
    header = f"搜索「{keyword}」，共 {len(rows)} 条：" if keyword else f"共 {len(rows)} 条："
    lines = [header]
    for i, row in enumerate(rows, 1):
        lines.append(f"[{i}] {row['id']}")
        uid = row.get("user_id")
        name = row.get("user_name")
        if name or uid:
            lines.append(f"作者: {name or '未知用户'}{f' ({uid})' if uid else ''}")
        if row.get("created_at"):
            lines.append(f"时间: {row['created_at']}")
        if row.get("synced_at"):
            lines.append(f"同步: {row['synced_at']}")
        counts = (
            f"转发 {row.get('reposts_count') or 0} | "
            f"评论 {row.get('comments_count') or 0} | "
            f"点赞 {row.get('attitudes_count') or 0}"
        )
        lines.append(f"互动: {counts}")
        if row.get("repost_id"):
            lines.append(f"转发内容: {row.get('text') or '(无转发文案)'}")
            parts = ["原微博:"]
            if row.get("repost_user_name"):
                parts.append(f"@{row['repost_user_name']}")
            if row.get("repost_id"):
                parts.append(f"({row['repost_id']})")
            lines.append(" ".join(parts))
            lines.append(row.get("repost_text") or "(原微博正文为空)")
        else:
            lines.append(row.get("text") or "(空正文)")
    return "\n".join(lines) + "\n"


def format_schedule_status(status: "Any") -> str:
    """格式化定时 sync 策略状态（含上次执行结果）。"""
    lines = ["定时同步策略"]
    if not status.configured:
        lines.append("状态: 未配置")
        lines.append("操作: 执行 `schedule set` 启用每日自动同步")
    else:
        lines.append(f"状态: {'已启用' if status.loaded else '已配置但未加载'}")
        if status.hour is not None and status.minute is not None:
            lines.append(f"触发时间: 每天 {status.hour:02d}:{status.minute:02d}")
        if status.pages is not None:
            lines.append(f"同步页数: {status.pages} 页（约 {status.pages * 20} 条）")
        lines.append(f"日志路径: {status.log_path}")
        if not status.loaded:
            lines.append("操作: 执行 `schedule set` 重新加载，或 `schedule off` 清除配置")
    # 上次执行结果（无论是否配置定时，只要有状态文件就显示）
    if status.last_run_at:
        lines.append("─────────────────")
        lines.append(f"上次执行: {status.last_run_at}")
        if status.last_run_success is True:
            added = status.last_run_added
            lines.append(f"结果: 成功{f'，新增 {added} 条' if added is not None else ''}")
        elif status.last_run_success is False:
            err = status.last_run_error or "未知错误"
            lines.append(f"结果: 失败 — {err}")
    return "\n".join(lines) + "\n"