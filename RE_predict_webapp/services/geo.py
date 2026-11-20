"""地理数据：中国边界 geojson、气候/土壤 shp 的读取与落区查询。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import geopandas as gpd
import pandas as pd
from pyproj import Transformer
from shapely import make_valid, prepare, union_all
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from .errors import DataUnavailableError
from .soil_codes import soil_type_name

EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Coordinate:
    """WGS84 经纬度。"""

    lat: float
    lon: float

    def to_point(self) -> Point:
        return Point(self.lon, self.lat)


def haversine_km(origin: Coordinate, target: Coordinate) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (origin.lat, origin.lon, target.lat, target.lon))
    delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
    a = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(min(1.0, a)))


class ChinaBoundary:
    """中国陆地边界：判断坐标是否落在境内（边界上的点视为境内）。"""

    def __init__(self, source: Path) -> None:
        try:
            payload = json.loads(Path(source).read_text(encoding="utf-8"))
            geometries = [shape(feature["geometry"]) for feature in payload["features"]]
        except (OSError, ValueError, KeyError) as exc:
            # 对外只说"边界数据读不到"，具体异常进 detail 供日志排查
            raise DataUnavailableError("中国陆地边界数据暂时无法加载，请稍后再试。", detail=str(exc)) from exc

        geometry = union_all(geometries) if len(geometries) > 1 else geometries[0]
        if not geometry.is_valid:
            geometry = make_valid(geometry)
        prepare(geometry)
        self._geometry = geometry

    def contains(self, coordinate: Coordinate) -> bool:
        return bool(self._geometry.covers(coordinate.to_point()))


class ZonalLayer:
    """shp 分区图层的通用查询：把 WGS84 坐标定位到图层的属性值。"""

    value_field = ""

    def __init__(self, source: Path, value_field: str | None = None) -> None:
        self._value_field = value_field or self.value_field
        frame = self._read(Path(source))
        if frame.crs is None:
            raise DataUnavailableError("分区数据缺少坐标系信息，暂时无法使用。", detail=Path(source).name)
        if self._value_field not in frame.columns:
            raise DataUnavailableError(
                "分区数据缺少必要的属性字段，暂时无法使用。",
                detail=f"{Path(source).name}: {self._value_field}",
            )

        self._geometries = list(frame.geometry)
        self._values = frame[self._value_field].tolist()
        self._tree = STRtree(self._geometries)
        self._transformer = Transformer.from_crs("EPSG:4326", frame.crs, always_xy=True)

    @staticmethod
    def _read(source: Path) -> gpd.GeoDataFrame:
        try:
            return gpd.read_file(source)
        except Exception:  # 属性表为 GBK 时回退
            try:
                return gpd.read_file(source, encoding="gbk")
            except Exception as exc:
                raise DataUnavailableError(
                    "分区数据读取失败，暂时无法使用。",
                    detail=f"{source.name}: {exc}",
                ) from exc

    def lookup(self, coordinate: Coordinate) -> str | None:
        x, y = self._transformer.transform(coordinate.lon, coordinate.lat)
        point = Point(x, y)
        for index in self._tree.query(point):
            if self._geometries[index].covers(point):
                return self._clean(self._values[index])
        return None

    @staticmethod
    def _clean(value: Any) -> str | None:
        if value is None or (not isinstance(value, str) and pd.isna(value)):
            return None
        text = str(value).strip()
        return text or None


class ClimateZones(ZonalLayer):
    """中国气候分区，属性字段 climate。"""

    value_field = "climate"


class SoilZones(ZonalLayer):
    """中国土壤分区，属性字段 SOIL_ID（编码经 soil_codes 换算成土类名称）。"""

    value_field = "SOIL_ID"

    def lookup(self, coordinate: Coordinate) -> str | None:
        raw_code = super().lookup(coordinate)
        return soil_type_name(raw_code) if raw_code else None
