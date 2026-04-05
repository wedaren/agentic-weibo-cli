"""关注时间线同步与搜索 Mixin。"""

from __future__ import annotations

import time
from urllib.parse import quote

from .local_db import RETENTION_DAYS, FeedDatabase
from .models import ListWeiboItem, SyncResult
from .normalizers import (
    assert_api_success,
    is_no_data_message,
    normalize_mblog,
    normalize_positive_integer,
    normalize_required_text,
)


class FeedMixin:
    """时间线同步与关键词搜索方法集。依赖 self.client。"""

    def get_friends_timeline(self, page: int = 1, count: int = 20) -> list[ListWeiboItem]:
        """获取首页关注用户时间线。"""
        response = self.client.request_json(  # type: ignore[attr-defined]
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

    def sync_feed(self, db: FeedDatabase, *, pages: int = 5) -> SyncResult:
        """增量同步关注用户时间线到本地数据库。"""
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

    def search_weibo(
        self, keyword: str, *, following_only: bool = False, limit: int = 20, page: int = 1
    ) -> list[ListWeiboItem]:
        """按关键词搜索微博。following_only=True 时自动翻页最多 5 页并过滤关注用户。"""
        normalized_keyword = normalize_required_text(keyword, "搜索关键词")
        normalized_limit = normalize_positive_integer(limit, "limit")

        if following_only:
            items: list[ListWeiboItem] = []
            for p in range(1, 6):
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
        containerid = f"100103type=1&q={quote(keyword)}&t=0"
        response = self.client.request_json(  # type: ignore[attr-defined]
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
