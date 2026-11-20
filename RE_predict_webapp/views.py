"""HTTP 入口：前端页面、JSON 预测接口、只读的训练情况/来源/公告接口，以及兼容旧版的纯文本接口。"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .content import PAGES, page_context
from .services import (
    InvalidInputError,
    PredictionError,
    PredictionResult,
    build_site_catalog,
    get_predictor,
)

logger = logging.getLogger(__name__)

JSON_CONTENT_TYPE = "application/json; charset=utf-8"

STATUS_BY_CODE = {
    "INVALID_INPUT": 400,
    "OUT_OF_CHINA": 422,
    "WEATHER_UNAVAILABLE": 503,
    "MODEL_UNAVAILABLE": 503,
    "DATA_UNAVAILABLE": 500,
}

LEGACY_MISSING_MESSAGE = "请在网址带上经纬度，比如 ?lat=39.9&lon=116.4"


def _json(payload: dict[str, Any], status: int = 200) -> JsonResponse:
    return JsonResponse(
        payload,
        status=status,
        json_dumps_params={"ensure_ascii": False},
        content_type=JSON_CONTENT_TYPE,
    )


def _page(request: HttpRequest, key: str) -> HttpResponse:
    return render(request, f"RE_predict_webapp/{PAGES[key].template}", page_context(key))


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    """无参数时返回前端页面；带 lat/lon 时保留旧的纯文本输出。"""
    if "lat" not in request.GET and "lon" not in request.GET:
        return _page(request, "home")
    return _predict_text(request)


@require_GET
def training_page(request: HttpRequest) -> HttpResponse:
    """模型训练情况页：模板只渲染骨架，数据由只读接口填充。"""
    return _page(request, "training")


@require_GET
def sources_page(request: HttpRequest) -> HttpResponse:
    """数据来源注明页：模板只渲染骨架，数据由只读接口填充。"""
    return _page(request, "sources")


@require_GET
def predict_api(request: HttpRequest) -> JsonResponse:
    """前端调用的 JSON 接口。"""
    started = time.perf_counter()
    try:
        result = _run_prediction(request)
    except PredictionError as exc:
        return _error_response(exc)
    except Exception:
        return _internal_error("预测接口出现未预期错误")

    return _json(
        {
            "ok": True,
            "request": {"lat": result.coordinate.lat, "lon": result.coordinate.lon},
            "result": result.to_dict(),
            "meta": {
                "generated_at": result.generated_at,
                "took_ms": int((time.perf_counter() - started) * 1000),
            },
        }
    )


@require_GET
def training_api(request: HttpRequest) -> JsonResponse:
    """各站点的模型训练情况（对外只含训练/测试规模、MSE、R² 与模型类别）。"""
    return _readonly_response("training")


@require_GET
def sources_api(request: HttpRequest) -> JsonResponse:
    """数据来源注明：来源页与预测结果区的来源标注共用这一份。"""
    return _readonly_response("sources")


@require_GET
def announcements_api(request: HttpRequest) -> JsonResponse:
    """公告列表（只读，按发布时间倒序）；发布与维护在服务端完成。"""
    return _readonly_response("announcements")


def _readonly_response(catalog_name: str) -> JsonResponse:
    """只读接口的统一外壳：成功附 ok/meta，业务错误沿用 v1.1.0 的 code 约定。

    catalog_name 是 SiteCatalog 上的目录属性名（training / sources / announcements），
    页面与接口都从同一份目录取数。
    """
    started = time.perf_counter()
    try:
        payload = getattr(build_site_catalog(), catalog_name).to_dict()
    except PredictionError as exc:
        return _error_response(exc)
    except Exception:
        return _internal_error("只读接口出现未预期错误")

    return _json(
        {
            "ok": True,
            **payload,
            "meta": {
                "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "took_ms": int((time.perf_counter() - started) * 1000),
            },
        }
    )


def _internal_error(log_message: str) -> JsonResponse:
    """未预期异常：服务端记完整堆栈，对外只给可读文案。"""
    logger.exception(log_message)
    return _json(
        {"ok": False, "error": {"code": "INTERNAL_ERROR", "message": "服务器内部错误，请稍后再试。"}},
        status=500,
    )


def _run_prediction(request: HttpRequest) -> PredictionResult:
    lat, lon = request.GET.get("lat"), request.GET.get("lon")
    if not lat or not lon:
        raise InvalidInputError("请同时提供纬度 lat 与经度 lon，例如 /api/predict/?lat=39.90&lon=116.40")
    return get_predictor().predict(lat, lon)


def _error_response(error: PredictionError) -> JsonResponse:
    status = STATUS_BY_CODE.get(error.code, 500)
    if status >= 500:
        logger.warning("接口失败（%s）：%s", error.code, error)
    return _json({"ok": False, "error": {"code": error.code, "message": error.message}}, status=status)


def _predict_text(request: HttpRequest) -> HttpResponse:
    """旧版接口：GET /?lat=…&lon=… 返回纯文本，保持对老调用方的兼容。"""
    lat, lon = request.GET.get("lat"), request.GET.get("lon")
    if not lat or not lon:
        return HttpResponse(LEGACY_MISSING_MESSAGE)

    try:
        result = get_predictor().predict(lat, lon)
    except PredictionError as exc:
        return HttpResponse(exc.message)
    except Exception:
        logger.exception("纯文本接口出现未预期错误")
        return HttpResponse("模型预测报错，请稍后重试。")

    match = result.match
    confidence = match.confidence
    return HttpResponse(
        f"您的位置:({result.coordinate.lat}, {result.coordinate.lon})。\n"
        f"匹配到最近的站点: {match.station.code} ({match.station.name})\n"
        f"距离: {match.distance_km:.2f} km\n"
        f"预测值: {result.prediction:.2f}\n"
        f"置信度: {confidence.label}（{confidence.note}）"
    )
