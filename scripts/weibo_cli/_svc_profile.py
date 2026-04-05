"""用户主页、关注/粉丝列表 Mixin。"""

from __future__ import annotations

from .models import FollowItem, UserProfile
from .normalizers import (
    assert_api_success,
    is_no_data_message,
    normalize_follow_item,
    normalize_optional_string,
    normalize_positive_integer,
    normalize_required_text,
    normalize_user_profile,
)

_TTL_USER = 600    # 用户信息 10 分钟
_TTL_FOLLOW = 300  # 关注/粉丝列表 5 分钟


class ProfileMixin:
    """用户信息与关注/粉丝列表方法集。依赖 self.client 和 self._cache。"""

    def resolve_uid(self) -> str:
        if self.resolved_uid:  # type: ignore[attr-defined]
            return self.resolved_uid  # type: ignore[attr-defined]
        session_uid = normalize_optional_string(self.client.session.uid)  # type: ignore[attr-defined]
        if session_uid:
            self.resolved_uid = session_uid  # type: ignore[attr-defined]
            return session_uid
        probe = self.client.validate_session()  # type: ignore[attr-defined]
        if not probe.uid:
            raise RuntimeError(
                "当前登录态缺少 uid。请先执行 status 确认状态；若登录态有效但缺少 uid，可补充 WEIBO_UID，"
                "否则执行 login 或 login --force 生成带 uid 的登录态。"
            )
        self.resolved_uid = probe.uid  # type: ignore[attr-defined]
        return probe.uid

    def get_user_profile(self, uid: str) -> UserProfile:
        """查询任意用户的主页基本信息（含缓存）。"""
        normalized_uid = normalize_required_text(uid, "uid")
        cache_key = f"user_profile:{normalized_uid}"
        cached = self._cache.get(cache_key)  # type: ignore[attr-defined]
        if cached is not None:
            return UserProfile(**cached)

        response = self.client.request_json(  # type: ignore[attr-defined]
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
        self._cache.set(cache_key, {  # type: ignore[attr-defined]
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

    def get_following(self, uid: str, page: int = 1) -> list[FollowItem]:
        """获取指定用户的关注列表（含缓存）。"""
        normalized_uid = normalize_required_text(uid, "uid")
        normalized_page = normalize_positive_integer(page, "page")
        cache_key = f"following:{normalized_uid}:page{normalized_page}"
        cached = self._cache.get(cache_key)  # type: ignore[attr-defined]
        if cached is not None:
            return [FollowItem(**item) for item in cached]

        items = self._fetch_follow_list(normalized_uid, "FOLLOW", normalized_page)
        self._cache.set(cache_key, [  # type: ignore[attr-defined]
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
        """一次性拉取全量关注列表（自动翻页）。"""
        normalized_uid = normalize_required_text(uid, "uid")
        all_items: list[FollowItem] = []
        for page in range(1, max_pages + 1):
            batch = self.get_following(normalized_uid, page=page)
            all_items.extend(batch)
            if len(batch) < 20:
                break
        return all_items

    def get_followers(self, uid: str, page: int = 1) -> list[FollowItem]:
        """获取指定用户的粉丝列表（含缓存）。"""
        normalized_uid = normalize_required_text(uid, "uid")
        normalized_page = normalize_positive_integer(page, "page")
        cache_key = f"followers:{normalized_uid}:page{normalized_page}"
        cached = self._cache.get(cache_key)  # type: ignore[attr-defined]
        if cached is not None:
            return [FollowItem(**item) for item in cached]

        items = self._fetch_follow_list(normalized_uid, "FANS", normalized_page)
        self._cache.set(cache_key, [  # type: ignore[attr-defined]
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
        """一次性拉取全量粉丝列表（自动翻页）。"""
        normalized_uid = normalize_required_text(uid, "uid")
        all_items: list[FollowItem] = []
        for page in range(1, max_pages + 1):
            batch = self.get_followers(normalized_uid, page=page)
            all_items.extend(batch)
            if len(batch) < 20:
                break
        return all_items

    def _fetch_follow_list(self, uid: str, kind: str, page: int) -> list[FollowItem]:
        path = "/api/friendships/friends" if kind == "FOLLOW" else "/api/friendships/followers"
        response = self.client.request_json(  # type: ignore[attr-defined]
            path,
            method="GET",
            query={"uid": uid, "page": page, "count": 20},
            headers={"referer": f"https://m.weibo.cn/u/{uid}"},
        )
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
