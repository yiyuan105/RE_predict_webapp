# 生态系统呼吸预测（RE_predict_webapp）

## 网站 https://ecofluxforecast.cn/

基于 Django 的生态系统呼吸（Re）在线预测站点：输入经纬度 → 判断是否落在中国陆地范围内 → 按气候分区与土壤分区逐级匹配最近的观测站 → 调用该站的随机森林模型预测 Re，并给出匹配置信度。

v1.1.2 起对外展示口径收敛：**页面不再出现任何文件地址、路径、文件名、模型文件或输入特征**；原"站点模型查看"改为"模型训练情况"，原"数据来源"改为署名式来源注明，并新增公告栏目与首页「左三框 + 右公告边栏」布局。

## 快速开始

```bash
pip install -r requirements.txt
python manage.py runserver
```

浏览器访问 <http://127.0.0.1:8000/>，输入经纬度即可预测。

## 页面

| 页面 | 地址 | 说明 |
|------|------|------|
| 预测首页 | `/` | **左侧「首页 / 站点 / 数据来源」三个导航框** + 中间预测区 + **右侧公告边栏**；输入经纬度 → 预测值、置信度、匹配方式、站点、距离、坐标，并在结果区署名气象来源与分区依据 |
| 站点（模型训练情况） | `/stations/` | 按站点展示训练 / 测试样本数、训练集与测试集的 MSE 与 R²、模型类别；支持按站点编码检索、按测试集 R² 区间筛选 |
| 数据来源 | `/sources/` | 五类来源的署名式说明：预测模型 / 地理边界 / 气候分区 / 土壤分区 / 气象数据，每项只有名称、类型、用途与更新方式 |

每个页面标题下都有一段「网页简述」，说明这页做什么、给谁用、怎么用；文案集中在 `RE_predict_webapp/content.py`。

## 首页布局

- **左侧栏**：自上而下三个框——「首页」「站点」「数据来源」，作为站点级导航入口，当前页有边框高亮；
- **主内容区**：经纬度输入、开始预测、预测结果；
- **右侧边栏**：公告（按发布时间倒序，可滚动，最新在上）；
- 窄屏 / 移动端按响应式规则堆叠为单列，表格与卡片不出现横向溢出。

## 对外能力

- **预测结果**：预测值 Re、置信度（高 / 中 / 低）、匹配方式、匹配站点、距离、输入坐标，并署名气与分区来源；
- **模型训练情况**：每个站点都完整展示训练 / 测试样本数与两个数据集的 MSE、R²（四项指标齐全）与模型类别，展示精度由配置集中控制；
- **来源注明**：只说明「是什么、用来做什么、怎么更新」，与结果区署名同源；
- **公告**：服务端发布与维护（标题 + 正文 + 发布时间），首页右侧边栏倒序展示，对外只有只读接口；
- **对外最小化**：三页页面与三个只读接口的返回内容中都不含路径、文件名、模型文件、输入特征或内部变量。

## 接口

| 用途 | 地址 | 返回 |
|------|------|------|
| 首页 / 预测页 | `GET /` | HTML（带 `lat`/`lon` 时仍走旧纯文本输出） |
| 训练情况页 | `GET /stations/` | HTML |
| 来源注明页 | `GET /sources/` | HTML |
| JSON 预测接口 | `GET /api/predict/?lat=36.83&lon=116.57` | JSON（预测值、置信度、匹配站点、分区信息、气象信息） |
| 训练情况接口 | `GET /api/stations/` | JSON（`code`、训练/测试样本数、四项 MSE/R²、`model_type`；只读） |
| 来源注明接口 | `GET /api/sources/` | JSON（`key`、`name`、`category`、`purpose`、`update`；只读） |
| 公告接口 | `GET /api/announcements/` | JSON（`title`、`body`、`published_at`，按发布时间倒序；只读） |
| 旧版纯文本接口 | `GET /?lat=36.83&lon=116.57` | 纯文本（保留兼容） |

错误约定沿用 v1.1.0：`ok=false` 时 `error.code` 供程序判断、`error.message` 可直接展示。预测接口状态码：`INVALID_INPUT`(400)、`OUT_OF_CHINA`(422)、`WEATHER_UNAVAILABLE`/`MODEL_UNAVAILABLE`(503)、`DATA_UNAVAILABLE`/`INTERNAL_ERROR`(500)；三个只读接口缺数据时返回 `DATA_UNAVAILABLE`(500) 的可读提示，写请求返回 405。

## 配置与运维

| 想改的内容 | 位置 |
|------------|------|
| 站点清单、模型输入定义 | `RE_predict_webapp/config.json` 的 `stations` / `features` / `variables` |
| 训练情况（样本数、MSE、R²、模型类别、展示精度） | `RE_predict_webapp/config.json` 的 `training` |
| 公告（标题 / 正文 / 发布时间 / 下架） | `RE_predict_webapp/announcements.json` |
| 来源注明 | `RE_predict_webapp/services/sources.py` |
| 页面标题、网页简述、导航三框文案 | `RE_predict_webapp/content.py` |

详细步骤见 [维修手册](方案存放/维修手册.md)（数据更新、匹配与气象逻辑、对外内容维护、接口字段范围、故障排查）。

## 部署与更新

部署完全使用 Docker，步骤（镜像构建、`docker-compose` 编排、端口与环境变量、数据/模型卷挂载、首次部署、更新与回滚、健康检查与故障排查）统一见：

- [《云端部署与更新》](方案存放/开发文档/云端部署与更新.md)
- 环境变量模板：`.env.example`（复制为 `.env` 后填真实值，`.env` 不入库）
- 编排文件：`docker-compose.yml`

## 文档

- [更新日志 v1.1.2](方案存放/更新日志/v1.1.2更新日志.md)（历史版本见同目录 `v1.1.0` / `v1.1.1`）
- [维修手册](方案存放/维修手册.md)（运维，不含部署步骤）
- [云端部署与更新](方案存放/开发文档/云端部署与更新.md)（部署唯一来源）
- [GitHub 版本控制](github版本控制.md)

## 仓库结构（开发参考）

```
mysite/                        Django 项目配置（settings / urls / wsgi）
RE_predict_webapp/
├── content.py                 页面标题、网页简述、导航与首页左侧三框文案
├── views.py                   页面、预测接口、只读训练/来源/公告接口
├── config.json                站点清单、模型输入定义、训练情况配置
├── announcements.json         公告条目
├── services/                  业务层：配置、地理、站点、匹配、模型、气象、三个对外目录
├── templates/RE_predict_webapp/
│   ├── base.html              公共框架：导航、标题、网页简述、页脚
│   ├── index.html             预测首页（三栏布局）
│   ├── training.html          模型训练情况页
│   ├── sources.html           来源注明页
│   └── _footer.html           公共页脚
├── static/frontend/           样式与脚本（common / app / training / notices / sources）
└── tests.py                   67 个测试
models/                        数据：中国边界 geojson、气候/土壤 shp、12 个站点模型
docker-compose.yml             容器编排（部署见《云端部署与更新》）
manage.py                      Django 管理入口
```

## 测试

```bash
python manage.py check
python manage.py test RE_predict_webapp
```
