"""微博业务服务层。

职责：封装对微博 API 的业务操作；不负责数据模型定义或 API 响应解析。
- 数据模型见 models.py
- API 响应解析见 normalizers.py
"""

from __future__ import annotations

import time
from urllib.parse import quote

from .api_client import WeiboApiClient
from .auth import WeiboAuthService
from .cache import DiskCache
from .local_db import DEFAULT_DB_PATH, RETENTION_DAYS, FeedDatabase
from .logger import get_logger

log = get_logger(__name__)

# 只读类操作的默认 TTL（秒）
_TTL_USER = 600       # 用户信息 10 分钟
_TTL_FOLLOW = 300     # 关注/粉丝列表 5 分钟

# 以下导入同时也充当向后兼容的公开 re-export（测试文件与 output.py 从此处导入）
from .models import (  # noqa: F401
    CommentItem,
    FollowItem,
    ListWeiboItem,
    PostWeiboResult,
    RepostItem,
    RepostedStatus,
    SyncResult,
    UserProfile,
    WeiboActionResult,
)
from .normalizers import (  # noqa: F401
    assert_api_success,
    extract_comment_payload,
    extract_status_payload,
    is_no_data_message,
    normalize_comment,
    normalize_follow_item,
    normalize_mblog,
    normalize_optional_number,
    normalize_optional_string,
    normalize_positive_integer,
    normalize_repost,
    normalize_required_text,
    normalize_user_profile,
    stringify_id,
)


class WeiboService:
    def __init__(self, client: WeiboApiClient):
        self.client = client
        self.resolved_uid: str | None = None
        self._cache = DiskCache()

    @classmethod
    def create_default(cls) -> "WeiboService":
        auth = WeiboAuthService()
        session = auth.require_valid_session()
        return cls(WeiboApiClient(session=session, store=auth.store, base_url=auth.base_url))

    def post_weibo(self, text: str) -> PostWeiboResult:
        content = normalize_required_text(text, "微博正文")
        response = self.client.request_json(
            "/api/statuses/update",
            method="POST",
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://m.weibo.cn",
                "referer": "https://m.weibo.cn/compose/",
            },
            data={"content": content},
        )
        assert_api_success(response, "发微博")
        status = (response.get("data") or {}).get("status")
        fallback_id = stringify_id((response.get("data") or {}).get("id"))
        item = normalize_mblog(status) if status else None
        weibo_id = item.id if item else fallback_id
        if not weibo_id:
            raise RuntimeError("发微博接口返回成功，但缺少微博 ID，无法确认发布结果。")
        bid = item.bid if item else normalize_optional_string((response.get("data") or {}).get("bid"))
        return PostWeiboResult(
            id=weibo_id,
            bid=bid,
            created_at=item.created_at if item else None,
            text=item.text if item else content,
            url=f"https://m.weibo.cn/status/{bid}" if bid else None,
        )

    def list_own_weibos(self, limit: int, page: int) -> list[ListWeiboItem]:
        normalized_limit = normalize_positive_integer(limit, "limit")
        normalized_page = normalize_positive_integer(page, "page")
        uid = self.resolve_uid()
        response = self.client.request_json(
            "/api/container/getIndex",
            method="GET",
            query={"type": "uid", "value": uid, "containerid": f"107603{uid}", "page": normalized_page},
            headers={"referer": f"https://m.weibo.cn/u/{uid}"},
        )
        cards = ((response.get("data") or {}).get("cards") or [])
        if response.get("ok") == 0 and not cards:
            return []
        assert_api_success(response, "读取最近微博")
        items = [normalize_mblog(card.get("mblog")) for card in cards]
        return [item for item in items if item is not None][:normalized_limit]

    def show_weibo(self, weibo_id: str) -> ListWeiboItem:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        response = self.client.request_json(
            "/api/statuses/show",
            method="GET",
            query={"id": normalized_weibo_id},
            headers={"referer": f"https://m.weibo.cn/status/{normalized_weibo_id}"},
        )
        assert_api_success(response, "读取微博详情")
        item = normalize_mblog(extract_status_payload(response))
        if item is None:
            raise RuntimeError("微博详情接口返回成功，但缺少可解析的微博内容。")
        return item

    def get_reposts(self, weibo_id: str, limit: int, page: int) -> list[RepostItem]:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        normalized_limit = normalize_positive_integer(limit, "limit")
        normalized_page = normalize_positive_integer(page, "page")
        response = self.client.request_json(
            "/api/statuses/repostTimeline",
            method="GET",
            query={"id": normalized_weibo_id, "page": normalized_page, "count": normalized_limit, "page_size": normalized_limit},
            headers={"referer": f"https://m.weibo.cn/status/{normalized_weibo_id}"},
        )
        if response.get("ok") == 0 and is_no_data_message(response.get("msg") or response.get("message")):
            return []
        assert_api_success(response, "查询微博转发")
        rows = ((response.get("data") or {}).get("data") or (response.get("data") or {}).get("list") or [])
        items = [normalize_repost(row) for row in rows[:normalized_limit]]
        return [item for item in items if item is not None]

    def get_comments(self, weibo_id: str, limit: int, page: int) -> list[CommentItem]:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        normalized_limit = normalize_positive_integer(limit, "limit")
        normalized_page = normalize_positive_integer(page, "page")
        response = self.client.request_json(
            "/api/comments/show",
            method="GET",
            query={"id": normalized_weibo_id, "page": normalized_page, "count": normalized_limit},
            headers={"referer": f"https://m.weibo.cn/status/{normalized_weibo_id}"},
        )
        if response.get("ok") == 0 and is_no_data_message(response.get("msg") or response.get("message")):
            return []
        assert_api_success(response, "读取微博评论")
        rows = ((response.get("data") or {}).get("data") or (response.get("data") or {}).get("list") or (response.get("data") or {}).get("comments") or [])
        items = [normalize_comment(row) for row in rows[:normalized_limit]]
        return [item for item in items if item is not None]

    def create_comment(self, weibo_id: str, text: str) -> CommentItem:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        normalized_text = normalize_required_text(text, "评论内容")
        response = self.client.request_json(
            "/api/comments/create",
            method="POST",
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://m.weibo.cn",
                "referer": f"https://m.weibo.cn/status/{normalized_weibo_id}",
            },
            data={"id": normalized_weibo_id, "content": normalized_text},
        )
        assert_api_success(response, "发表评论")
        item = normalize_comment(extract_comment_payload(response))
        if item is None:
            raise RuntimeError("评论接口返回成功，但缺少可解析的评论内容。")
        return item

    def like_weibo(self, weibo_id: str) -> WeiboActionResult:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        response = self.client.request_json(
            "/api/attitudes/create",
            method="POST",
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://m.weibo.cn",
                "referer": f"https://m.weibo.cn/status/{normalized_weibo_id}",
            },
            data={"id": normalized_weibo_id, "attitude": "heart"},
        )
        assert_api_success(response, "点赞微博")
        return WeiboActionResult(
            action="点赞成功",
            weibo_id=normalized_weibo_id,
            message=normalize_optional_string(response.get("msg") or response.get("message")) or "已点赞这条微博。",
            url=f"https://m.weibo.cn/status/{normalized_weibo_id}",
        )

    def unlike_weibo(self, weibo_id: str) -> WeiboActionResult:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        response = self.client.request_json(
            "/api/attitudes/destroy",
            method="POST",
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://m.weibo.cn",
                "referer": f"https://m.weibo.cn/status/{normalized_weibo_id}",
            },
            data={"id": normalized_weibo_id},
        )
        assert_api_success(response, "取消点赞")
        return WeiboActionResult(
            action="取消点赞成功",
            weibo_id=normalized_weibo_id,
            message=normalize_optional_string(response.get("msg") or response.get("message")) or "已取消点赞这条微博。",
            url=f"https://m.weibo.cn/status/{normalized_weibo_id}",
        )

    def delete_weibo(self, weibo_id: str) -> WeiboActionResult:
        normalized_weibo_id = normalize_required_text(weibo_id, "微博 ID")
        response = self.client.request_json(
            "/api/statuses/destroy",
            method="POST",
            headers={
                "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
                "x-requested-with": "XMLHttpRequest",
                "origin": "https://m.weibo.cn",
                "referer": f"https://m.weibo.cn/status/{normalized_weibo_id}",
            },
            data={"id": normalized_weibo_id},
        )
        assert_api_success(response, "删除微博")
        return WeiboActionResult(
            action="删除成功",
            weibo_id=normalized_weibo_id,
            message=normalize_optional_string(response.get("msg") or response.get("message")) or "已删除这条微博。",
            url=None,
        )

    def expand_reposted_status(self, items: list[ListWeiboItem]) -> None:
        """就地展开各条转发的原微博正文（失败时静默跳过）。

        通过 show_weibo 获取原微博完整正文和用户名，覆盖转发记录中截断的内容。
        """
        for item in items:
            repost_info = item.reposted_status
            if not repost_info or not repost_info.id:
                continue
            try:
                original = self.show_weibo(repost_info.id)
                if original.text:
                    repost_info.text = original.text
                if original.user_name:
                    repost_info.user_name = original.user_name
            except Exception:  # noqa: BLE001
                # 展开失败不应阻塞整体列表显示
                continue

    def resolve_uid(self) -> str:
        if self.resolved_uid:
            return self.resolved_uid
        session_uid = normalize_optional_string(self.client.session.uid)
        if session_uid:
            self.resolved_uid = session_uid
            return session_uid
        probe = self.client.validate_session()
        if not probe.uid:
            raise RuntimeError(
                "当前登录态缺少 uid。请先执行 status 确认状态；若登录态有效但缺少 uid，可补充 WEIBO_UID，"
                "否则执行 login 或 login --force 生成带 uid 的登录态。"
            )
        self.resolved_uid = probe.uid
        return probe.uid

    # ------------------------------------------------------------------
    # 用户信息
    # ------------------------------------------------------------------

    def get_user_profile(self, uid: str) -> UserProfile:
        """查询任意用户的主页基本信息（含缓存）。"""
        normalized_uid = normalize_required_text(uid, "uid")
        cache_key = f"user_profile:{normalized_uid}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            log.debug("用户信息缓存命中: uid=%s", normalized_uid)
            return UserProfile(**cached)

        log.info("查询用户信息: uid=%s", normalized_uid)
        response = self.client.request_json(
            "/api/container/getIndex",
            method="GET",
            query={"type": "uid", "value": normalized_uid, "containerid": f"100505{normalized_uid}"},
            headers={"referer": f"https://m.weibo.cn/u/{normalized_uid}"},
        )
        assert_api_success(response, "读取用户信息")
        user_info = (response.get("data") or {}).get("userInfo") or {}
        profile = normalize_user_profile(user_info)
        if profile is None:
            raise RuntimeError(f"用户信息接口未返回可解析的数据（uid={normalized_uid}）。")
        self._cache.set(cache_key, {
            "uid": profile.uid,
            "screen_name": profile.screen_name,
            "description": profile.description,
            "followers_count": profile.followers_count,
            "friends_count": profile.friends_count,
            "statuses_count": profile.statuses_count,
            "verified": profile.verified,
            "verified_reason": profile.verified_reason,
            "location": profile.location,
            "profile_url": profile.profile_url,
        }, ttl_sec=_TTL_USER)
        return profile

    # ------------------------------------------------------------------
    # 关注 / 粉丝列表
    # ------------------------------------------------------------------

    def get_following(self, uid: str, page: int = 1) -> list[FollowItem]:
        """获取指定用户的关注列表（含缓存）。每次返回约 20 条；使用 get_following_all 可一次拉全量。"""
        normalized_uid = normalize_required_text(uid, "uid")
        normalized_page = normalize_positive_integer(page, "page")
        cache_key = f"following:{normalized_uid}:page{normalized_page}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            log.debug("关注列表缓存命中: uid=%s page=%d", normalized_uid, normalized_page)
            return [FollowItem(**item) for item in cached]

        log.info("查询关注列表: uid=%s page=%d", normalized_uid, normalized_page)
        items = self._fetch_follow_list(normalized_uid, "FOLLOW", normalized_page)
        self._cache.set(cache_key, [
            {
                "uid": i.uid, "screen_name": i.screen_name, "description": i.description,
                "followers_count": i.followers_count, "friends_count": i.friends_count,
                "statuses_count": i.statuses_count, "verified": i.verified,
                "verified_reason": i.verified_reason,
            }
            for i in items
        ], ttl_sec=_TTL_FOLLOW)
        return items

    def get_following_all(self, uid: str, *, max_pages: int = 50) -> list[FollowItem]:
        """一次性拉取全量关注列表（自动翻页，上限 max_pages 页 × 20 条/页）。

        供 agent 直接使用，无需自行循环翻页。
        """
        normalized_uid = normalize_required_text(uid, "uid")
        all_items: list[FollowItem] = []
        for page in range(1, max_pages + 1):
            batch = self.get_following(normalized_uid, page=page)
            all_items.extend(batch)
            if len(batch) < 20:  # 不足 20 条，已到最后一页
                break
        return all_items

    def get_followers(self, uid: str, page: int = 1) -> list[FollowItem]:
        """获取指定用户的粉丝列表（含缓存）。每次返回约 20 条；使用 get_followers_all 可一次拉全量。"""
        normalized_uid = normalize_required_text(uid, "uid")
        normalized_page = normalize_positive_integer(page, "page")
        cache_key = f"followers:{normalized_uid}:page{normalized_page}"
        cached = self._cache.get(cache_key)
        if cached is not None:
            log.debug("粉丝列表缓存命中: uid=%s page=%d", normalized_uid, normalized_page)
            return [FollowItem(**item) for item in cached]

        log.info("查询粉丝列表: uid=%s page=%d", normalized_uid, normalized_page)
        items = self._fetch_follow_list(normalized_uid, "FANS", normalized_page)
        self._cache.set(cache_key, [
            {
                "uid": i.uid, "screen_name": i.screen_name, "description": i.description,
                "followers_count": i.followers_count, "friends_count": i.friends_count,
                "statuses_count": i.statuses_count, "verified": i.verified,
                "verified_reason": i.verified_reason,
            }
            for i in items
        ], ttl_sec=_TTL_FOLLOW)
        return items

    def get_followers_all(self, uid: str, *, max_pages: int = 50) -> list[FollowItem]:
        """一次性拉取全量粉丝列表（自动翻页，上限 max_pages 页 × 20 条/页）。

        供 agent 直接使用，无需自行循环翻页。
        """
        normalized_uid = normalize_required_text(uid, "uid")
        all_items: list[FollowItem] = []
        for page in range(1, max_pages + 1):
            batch = self.get_followers(normalized_uid, page=page)
            all_items.extend(batch)
            if len(batch) < 20:  # 不足 20 条，已到最后一页
                break
        return all_items

    # ------------------------------------------------------------------
    # 关注时间线 & 本地同步
    # ------------------------------------------------------------------

    def get_friends_timeline(self, page: int = 1, count: int = 20) -> list[ListWeiboItem]:
        """获取首页关注用户时间线（模拟刷首页行为）。

        每次请求约等于真实用户在 App 中下拉刷新一次，风险极低。
        API: GET /api/statuses/friends_timeline?page=N&count=20&feature=0
        响应结构: {"ok":1, "data": {"statuses": [...]}}
        """
        response = self.client.request_json(
            "/api/statuses/friends_timeline",
            method="GET",
            query={"page": page, "count": count, "feature": 0},
            headers={"referer": "https://m.weibo.cn/"},
        )
        if response.get("ok") == 0:
            if is_no_data_message(response.get("msg") or response.get("message")):
                return []
            assert_api_success(response, "获取首页时间线")
        data = response.get("data") or response
        statuses = data.get("statuses") or []
        items = [normalize_mblog(s) for s in statuses]
        return [item for item in items if item is not None]

    def sync_feed(self, db: FeedDatabase, *, pages: int = 3) -> SyncResult:
        """增量同步关注用户时间线到本地数据库。

        策略：
        - 拉取 pages 页（默认 3 页 ≈ 60 条），逐条 INSERT OR IGNORE 去重
        - 每页若返回空则提前终止
        - 同步完成后清理超期记录（保留 RETENTION_DAYS 天）
        """
        synced_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        added = 0
        skipped = 0
        pages_fetched = 0

        for page in range(1, pages + 1):
            batch = self.get_friends_timeline(page=page)
            pages_fetched += 1
            if not batch:
                break
            for item in batch:
                repost = item.reposted_status
                is_new = db.insert_post(
                    post_id=item.id,
                    bid=item.bid,
                    user_id=item.user_id,
                    user_name=item.user_name,
                    created_at=item.created_at,
                    synced_at=synced_at,
                    text=item.text,
                    repost_id=repost.id if repost else None,
                    repost_user_name=repost.user_name if repost else None,
                    repost_text=repost.text if repost else None,
                    reposts_count=item.reposts_count,
                    comments_count=item.comments_count,
                    attitudes_count=item.attitudes_count,
                )
                if is_new:
                    added += 1
                else:
                    skipped += 1

        db.commit()
        purged = db.purge_old()
        total = db.total()

        return SyncResult(
            added=added,
            skipped=skipped,
            purged=purged,
            total=total,
            pages_fetched=pages_fetched,
            db_path=str(db.path),
        )

    # ------------------------------------------------------------------
    # 搜索
    # ------------------------------------------------------------------

    def search_weibo(
        self, keyword: str, *, following_only: bool = False, limit: int = 20, page: int = 1
    ) -> list[ListWeiboItem]:
        """按关键词搜索微博。

        following_only=True 时，自动翻页（最多 5 页）并过滤出关注用户发布的结果。
        following_only=False 时，返回指定 page 的搜索结果（不过滤）。
        """
        normalized_keyword = normalize_required_text(keyword, "搜索关键词")
        normalized_limit = normalize_positive_integer(limit, "limit")

        if following_only:
            items: list[ListWeiboItem] = []
            for p in range(1, 6):  # 最多翻 5 页来凑结果
                batch_raw, has_more = self._fetch_search_page(normalized_keyword, page=p)
                for raw in batch_raw:
                    if (raw.get("user") or {}).get("following"):
                        item = normalize_mblog(raw)
                        if item:
                            items.append(item)
                if len(items) >= normalized_limit or not has_more:
                    break
            return items[:normalized_limit]
        else:
            normalized_page = normalize_positive_integer(page, "page")
            batch_raw, _ = self._fetch_search_page(normalized_keyword, page=normalized_page)
            items = []
            for raw in batch_raw:
                item = normalize_mblog(raw)
                if item:
                    items.append(item)
            return items[:normalized_limit]

    def _fetch_search_page(self, keyword: str, page: int) -> tuple[list[dict], bool]:
        """拉取搜索结果的一页，返回 (raw_mblogs_list, has_more)。"""
        containerid = f"100103type=1&q={quote(keyword)}&t=0"
        response = self.client.request_json(
            "/api/container/getIndex",
            method="GET",
            query={"containerid": containerid, "page_type": "searchall", "page": page},
            headers={"referer": f"https://m.weibo.cn/search?containerid={quote(containerid)}"},
        )
        if response.get("ok") == 0:
            if is_no_data_message(response.get("msg") or response.get("message")):
                return [], False
            assert_api_success(response, "搜索微博")
        cards = (response.get("data") or {}).get("cards") or []
        mblogs: list[dict] = []
        for card in cards:
            if card.get("card_type") != 9:
                continue
            raw = card.get("mblog")
            if raw:
                mblogs.append(raw)
        return mblogs, bool(cards)

    def _fetch_follow_list(self, uid: str, kind: str, page: int) -> list[FollowItem]:
        """公共内部方法，拉取关注(FOLLOW)或粉丝(FANS)列表。

        使用微博 friendship API：
          - FOLLOW (关注): GET /api/friendships/friends?uid={uid}&page={page}&count=20
          - FANS   (粉丝): GET /api/friendships/followers?uid={uid}&page={page}&count=20
        响应结构: {"users": [...], ...} 或 {"data": {"users": [...]}, ...}
        """
        path = "/api/friendships/friends" if kind == "FOLLOW" else "/api/friendships/followers"
        response = self.client.request_json(
            path,
            method="GET",
            query={"uid": uid, "page": page, "count": 20},
            headers={"referer": f"https://m.weibo.cn/u/{uid}"},
        )
        # 响应可能是顶层 users 数组，也可能包裹在 data 下
        users_raw: list[dict] = (
            response.get("users")
            or (response.get("data") or {}).get("users")
            or []
        )
        if not users_raw and response.get("ok") == 0:
            if is_no_data_message(response.get("msg") or response.get("message")):
                return []
            assert_api_success(response, f"读取{'关注' if kind == 'FOLLOW' else '粉丝'}列表")
        users: list[FollowItem] = []
        for user_raw in users_raw:
            item = normalize_follow_item(user_raw)
            if item:
                users.append(item)
        return users