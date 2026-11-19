"""模型输入特征的定义：名称、含义、单位与对应的气象变量。

站点详情与数据来源栏目都从这里取特征说明，避免两处各写一份。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class FeatureInfo:
    """一个模型输入特征。variable 是 Open-Meteo 的变量名（别名换算见 weather.py）。"""

    name: str
    label: str
    unit: str
    variable: str
    transform: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "label": self.label,
            "unit": self.unit,
            "variable": self.variable,
            "transform": self.transform,
        }


FEATURES: dict[str, FeatureInfo] = {
    "rn": FeatureInfo(
        name="rn",
        label="净辐射",
        unit="W/m²",
        variable="shortwave_radiation",
        transform="短波辐射 × 0.6",
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


def describe_features(names: Iterable[str]) -> tuple[FeatureInfo, ...]:
    """按给定顺序生成特征说明；未登记的特征回退为占位说明，新增特征时接口不会因此报错。"""
    return tuple(
        FEATURES.get(name) or FeatureInfo(name=name, label=name, unit="", variable="")
        for name in names
    )
