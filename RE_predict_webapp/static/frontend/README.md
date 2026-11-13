# 生态系统呼吸预测 · 前端

白底黑字的静态页面，零构建、零依赖。放在 Django 应用的 `static/` 目录里，由开发服务器直接提供。

**没有改动预测接口**：页面只是调用现有的 `GET /?lat=…&lon=…` 接口，解析它返回的纯文本。

## 打开方式

```bash
python manage.py runserver
```

启动后会自动打开下面的页面（`manage.py` 里加了几行启动逻辑）。如果没有弹出，手动访问：

```
http://127.0.0.1:8000/static/frontend/index.html
```

> 当前 `DEBUG = True`，Django 会自动提供 `static/` 下的文件。
> 如果开发服务器在新建 `static/` 目录之前就已经启动，需要重启一次（Django 启动时会缓存应用的静态目录）。

## 页面功能

- 输入纬度、经度，点击「开始预测」
- 输出框显示预测值 `Re = …`、匹配站点、距离、坐标
- 加载时显示用时，可取消请求
- 失败时显示原因，可展开服务器原始返回
- 支持全角数字与负号，`Enter` 或 `Ctrl / Cmd + Enter` 提交，结果可复制

## 如何修改文字内容

页面文字分两处：**静态文字在 `index.html`**，**动态提示在 `js/app.js`**。改完保存，刷新浏览器即可，不需要重启 Django（若浏览器有缓存，用 `Ctrl + F5` 强制刷新）。

### 一、静态文字 → `index.html`

打开 `index.html`，每条文字上方都有 `<!-- 文案：… -->` 注释，直接改标签里的文字即可：

| 想改的内容 | 位置 / 关键词 |
| --- | --- |
| 页面标题（浏览器标签页 + 大标题） | `<title>生态系统呼吸预测</title>`、`<h1>` |
| 标题下的一句话说明 | `<p class="intro">` |
| 输入框名称 | `<label for="lat">纬度</label>`、`<label for="lon">经度</label>` |
| 输入框里的占位示例 | `<input … placeholder="39.90">`、`placeholder="116.40"` |
| 默认的范围提示 | `<p class="hint" id="form-message">` |
| 按钮文字 | `<span id="submit-label">开始预测</span>` |
| 输出框标题 | `<h2 class="result-title">预测结果</h2>` |
| 未预测时的文字 | `<p class="placeholder">尚未预测</p>` |
| 页脚说明 | `<footer class="footer">` 里的两行 `<p>` |

> 注意：`id`、`class`、`name`、`data-*` 这些属性请不要改动，JavaScript 靠它们工作。

### 二、动态文字 → `js/app.js` 顶部的 `TEXT`

打开 `js/app.js`，最上面的 `const TEXT = { … }` 集中了所有由脚本生成的文字：

| 字段 | 含义 |
| --- | --- |
| `submitting` | 请求进行中，按钮上的文字 |
| `loading` | 请求进行中，输出框里的标题 |
| `elapsed` | 用时文案，`(seconds) => ...` |
| `cancel` | 「取消」链接 |
| `cancelled` / `cancelledHint` | 取消后的标题与说明 |
| `valueSymbol` | 数值前的符号，默认 `Re =` |
| `copyValueLabel` | 复制结果时「预测值」的标签 |
| `station` / `distance` / `coords` | 输出框里三行的标签 |
| `copy` / `copied` / `copyFailed` | 复制按钮的三种状态 |
| `errorTitle` / `errorRaw` | 失败标题、展开原文的链接文字 |
| `errors.required` | 未填写，例：`请输入纬度。` |
| `errors.numeric` | 不是数字 |
| `errors.range` | 超出范围 |
| `errors.http` / `timeout` / `network` | 服务器错误、超时、连接失败 |
| `errors.unknown` / `modelLoad` / `invalidValue` / `predict` | 解析失败、模型加载失败、无效数值、模型报错 |

带参数的字段写成函数，冒号后面是拼接进去的变量，例如：

```js
range: (name, min, max) => `${name}需在 ${min} ~ ${max} 之间。`,
```

只改引号里的中文即可，`${…}` 和逗号不要删。

> 提示：`index.html` 里的默认提示会被脚本读取，校验失败后再恢复，所以只需改 HTML 那一处即可，不用在 JS 里再写一遍。

## 文件

```
frontend/
├── index.html
├── css/style.css
├── js/app.js
├── assets/favicon.svg
├── preview.jpg
└── README.md
```

## 后端接口（仅供对照）

请求 `GET /?lat=纬度&lon=经度`，返回纯文本：

```
您的位置:(39.9, 116.4)。
匹配到最近的站点: YCA (禹城站冬小麦-夏玉米复种农田)
距离: 3.08 度
预测值: 11.15
```

前端按行解析这四类信息；后端返回的报错文字也会被识别并展示。
