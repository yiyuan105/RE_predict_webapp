"""预测服务层：配置、地理数据、站点匹配、随机森林与气象数据的封装。"""

from .catalog import StationCatalog, StationProfile
from .config import Configuration, DataPaths
from .errors import (
    DataUnavailableError,
    InvalidInputError,
    ModelUnavailableError,
    OutOfChinaError,
    PredictionError,
    WeatherUnavailableError,
)
from .features import FeatureInfo, describe_features
from .predictor import PredictionResult, RePredictor, build_predictor, get_predictor, reset_predictor
from .rf import ModelStatus, RandomForestRepository
from .sources import DataSource, SourceCatalog, build_source_catalog

__all__ = [
    "Configuration",
    "DataPaths",
    "DataUnavailableError",
    "DataSource",
    "FeatureInfo",
    "InvalidInputError",
    "ModelStatus",
    "ModelUnavailableError",
    "OutOfChinaError",
    "PredictionError",
    "PredictionResult",
    "RePredictor",
    "RandomForestRepository",
    "SourceCatalog",
    "StationCatalog",
    "StationProfile",
    "WeatherUnavailableError",
    "build_predictor",
    "build_source_catalog",
    "describe_features",
    "get_predictor",
    "reset_predictor",
]
