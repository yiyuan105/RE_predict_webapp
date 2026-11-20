"""测试：分级匹配、地理数据查询、预测编排、对外目录（训练情况/来源/公告）、页面契约与对外字段。"""

from __future__ import annotations

import json
import re
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from .services.announcements import AnnouncementCatalog
from .services.config import Configuration
from .services.errors import (
    DataUnavailableError,
    InvalidInputError,
    ModelUnavailableError,
    OutOfChinaError,
    PredictionError,
    WeatherUnavailableError,
)
from .services.features import FEATURES, FEATURE_TRANSFORMS, FEATURE_VARIABLES
from .services.geo import ChinaBoundary, ClimateZones, Coordinate, SoilZones
from .services.matching import StationMatcher
from .services.predictor import RePredictor
from .services.rf import RandomForestRepository
from .services.sources import build_source_catalog
from .services.stations import Station, StationRepository
from .services.training import DEFAULT_DISPLAY, TrainingCatalog, build_training_catalog
from .services.weather import OpenMeteoWeatherProvider, WeatherSample

YCA_COORDINATE = (36.8294, 116.5682)

# 需求文档给出的各站点训练结果：对外展示口径的基准值
EXPECTED_TRAINING = {
    "NMG": (2045, 512, 1.1417, 0.9947, 17.8560, 0.9263),
    "QYF": (2337, 585, 0.1976, 0.9973, 2.4848, 0.9641),
    "DXG": (2045, 512, 0.2628, 0.9949, 2.5535, 0.9500),
    "HBG_S01": (2337, 585, 0.5409, 0.9926, 5.2283, 0.9318),
    "HBG_W01": (1753, 439, 0.8356, 0.9900, 6.7783, 0.9118),
    "YCA": (2337, 585, 0.2568, 0.9976, 3.2528, 0.9720),
    "BNF": (2337, 585, 0.0673, 0.9949, 3.7594, 0.7078),
    "CBF": (2337, 585, 1.2755, 0.9917, 16.7521, 0.8992),
    "DHF": (2337, 585, 0.4170, 0.9887, 3.7458, 0.9007),
    "JUR": (1753, 439, 0.4977, 0.9939, 9.7765, 0.8920),
    "DM": (3681, 921, 0.3984, 0.9971, 5.2686, 0.9616),
    "HN": (2274, 569, 0.2193, 0.9898, 8.2398, 0.7130),
}

# 对外可见层不得出现的内部信息：文件地址、模型文件、输入特征、模块与接口路径
FORBIDDEN_OUTWARD = (
    "joblib",
    ".shp",
    "geojson",
    "config.json",
    "announcements.json",
    "models/",
    "services/",
    "RE_predict_webapp",
    "rf_models",
    "/api/",
    "soil_moisture",
    "temperature_2m",
    "relative_humidity_2m",
    "shortwave_radiation",
    "surface_pressure",
    "SOIL_ID",
)

STATIC_URL_PATTERN = re.compile(r"/static/[^\"'\s>]+")


def make_station(code: str, lat: float, lon: float, soil: str, climate: str) -> Station:
    return Station(code=code, name=f"站点{code}", lat=lat, lon=lon, soil_type=soil, climate_type=climate)


def outward_text(html: str) -> str:
    """去掉静态资源地址后再做对外信息检查（样式与脚本地址是页面正常组成部分）。"""
    return STATIC_URL_PATTERN.sub("", html)


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

    def test_exhausted_tiers_raise_readable_message(self):
        matcher = StationMatcher()  # 所有级别都不命中时（候选为空）给出可读提示
        with self.assertRaises(PredictionError):
            matcher.match(Coordinate(30.0, 110.0), (), "红壤", None)


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

    def test_boundary_errors_hide_file_details(self):
        with self.assertRaises(DataUnavailableError) as caught:
            ChinaBoundary(Path("不存在的边界数据.geojson"))
        self.assertNotIn(".geojson", caught.exception.message)
        self.assertTrue(caught.exception.detail)


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


class FeatureRegistryTests(SimpleTestCase):
    """特征与气象变量的映射只维护一份，配置里用到的特征都必须登记。"""

    def test_config_features_are_registered(self):
        configuration = Configuration.load()
        self.assertEqual(set(configuration.features), set(FEATURES))
        self.assertEqual(set(FEATURE_VARIABLES), set(FEATURES))

    def test_variables_cover_every_feature(self):
        configuration = Configuration.load()
        aliases = {"surface_pressure_2m": "surface_pressure"}
        api_variables = {aliases.get(name, name) for name in configuration.variables}
        for name in configuration.features:
            self.assertIn(FEATURE_VARIABLES[name], api_variables)

    def test_only_net_radiation_is_transformed(self):
        self.assertEqual(set(FEATURE_TRANSFORMS), {"rn"})
        self.assertAlmostEqual(FEATURE_TRANSFORMS["rn"](100.0), 60.0)


class RandomForestRepositoryTests(SimpleTestCase):
    """模型仓库：缺失文件只返回可读提示，不把路径或文件名带给访客。"""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.repository = RandomForestRepository(Path(directory.name), ("rn",))

    def test_missing_model_reports_readable_message(self):
        with self.assertRaises(ModelUnavailableError) as caught:
            self.repository.predict("YCA", (1.0,))
        self.assertIn("暂不可用", caught.exception.message)
        self.assertNotIn(".joblib", caught.exception.message)
        self.assertNotIn(str(Path(tempfile.gettempdir())), caught.exception.message)

    def test_feature_names_follow_configuration(self):
        configuration = Configuration.load()
        repository = RandomForestRepository(configuration.paths.rf_model_dir, configuration.features)
        self.assertEqual(repository.feature_names, configuration.features)

    def test_feature_count_mismatch_is_reported(self):
        with self.assertRaises(PredictionError):
            RandomForestRepository(Configuration.load().paths.rf_model_dir, ("rn", "ts1")).predict(
                "YCA", (1.0, 2.0, 3.0)
            )


class TrainingCatalogTests(SimpleTestCase):
    """训练情况目录：只输出对外字段，数值与需求文档给出的训练结果一致。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.catalog = build_training_catalog()
        cls.payload = cls.catalog.to_dict()

    def test_covers_every_station_in_document_order(self):
        self.assertEqual([row["code"] for row in self.payload["stations"]], list(EXPECTED_TRAINING))

    def test_metrics_match_the_required_values(self):
        rows = {row["code"]: row for row in self.payload["stations"]}
        for code, expected in EXPECTED_TRAINING.items():
            with self.subTest(station=code):
                row = rows[code]
                self.assertEqual(row["train_size"], expected[0])
                self.assertEqual(row["test_size"], expected[1])
                for key, value in zip(("train_mse", "train_r2", "test_mse", "test_r2"), expected[2:]):
                    self.assertAlmostEqual(row[key], value, places=6)
                self.assertEqual(row["model_type"], "随机森林 / RandomForestRegressor")

    def test_row_exposes_only_the_outward_fields(self):
        allowed = {
            "code",
            "train_size",
            "test_size",
            "train_mse",
            "train_r2",
            "test_mse",
            "test_r2",
            "model_type",
        }
        for row in self.payload["stations"]:
            self.assertEqual(set(row), allowed)
        for forbidden in ("features", "model", "filename", "path", "lat", "lon", "name"):
            self.assertNotIn(forbidden, self.payload)
            self.assertNotIn(forbidden, self.payload["stations"][0])

    def test_display_precision_comes_from_configuration(self):
        configuration = Configuration.load()
        expected = configuration.training["display"]
        self.assertEqual(self.payload["display"], expected)
        self.assertEqual(self.payload["display"], {"mse_digits": 4, "r2_digits": 4})

    def test_display_precision_defaults_and_clamps(self):
        catalog = TrainingCatalog([], {"mse_digits": "abc", "r2_digits": 99})
        self.assertEqual(catalog.to_dict()["display"], {"mse_digits": DEFAULT_DISPLAY["mse_digits"], "r2_digits": 6})
        self.assertEqual(TrainingCatalog([]).to_dict()["display"], dict(DEFAULT_DISPLAY))

    def test_missing_section_yields_empty_catalog(self):
        configuration = Configuration.load()
        empty = Configuration(
            paths=configuration.paths,
            stations=configuration.stations,
            features=configuration.features,
            variables=configuration.variables,
            training={},
        )
        payload = TrainingCatalog.from_configuration(empty).to_dict()
        self.assertEqual(payload["count"], 0)
        self.assertEqual(payload["stations"], [])

    def test_unknown_station_code_is_skipped(self):
        configuration = Configuration.load()
        training = json.loads(json.dumps(configuration.training))
        training["records"]["__unknown__"] = training["records"]["YCA"]
        patched = Configuration(
            paths=configuration.paths,
            stations=configuration.stations,
            features=configuration.features,
            variables=configuration.variables,
            training=training,
        )
        codes = [record.code for record in TrainingCatalog.from_configuration(patched).records]
        self.assertNotIn("__unknown__", codes)
        self.assertIn("YCA", codes)

    def test_incomplete_record_reports_readable_error(self):
        configuration = Configuration.load()
        with self.assertRaises(DataUnavailableError) as caught:
            TrainingCatalog.from_configuration(
                Configuration(
                    paths=configuration.paths,
                    stations=configuration.stations,
                    features=configuration.features,
                    variables=configuration.variables,
                    training={"records": {"YCA": {"train_size": 10}}},
                )
            )
        self.assertIn("训练情况不完整", caught.exception.message)
        self.assertNotIn("config.json", caught.exception.message)

    def test_non_integer_sample_size_is_rejected(self):
        with self.assertRaises(DataUnavailableError):
            TrainingCatalog.from_configuration(
                Configuration(
                    paths=Configuration.load().paths,
                    stations={"YCA": {}},
                    features=("rn",),
                    variables=("shortwave_radiation",),
                    training={
                        "records": {
                            "YCA": {
                                "train_size": 10.5,
                                "test_size": 2,
                                "train_mse": 1,
                                "train_r2": 0.9,
                                "test_mse": 1,
                                "test_r2": 0.9,
                            }
                        }
                    },
                )
            )


class SourceCatalogTests(SimpleTestCase):
    """来源注明：五项来源齐全，只含名称/类型/用途/更新方式，不含路径与地址。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.payload = build_source_catalog().to_dict()

    def test_covers_the_required_source_kinds(self):
        self.assertEqual(
            [item["key"] for item in self.payload["sources"]],
            ["model", "boundary", "climate", "soil", "weather"],
        )
        self.assertEqual(
            [item["category"] for item in self.payload["sources"]],
            ["预测模型", "地理边界", "气候分区", "土壤分区", "气象数据"],
        )

    def test_every_source_has_only_outward_fields(self):
        for source in self.payload["sources"]:
            self.assertEqual(set(source), {"key", "name", "category", "purpose", "update"})
            for field in ("name", "category", "purpose", "update"):
                self.assertTrue(source[field], f"{source['key']} 缺少 {field}")

    def test_no_paths_addresses_or_variables(self):
        text = json.dumps(self.payload, ensure_ascii=False)
        for token in ("/", "\\", ".shp", ".geojson", ".json", "http", "joblib", "SOIL_ID", "variable"):
            self.assertNotIn(token, text, f"来源说明里出现了 {token!r}")
        for forbidden in FORBIDDEN_OUTWARD:
            self.assertNotIn(forbidden, text)

    def test_attribution_names_are_reusable(self):
        names = {source["key"]: source["name"] for source in self.payload["sources"]}
        self.assertEqual(names["weather"], "Open-Meteo 实时气象数据")
        self.assertEqual(names["soil"], "中国土壤分区")
        self.assertEqual(names["climate"], "中国气候分区")


class AnnouncementCatalogTests(SimpleTestCase):
    """公告：按发布时间倒序、只含标题/正文/时间，坏条目跳过，整份读不到给可读错误。"""

    def write(self, payload: str) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "announcements.json"
        path.write_text(payload, encoding="utf-8")
        return path

    def test_sorted_by_published_desc(self):
        path = self.write(
            json.dumps(
                {
                    "announcements": [
                        {"title": "旧的", "body": "正文", "published_at": "2026-11-01"},
                        {"title": "新的", "body": "正文", "published_at": "2026-11-20"},
                        {
                            "title": "中间的",
                            "body": "正文",
                            "published_at": "2026-11-10T09:00:00+08:00",
                        },
                    ]
                },
                ensure_ascii=False,
            )
        )
        payload = AnnouncementCatalog.load(path).to_dict()
        self.assertEqual([item["title"] for item in payload["announcements"]], ["新的", "中间的", "旧的"])
        self.assertEqual(set(payload["announcements"][0]), {"title", "body", "published_at"})

    def test_inactive_and_incomplete_entries_are_skipped(self):
        path = self.write(
            json.dumps(
                {
                    "announcements": [
                        {"title": "已下架", "body": "正文", "published_at": "2026-11-20", "active": False},
                        {"title": "缺正文", "published_at": "2026-11-19"},
                        {"title": "时间不规范", "body": "正文", "published_at": "昨天"},
                        {"title": "正常", "body": "正文", "published_at": "2026-11-18"},
                    ]
                },
                ensure_ascii=False,
            )
        )
        payload = AnnouncementCatalog.load(path).to_dict()
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["announcements"][0]["title"], "正常")

    def test_missing_file_means_no_announcement(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        payload = AnnouncementCatalog.load(Path(directory.name) / "announcements.json").to_dict()
        self.assertEqual(payload, {"count": 0, "announcements": []})

    def test_broken_file_reports_readable_error(self):
        path = self.write("{ not json")
        with self.assertRaises(DataUnavailableError) as caught:
            AnnouncementCatalog.load(path)
        self.assertIn("公告", caught.exception.message)
        self.assertNotIn("announcements.json", caught.exception.message)

    def test_shipped_announcements_are_outward_safe(self):
        payload = AnnouncementCatalog.load(Configuration.load().paths.announcement_config).to_dict()
        self.assertGreaterEqual(payload["count"], 1)
        text = json.dumps(payload, ensure_ascii=False)
        for forbidden in FORBIDDEN_OUTWARD:
            self.assertNotIn(forbidden, text)

    def test_shipped_announcements_are_sorted(self):
        payload = AnnouncementCatalog.load(Configuration.load().paths.announcement_config).to_dict()
        times = [item["published_at"] for item in payload["announcements"]]
        self.assertEqual(times, sorted(times, reverse=True))


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

    def test_model_unavailable_is_reported_without_file_details(self):
        class FailingModels:
            def predict(self, station_code: str, features: tuple[float, ...]) -> float:
                raise ModelUnavailableError(f"站点 {station_code} 的模型暂不可用，请稍后再试。")

        predictor = RePredictor(
            boundary=self.boundary,
            climate=self.climate,
            soil=self.soil,
            stations=self.stations,
            matcher=StationMatcher(),
            models=FailingModels(),
            weather=_StubWeather(),
        )
        with mock.patch("RE_predict_webapp.views.get_predictor", return_value=predictor):
            response = self.client.get("/api/predict/", {"lat": YCA_COORDINATE[0], "lon": YCA_COORDINATE[1]})

        payload = response.json()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(payload["error"]["code"], "MODEL_UNAVAILABLE")
        self.assertNotIn(".joblib", payload["error"]["message"])

    def test_legacy_text_endpoint_still_works(self):
        response = self.client.get("/", {"lat": YCA_COORDINATE[0], "lon": YCA_COORDINATE[1]})
        content = response.content.decode("utf-8")

        self.assertEqual(response.status_code, 200)
        self.assertIn("预测值: 9.87", content)
        self.assertIn("置信度: 高", content)
        self.assertIn("匹配到最近的站点: YCA", content)


class PageRoutingTests(SimpleTestCase):
    """多页面：三页都能渲染，导航与首页布局符合"左三框 + 右公告边栏"。"""

    PAGES = (
        ("/", "生态系统呼吸预测"),
        ("/stations/", "模型训练情况"),
        ("/sources/", "数据来源注明"),
    )

    def test_pages_render_with_navigation_and_brief(self):
        for path, title in self.PAGES:
            with self.subTest(path=path):
                response = self.client.get(path)
                html = response.content.decode("utf-8")

                self.assertEqual(response.status_code, 200)
                self.assertIn(f"<title>{title}</title>", html)
                self.assertIn('<p class="intro">', html)  # 网页简述
                nav = re.search(r'<nav class="site-nav".*?</nav>', html, re.S).group(0)
                self.assertEqual(re.findall(r"site-nav-link[^\"]*\"[^>]*>([^<]+)<", nav, re.S), ["首页", "站点", "数据来源"])

    def test_home_has_three_rail_boxes_and_notice_sidebar(self):
        html = self.client.get("/").content.decode("utf-8")

        rail = re.search(r'<aside class="rail".*?</aside>', html, re.S).group(0)
        self.assertEqual(re.findall(r'rail-box-label">([^<]+)<', rail), ["首页", "站点", "数据来源"])

        sidebar = re.search(r'<aside class="sidebar".*?</aside>', html, re.S).group(0)
        self.assertIn("公告", sidebar)
        self.assertIn('id="notice-list"', sidebar)
        self.assertIn('id="notice-status"', sidebar)
        self.assertIn("frontend/js/notices.js", html)

    def test_home_keeps_prediction_form(self):
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

    def test_training_page_shows_all_metric_columns(self):
        html = self.client.get("/stations/").content.decode("utf-8")
        for header in (
            "站点",
            "训练样本数",
            "测试样本数",
            "训练集 MSE",
            "训练集 R²",
            "测试集 MSE",
            "测试集 R²",
            "模型类别",
        ):
            self.assertIn(f"<th scope=\"col\">{header}</th>", html)
        for control in ('id="code-search"', 'id="filter-r2"', 'id="filter-reset"', 'id="training-body"'):
            self.assertIn(control, html)

    def test_unknown_page_is_404(self):
        self.assertEqual(self.client.get("/nope/").status_code, 404)


class ReadonlyApiTests(SimpleTestCase):
    """只读接口：字段范围、排序、只读语义与缺数据时的可读提示。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.configuration = Configuration.load()

    def test_training_api_returns_training_only(self):
        response = self.client.get("/api/stations/")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], len(EXPECTED_TRAINING))
        self.assertEqual(payload["display"], self.configuration.training["display"])
        self.assertEqual([row["code"] for row in payload["stations"]], list(EXPECTED_TRAINING))
        self.assertIn("generated_at", payload["meta"])

    def test_training_api_has_no_internal_fields(self):
        payload = self.client.get("/api/stations/").json()

        self.assertEqual(set(payload), {"ok", "count", "display", "stations", "meta"})
        allowed = {"code", "train_size", "test_size", "train_mse", "train_r2", "test_mse", "test_r2", "model_type"}
        for row in payload["stations"]:
            self.assertEqual(set(row), allowed)

        text = json.dumps(payload, ensure_ascii=False)
        for token in FORBIDDEN_OUTWARD + ("filename", "size_kb", "available", "features"):
            self.assertNotIn(token, text)

    def test_sources_api_returns_attribution_only(self):
        payload = self.client.get("/api/sources/").json()

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], 5)
        self.assertEqual(set(payload), {"ok", "count", "sources", "meta"})
        for item in payload["sources"]:
            self.assertEqual(set(item), {"key", "name", "category", "purpose", "update"})

        text = json.dumps(payload, ensure_ascii=False)
        for token in FORBIDDEN_OUTWARD + ("shorts", "features", "location", "doc_ref", "endpoint", "variables"):
            self.assertNotIn(token, text)

    def test_announcements_api_is_sorted_and_outward(self):
        payload = self.client.get("/api/announcements/").json()

        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(payload["count"], 1)
        self.assertEqual(set(payload), {"ok", "count", "announcements", "meta"})
        times = [item["published_at"] for item in payload["announcements"]]
        self.assertEqual(times, sorted(times, reverse=True))
        for item in payload["announcements"]:
            self.assertEqual(set(item), {"title", "body", "published_at"})
            self.assertTrue(item["title"] and item["body"])

    def test_readonly_endpoints_reject_writes(self):
        for path in ("/api/stations/", "/api/sources/", "/api/announcements/"):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path).status_code, 405)

    def test_readonly_endpoints_report_data_errors(self):
        with mock.patch("RE_predict_webapp.views.build_site_catalog", side_effect=DataUnavailableError()):
            response = self.client.get("/api/stations/")

        self.assertEqual(response.status_code, 500)
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "DATA_UNAVAILABLE")
        self.assertTrue(payload["error"]["message"])

    def test_announcements_error_is_reported_as_readable_json(self):
        with mock.patch(
            "RE_predict_webapp.services.announcements.AnnouncementCatalog.load",
            side_effect=DataUnavailableError("公告内容暂时无法读取，请稍后再试。"),
        ):
            response = self.client.get("/api/announcements/")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.json()["error"]["code"], "DATA_UNAVAILABLE")


class OutwardLeakTests(SimpleTestCase):
    """对外化检查：页面与只读接口都不得出现路径、文件名、输入特征或内部模块名。"""

    PAGES = ("/", "/stations/", "/sources/")
    APIS = ("/api/stations/", "/api/sources/", "/api/announcements/")

    def test_pages_have_no_internal_details(self):
        for path in self.PAGES:
            with self.subTest(path=path):
                html = outward_text(self.client.get(path).content.decode("utf-8"))
                for token in FORBIDDEN_OUTWARD:
                    self.assertNotIn(token, html, f"{path} 出现了 {token!r}")

    def test_readonly_payloads_have_no_internal_details(self):
        for path in self.APIS:
            with self.subTest(path=path):
                text = json.dumps(self.client.get(path).json(), ensure_ascii=False)
                for token in FORBIDDEN_OUTWARD:
                    self.assertNotIn(token, text, f"{path} 出现了 {token!r}")

    def test_pages_do_not_render_template_comments(self):
        for path in self.PAGES:
            with self.subTest(path=path):
                html = self.client.get(path).content.decode("utf-8")
                self.assertNotIn("<!--", html)
