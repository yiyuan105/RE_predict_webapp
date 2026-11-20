"""随机森林模型：按站点懒加载，并用 LRU 缓存控制内存占用。

模型文件的存在性不对外展示：缺文件时只返回可读的 MODEL_UNAVAILABLE，具体路径留在服务端日志。
"""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Sequence

import joblib
import numpy as np
import pandas as pd

from .errors import ModelUnavailableError, PredictionError

logger = logging.getLogger(__name__)


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

    def predict(self, station_code: str, features: Sequence[float]) -> float:
        model = self._load(station_code)
        if len(features) != len(self._feature_names):
            raise PredictionError("模型输入维度不匹配，请检查输入数据。")

        frame = pd.DataFrame([list(features)], columns=list(self._feature_names))
        try:
            value = float(np.ravel(model.predict(frame))[0])
        except Exception as exc:
            raise PredictionError("模型预测出错，请稍后再试。", detail=str(exc)) from exc

        if not np.isfinite(value):
            raise PredictionError("模型返回了无效数值，请稍后再试。")
        return value

    def _load(self, station_code: str) -> Any:
        with self._lock:
            cached = self._cache.get(station_code)
            if cached is not None:
                self._cache.move_to_end(station_code)
                return cached

            path = self._path(station_code)
            if not path.exists():
                logger.warning("站点 %s 的模型文件不存在：%s", station_code, path)
                raise ModelUnavailableError(f"站点 {station_code} 的模型暂不可用，请稍后再试。")
            try:
                model = joblib.load(path)
            except Exception as exc:
                logger.warning("站点 %s 的模型加载失败：%s", station_code, exc)
                raise ModelUnavailableError(f"站点 {station_code} 的模型暂不可用，请稍后再试。") from exc

            self._cache[station_code] = model
            self._cache.move_to_end(station_code)
            while len(self._cache) > self._cache_size:
                dropped, _ = self._cache.popitem(last=False)
                logger.debug("模型缓存淘汰：%s", dropped)
            return model

    def _path(self, station_code: str) -> Path:
        return self._model_dir / f"{station_code}_rf.joblib"
