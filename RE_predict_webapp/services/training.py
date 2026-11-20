"""模型训练情况：对外只展示每个站点的训练/测试规模、MSE、R² 与模型类别。

这是"对外可见层"的取数入口：它刻意不接触模型文件、输入特征或内部变量，
页面上能看到的字段就是 TrainingRecord 声明的这 8 个，接口与页面都从这里取。
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .config import DEFAULT_MODEL_TYPE, Configuration
from .errors import DataUnavailableError

logger = logging.getLogger(__name__)

# 展示精度：MSE 与 R² 的小数位数，config.json 的 training.display 可覆盖。
# 默认取 4 位，与训练结果表给出的数据位数一致，页面上看到的数值可直接对照。
DEFAULT_DISPLAY: Mapping[str, int] = {"mse_digits": 4, "r2_digits": 4}

# toFixed 的位数上限取小一点，配置写错时不至于让前端抛异常
_DIGITS_RANGE = (0, 6)

_REQUIRED_FIELDS = ("train_size", "test_size", "train_mse", "train_r2", "test_mse", "test_r2")


@dataclass(frozen=True)
class TrainingRecord:
    """一个站点的训练结果概况，字段即对外字段。"""

    code: str
    model_type: str
    train_size: int
    test_size: int
    train_mse: float
    train_r2: float
    test_mse: float
    test_r2: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "train_size": self.train_size,
            "test_size": self.test_size,
            "train_mse": self.train_mse,
            "train_r2": self.train_r2,
            "test_mse": self.test_mse,
            "test_r2": self.test_r2,
            "model_type": self.model_type,
        }

    @classmethod
    def from_mapping(cls, code: str, payload: Any, model_type: str) -> "TrainingRecord":
        if not isinstance(payload, Mapping):
            raise DataUnavailableError(f"站点 {code} 的训练情况格式不正确。")
        return cls(
            code=code,
            model_type=model_type,
            train_size=_sample_size(code, payload, "train_size"),
            test_size=_sample_size(code, payload, "test_size"),
            train_mse=_metric(code, payload, "train_mse"),
            train_r2=_metric(code, payload, "train_r2"),
            test_mse=_metric(code, payload, "test_mse"),
            test_r2=_metric(code, payload, "test_r2"),
        )


class TrainingCatalog:
    """只读的训练情况目录：顺序、字段与展示精度都由配置决定，不做额外推导。"""

    def __init__(
        self,
        records: Sequence[TrainingRecord],
        display: Mapping[str, int] | None = None,
    ) -> None:
        self._records = tuple(records)
        self._display = _display_rules(display)

    @classmethod
    def from_configuration(cls, configuration: Configuration) -> "TrainingCatalog":
        raw = configuration.training or {}
        model_type = str(raw.get("model_type") or DEFAULT_MODEL_TYPE)
        display = raw.get("display") or {}
        records = raw.get("records") or {}
        if not isinstance(records, Mapping):
            raise DataUnavailableError("模型训练情况配置格式不正确。")

        known = set(configuration.stations)
        parsed: list[TrainingRecord] = []
        for code, payload in records.items():
            if code not in known:
                # 站点清单里没有的编码不展示，避免页面上出现系统并不支持的站点
                logger.warning("训练情况里的站点 %s 不在站点清单中，已跳过。", code)
                continue
            parsed.append(TrainingRecord.from_mapping(code, payload, model_type))

        missing = known - {record.code for record in parsed}
        if missing:
            logger.warning("以下站点缺少训练情况：%s", "、".join(sorted(missing)))
        return cls(parsed, display if isinstance(display, Mapping) else None)

    @property
    def records(self) -> tuple[TrainingRecord, ...]:
        return self._records

    def to_dict(self) -> dict[str, Any]:
        return {
            "count": len(self._records),
            "display": dict(self._display),
            "stations": [record.to_dict() for record in self._records],
        }


def build_training_catalog(configuration: Configuration | None = None) -> TrainingCatalog:
    """按当前配置生成训练情况目录（config.json 很小，按需读取即可）。"""
    return TrainingCatalog.from_configuration(configuration or Configuration.load())


def _sample_size(code: str, payload: Mapping[str, Any], key: str) -> int:
    value = _number(code, payload, key)
    if not float(value).is_integer() or value < 0:
        raise DataUnavailableError(f"站点 {code} 的样本数为非整数，配置有误。")
    return int(value)


def _metric(code: str, payload: Mapping[str, Any], key: str) -> float:
    value = _number(code, payload, key)
    if value < 0:
        raise DataUnavailableError(f"站点 {code} 的误差或决定系数为负数，配置有误。")
    return value


def _number(code: str, payload: Mapping[str, Any], key: str) -> float:
    try:
        value = float(payload[key])
    except (KeyError, TypeError, ValueError) as exc:
        missing_fields = [field for field in _REQUIRED_FIELDS if field not in payload]
        hint = f"缺少 {', '.join(missing_fields)}" if missing_fields else key
        raise DataUnavailableError(f"站点 {code} 的训练情况不完整（{hint}）。", detail=str(exc)) from exc
    if not math.isfinite(value):
        raise DataUnavailableError(f"站点 {code} 的训练情况含无效数值。")
    return value


def _display_rules(raw: Mapping[str, int] | None) -> dict[str, int]:
    raw = raw or {}
    return {key: _digits(raw.get(key), fallback) for key, fallback in DEFAULT_DISPLAY.items()}


def _digits(value: Any, fallback: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return fallback
    return max(_DIGITS_RANGE[0], min(_DIGITS_RANGE[1], number))
