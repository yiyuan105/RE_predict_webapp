"""Django settings for mysite project.

部署时用环境变量覆盖：DJANGO_DEBUG / DJANGO_SECRET_KEY / DJANGO_ALLOWED_HOSTS /
DJANGO_CSRF_TRUSTED_ORIGINS，以及业务配置 MODEL_DATA_DIR 等（见《维修手册》）。
"""

import importlib.util
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "true").strip().lower() in {"1", "true", "yes", "on"}

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or "django-insecure-cuz&dt53bj+(s$)5$+ga$+d8c0oti65je9tnx&ee9_68j^9ifo"


def _env_list(name: str, default: list[str]) -> list[str]:
    values = [item.strip() for item in os.environ.get(name, "").split(",") if item.strip()]
    return values or default


# 未配置时：开发环境只接受本机，线上接受任意 Host（部署后建议显式设置）
ALLOWED_HOSTS = _env_list("DJANGO_ALLOWED_HOSTS", ["127.0.0.1", "localhost"] if DEBUG else ["*"])
CSRF_TRUSTED_ORIGINS = _env_list("DJANGO_CSRF_TRUSTED_ORIGINS", [])

# 托管平台通常由反向代理转发 HTTPS，按代理头判断实际协议
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# 线上（DEBUG=False）默认启用 Cookie 安全属性；平台已提供 HTTPS 时无需额外配置
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "RE_predict_webapp",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# 生产环境用 WhiteNoise 直接提供静态文件（需要 pip install whitenoise）
WHITENOISE_AVAILABLE = importlib.util.find_spec("whitenoise") is not None
if WHITENOISE_AVAILABLE:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")

ROOT_URLCONF = "mysite.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "mysite.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"
        if WHITENOISE_AVAILABLE
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}

# ---------------------------------------------------------------------------
# 业务配置
# ---------------------------------------------------------------------------

# 根目录 models/ 的位置；数据目录换位置时只改这一项
MODEL_DATA_DIR = Path(os.environ.get("MODEL_DATA_DIR", BASE_DIR / "models"))
# 同时缓存在内存中的随机森林模型数量（单个约 20MB）
RF_MODEL_CACHE_SIZE = int(os.environ.get("RF_MODEL_CACHE_SIZE", "4"))
# Open-Meteo 请求参数：预报源、模型（留空用 best_match）、超时与预报天数
WEATHER_ENDPOINT = os.environ.get("WEATHER_ENDPOINT", "https://api.open-meteo.com/v1/forecast")
WEATHER_MODEL = os.environ.get("WEATHER_MODEL", "")
WEATHER_TIMEOUT_SECONDS = float(os.environ.get("WEATHER_TIMEOUT_SECONDS", "20"))
WEATHER_FORECAST_DAYS = int(os.environ.get("WEATHER_FORECAST_DAYS", "1"))

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "RE_predict_webapp": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # 4xx（如境外坐标）属于正常业务反馈，只记录 5xx
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
    },
}
