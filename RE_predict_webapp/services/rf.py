"""随机森林模型：按站点懒加载，并用 LRU 缓存控制内存占用。"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import pandas as pd

from .errors import ModelUnavailableError, PredictionError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelStatus:
    """模型文件的状态。只做存在性与可读性检查，真正能否加载要等预测时懒加载才知道。"""

    filename: str
    status: str
    size_bytes: int = 0
    message: str = ""

    @property
    def available(self) -> bool:
        return self.status == "ok"

    def to_dict(self) -> dict[str, Any]:
        return {
            "filename": self.filename,
            "status": self.status,
            "available": self.available,
            "size_bytes": self.size_bytes,
            "size_kb": round(self.size_bytes / 1024, 1) if self.size_bytes else 0,
            "message": self.message,
        }


class RandomForestRepository:
    """站点编码 → 模型文件 models/rf_models/<code>_rf.joblib。"""

    def __init__(self, model_dir: Path, feature_names: Sequence[str], cache_size: int = 4) -> None:
        if not feature_names:
            raise ValueError("feature_names 不能为空")
        self._model_dir = Path(model_dir)
        self._feature_names = tuple(feature_names)
        self._cache_size = max(1, int(cache_size))
        self._cache: "OrderedDict[str, Any]" = OrderedDict()
        self._lock = threading.Lock()

    @property
    def feature_names(self) -> tuple[str, ...]:
        return self._feature_names

    def status(self, station_code: str) -> ModelStatus:
        """模型文件是否就绪，供站点模型页展示；不加载模型，避免一次读入上百 MB。"""
        path = self._path(station_code)
        try:
            size = path.stat().st_size
        except FileNotFoundError:
            return ModelStatus(filename=path.name, status="missing", message="模型文件不存在")
        except OSError as exc:
            return ModelStatus(filename=path.name, status="unreadable", message=f"模型文件无法读取：{exc}")
        if size == 0:
            return ModelStatus(filename=path.name, status="empty", message="模型文件为空")
        return ModelStatus(filename=path.name, status="ok", size_bytes=size, message="模型文件就绪")

    def predict(self, station_code: str, features: Sequence[float]) -> float:
        model = self._load(station_code)
        if len(features) != len(self._feature_names):
            raise PredictionError(f"模型输入维度不匹配：需要 {len(self._feature_names)} 个特征。")

        frame = pd.DataFrame([list(features)], columns=list(self._feature_names))
        try:
            value = float(np.ravel(model.predict(frame))[0])
        except Exception as exc:
            raise PredictionError("模型预测出错，请检查输入数据与模型是否匹配。", detail=str(exc)) from exc

        if not np.isfinite(value):
            raise PredictionError(f"模型返回了无效数值（{value}）。")
        return value

    def _load(self, station_code: str) -> Any:
        with self._lock:
            cached = self._cache.get(station_code)
            if cached is not None:
                self._cache.move_to_end(station_code)
                return cached

            path = self._path(station_code)
            if not path.exists():
                raise ModelUnavailableError(f"站点 {station_code} 的模型文件不存在：{path.name}")
            try:
                model = joblib.load(path)
            except Exception as exc:
                raise ModelUnavailableError(f"站点 {station_code} 的模型加载失败。", detail=str(exc)) from exc

            self._cache[station_code] = model
            self._cache.move_to_end(station_code)
            while len(self._cache) > self._cache_size:
                dropped, _ = self._cache.popitem(last=False)
                logger.debug("模型缓存淘汰：%s", dropped)
            return model

    def _path(self, station_code: str) -> Path:
        return self._model_dir / f"{station_code}_rf.joblib"
