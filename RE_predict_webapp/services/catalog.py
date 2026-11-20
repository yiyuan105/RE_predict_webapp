"""对外只读目录的装配入口。

训练情况、来源注明与公告各自在 training.py / sources.py / announcements.py 里定义
（三者都是一处数据源），这里只负责装配：视图、测试都从 SiteCatalog 取数，
将来新增对外栏目时也只加一个属性，不必改视图里的取数方式。
"""

from __future__ import annotations

from functools import cached_property

from .announcements import AnnouncementCatalog, build_announcement_catalog
from .config import Configuration, DataPaths
from .sources import SourceCatalog, build_source_catalog
from .training import TrainingCatalog, build_training_catalog


class SiteCatalog:
    """按需构建三个对外目录；没被访问的目录不会读盘。"""

    def __init__(self, configuration: Configuration | None = None) -> None:
        self._configuration = configuration

    @cached_property
    def configuration(self) -> Configuration:
        return self._configuration or Configuration.load()

    @cached_property
    def training(self) -> TrainingCatalog:
        return build_training_catalog(self.configuration)

    @cached_property
    def sources(self) -> SourceCatalog:
        return build_source_catalog()

    @cached_property
    def announcements(self) -> AnnouncementCatalog:
        # 公告只依赖路径，不必为了它把站点配置也读一遍
        paths = self._configuration.paths if self._configuration else DataPaths.from_settings()
        return build_announcement_catalog(paths)


def build_site_catalog(configuration: Configuration | None = None) -> SiteCatalog:
    return SiteCatalog(configuration)
