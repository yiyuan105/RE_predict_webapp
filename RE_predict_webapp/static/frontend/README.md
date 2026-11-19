# 生态系统呼吸预测 · 前端

白底黑字的页面，零构建、零依赖。页面由 Django 模板渲染，静态文件放在应用的 `static/frontend/` 下。

v1.1.1 起为三页站点：**预测首页**、**站点模型查看**、**数据来源**，公共导航与页脚复用，每页标题下有一段「网页简述」。

## 打开方式

```bash
python manage.py runserver
```

启动后会自动打开 <http://127.0.0.1:8000/>（`manage.py` 里加了自动打开逻辑），也可以手动访问 `/`、`/stations/`、`/sources/`。

## 页面与脚本

| 页面 | 模板 | 脚本 | 数据接口 |
|------|------|------|----------|
| 预测首页 | `templates/RE_predict_webapp/index.html` | `js/app.js` | `GET /api/predict/`（另取 `/api/sources/` 做来源标注） |
| 站点模型查看 | `templates/RE_predict_webapp/stations.html` | `js/stations.js` | `GET /api/stations/`（另取 `/api/sources/` 做来源说明） |
| 数据来源 | `templates/RE_predict_webapp/sources.html` | `js/sources.js` | `GET /api/sources/` |

公共部分：

- `templates/RE_predict_webapp/base.html`：`<head>`、导航、页面标题与网页简述、内容插槽；
- `templates/RE_predict_webapp/_footer.html`：页脚；
- `js/common.js`：`escapeHtml`、`formatText`、`getJson`（统一解析 `ok=false`）、`loadSources()`（同一次请求供结果区标注复用）。

## 预测页功能

- 输入纬度、经度，点击「开始预测」
- 输出预测值 `Re = …`，以及置信度（高 / 中 / 低）与匹配方式
- 结果表新增「气象来源」「分区依据」两行（数据来自 `/api/sources/`，与数据来源页同源）
- 加载时显示用时，可取消请求
- 失败时显示服务端返回的原因
- 支持全角数字与负号，`Enter` 或 `Ctrl / Cmd + Enter` 提交，结果可复制

## 站点模型页功能

- 列出全部站点的编码、名称、经纬度、生态/植被、土壤/气候分区与模型可用状态
- 检索（编码、名称、生态、植被、分区）与四个筛选（生态类型、气候分区、土壤类型、模型状态），下拉项由已加载数据生成
- 展开任一站点查看模型文件名、大小、状态与 6 个输入特征的含义/单位/气象变量
- 「重置筛选」恢复全部站点

## 如何修改文字内容

页面文字分三处：**页面级文案在 `content.py`**，**静态文字在模板里**，**动态提示在各页脚本顶部的 `TEXT`**。改完保存，刷新浏览器即可，不需要重启 Django（若浏览器有缓存，用 `Ctrl + F5` 强制刷新）。

### 一、页面标题 / 网页简述 / 导航 → `RE_predict_webapp/content.py`

```python
PAGES["home"] = Page(
    key="home",
    title="生态系统呼吸预测",
    brief="输入经纬度，先判断是否落在中国陆地范围内……",
    template="index.html",
    url_name="home",
    nav_label="预测",
)
```

改 `title` / `brief` / `nav_label` 即可；新增页面时在这里加一项，`NAV_PAGES` 里追加后导航会自动出现入口。

### 二、静态文字 → 模板

打开对应模板，每条文字上方都有 `<!-- 文案：… -->` 注释，直接改标签里的文字即可：

| 想改的内容 | 位置 / 关键词 |
| --- | --- |
| 输入框名称 | `<label for="lat">纬度</label>`、`<label for="lon">经度</label>` |
| 输入框里的占位示例 | `placeholder="39.90"`、`placeholder="116.40"` |
| 默认的范围提示 | `<p class="hint" id="form-message">` |
| 按钮文字 | `<span id="submit-label">开始预测</span>` |
| 输出框标题 | `<h2 class="result-title">预测结果</h2>` |
| 未预测时的文字 | `<p class="placeholder">尚未预测</p>` |
| 站点页筛选标签 | `stations.html` 的 `<label for="filter-…">` |
| 页脚说明 | `_footer.html` |

> 注意：`id`、`class`、`name`、`data-*`、`{% static … %}`、`{% url … %}` 这些不要改动，JavaScript 和接口靠它们工作。

### 三、动态文字 → 各页脚本顶部的 `TEXT`

| 文件 | 负责的文字 |
|------|------------|
| `js/app.js` | 预测中/加载中、取消、错误提示、结果行标签（含「气象来源」「分区依据」）、复制状态 |
| `js/stations.js` | 站点加载中/失败、统计句、模型可用/不可用、详情标签、空结果 |
| `js/sources.js` | 来源加载中/失败、分组计数、字段名（位置/用途/更新方式/说明/对应文档） |
| `js/common.js` | 通用错误文案与错误码兜底 |

带参数的字段写成函数，冒号后面是拼接进去的变量，例如：

```js
loaded: (shown, total) => `共 ${total} 个站点，当前显示 ${shown} 个。`,
```

只改引号里的中文即可，`${…}` 和逗号不要删。

> 提示：预测页的默认提示会被脚本读取，校验失败后再恢复，所以只需改模板那一处即可，不用在 JS 里再写一遍。

## 数据来源单一来源

- 页面上的来源名称、路径、更新方式都来自 `/api/sources/`（后端 `services/sources.py`），**不要在 HTML/JS 里另写一份**；
- 结果区的「气象来源」「分区依据」使用同一接口返回的 `weather.label` 与 `shorts`，改数据来源页文案时两处同步；
- 模型输入特征的含义、单位、气象变量来自 `/api/stations/` 的 `features`（后端 `services/features.py`）。

## 文件

```
RE_predict_webapp/
├── content.py                              页面标题 / 网页简述 / 导航
├── templates/RE_predict_webapp/
│   ├── base.html                           公共框架（导航、标题、简述）
│   ├── _footer.html                        公共页脚
│   ├── index.html                          预测首页
│   ├── stations.html                       站点模型查看页
│   └── sources.html                        数据来源页
└── static/frontend/
    ├── css/style.css                       样式（三页共用）
    ├── js/common.js                        公共请求与工具
    ├── js/app.js                           预测页逻辑
    ├── js/stations.js                      站点模型页逻辑
    ├── js/sources.js                       数据来源页逻辑
    ├── assets/favicon.svg                  图标
    ├── preview.jpg                         v1.0 页面截图（未更新）
    └── README.md                           本文件
```

## 后端接口（仅供对照）

- `GET /api/predict/?lat=纬度&lon=经度` → 预测值、置信度、站点、匹配、气象；
- `GET /api/stations/` → 站点清单、模型状态、特征说明；
- `GET /api/sources/` → 六类数据来源、特征、气象变量。

成功外层为 `{"ok": true, …}`；失败为 `{"ok": false, "error": {"code": "…", "message": "…"}}`，页面会直接展示 `message`。

旧的 `GET /?lat=…&lon=…` 纯文本接口仍然保留，供已有脚本调用。
