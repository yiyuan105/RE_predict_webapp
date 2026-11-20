"""数据来源注明：对外只做署名式说明——来源名称、类型、用途与更新方式。

这里刻意不含路径、文件名、接口地址与变量名：来源页与预测结果区的来源标注
都从这一份配置取数，新增或替换来源只改 ATTRIBUTIONS，不用动页面与接口。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence


@dataclass(frozen=True)
class DataSource:
    """一项对外注明的数据来源。"""

    key: str
    name: str
    category: str
    purpose: str
    update: str

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "name": self.name,
            "category": self.category,
            "purpose": self.purpose,
            "update": self.update,
        }


# 顺序即来源页的展示顺序
ATTRIBUTIONS: tuple[DataSource, ...] = (
    DataSource(
        key="model",
        name="站点随机森林模型",
        category="预测模型",
        purpose="各观测站点基于本站长期观测数据分别训练的随机森林模型，用于预测该站点周边区域的生态系统呼吸（Re）。",
        update="随观测数据积累由项目组重新训练后统一更新，更新后自动用于在线预测。",
    ),
    DataSource(
        key="boundary",
        name="中国陆地边界",
        category="地理边界",
        purpose="用于判断输入的经纬度是否落在中国陆地范围内，界外坐标不参与预测。",
        update="随行政区划与海岸线成果更新由项目组统一替换，替换后自动生效。",
    ),
    DataSource(
        key="climate",
        name="中国气候分区",
        category="气候分区",
        purpose="用于判断输入位置与各观测站点是否属于同一气候区，作为站点匹配的同类依据之一。",
        update="随气候分区成果更新由项目组统一替换，替换后自动生效。",
    ),
    DataSource(
        key="soil",
        name="中国土壤分区",
        category="土壤分区",
        purpose="用于判断输入位置与各观测站点是否属于同一土壤区，作为站点匹配的同类依据之一。",
        update="随土壤分区成果更新由项目组统一替换，替换后自动生效。",
    ),
    DataSource(
        key="weather",
        name="Open-Meteo 实时气象数据",
        category="气象数据",
        purpose="提供预测时所需的当日实时气象要素取值，作为模型输入的外部数据来源。",
        update="由公开气象数据服务持续更新，本站实时获取，无需人工维护。",
    ),
)


class SourceCatalog:
    """来源注明目录：只负责输出对外字段，不做路径推导，也不读内部配置。"""

    def __init__(self, sources: Sequence[DataSource] = ATTRIBUTIONS) -> None:
        self._sources = tuple(sources)

    @property
    def sources(self) -> tuple[DataSource, ...]:
        return self._sources

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self._sources),
            "sources": [source.to_dict() for source in self._sources],
        }


def build_source_catalog(sources: Sequence[DataSource] | None = None) -> SourceCatalog:
    return SourceCatalog(ATTRIBUTIONS if sources is None else sources)
