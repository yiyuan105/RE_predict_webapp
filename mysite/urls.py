"""URL 配置：前端页面、JSON 预测接口、只读站点/来源接口与后台。"""

from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import path

from RE_predict_webapp import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("stations/", views.stations_page, name="stations"),
    path("sources/", views.sources_page, name="sources"),
    path("api/predict/", views.predict_api, name="predict-api"),
    path("api/stations/", views.stations_api, name="stations-api"),
    path("api/sources/", views.sources_api, name="sources-api"),
]

# 未安装 WhiteNoise 且关闭 DEBUG 时的兜底，保证部署后样式与脚本仍可访问
if not settings.DEBUG and not getattr(settings, "WHITENOISE_AVAILABLE", False):
    urlpatterns += [path("static/<path:path>", staticfiles_serve, {"insecure": True})]
