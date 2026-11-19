"""站点清单：从 config.json 读取，并用分区图层标注每个站点的土壤与气候类型。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .errors import DataUnavailableError
from .geo import ClimateZones, Coordinate, SoilZones, haversine_km


@dataclass(frozen=True)
class Station:
    """一个通量观测站。"""

    code: str
    name: str
    lat: float
    lon: float
    soil_type: str | None
    climate_type: str | None
    ecosystem: str = ""
    veg_type: str = ""

    @property
    def coordinate(self) -> Coordinate:
        return Coordinate(lat=self.lat, lon=self.lon)

    def distance_km(self, coordinate: Coordinate) -> float:
        return haversine_km(coordinate, self.coordinate)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "lat": self.lat,
            "lon": self.lon,
            "soil_type": self.soil_type,
            "climate_type": self.climate_type,
            "ecosystem": self.ecosystem,
            "veg_type": self.veg_type,
        }


class StationRepository:
    """站点集合。土壤/气候类型以 shp 查询结果为准，查不到时回退到 config.json。"""

    def __init__(
        self,
        raw_stations: Mapping[str, Mapping[str, Any]],
        climate: ClimateZones | None = None,
        soil: SoilZones | None = None,
    ) -> None:
        self._stations = tuple(
            self._build(code, payload, climate, soil) for code, payload in raw_stations.items()
        )
        self._index = {station.code: station for station in self._stations}

    @property
    def stations(self) -> tuple[Station, ...]:
        return self._stations

    def get(self, code: str) -> Station | None:
        return self._index.get(code)

    @staticmethod
    def _build(
        code: str,
        payload: Mapping[str, Any],
        climate: ClimateZones | None,
        soil: SoilZones | None,
    ) -> Station:
        try:
            coordinate = Coordinate(lat=float(payload["lat"]), lon=float(payload["lon"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise DataUnavailableError(f"站点 {code} 缺少有效的经纬度。", detail=str(exc)) from exc

        return Station(
            code=code,
            name=str(payload.get("site_name") or code),
            lat=coordinate.lat,
            lon=coordinate.lon,
            soil_type=(soil.lookup(coordinate) if soil else None) or payload.get("soil_type"),
            climate_type=(climate.lookup(coordinate) if climate else None) or payload.get("climate_type"),
            ecosystem=str(payload.get("ecosystem") or ""),
            veg_type=str(payload.get("veg_type") or ""),
        )
