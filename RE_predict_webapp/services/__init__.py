"""预测服务层：配置、地理数据、站点匹配、随机森林与气象数据的封装，以及对外只读目录。"""

from .announcements import Announcement, AnnouncementCatalog, build_announcement_catalog
from .catalog import SiteCatalog, build_site_catalog
from .config import Configuration, DataPaths
from .errors import (
    DataUnavailableError,
    InvalidInputError,
    ModelUnavailableError,
    OutOfChinaError,
    PredictionError,
    WeatherUnavailableError,
)
from .predictor import PredictionResult, RePredictor, build_predictor, get_predictor, reset_predictor
from .rf import RandomForestRepository
from .sources import DataSource, SourceCatalog, build_source_catalog
from .training import TrainingCatalog, TrainingRecord, build_training_catalog

__all__ = [
    "Announcement",
    "AnnouncementCatalog",
    "Configuration",
    "DataPaths",
    "DataUnavailableError",
    "DataSource",
    "InvalidInputError",
    "ModelUnavailableError",
    "OutOfChinaError",
    "PredictionError",
    "PredictionResult",
    "RePredictor",
    "RandomForestRepository",
    "SiteCatalog",
    "SourceCatalog",
    "TrainingCatalog",
    "TrainingRecord",
    "WeatherUnavailableError",
    "build_announcement_catalog",
    "build_predictor",
    "build_site_catalog",
    "build_source_catalog",
    "build_training_catalog",
    "get_predictor",
    "reset_predictor",
]
