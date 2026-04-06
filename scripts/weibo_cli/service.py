"""微博业务服务层。

WeiboService 由四个领域 Mixin 组合而成：
  - ReadMixin    (_svc_read.py)   只读查询：列表、详情、转发、评论
  - WriteMixin   (_svc_write.py)  写操作：发微博、评论、点赞、删除
  - ProfileMixin (_svc_profile.py) 用户主页、关注/粉丝列表
  - FeedMixin    (_svc_feed.py)   关注时间线同步、关键词搜索

对外 API 保持不变：调用方仍通过 WeiboService.create_default() 获取实例。
模型类与 normalizer 函数在此处继续 re-export，保持向后兼容。
"""

from __future__ import annotations

from ._svc_feed import FeedMixin
from ._svc_profile import ProfileMixin
from ._svc_read import ReadMixin
from ._svc_write import WriteMixin
from .api_client import WeiboApiClient
from .auth import WeiboAuthService
from .cache import DiskCache
from .local_db import DEFAULT_DB_PATH, RETENTION_DAYS, FeedDatabase  # noqa: F401

# 向后兼容 re-export：其他模块（output.py、tests、cli.py）从此处导入
from .models import (  # noqa: F401
    CommentItem,
    FollowItem,
    ListWeiboItem,
    PerUserSyncResult,
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


class WeiboService(ReadMixin, WriteMixin, ProfileMixin, FeedMixin):
    """微博业务服务。通过 create_default() 获取已鉴权的实例。"""

    def __init__(self, client: WeiboApiClient):
        self.client = client
        self.resolved_uid: str | None = None
        self._cache = DiskCache()

    @classmethod
    def create_default(cls) -> "WeiboService":
        auth = WeiboAuthService()
        session = auth.require_valid_session()
        return cls(WeiboApiClient(session=session, store=auth.store, base_url=auth.base_url))
