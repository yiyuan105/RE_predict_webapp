"""站点匹配：按"土壤 + 气候 → 气候 → 土壤 → 空间最近"逐级降级，并给出置信度。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .errors import PredictionError
from .geo import Coordinate
from .stations import Station

CONFIDENCE_LABELS = {"high": "高", "medium": "中", "low": "低"}


@dataclass(frozen=True)
class MatchTier:
    """一级匹配策略。same_soil / same_climate 表示该级要求分区类型相同。"""

    code: str
    label: str
    confidence: str
    note: str
    same_soil: bool = False
    same_climate: bool = False
    match_any: bool = False

    def accepts(self, station: Station, soil_type: str | None, climate_type: str | None) -> bool:
        if self.match_any:
            return True
        if self.same_soil and not _same(soil_type, station.soil_type):
            return False
        if self.same_climate and not _same(climate_type, station.climate_type):
            return False
        return True


def _same(left: str | None, right: str | None) -> bool:
    return left is not None and right is not None and left == right


# 调整匹配顺序或增减层级，只改这个元组即可。
MATCH_TIERS: tuple[MatchTier, ...] = (
    MatchTier(
        code="soil_climate",
        label="同类土壤 + 同类气候",
        confidence="high",
        note="土壤类型与气候分区均与站点一致",
        same_soil=True,
        same_climate=True,
    ),
    MatchTier(
        code="climate",
        label="同类气候",
        confidence="medium",
        note="仅气候分区一致，土壤类型不同",
        same_climate=True,
    ),
    MatchTier(
        code="soil",
        label="同类土壤",
        confidence="medium",
        note="仅土壤类型一致，气候分区未匹配",
        same_soil=True,
    ),
    MatchTier(
        code="nearest",
        label="空间最近站点",
        confidence="low",
        note="未匹配到同类土壤或气候，按空间最近站点预测",
        match_any=True,
    ),
)


@dataclass(frozen=True)
class Confidence:
    code: str
    label: str
    note: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "label": self.label, "note": self.note}


@dataclass(frozen=True)
class MatchResult:
    """匹配结果：命中的站点、所用的层级、距离与输入点的分区。"""

    station: Station
    tier: MatchTier
    order: int
    distance_km: float
    input_soil_type: str | None
    input_climate_type: str | None

    @property
    def same_soil(self) -> bool:
        return _same(self.input_soil_type, self.station.soil_type)

    @property
    def same_climate(self) -> bool:
        return _same(self.input_climate_type, self.station.climate_type)

    @property
    def confidence(self) -> Confidence:
        return Confidence(
            code=self.tier.confidence,
            label=CONFIDENCE_LABELS[self.tier.confidence],
            note=self.tier.note,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "tier": self.order,
            "code": self.tier.code,
            "label": self.tier.label,
            "distance_km": round(self.distance_km, 2),
            "same_soil": self.same_soil,
            "same_climate": self.same_climate,
            "input_soil_type": self.input_soil_type,
            "input_climate_type": self.input_climate_type,
        }


class StationMatcher:
    """逐级尝试匹配策略，命中后在该级候选站点中取最近的一个。"""

    def __init__(self, tiers: Sequence[MatchTier] = MATCH_TIERS) -> None:
        if not tiers:
            raise ValueError("匹配策略不能为空")
        self._tiers = tuple(tiers)

    @property
    def tiers(self) -> tuple[MatchTier, ...]:
        return self._tiers

    def match(
        self,
        coordinate: Coordinate,
        stations: Sequence[Station],
        soil_type: str | None,
        climate_type: str | None,
    ) -> MatchResult:
        if not stations:
            raise PredictionError("站点清单为空，无法匹配站点。")

        for order, tier in enumerate(self._tiers, start=1):
            candidates = [item for item in stations if tier.accepts(item, soil_type, climate_type)]
            if not candidates:
                continue
            station = min(candidates, key=lambda item: item.distance_km(coordinate))
            return MatchResult(
                station=station,
                tier=tier,
                order=order,
                distance_km=station.distance_km(coordinate),
                input_soil_type=soil_type,
                input_climate_type=climate_type,
            )

        raise PredictionError("没有可用的匹配策略，请检查 MATCH_TIERS 配置。")
