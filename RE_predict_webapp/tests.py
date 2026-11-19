"""测试：分级匹配、地理数据查询、预测编排、站点/来源接口与页面契约。"""

from __future__ import annotations

from unittest import mock

from django.conf import settings
from django.test import SimpleTestCase

from .services.catalog import StationCatalog
from .services.config import Configuration
from .services.errors import (
    DataUnavailableError,
    InvalidInputError,
    OutOfChinaError,
    PredictionError,
    WeatherUnavailableError,
)
from .services.features import FEATURES, describe_features
from .services.geo import ChinaBoundary, ClimateZones, Coordinate, SoilZones
from .services.matching import StationMatcher
from .services.predictor import RePredictor
from .services.rf import ModelStatus, RandomForestRepository
from .services.sources import build_source_catalog
from .services.stations import Station, StationRepository
from .services.weather import FEATURE_VARIABLES, OpenMeteoWeatherProvider, WeatherSample

YCA_COORDINATE = (36.8294, 116.5682)


def make_station(code: str, lat: float, lon: float, soil: str, climate: str) -> Station:
    return Station(code=code, name=f"站点{code}", lat=lat, lon=lon, soil_type=soil, climate_type=climate)


class StationMatcherTests(SimpleTestCase):
    """四级降级匹配：土壤+气候 → 气候 → 土壤 → 空间最近。"""

    stations = (
        make_station("A", 30.0, 110.0, "红壤", "北亚热带湿润地区"),
        make_station("B", 30.0, 112.0, "潮土", "北亚热带湿润地区"),
        make_station("C", 40.0, 130.0, "黑土", "中温带半湿润地区"),
    )

    def setUp(self) -> None:
        self.matcher = StationMatcher()

    def test_first_tier_requires_both_soil_and_climate(self):
        result = self.matcher.match(Coordinate(30.0, 111.9), self.stations, "红壤", "北亚热带湿润地区")
        self.assertEqual(result.station.code, "A")  # 比 B 远，但土壤与气候都一致
        self.assertEqual(result.order, 1)
        self.assertTrue(result.same_soil)
        self.assertTrue(result.same_climate)
        self.assertEqual(result.confidence.label, "高")

    def test_second_tier_matches_climate_only(self):
        result = self.matcher.match(Coordinate(30.0, 111.9), self.stations, "水稻土", "北亚热带湿润地区")
        self.assertEqual(result.station.code, "B")
        self.assertEqual(result.tier.code, "climate")
        self.assertEqual(result.confidence.label, "中")

    def test_third_tier_matches_soil_only(self):
        result = self.matcher.match(Coordinate(30.2, 110.2), self.stations, "红壤", None)
        self.assertEqual(result.station.code, "A")
        self.assertEqual(result.tier.code, "soil")
        self.assertEqual(result.confidence.label, "中")

    def test_fourth_tier_falls_back_to_nearest(self):
        result = self.matcher.match(Coordinate(41.0, 131.0), self.stations, "水稻土", "边缘热带湿润地区")
        self.assertEqual(result.station.code, "C")
        self.assertEqual(result.order, 4)
        self.assertEqual(result.confidence.label, "低")
        self.assertGreater(result.distance_km, 0)

    def test_empty_stations_raise(self):
        with self.assertRaisesMessage(PredictionError, "站点清单为空"):
            self.matcher.match(Coordinate(30.0, 110.0), (), "红壤", "北亚热带湿润地区")


class GeoDataTests(SimpleTestCase):
    """真实 geojson / shp 数据的边界判断与分区查询。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        paths = Configuration.load().paths
        cls.boundary = ChinaBoundary(paths.boundary_geojson)
        cls.climate = ClimateZones(paths.climate_shp)
        cls.soil = SoilZones(paths.soil_shp)

    def test_land_point_inside_china(self):
        self.assertTrue(self.boundary.contains(Coordinate(39.90, 116.40)))

    def test_overseas_point_outside_china(self):
        self.assertFalse(self.boundary.contains(Coordinate(35.68, 139.69)))

    def test_climate_zone_of_yucheng(self):
        self.assertEqual(self.climate.lookup(Coordinate(*YCA_COORDINATE)), "暖温带半湿润地区")

    def test_soil_zone_of_yucheng(self):
        self.assertEqual(self.soil.lookup(Coordinate(*YCA_COORDINATE)), "潮土")

    def test_sea_point_has_no_zone(self):
        self.assertIsNone(self.climate.lookup(Coordinate(30.0, 125.0)))
        self.assertIsNone(self.soil.lookup(Coordinate(30.0, 125.0)))


class _StubLayer:
    def __init__(self, value: str | None = None) -> None:
        self._value = value

    def lookup(self, coordinate: Coordinate) -> str | None:
        return self._value


class StationRepositoryTests(SimpleTestCase):
    """站点分区类型以 shp 查询结果为准，查不到时回退 config.json。"""

    raw = {
        "X": {
            "site_name": "测试站",
            "lat": 30.0,
            "lon": 110.0,
            "soil_type": "红壤",
            "climate_type": "北亚热带湿润地区",
        }
    }

    def test_shapefile_value_wins(self):
        repository = StationRepository(self.raw, _StubLayer("暖温带半湿润地区"), _StubLayer("潮土"))
        station = repository.get("X")
        self.assertEqual(station.soil_type, "潮土")
        self.assertEqual(station.climate_type, "暖温带半湿润地区")

    def test_falls_back_to_config_value(self):
        repository = StationRepository(self.raw, _StubLayer(None), _StubLayer(None))
        station = repository.get("X")
        self.assertEqual(station.soil_type, "红壤")
        self.assertEqual(station.climate_type, "北亚热带湿润地区")


class _StubWeather:
    def __init__(self, features: tuple[float, ...] = (120.0, 15.0, 60.0, 1010.0, 0.2, 0.25)) -> None:
        self.features = features
        self.calls: list[Coordinate] = []

    def fetch(self, coordinate: Coordinate) -> WeatherSample:
        self.calls.append(coordinate)
        return WeatherSample(features=self.features, values={}, source="stub")


class _StubModels:
    def __init__(self, value: float = 12.5) -> None:
        self.value = value
        self.calls: list[tuple[str, tuple[float, ...]]] = []

    def predict(self, station_code: str, features: tuple[float, ...]) -> float:
        self.calls.append((station_code, features))
        return self.value


class RePredictorTests(SimpleTestCase):
    """完整流程：边界 → 分区匹配 → 气象特征 → 模型预测（气象与模型用桩替换）。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        configuration = Configuration.load()
        paths = configuration.paths
        cls.climate = ClimateZones(paths.climate_shp)
        cls.soil = SoilZones(paths.soil_shp)
        cls.boundary = ChinaBoundary(paths.boundary_geojson)
        cls.stations = StationRepository(configuration.stations, cls.climate, cls.soil)

    def build(self, models=None, weather=None) -> RePredictor:
        self.models = models or _StubModels()
        self.weather = weather or _StubWeather()
        return RePredictor(
            boundary=self.boundary,
            climate=self.climate,
            soil=self.soil,
            stations=self.stations,
            matcher=StationMatcher(),
            models=self.models,
            weather=self.weather,
        )

    def test_yucheng_matches_first_tier_with_high_confidence(self):
        result = self.build().predict(*YCA_COORDINATE)
        self.assertEqual(result.match.station.code, "YCA")
        self.assertEqual(result.match.order, 1)
        self.assertEqual(result.match.confidence.label, "高")
        self.assertEqual(result.prediction, 12.5)
        self.assertEqual(self.models.calls, [("YCA", self.weather.features)])

    def test_outside_china_stops_before_weather_and_model(self):
        with self.assertRaises(OutOfChinaError):
            self.build().predict(35.68, 139.69)
        self.assertEqual(self.weather.calls, [])
        self.assertEqual(self.models.calls, [])

    def test_invalid_coordinates(self):
        predictor = self.build()
        with self.assertRaisesMessage(InvalidInputError, "必须是数字"):
            predictor.predict("abc", 116.4)
        with self.assertRaisesMessage(InvalidInputError, "纬度需在"):
            predictor.predict(91, 116.4)
        with self.assertRaisesMessage(InvalidInputError, "经度需在"):
            predictor.predict(36.8, 181)
        with self.assertRaisesMessage(InvalidInputError, "有效数字"):
            predictor.predict(float("nan"), 116.4)

    def test_weather_failure_propagates(self):
        class FailingWeather:
            def fetch(self, coordinate: Coordinate) -> WeatherSample:
                raise WeatherUnavailableError()

        with self.assertRaises(WeatherUnavailableError):
            self.build(weather=FailingWeather()).predict(*YCA_COORDINATE)


class WeatherProviderConfigTests(SimpleTestCase):
    def test_unknown_feature_is_rejected(self):
        with self.assertRaises(ValueError):
            OpenMeteoWeatherProvider(["unknown"], ["temperature_2m"])

    def test_missing_variable_is_rejected(self):
        with self.assertRaises(ValueError):
            OpenMeteoWeatherProvider(["rn"], ["temperature_2m"])


class ApiViewTests(SimpleTestCase):
    """HTTP 契约：页面、JSON 接口的状态码与字段，以及旧纯文本接口。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        configuration = Configuration.load()
        paths = configuration.paths
        cls.climate = ClimateZones(paths.climate_shp)
        cls.soil = SoilZones(paths.soil_shp)
        cls.boundary = ChinaBoundary(paths.boundary_geojson)
        cls.stations = StationRepository(configuration.stations, cls.climate, cls.soil)

    def setUp(self) -> None:
        predictor = self.make_predictor()
        patcher = mock.patch("RE_predict_webapp.views.get_predictor", return_value=predictor)
        patcher.start()
        self.addCleanup(patcher.stop)

    def make_predictor(self, weather=None) -> RePredictor:
        return RePredictor(
            boundary=self.boundary,
            climate=self.climate,
            soil=self.soil,
            stations=self.stations,
            matcher=StationMatcher(),
            models=_StubModels(9.87),
            weather=weather or _StubWeather(),
        )

    def test_page_renders(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "生态系统呼吸预测")

    def test_api_returns_prediction_and_confidence(self):
        response = self.client.get("/api/predict/", {"lat": YCA_COORDINATE[0], "lon": YCA_COORDINATE[1]})
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["result"]["prediction"], 9.87)
        self.assertEqual(payload["result"]["confidence"]["label"], "高")
        self.assertEqual(payload["result"]["station"]["code"], "YCA")
        self.assertEqual(payload["result"]["matching"]["tier"], 1)

    def test_api_outside_china(self):
        response = self.client.get("/api/predict/", {"lat": 35.68, "lon": 139.69})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["error"]["code"], "OUT_OF_CHINA")

    def test_api_missing_parameters(self):
        response = self.client.get("/api/predict/")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "INVALID_INPUT")

    def test_api_weather_failure(self):
        class FailingWeather:
            def fetch(self, coordinate: Coordinate) -> WeatherSample:
                raise WeatherUnavailableError()

        with mock.patch("RE_predict_webapp.views.get_predictor", return_value=self.make_predictor(FailingWeather())):
            response = self.client.get("/api/predict/", {"lat": YCA_COORDINATE[0], "lon": YCA_COORDINATE[1]})

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "WEATHER_UNAVAILABLE")

    def test_legacy_text_endpoint_still_works(self):
        response = self.client.get("/", {"lat": YCA_COORDINATE[0], "lon": YCA_COORDINATE[1]})
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("预测值: 9.87", content)
        self.assertIn("置信度: 高", content)
        self.assertIn("匹配到最近的站点: YCA", content)


class FeatureMetadataTests(SimpleTestCase):
    """特征说明必须与气象层实际取用的变量一致，避免两处口径漂移。"""

    def test_metadata_covers_weather_features(self):
        self.assertEqual(set(FEATURES), set(FEATURE_VARIABLES))
        for name, variable in FEATURE_VARIABLES.items():
            self.assertEqual(FEATURES[name].variable, variable)
            self.assertTrue(FEATURES[name].label)

    def test_describe_features_follows_config_order(self):
        configuration = Configuration.load()
        described = describe_features(configuration.features)
        self.assertEqual([feature.name for feature in described], list(configuration.features))
        self.assertEqual(described, tuple(FEATURES[name] for name in configuration.features))


class ModelStatusTests(SimpleTestCase):
    """模型文件状态：就绪、缺失、空文件、不可读都要可读地返回，而不是让页面崩溃。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.paths = Configuration.load().paths
        cls.repository = RandomForestRepository(cls.paths.rf_model_dir, ("rn",))

    def test_existing_model_is_available(self):
        status = self.repository.status("YCA")
        self.assertTrue(status.available)
        self.assertEqual(status.filename, "YCA_rf.joblib")
        self.assertGreater(status.size_bytes, 0)
        self.assertEqual(status.to_dict()["status"], "ok")

    def test_missing_model_is_reported(self):
        status = self.repository.status("__missing__")
        self.assertFalse(status.available)
        self.assertEqual(status.status, "missing")
        self.assertTrue(status.message)

    def test_empty_and_unreadable_models_are_reported(self):
        with mock.patch("pathlib.Path.stat", return_value=mock.Mock(st_size=0)):
            self.assertEqual(self.repository.status("YCA").status, "empty")
        with mock.patch("pathlib.Path.stat", side_effect=PermissionError("denied")):
            self.assertEqual(self.repository.status("YCA").status, "unreadable")


class StationCatalogTests(SimpleTestCase):
    """站点模型目录：全部站点、模型状态与特征清单都来自服务层。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.configuration = Configuration.load()
        paths = cls.configuration.paths
        climate = ClimateZones(paths.climate_shp)
        soil = SoilZones(paths.soil_shp)
        stations = StationRepository(cls.configuration.stations, climate, soil)
        models = RandomForestRepository(paths.rf_model_dir, cls.configuration.features)
        cls.catalog = StationCatalog(stations.stations, models)

    def test_catalog_covers_every_configured_station(self):
        payload = self.catalog.to_dict()
        self.assertEqual(payload["count"], len(self.configuration.stations))
        self.assertEqual(
            {item["code"] for item in payload["stations"]},
            set(self.configuration.stations),
        )
        summary = payload["summary"]
        self.assertEqual(summary["total"], payload["count"])
        self.assertEqual(summary["available"] + summary["unavailable"], payload["count"])

    def test_station_entry_exposes_model_and_features(self):
        payload = self.catalog.to_dict()
        station = next(item for item in payload["stations"] if item["code"] == "YCA")

        self.assertEqual(station["name"], "禹城站冬小麦-夏玉米复种农田")
        self.assertAlmostEqual(station["lat"], 36.8294)
        self.assertEqual(station["ecosystem"], "Cropland")
        self.assertEqual(station["climate_type"], "暖温带半湿润地区")
        self.assertEqual(station["soil_type"], "潮土")
        self.assertEqual(station["model"]["filename"], "YCA_rf.joblib")
        self.assertTrue(station["model"]["available"])
        self.assertEqual(station["features"], list(self.configuration.features))
        self.assertEqual([item["name"] for item in payload["features"]], list(self.configuration.features))


class SourceCatalogTests(SimpleTestCase):
    """数据来源目录：六类来源齐全、路径相对 BASE_DIR、气象默认值取自 settings。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.configuration = Configuration.load()
        cls.catalog = build_source_catalog(cls.configuration)

    def test_covers_the_six_required_sources(self):
        payload = self.catalog.to_dict()
        self.assertEqual(
            [item["key"] for item in payload["sources"]],
            ["model", "boundary", "climate", "soil", "weather", "config"],
        )
        self.assertEqual(
            {item["category"] for item in payload["sources"]},
            {"模型", "地理", "分区", "气象", "配置"},
        )

    def test_every_source_is_complete(self):
        for source in self.catalog.to_dict()["sources"]:
            for field in ("name", "category", "location", "short", "purpose", "update"):
                self.assertTrue(source[field], f"{source['key']} 缺少 {field}")

    def test_locations_stay_inside_workspace_and_weather_comes_from_settings(self):
        base = str(settings.BASE_DIR)
        payload = self.catalog.to_dict()

        for source in payload["sources"]:
            if source["key"] == "weather":
                self.assertEqual(source["location"], settings.WEATHER_ENDPOINT)
                continue
            self.assertNotIn(base, source["location"])
            self.assertNotRegex(source["location"], r"^[A-Za-z]:")

        self.assertEqual(payload["weather"]["model"], settings.WEATHER_MODEL or "best_match")
        self.assertEqual(payload["shorts"]["weather"], payload["weather"]["label"])

    def test_feature_metadata_is_shared_with_the_model(self):
        payload = self.catalog.to_dict()
        self.assertEqual([item["name"] for item in payload["features"]], list(self.configuration.features))
        self.assertIn(
            f"{len(self.configuration.stations)} 个站点",
            payload["sources"][0]["detail"],
        )


class PageRoutingTests(SimpleTestCase):
    """多页面：三页都能渲染，且每页都有导航与网页简述。"""

    PAGES = (
        ("/", "生态系统呼吸预测"),
        ("/stations/", "站点模型查看"),
        ("/sources/", "数据来源"),
    )

    def test_pages_render_with_navigation_and_brief(self):
        for path, title in self.PAGES:
            with self.subTest(path=path):
                response = self.client.get(path)
                html = response.content.decode("utf-8")

                self.assertEqual(response.status_code, 200)
                self.assertIn(f"<title>{title}</title>", html)
                self.assertIn('<p class="intro">', html)  # 网页简述
                for label in ("预测", "站点模型", "数据来源"):
                    self.assertIn(f">{label}</a>", html)

    def test_home_page_keeps_prediction_form(self):
        response = self.client.get("/")
        for marker in (
            'id="predict-form"',
            'id="lat"',
            'id="lon"',
            'id="submit-btn"',
            'id="result-body"',
            "frontend/js/common.js",
            "frontend/js/app.js",
        ):
            self.assertContains(response, marker)

    def test_unknown_page_is_404(self):
        self.assertEqual(self.client.get("/nope/").status_code, 404)


class ReadonlyApiTests(SimpleTestCase):
    """只读接口：结构、错误码与缺数据时的可读提示。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.configuration = Configuration.load()

    def test_stations_api_returns_catalog(self):
        response = self.client.get("/api/stations/")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], len(self.configuration.stations))
        self.assertEqual(len(payload["stations"]), payload["count"])
        self.assertEqual(payload["summary"]["total"], payload["count"])
        self.assertIn("generated_at", payload["meta"])

        yca = next(item for item in payload["stations"] if item["code"] == "YCA")
        self.assertEqual(yca["model"]["filename"], "YCA_rf.joblib")
        self.assertTrue(yca["model"]["available"])
        self.assertEqual(yca["features"], list(self.configuration.features))
        self.assertEqual([item["name"] for item in payload["features"]], list(self.configuration.features))

    def test_sources_api_returns_sources_and_features(self):
        response = self.client.get("/api/sources/")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        keys = {item["key"] for item in payload["sources"]}
        self.assertEqual(keys, {"model", "boundary", "climate", "soil", "weather", "config"})
        self.assertEqual(set(payload["shorts"]), keys)
        self.assertEqual([item["name"] for item in payload["features"]], list(self.configuration.features))
        self.assertEqual(payload["weather"]["label"], payload["shorts"]["weather"])

    def test_stations_api_reports_data_errors(self):
        with mock.patch("RE_predict_webapp.views.get_predictor", side_effect=DataUnavailableError()):
            response = self.client.get("/api/stations/")

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "DATA_UNAVAILABLE")
        self.assertTrue(payload["error"]["message"])

    def test_sources_api_reports_data_errors(self):
        with mock.patch("RE_predict_webapp.views.build_source_catalog", side_effect=DataUnavailableError()):
            response = self.client.get("/api/sources/")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "DATA_UNAVAILABLE")

    def test_missing_models_are_reported_not_raised(self):
        missing = ModelStatus(filename="YCA_rf.joblib", status="missing", message="模型文件不存在")
        with mock.patch(
            "RE_predict_webapp.services.rf.RandomForestRepository.status",
            return_value=missing,
        ):
            response = self.client.get("/api/stations/")

        payload = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["summary"]["available"], 0)
        self.assertEqual(payload["summary"]["unavailable"], payload["count"])
        self.assertFalse(payload["stations"][0]["model"]["available"])
