"""气象数据：调用 Open-Meteo 预报接口，取当日均值并折算成随机森林的输入特征。"""

from __future__ import annotations

import logging
import math
import warnings
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import openmeteo_requests
import pandas as pd

from .errors import WeatherUnavailableError
from .geo import Coordinate

logger = logging.getLogger(__name__)

DEFAULT_ENDPOINT = "https://api.open-meteo.com/v1/forecast"

# config.json 里的变量名与 Open-Meteo 字段名不一致时的别名
API_VARIABLE_ALIASES = {"surface_pressure_2m": "surface_pressure"}

# 模型特征 -> 所需气象变量
FEATURE_VARIABLES: Mapping[str, str] = {
    "rn": "shortwave_radiation",
    "ts1": "temperature_2m",
    "rh": "relative_humidity_2m",
    "pa": "surface_pressure",
    "soil_moisture_0_to_7cm": "soil_moisture_0_to_7cm",
    "soil_moisture_7_to_28cm": "soil_moisture_7_to_28cm",
}

# 净辐射由短波辐射按固定比例折算
FEATURE_TRANSFORMS: Mapping[str, Callable[[float], float]] = {"rn": lambda value: value * 0.6}


@dataclass(frozen=True)
class WeatherSample:
    """一次预测所用的气象输入。"""

    features: tuple[float, ...]
    values: Mapping[str, float]
    source: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "features": {name: round(value, 4) for name, value in self.values.items()},
        }


class OpenMeteoWeatherProvider:
    """按坐标获取当日气象均值；兼容单模型与集合预报的变量排布。"""

    def __init__(
        self,
        features: Sequence[str],
        variables: Sequence[str],
        *,
        endpoint: str = DEFAULT_ENDPOINT,
        model: str = "",
        timeout: float = 20.0,
        forecast_days: int = 1,
        client_factory: Callable[[], Any] = openmeteo_requests.Client,
    ) -> None:
        if not features:
            raise ValueError("features 不能为空")
        if not variables:
            raise ValueError("variables 不能为空")

        unknown = [name for name in features if name not in FEATURE_VARIABLES]
        if unknown:
            raise ValueError(f"未知的模型输入特征：{', '.join(unknown)}")

        self._features = tuple(features)
        self._variables = tuple(variables)
        self._api_variables = tuple(API_VARIABLE_ALIASES.get(name, name) for name in variables)
        missing = [
            FEATURE_VARIABLES[name]
            for name in features
            if FEATURE_VARIABLES[name] not in self._api_variables
        ]
        if missing:
            raise ValueError(f"variables 未包含模型所需的变量：{', '.join(sorted(set(missing)))}")

        self._endpoint = endpoint
        self._model = model
        self._timeout = float(timeout)
        self._forecast_days = int(forecast_days)
        self._client_factory = client_factory
        self._source = f"Open-Meteo {model or 'best_match'}"

    @property
    def source(self) -> str:
        return self._source

    def fetch(self, coordinate: Coordinate) -> WeatherSample:
        response = self._request(coordinate)
        means = self._daily_means(response)

        values: dict[str, float] = {}
        for name in self._features:
            source_variable = FEATURE_VARIABLES[name]
            try:
                value = float(means[source_variable])
            except KeyError as exc:
                raise WeatherUnavailableError(f"气象数据缺少变量 {source_variable}。", detail=str(exc)) from exc
            transform = FEATURE_TRANSFORMS.get(name)
            values[name] = float(transform(value)) if transform else value

        features = tuple(values[name] for name in self._features)
        if not all(math.isfinite(value) for value in features):
            raise WeatherUnavailableError("气象数据缺失（可能该气象源不提供土壤湿度），请换个气象模型或稍后再试。")

        return WeatherSample(features=features, values=values, source=self._source)

    def _request(self, coordinate: Coordinate) -> Any:
        payload: dict[str, Any] = {
            "latitude": coordinate.lat,
            "longitude": coordinate.lon,
            "hourly": list(self._api_variables),
            "forecast_days": self._forecast_days,
            "timezone": "Asia/Shanghai",
        }
        if self._model:
            payload["models"] = self._model

        try:
            client = self._client_factory()
            return client.weather_api(self._endpoint, params=payload, timeout=self._timeout)[0]
        except Exception as exc:
            logger.warning("Open-Meteo 请求失败：%s", exc)
            raise WeatherUnavailableError(detail=str(exc)) from exc

    def _daily_means(self, response: Any) -> pd.Series:
        hourly = response.Hourly()
        variable_count = len(self._api_variables)
        total = hourly.VariablesLength()
        if total < variable_count or total % variable_count:
            raise WeatherUnavailableError(f"气象接口返回的变量数量异常（{total}）。")

        members = total // variable_count
        frame = pd.DataFrame(
            {
                "time": pd.date_range(
                    start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                    end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                    freq=pd.Timedelta(seconds=hourly.Interval()),
                    inclusive="left",
                )
            }
        )
        for index, variable in enumerate(self._api_variables):
            block = np.vstack(
                [hourly.Variables(index * members + member).ValuesAsNumpy() for member in range(members)]
            )
            if members > 1:
                with warnings.catch_warnings():  # 某些成员可能整段缺测
                    warnings.simplefilter("ignore", RuntimeWarning)
                    frame[variable] = np.nanmean(block, axis=0)
            else:
                frame[variable] = block[0]

        return frame.drop(columns="time").mean(numeric_only=True)
