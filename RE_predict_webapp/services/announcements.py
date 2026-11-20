"""公告：服务端维护、首页右侧边栏展示的对外公告条目。

每条形如 {"title": …, "body": …, "published_at": …, "active": true}，写在
RE_predict_webapp/announcements.json。新增、编辑、下架只改这个文件，
前端结构与接口字段都不用动；对外只提供只读数据，不开放访客写入。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import DataPaths
from .errors import DataUnavailableError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Announcement:
    """一条公告：published_at 原样展示，published 只用于排序。"""

    title: str
    body: str
    published_at: str
    published: datetime

    def to_dict(self) -> dict[str, str]:
        return {"title": self.title, "body": self.body, "published_at": self.published_at}


class AnnouncementCatalog:
    """只读公告集合，按发布时间倒序；坏条目跳过，整份配置读不到时给可读错误。"""

    def __init__(self, announcements: Sequence[Announcement]) -> None:
        self._items = tuple(sorted(announcements, key=lambda item: item.published, reverse=True))

    @classmethod
    def load(cls, path: Path) -> "AnnouncementCatalog":
        path = Path(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            # 还没发布过公告是正常状态，页面显示"暂无公告"即可
            logger.info("公告配置不存在，按无公告处理。")
            return cls(())
        except (OSError, ValueError) as exc:
            raise DataUnavailableError("公告内容暂时无法读取，请稍后再试。", detail=str(exc)) from exc

        entries = payload.get("announcements") if isinstance(payload, Mapping) else None
        if not isinstance(entries, list):
            raise DataUnavailableError("公告配置格式不正确，暂时无法显示公告。")

        parsed = [item for item in (cls._parse(entry, index) for index, entry in enumerate(entries)) if item]
        return cls(parsed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self._items),
            "announcements": [item.to_dict() for item in self._items],
        }

    @staticmethod
    def _parse(entry: Any, index: int) -> Announcement | None:
        if not isinstance(entry, Mapping):
            logger.warning("第 %s 条公告格式不正确，已跳过。", index + 1)
            return None
        if entry.get("active", True) is False:
            return None  # 下架公告：保留条目但不展示

        title = _text(entry.get("title"))
        body = _text(entry.get("body"))
        published_at = _text(entry.get("published_at"))
        published = _parse_time(published_at)
        if not (title and body and published):
            logger.warning("第 %s 条公告缺少标题、正文或可识别的发布时间，已跳过。", index + 1)
            return None
        return Announcement(title=title, body=body, published_at=published_at, published=published)


def build_announcement_catalog(paths: DataPaths | None = None) -> AnnouncementCatalog:
    """读取当前公告配置；路径与站点配置同源，换目录时只需改 DataPaths。"""
    paths = paths or DataPaths.from_settings()
    return AnnouncementCatalog.load(paths.announcement_config)


def _text(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) else ""


def _parse_time(text: str) -> datetime | None:
    """接受 2026-11-20 或带时区的 ISO 时间；无时区的按 UTC，保证可比较。"""
    try:
        value = datetime.fromisoformat(text)
    except ValueError:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
