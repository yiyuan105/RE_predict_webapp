"""预测编排：中国陆地判断 → 站点匹配 → 气象数据 → 随机森林预测。"""

from __future__ import annotations

import logging
import math
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from django.conf import settings

from .catalog import StationCatalog
from .config import Configuration
from .errors import InvalidInputError, OutOfChinaError
from .geo import ChinaBoundary, ClimateZones, Coordinate, SoilZones
from .matching import MatchResult, StationMatcher
from .rf import RandomForestRepository
from .stations import StationRepository
from .weather import OpenMeteoWeatherProvider, WeatherSample

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PredictionResult:
    """一次完整预测的产出。"""

    coordinate: Coordinate
    prediction: float
    match: MatchResult
    weather: WeatherSample
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "prediction": round(self.prediction, 4),
            "confidence": self.match.confidence.to_dict(),
            "station": self.match.station.to_dict(),
            "matching": self.match.to_dict(),
            "weather": self.weather.to_dict(),
        }


class RePredictor:
    """把各服务组装成一次预测，本身不关心 HTTP 与展示。"""

    def __init__(
        self,
        boundary: ChinaBoundary,
        climate: ClimateZones,
        soil: SoilZones,
        stations: StationRepository,
        matcher: StationMatcher,
        models: RandomForestRepository,
        weather: OpenMeteoWeatherProvider,
    ) -> None:
        self._boundary = boundary
        self._climate = climate
        self._soil = soil
        self._stations = stations
        self._matcher = matcher
        self._models = models
        self._weather = weather
        self._catalog: StationCatalog | None = None

    @property
    def station_catalog(self) -> StationCatalog:
        """站点模型目录，与预测共用同一批站点/模型实例，保证两处口径与内存开销一致。"""
        if self._catalog is None:
            self._catalog = StationCatalog(self._stations.stations, self._models)
        return self._catalog

    def predict(self, lat: Any, lon: Any) -> PredictionResult:
        coordinate = self._validate(lat, lon)
        if not self._boundary.contains(coordinate):
            raise OutOfChinaError()

        soil_type = self._soil.lookup(coordinate)
        climate_type = self._climate.lookup(coordinate)
        match = self._matcher.match(
            coordinate, self._stations.stations, soil_type, climate_type
        )
        weather = self._weather.fetch(coordinate)
        value = self._models.predict(match.station.code, weather.features)

        logger.info(
            "预测完成：(%s, %s) -> 站点 %s（第 %s 级 %s，%s）",
            coordinate.lat,
            coordinate.lon,
            match.station.code,
            match.order,
            match.tier.label,
            match.confidence.label,
        )
        return PredictionResult(
            coordinate=coordinate,
            prediction=value,
            match=match,
            weather=weather,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    @staticmethod
    def _validate(lat: Any, lon: Any) -> Coordinate:
        try:
            lat_value = float(lat)
            lon_value = float(lon)
        except (TypeError, ValueError) as exc:
            raise InvalidInputError("经纬度必须是数字，例如 lat=39.90&lon=116.40。") from exc

        if not (math.isfinite(lat_value) and math.isfinite(lon_value)):
            raise InvalidInputError("经纬度必须是有效数字。")
        if not -90 <= lat_value <= 90:
            raise InvalidInputError("纬度需在 -90 ~ 90 之间。")
        if not -180 <= lon_value <= 180:
            raise InvalidInputError("经度需在 -180 ~ 180 之间。")
        return Coordinate(lat=lat_value, lon=lon_value)


def build_predictor(configuration: Configuration | None = None) -> RePredictor:
    """按当前配置装配一个预测器（每次调用都会重新读取数据）。"""
    configuration = configuration or Configuration.load()
    paths = configuration.paths

    climate = ClimateZones(paths.climate_shp)
    soil = SoilZones(paths.soil_shp)
    return RePredictor(
        boundary=ChinaBoundary(paths.boundary_geojson),
        climate=climate,
        soil=soil,
        stations=StationRepository(configuration.stations, climate=climate, soil=soil),
        matcher=StationMatcher(),
        models=RandomForestRepository(
            paths.rf_model_dir,
            configuration.features,
            cache_size=getattr(settings, "RF_MODEL_CACHE_SIZE", 4),
        ),
        weather=OpenMeteoWeatherProvider(
            configuration.features,
            configuration.variables,
            endpoint=getattr(settings, "WEATHER_ENDPOINT", None) or "https://api.open-meteo.com/v1/forecast",
            model=getattr(settings, "WEATHER_MODEL", "") or "",
            timeout=getattr(settings, "WEATHER_TIMEOUT_SECONDS", 20.0),
            forecast_days=getattr(settings, "WEATHER_FORECAST_DAYS", 1),
        ),
    )


_predictor: RePredictor | None = None
_predictor_lock = threading.Lock()


def get_predictor() -> RePredictor:
    """懒加载单例：第一次预测时才读取地理数据，避免拖慢启动与运维命令。"""
    global _predictor
    if _predictor is None:
        with _predictor_lock:
            if _predictor is None:
                _predictor = build_predictor()
    return _predictor


def reset_predictor() -> None:
    """清空单例，用于测试或热更新数据后重新加载。"""
    global _predictor
    with _predictor_lock:
        _predictor = None
