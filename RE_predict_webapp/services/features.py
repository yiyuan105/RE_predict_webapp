"""模型输入特征：内部定义，不对访客展示。

每个特征对应一个 Open-Meteo 变量，个别特征需要按固定比例换算；weather.py 从这里取
"特征 → 气象变量 / 换算"的映射，改特征时只改这一处，避免两处口径漂移。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


def _net_radiation(shortwave: float) -> float:
    """净辐射按短波辐射的固定比例折算（沿用建模时的换算口径）。"""
    return shortwave * 0.6


@dataclass(frozen=True)
class FeatureInfo:
    """一个模型输入特征：含义、单位、对应的气象变量与可选换算。"""

    name: str
    label: str
    unit: str
    variable: str
    transform: Callable[[float], float] | None = None
    note: str = ""


FEATURES: Mapping[str, FeatureInfo] = {
    "rn": FeatureInfo(
        name="rn",
        label="净辐射",
        unit="W/m²",
        variable="shortwave_radiation",
        transform=_net_radiation,
        note="短波辐射 × 0.6",
    ),
    "ts1": FeatureInfo(name="ts1", label="气温", unit="°C", variable="temperature_2m"),
    "rh": FeatureInfo(name="rh", label="相对湿度", unit="%", variable="relative_humidity_2m"),
    "pa": FeatureInfo(name="pa", label="气压", unit="hPa", variable="surface_pressure"),
    "soil_moisture_0_to_7cm": FeatureInfo(
        name="soil_moisture_0_to_7cm",
        label="0–7 cm 土壤水分",
        unit="m³/m³",
        variable="soil_moisture_0_to_7cm",
    ),
    "soil_moisture_7_to_28cm": FeatureInfo(
        name="soil_moisture_7_to_28cm",
        label="7–28 cm 土壤水分",
        unit="m³/m³",
        variable="soil_moisture_7_to_28cm",
    ),
}

# 供气象层直接使用的两张映射，均由 FEATURES 派生，不单独维护
FEATURE_VARIABLES: Mapping[str, str] = {name: feature.variable for name, feature in FEATURES.items()}

FEATURE_TRANSFORMS: Mapping[str, Callable[[float], float]] = {
    name: feature.transform
    for name, feature in FEATURES.items()
    if feature.transform is not None
}
