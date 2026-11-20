# 生态系统呼吸预测 · 前端

白底黑字的页面，零构建、零依赖。页面由 Django 模板渲染，静态文件放在应用的 `static/frontend/` 下。

v1.1.2 起对外化：**页面不出现文件地址、路径、文件名、模型文件与输入特征**。站点页改为「模型训练情况」，来源页改为署名式「来源注明」，首页改为「左侧三个导航框 + 中间预测区 + 右侧公告边栏」。

## 打开方式

```bash
python manage.py runserver
```

启动后会自动打开 <http://127.0.0.1:8000/>（`manage.py` 里加了自动打开逻辑），也可以手动访问 `/`、`/stations/`、`/sources/`。

## 页面与脚本

| 页面 | 模板 | 脚本 | 数据接口 |
|------|------|------|----------|
| 预测首页 | `templates/RE_predict_webapp/index.html` | `js/app.js` + `js/notices.js` | 预测接口；另取来源接口做署名、取公告接口填右侧边栏 |
| 模型训练情况 | `templates/RE_predict_webapp/training.html` | `js/training.js` | 训练情况接口 |
| 数据来源注明 | `templates/RE_predict_webapp/sources.html` | `js/sources.js` | 来源接口 |

公共部分：

- `templates/RE_predict_webapp/base.html`：`<head>`、顶部导航、页面标题与网页简述、`{% block body %}`；
- `templates/RE_predict_webapp/_footer.html`：页脚；
- `js/common.js`：`escapeHtml`、`formatText`、`getJson`（统一解析 `ok=false`）、`loadSources()`、`sourceNames()`（来源 key → 名称，结果区署名与来源页共用同一次请求）。

首页布局（`css/style.css` 的 `.layout`）：

- 左栏 `.rail`：三个 `.rail-box`，自上而下「首页 / 站点 / 数据来源」，当前页加 `is-active`；
- 主内容 `.main`：表单与结果区；
- 右侧 `.sidebar`：公告标题、状态行与 `.notice-list`（倒序、可滚动）；
- `≤900px` 时三栏堆叠为单列，`≤560px` 表单与来源卡片单列。

## 预测页功能

- 输入纬度、经度，点击「开始预测」
- 输出预测值 `Re = …`，以及置信度（高 / 中 / 低）与匹配方式
- 结果表包含「气象来源」「分区依据」两行，文案取自来源接口（署名式，如「来源：中国土壤分区、中国气候分区」）
- 加载时显示用时，可取消请求
- 失败时显示服务端返回的原因
- 支持全角数字与负号，`Enter` 或 `Ctrl / Cmd + Enter` 提交，结果可复制

## 训练情况页功能

- 8 列表格：站点、训练样本数、测试样本数、训练集 MSE / R²、测试集 MSE / R²、模型类别
- 展示精度由接口返回的 `display` 决定（后端集中配置，默认 MSE 与 R² 各 4 位小数）
- 检索按站点编码；「测试集 R²」下拉按区间筛选（0.95 以上 / 0.90 ~ 0.95 / 0.90 以下）；「重置筛选」恢复全部
- 筛选结果为空时表格内显示提示行，不出现横向溢出（表格在容器内滚动）

## 公告边栏

- 读取公告接口，按后端返回顺序（发布时间倒序）渲染紧凑卡片；
- 标题与日期同行，正文按空行分段；
- 加载失败显示可读提示与「重试」；没有公告时显示「暂无公告。」；
- 桌面端边栏吸顶、列表可滚动；窄屏时排到主内容下方。

## 来源注明页功能

- 五张署名卡片按配置顺序平铺，每张卡片只有名称、类型（徽标）、用途、更新方式；
- 不显示路径、地址、文件名、变量名——这些不属于对外可见层。

## 如何修改文字内容

页面文字分三处：**页面级文案在 `content.py`**，**静态文字在模板里**，**动态提示在各页脚本顶部的 `TEXT`**。改完保存，刷新浏览器即可，不需要重启 Django（若浏览器有缓存，用 `Ctrl + F5` 强制刷新）。

### 一、页面标题 / 网页简述 / 导航 / 左侧三框 → `RE_predict_webapp/content.py`

```python
PAGES["home"] = Page(
    key="home",
    title="生态系统呼吸预测",
    brief="输入经纬度，即可获得该位置的生态系统呼吸（Re）预测值、匹配置信度与匹配站点。……",
    template="index.html",
    url_name="home",
    nav_label="首页",     # 顶部导航
    box_label="首页",     # 首页左侧三框
    box_hint="返回预测",
)
```

改 `title` / `brief` / `nav_label` / `box_label` / `box_hint` 即可；新增页面时在这里加一项并加入 `NAV_PAGES`，顶部导航与左侧三框会同时出现入口。

### 二、静态文字 → 模板

打开对应模板，`{# 文案：… #}` 注释标出了该改哪里，直接改标签里的文字：

| 想改的内容 | 位置 / 关键词 |
| --- | --- |
| 输入框名称 | `<label for="lat">纬度</label>`、`<label for="lon">经度</label>` |
| 输入框里的占位示例 | `placeholder="39.90"`、`placeholder="116.40"` |
| 默认的范围提示 | `<p class="hint" id="form-message">` |
| 按钮文字 | `<span id="submit-label">开始预测</span>` |
| 输出框标题 | `<h2 class="result-title">预测结果</h2>` |
| 未预测时的文字 | `<p class="placeholder">尚未预测</p>` |
| 首页左侧三框小标题 | `index.html` 里的 `<h2 class="section-title">导航</h2>` |
| 公告边栏标题 | `index.html` 里的 `<h2 class="section-title" id="notice-title">公告</h2>` |
| 训练页筛选标签与表头 | `training.html` 的 `<label for="…">` 与 `<th scope="col">` |
| 页脚说明 | `_footer.html` |

> 注意：`id`、`class`、`name`、`data-*`、`{% static … %}`、`{% url … %}` 这些不要改动，JavaScript 和接口靠它们工作。
>
> **模板注释必须用 `{# … #}`，不要用 `<!-- … -->`**：HTML 注释会输出到页面源码里，写了文件名就等于对外暴露内部信息（测试会检查）。

### 三、动态文字 → 各页脚本顶部的 `TEXT`

| 文件 | 负责的文字 |
|------|------------|
| `js/app.js` | 预测中/加载中、取消、错误提示、结果行标签（含「气象来源」「分区依据」「来源」）、复制状态 |
| `js/training.js` | 训练情况加载中/失败、统计句、空结果、重试 |
| `js/sources.js` | 来源加载中/失败、统计句、字段名（用途 / 更新方式） |
| `js/notices.js` | 公告加载中/失败、暂无公告、重试 |
| `js/common.js` | 通用错误文案与错误码兜底 |

带参数的字段写成函数，冒号后面是拼接进去的变量，例如：

```js
loaded: (shown, total) => `共 ${total} 个站点，当前显示 ${shown} 个。`,
```

只改引号里的中文即可，`${…}` 和逗号不要删。

> 提示：预测页的默认提示会被脚本读取，校验失败后再恢复，所以只需改模板那一处即可，不用在 JS 里再写一遍。

## 数据来源单一来源

- **训练情况**：来自后端 `services/training.py`（数据在 `config.json` 的 `training`），页面只按返回的 `display` 格式化；
- **来源注明**：来自后端 `services/sources.py`，**不要在 HTML/JS 里另写一份**；
- **公告**：来自后端 `services/announcements.py`（数据在 `announcements.json`），页面只负责展示顺序与排版；
- 结果区的「气象来源」「分区依据」使用来源接口返回的 `name`，改文案时结果区与来源页同步。

## 文件

```
RE_predict_webapp/
├── content.py                              页面标题 / 网页简述 / 导航与三框文案
├── templates/RE_predict_webapp/
│   ├── base.html                           公共框架（导航、标题、简述、内容插槽）
│   ├── _footer.html                        公共页脚
│   ├── index.html                          预测首页（左三框 + 主内容 + 公告边栏）
│   ├── training.html                       模型训练情况页
│   └── sources.html                        来源注明页
└── static/frontend/
    ├── css/style.css                       样式（三页共用）
    ├── js/common.js                        公共请求与工具
    ├── js/app.js                           预测页逻辑
    ├── js/training.js                      训练情况页逻辑
    ├── js/notices.js                       首页公告边栏逻辑
    ├── js/sources.js                       来源注明页逻辑
    ├── assets/favicon.svg                  图标
    ├── preview.jpg                         v1.0 页面截图（未更新）
    └── README.md                           本文件
```

## 后端接口（仅供对照）

- `GET /api/predict/?lat=纬度&lon=经度` → 预测值、置信度、站点、匹配、气象；
- `GET /api/stations/` → 各站点训练情况（8 个对外字段 + `display`）；
- `GET /api/sources/` → 五项来源注明；
- `GET /api/announcements/` → 公告（倒序）。

成功外层为 `{"ok": true, …}`；失败为 `{"ok": false, "error": {"code": "…", "message": "…"}}`，页面会直接展示 `message`。只读接口均不接受写请求（405）。

旧的 `GET /?lat=…&lon=…` 纯文本接口仍然保留，供已有脚本调用。
