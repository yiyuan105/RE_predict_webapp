"""站点模型目录：把站点、分区标注、模型文件状态与特征说明汇总成只读结构。

站点模型页与 GET /api/stations/ 都从这里取数，站点或模型文件变化后无需改视图。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .features import FeatureInfo, describe_features
from .rf import ModelStatus, RandomForestRepository
from .stations import Station


@dataclass(frozen=True)
class StationProfile:
    """一个站点的模型信息：站点自身 + 模型文件状态 + 该站模型的输入特征。"""

    station: Station
    model: ModelStatus
    features: tuple[FeatureInfo, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.station.to_dict(),
            "model": self.model.to_dict(),
            "features": [feature.name for feature in self.features],
        }


class StationCatalog:
    """只读的站点模型目录。数据来自站点集合（shp 分区标注）与模型仓库，本身不做 I/O 之外的推导。"""

    def __init__(self, stations: Sequence[Station], models: RandomForestRepository) -> None:
        self._stations = tuple(stations)
        self._models = models

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(self._models.feature_names)

    @property
    def features(self) -> tuple[FeatureInfo, ...]:
        return describe_features(self.feature_names)

    def profiles(self) -> tuple[StationProfile, ...]:
        features = self.features
        return tuple(
            StationProfile(
                station=station,
                model=self._models.status(station.code),
                features=features,
            )
            for station in self._stations
        )

    def to_dict(self) -> dict[str, Any]:
        profiles = self.profiles()
        available = sum(1 for profile in profiles if profile.model.available)
        return {
            "count": len(profiles),
            "features": [feature.to_dict() for feature in self.features],
            "stations": [profile.to_dict() for profile in profiles],
            "summary": {
                "total": len(profiles),
                "available": available,
                "unavailable": len(profiles) - available,
            },
        }
