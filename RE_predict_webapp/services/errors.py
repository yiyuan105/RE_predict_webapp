"""业务异常：服务层抛出，视图层按 code 翻译成响应，不依赖 Django。"""

from __future__ import annotations


class PredictionError(Exception):
    """可预期的业务错误。"""

    code = "PREDICTION_FAILED"
    default_message = "预测失败，请稍后再试。"

    def __init__(self, message: str | None = None, *, detail: str | None = None) -> None:
        self.message = message or self.default_message
        self.detail = detail
        super().__init__(self.message)


class InvalidInputError(PredictionError):
    code = "INVALID_INPUT"
    default_message = "经纬度格式不正确，请输入数字。"


class OutOfChinaError(PredictionError):
    code = "OUT_OF_CHINA"
    default_message = "输入的经纬度不在中国陆地范围内，无法进行预测。"


class DataUnavailableError(PredictionError):
    code = "DATA_UNAVAILABLE"
    default_message = "地理或站点数据加载失败，请检查服务端日志。"


class ModelUnavailableError(PredictionError):
    code = "MODEL_UNAVAILABLE"
    default_message = "该站点的随机森林模型不可用，请检查服务端日志。"


class WeatherUnavailableError(PredictionError):
    code = "WEATHER_UNAVAILABLE"
    default_message = "未能获取 Open-Meteo 气象数据，请稍后再试。"
