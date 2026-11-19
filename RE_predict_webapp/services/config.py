"""配置与数据文件路径：全部由 settings.BASE_DIR 推导，换机器或部署时无需改代码。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from django.conf import settings

from .errors import DataUnavailableError


@dataclass(frozen=True)
class DataPaths:
    """根目录 models/ 下的数据文件与站点配置。"""

    base_dir: Path
    models_dir: Path
    boundary_geojson: Path
    climate_shp: Path
    soil_shp: Path
    rf_model_dir: Path
    station_config: Path

    @classmethod
    def from_settings(cls) -> "DataPaths":
        base_dir = Path(settings.BASE_DIR)
        models_dir = Path(getattr(settings, "MODEL_DATA_DIR", base_dir / "models"))
        return cls(
            base_dir=base_dir,
            models_dir=models_dir,
            boundary_geojson=models_dir / "Chinageo" / "china_province.geojson",
            climate_shp=models_dir / "atoshp" / "shp" / "Chinese_climate.shp",
            soil_shp=models_dir / "soilshp" / "shp" / "Soil.shp",
            rf_model_dir=models_dir / "rf_models",
            station_config=base_dir / "RE_predict_webapp" / "config.json",
        )

    def model_file(self, station_code: str) -> Path:
        return self.rf_model_dir / f"{station_code}_rf.joblib"


@dataclass(frozen=True)
class Configuration:
    """站点清单与模型输入定义，对应 RE_predict_webapp/config.json。"""

    paths: DataPaths
    stations: Mapping[str, Mapping[str, Any]]
    features: tuple[str, ...]
    variables: tuple[str, ...]

    @classmethod
    def load(cls, paths: DataPaths | None = None) -> "Configuration":
        paths = paths or DataPaths.from_settings()
        try:
            payload = json.loads(paths.station_config.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise DataUnavailableError(
                "站点配置读取失败，请检查 RE_predict_webapp/config.json。",
                detail=str(exc),
            ) from exc

        stations = payload.get("stations") or {}
        features = tuple(payload.get("features") or ())
        variables = tuple(payload.get("variables") or ())
        if not stations:
            raise DataUnavailableError("config.json 缺少 stations 站点清单。")
        if not features:
            raise DataUnavailableError("config.json 缺少 features 模型输入字段。")
        return cls(paths=paths, stations=stations, features=features, variables=variables)
