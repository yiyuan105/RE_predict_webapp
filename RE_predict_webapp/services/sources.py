"""数据来源：六类来源的名称、类型、位置、用途与更新方式集中定义。

数据来源页、GET /api/sources/ 与预测结果区的来源标注都从这里取，
替换数据文件或气象接口后只需改这一处。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from django.conf import settings

from .config import Configuration, DataPaths
from .features import FeatureInfo, describe_features
from .soil_codes import SOIL_CLASS_NAMES

DEFAULT_WEATHER_ENDPOINT = "https://api.open-meteo.com/v1/forecast"


@dataclass(frozen=True)
class DataSource:
    """一项数据来源。location 只能是相对 BASE_DIR 的路径或外部地址，不含盘符。"""

    key: str
    name: str
    category: str
    location: str
    short: str
    purpose: str
    update: str
    detail: str = ""
    doc_ref: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "key": self.key,
            "name": self.name,
            "category": self.category,
            "location": self.location,
            "short": self.short,
            "purpose": self.purpose,
            "update": self.update,
            "detail": self.detail,
            "doc_ref": self.doc_ref,
        }


class SourceCatalog:
    """数据来源目录：路径、数量与气象默认值全部从 Configuration / settings 推导。"""

    def __init__(self, configuration: Configuration) -> None:
        self._configuration = configuration

    @property
    def features(self) -> tuple[FeatureInfo, ...]:
        return describe_features(self._configuration.features)

    @property
    def weather_endpoint(self) -> str:
        return getattr(settings, "WEATHER_ENDPOINT", "") or DEFAULT_WEATHER_ENDPOINT

    @property
    def weather_model(self) -> str:
        return (getattr(settings, "WEATHER_MODEL", "") or "").strip()

    @property
    def weather_label(self) -> str:
        return f"Open-Meteo {self.weather_model or 'best_match'}"

    def sources(self) -> tuple[DataSource, ...]:
        paths = self._configuration.paths
        return (
            self._model_source(paths),
            self._boundary_source(paths),
            self._climate_source(paths),
            self._soil_source(paths),
            self._weather_source(),
            self._config_source(paths),
        )

    def to_dict(self) -> dict[str, Any]:
        sources = self.sources()
        return {
            "count": len(sources),
            "sources": [source.to_dict() for source in sources],
            "shorts": {source.key: source.short for source in sources},
            "features": [feature.to_dict() for feature in self.features],
            "weather": {
                "label": self.weather_label,
                "endpoint": self.weather_endpoint,
                "model": self.weather_model or "best_match",
                "variables": list(self._configuration.variables),
            },
        }

    def _model_source(self, paths: DataPaths) -> DataSource:
        directory = _display(paths.rf_model_dir, paths.base_dir)
        station_count = len(self._configuration.stations)
        return DataSource(
            key="model",
            name="站点随机森林模型",
            category="模型",
            location=f"{directory}/<站点编码>_rf.joblib",
            short="rf_models/<站点编码>_rf.joblib",
            purpose="按匹配到的站点调用对应随机森林模型预测生态系统呼吸 Re，输入为 config.json 中 features 的 6 个气象特征。",
            update="覆盖同名 joblib 文件后重启服务；新增站点需同时补模型文件与 config.json 条目。",
            detail=f"当前 {station_count} 个站点各一个模型，单个约 15–32 MB；按需懒加载并做 LRU 缓存。",
            doc_ref="3.1 / 3.2",
        )

    def _boundary_source(self, paths: DataPaths) -> DataSource:
        location = _display(paths.boundary_geojson, paths.base_dir)
        return DataSource(
            key="boundary",
            name="中国陆地边界",
            category="地理",
            location=location,
            short=paths.boundary_geojson.name,
            purpose="判断输入经纬度是否落在中国陆地范围内；界外坐标直接返回提示，不做匹配、不取气象、不预测。",
            update="替换为新的 FeatureCollection（WGS84 经纬度、面要素）即可，自相交会自动 make_valid 修复。",
            detail="省级边界在首次加载时合并为一个整体参与 covers 判断，之后复用。",
            doc_ref="3.3",
        )

    def _climate_source(self, paths: DataPaths) -> DataSource:
        location = _display(paths.climate_shp, paths.base_dir)
        return DataSource(
            key="climate",
            name="中国气候分区",
            category="分区",
            location=f"{location}（字段 climate）",
            short=f"{paths.climate_shp.name}（气候分区）",
            purpose="把输入点与站点落到气候分区上，作为“同类气候”的判定依据，决定第 1、2 级匹配。",
            update="连同 .dbf、.prj 一起替换同名 shp；字段名在 services/geo.py::ClimateZones.value_field 修改。",
            detail="缺少 .prj 会直接返回 DATA_UNAVAILABLE，因为无法判断坐标含义。",
            doc_ref="3.4",
        )

    def _soil_source(self, paths: DataPaths) -> DataSource:
        location = _display(paths.soil_shp, paths.base_dir)
        return DataSource(
            key="soil",
            name="中国土壤分区",
            category="分区",
            location=f"{location}（字段 SOIL_ID）",
            short=f"{paths.soil_shp.name}（土壤分区）",
            purpose="把输入点与站点落到土壤分区上，作为“同类土壤”的判定依据，决定第 1、3 级匹配。",
            update="连同 .dbf、.prj 一起替换同名 shp；SOIL_ID 编码与土类名称的对应关系在 services/soil_codes.py。",
            detail=f"当前收录 {len(SOIL_CLASS_NAMES)} 个土类编码，未登记的编码显示为“未收录土类(编号)”。",
            doc_ref="3.4 / 3.5",
        )

    def _weather_source(self) -> DataSource:
        forecast_days = getattr(settings, "WEATHER_FORECAST_DAYS", 1)
        timeout = getattr(settings, "WEATHER_TIMEOUT_SECONDS", 20)
        return DataSource(
            key="weather",
            name="Open-Meteo 实时气象特征",
            category="气象",
            location=self.weather_endpoint,
            short=self.weather_label,
            purpose="提供模型所需的 6 个气象特征（当日 24 小时均值），其中净辐射由短波辐射折算。",
            update="无需维护文件；换源改环境变量 WEATHER_ENDPOINT / WEATHER_MODEL，注意 GFS 不提供土壤湿度。",
            detail=f"请求模型 {self.weather_model or 'best_match'}，预报 {forecast_days} 天、超时 {timeout:g} 秒，返回当日 24 小时均值。",
            doc_ref="4.2",
        )

    def _config_source(self, paths: DataPaths) -> DataSource:
        configuration = self._configuration
        return DataSource(
            key="config",
            name="站点配置与特征顺序",
            category="配置",
            location=_display(paths.station_config, paths.base_dir),
            short="config.json",
            purpose="声明站点清单（编码、名称、经纬度、生态/植被类型、分区兜底值）、模型输入特征顺序与气象变量清单。",
            update="直接编辑 config.json；新增站点会自动出现在站点模型页与匹配候选中。",
            detail=f"当前 {len(configuration.stations)} 个站点、{len(configuration.features)} 个模型特征、{len(configuration.variables)} 个气象变量。",
            doc_ref="3.1",
        )


def build_source_catalog(configuration: Configuration | None = None) -> SourceCatalog:
    """按当前配置生成来源目录（config.json 很小，按需读取即可）。"""
    return SourceCatalog(configuration or Configuration.load())


def _display(path: Path, base: Path) -> str:
    """路径统一显示为相对 BASE_DIR 的形式，换机器或部署目录后文档无需改动。"""
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()
