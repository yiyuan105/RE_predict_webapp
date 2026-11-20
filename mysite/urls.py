"""URL 配置：前端页面、JSON 预测接口、只读训练情况/来源/公告接口与后台。

路径沿用 v1.1.1（/stations/、/api/stations/），只把页面与接口的内容换成对外口径，
老地址依然可用；公告接口是 v1.1.2 新增的只读通道。
"""

from django.conf import settings
from django.contrib import admin
from django.contrib.staticfiles.views import serve as staticfiles_serve
from django.urls import path

from RE_predict_webapp import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.home, name="home"),
    path("stations/", views.training_page, name="training"),
    path("sources/", views.sources_page, name="sources"),
    path("api/predict/", views.predict_api, name="predict-api"),
    path("api/stations/", views.training_api, name="training-api"),
    path("api/sources/", views.sources_api, name="sources-api"),
    path("api/announcements/", views.announcements_api, name="announcements-api"),
]

# 未安装 WhiteNoise 且关闭 DEBUG 时的兜底，保证部署后样式与脚本仍可访问
if not settings.DEBUG and not getattr(settings, "WHITENOISE_AVAILABLE", False):
    urlpatterns += [path("static/<path:path>", staticfiles_serve, {"insecure": True})]
