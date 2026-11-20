"""配置与数据文件路径：全部由 settings.BASE_DIR 推导，换机器或部署时无需改代码。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from django.conf import settings

from .errors import DataUnavailableError

# 对外展示统一使用的模型类别；config.json 的 training.model_type 可覆盖
DEFAULT_MODEL_TYPE = "随机森林 / RandomForestRegressor"


@dataclass(frozen=True)
class DataPaths:
    """根目录 models/ 下的数据文件，以及应用目录里的站点与公告配置。"""

    base_dir: Path
    models_dir: Path
    boundary_geojson: Path
    climate_shp: Path
    soil_shp: Path
    rf_model_dir: Path
    station_config: Path
    announcement_config: Path

    @classmethod
    def from_settings(cls) -> "DataPaths":
        base_dir = Path(settings.BASE_DIR)
        models_dir = Path(getattr(settings, "MODEL_DATA_DIR", base_dir / "models"))
        app_dir = base_dir / "RE_predict_webapp"
        return cls(
            base_dir=base_dir,
            models_dir=models_dir,
            boundary_geojson=models_dir / "Chinageo" / "china_province.geojson",
            climate_shp=models_dir / "atoshp" / "shp" / "Chinese_climate.shp",
            soil_shp=models_dir / "soilshp" / "shp" / "Soil.shp",
            rf_model_dir=models_dir / "rf_models",
            station_config=app_dir / "config.json",
            announcement_config=app_dir / "announcements.json",
        )

    def model_file(self, station_code: str) -> Path:
        return self.rf_model_dir / f"{station_code}_rf.joblib"


@dataclass(frozen=True)
class Configuration:
    """站点清单、模型输入定义与对外展示的训练情况，对应 RE_predict_webapp/config.json。

    training 段只给对外展示用（训练/测试规模、MSE、R²、模型类别），参与预测的是
    stations / features / variables 三段。
    """

    paths: DataPaths
    stations: Mapping[str, Mapping[str, Any]]
    features: tuple[str, ...]
    variables: tuple[str, ...]
    training: Mapping[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, paths: DataPaths | None = None) -> "Configuration":
        paths = paths or DataPaths.from_settings()
        try:
            payload = json.loads(paths.station_config.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            # 对外只给可读提示，具体异常留在 detail 里由服务端日志记录
            raise DataUnavailableError("站点配置读取失败，请稍后再试。", detail=str(exc)) from exc

        stations = payload.get("stations") or {}
        features = tuple(payload.get("features") or ())
        variables = tuple(payload.get("variables") or ())
        if not stations:
            raise DataUnavailableError("站点清单缺失，暂时无法预测。")
        if not features:
            raise DataUnavailableError("模型输入定义缺失，暂时无法预测。")

        training = payload.get("training") or {}
        if not isinstance(training, Mapping):
            raise DataUnavailableError("模型训练情况配置格式不正确。")
        return cls(
            paths=paths,
            stations=stations,
            features=features,
            variables=variables,
            training=training,
        )
