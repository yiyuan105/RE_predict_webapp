# 生态系统呼吸预测（RE_predict_webapp）

基于 Django 的生态系统呼吸（Re）在线预测站点：输入经纬度，先判断是否落在中国陆地内，再按气候分区与土壤分区逐级匹配最近的观测站，调用该站的随机森林模型预测 Re，并给出匹配置信度。

v1.1.1 起站点扩展为多页面：**预测首页**、**站点模型查看**、**数据来源**，每页顶部都有简短的用途说明。

## 快速开始

```bash
pip install -r requirements.txt
python manage.py runserver
```

浏览器访问 <http://127.0.0.1:8000/>，输入经纬度即可预测。

## 页面

| 页面 | 地址 | 说明 |
|------|------|------|
| 预测首页 | `/` | 输入经纬度 → 预测值、置信度、匹配方式、站点、距离、坐标，并标注气象来源与分区依据 |
| 站点模型查看 | `/stations/` | 全部站点的编码、名称、经纬度、生态/植被、土壤/气候分区、模型可用状态与输入特征；支持检索、筛选、展开详情 |
| 数据来源 | `/sources/` | 六类数据来源（模型 / 地理 / 分区 / 气象 / 配置）的名称、类型、路径或地址、用途与更新方式 |

## 接口

| 用途 | 地址 | 返回 |
|------|------|------|
| 预测页 | `GET /` | HTML |
| 站点模型页 | `GET /stations/` | HTML |
| 数据来源页 | `GET /sources/` | HTML |
| JSON 预测接口 | `GET /api/predict/?lat=36.83&lon=116.57` | JSON（预测值、置信度、匹配站点、分区信息、气象特征） |
| 站点模型接口 | `GET /api/stations/` | JSON（站点清单、模型文件状态、特征说明；只读） |
| 数据来源接口 | `GET /api/sources/` | JSON（六类数据来源、特征与气象变量；只读） |
| 旧版纯文本接口 | `GET /?lat=36.83&lon=116.57` | 纯文本（保留兼容） |

错误约定沿用 v1.1.0：`ok=false` 时 `error.code` 供程序判断、`error.message` 可直接展示。预测接口状态码：`INVALID_INPUT`(400)、`OUT_OF_CHINA`(422)、`WEATHER_UNAVAILABLE`/`MODEL_UNAVAILABLE`(503)、`DATA_UNAVAILABLE`/`INTERNAL_ERROR`(500)；新增只读接口缺数据时返回 `DATA_UNAVAILABLE`(500) 的可读提示，不会让页面崩溃。

## 部署

```bash
python manage.py collectstatic --noinput
gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT
```

根目录的 `Procfile` 已写好同样的启动命令，可直接被 Heroku / Railway 等平台识别。

详细的部署步骤、环境变量与故障排查见 [维修手册](维修手册.md)；本次升级内容见 [更新日志](更新日志.md)；推送代码到 GitHub 见 [GitHub 版本控制](github版本控制.md)。

## 目录

```
mysite/                        Django 项目配置（settings / urls / wsgi）
RE_predict_webapp/
├── content.py                 页面标题、网页简述与导航项（改文案只动这里）
├── views.py                   页面、预测接口与只读站点/来源接口
├── services/                  业务层：配置、地理、站点、匹配、模型、气象、来源目录
├── templates/RE_predict_webapp/
│   ├── base.html              公共框架：导航、标题、网页简述、页脚
│   ├── index.html             预测首页
│   ├── stations.html          站点模型查看页
│   ├── sources.html           数据来源页
│   └── _footer.html           公共页脚
├── static/frontend/           样式与脚本（common.js 供三个页面共用）
├── config.json                站点清单、模型特征、气象变量
└── tests.py                   43 个测试
models/                        数据：中国边界 geojson、气候/土壤 shp、12 个站点模型
manage.py                      Django 管理入口
```

## 测试

```bash
python manage.py check
python manage.py test RE_predict_webapp
```
