# GitHub 版本控制

把 v1.1.1 的改动提交并推送到现有仓库：<https://github.com/yiyuan105/RE_predict_webapp.git>。

- 当前分支：`main`
- 远端：`origin` → `https://github.com/yiyuan105/RE_predict_webapp.git`
- 上一次提交：`0e763c0 RE_predict_webapp_v1.0.0`（**v1.1.0 的改动此前一直留在工作区未提交**，本次会与 v1.1.1 一起提交）
- 本次版本：v1.1.1（前端多页面改版 + 站点模型查看 + 数据来源栏目）

> 以下命令都在项目根目录执行（当前是 `D:\编程\ICT_Re_predict\mysite`）。PowerShell 与 Git Bash 的 git 命令完全相同。

---

## 1. 提交前检查

```bash
git status --short
```

本次应包含的内容（节选）：

```
M  mysite/urls.py
M  mysite/settings.py
M  RE_predict_webapp/views.py
M  RE_predict_webapp/apps.py
M  RE_predict_webapp/config.json
M  RE_predict_webapp/tests.py
M  RE_predict_webapp/static/frontend/css/style.css
M  RE_predict_webapp/static/frontend/js/app.js
M  RE_predict_webapp/static/frontend/README.md
M  manage.py
M  README.md
D  RE_predict_webapp/models_loader.py
D  RE_predict_webapp/openmeteo.py
D  RE_predict_webapp/static/frontend/index.html
?? RE_predict_webapp/content.py
?? RE_predict_webapp/services/
?? RE_predict_webapp/templates/
?? RE_predict_webapp/static/frontend/js/common.js
?? RE_predict_webapp/static/frontend/js/stations.js
?? RE_predict_webapp/static/frontend/js/sources.js
?? 更新日志.md
?? 维修手册.md
?? github版本控制.md
```

> 说明：`RE_predict_webapp/apps.py`、`config.json`、`manage.py`、`mysite/settings.py`、删除的 `models_loader.py` / `openmeteo.py` / `static/frontend/index.html` 属于 v1.1.0 的升级内容，因当时未提交，会一并出现在本次提交里。

检查要点：

1. **284 MB 的 `re-predict-webapp.tar` 不要入库**（`.gitignore` 已加入 `*.tar` / `*.tar.gz`；`git status` 里不应再出现它）。
2. `.tmp*` 临时文件与截图不应出现（`.gitignore` 已忽略）。
3. `staticfiles/`、`db.sqlite3`、`*.pyc` 不应出现（已有忽略规则）。
4. `models/rf_models/*.joblib` 在 v1.0.0 已入库，**本次没有变更**，`git status` 里不应出现它们。
5. `models/Chinageo/`、`models/atoshp/`、`models/soilshp/` 目前未入库（本次之前即如此），`git add -A` 会一并提交（约 11 MB）——线上部署需要这些数据，建议提交。
6. `方案存放/` 是需求文档与版本档案目录，本次之前也未入库；`git add -A` 会一起提交。如果不想把需求文档放进代码仓库，可用 `git add` 逐项指定文件，或把 `方案存放/` 加入 `.gitignore`。

确认没有遗漏、也没有不该提交的文件后再继续。

---

## 2. 提交 v1.1.1

```bash
# 加入本次所有改动
git add -A

# 再确认一次暂存内容（重点看是否有大文件/临时文件）
git status --short

# 提交
git commit -m "RE_predict_webapp v1.1.1：前端多页面改版 + 站点模型查看 + 数据来源栏目（含 v1.1.0 匹配升级）"

# 打标签（可选但推荐，与 v1.0.0 的命名习惯保持一致）
git tag -a v1.1.1 -m "RE_predict_webapp v1.1.1"

# 推送到 GitHub
git push origin main
git push origin v1.1.1
```

如果远端有新提交，先同步再推：

```bash
git pull --rebase origin main
git push origin main
git push origin v1.1.1
```

---

## 3. 首次推送（仅当远端还没有 `main` 时）

仓库已存在且 `main` 已关联 `origin`，通常**不需要**这一段。若换了新仓库：

```bash
git remote remove origin            # 已有 origin 时先移除
git remote add origin https://github.com/yiyuan105/RE_predict_webapp.git
git branch -M main
git push -u origin main
```

---

## 4. 认证方式

**HTTPS（推荐给 Windows）**

```bash
git config --global credential.helper manager
git push origin main       # 弹窗登录 GitHub 账号，或输入 Personal Access Token
```

Token 需要 `repo` 权限：GitHub → Settings → Developer settings → Personal access tokens。

**SSH**

```bash
git remote set-url origin git@github.com:yiyuan105/RE_predict_webapp.git
ssh -T git@github.com      # 首次需把公钥加到 GitHub
git push origin main
```

---

## 5. 关于大文件（模型 238 MB）

- 12 个模型 `models/rf_models/*.joblib` 共约 238 MB，v1.0.0 已入库；单个最大约 32 MB，**低于 GitHub 单文件 100 MB 限制**，无需 LFS 也能推送。
- 仓库总量接近 GitHub 建议的 1 GB 上限时，再考虑把 `models/` 迁到 Git LFS 或发布为 Release 附件（LFS 会重写历史，需谨慎并在团队内约定）：

  ```bash
  git lfs install
  git lfs track "models/rf_models/*.joblib"
  git add .gitattributes
  ```

- `re-predict-webapp.tar`（284 MB）是打包备份，已排除在版本库外；需要分发时用 GitHub Releases 上传，不要提交。

---

## 6. 可选清理：已入库的 `__pycache__`

v1.0.0 把 `RE_predict_webapp/__pycache__/`、`mysite/__pycache__/` 里的 `.pyc` 一并提交了。`.gitignore` 虽已忽略，但已跟踪的文件不会自动移除。想让仓库干净一些，可以单独做一次清理提交：

```bash
git rm -r --cached RE_predict_webapp/__pycache__ mysite/__pycache__
git commit -m "chore：移除已入库的 __pycache__"
git push origin main
```

这只删除索引中的记录，不会删除本地文件；属于可选操作，不影响功能。

---

## 7. 推送后验证

```bash
git log --oneline -3
git ls-remote --heads origin main
git ls-remote --tags origin v1.1.1
```

浏览器打开仓库，确认：

1. 首页文件列表出现 `更新日志.md`、`维修手册.md`、`github版本控制.md`；
2. `RE_predict_webapp/services/` 下有 `features.py`、`catalog.py`、`sources.py`；
3. `RE_predict_webapp/templates/RE_predict_webapp/` 下有 `base.html`、`stations.html`、`sources.html`；
4. 最新提交信息以 `RE_predict_webapp v1.1.1` 开头，标签 `v1.1.1` 可见；
5. 若平台接了自动部署（Render / Railway 等），等构建完成后访问线上 `/stations/`、`/sources/` 确认与本地一致。

---

## 8. 常见问题

| 现象 | 原因 | 处理 |
|------|------|------|
| `push` 被拒（`non-fast-forward`） | 远端有本地没有的提交 | `git pull --rebase origin main` 后重推 |
| `File ... is 284 MB; this exceeds GitHub's file size limit of 100 MB` | 把 tar 或大文件加入了暂存 | `git restore --staged <文件>`；确认 `.gitignore` 含 `*.tar` |
| 推送很慢 / 超时 | 首次推 238 MB 模型 + 历史 | 网络稳定时重试，或改用 SSH；必要时分两次推（先代码后标签） |
| `remote: Permission to ... denied` | 账号无权限或 token 过期 | 重新登录 / 生成有 `repo` 权限的 token |
| 中文文件名在 `git status` 里显示为转义 | Git 的 `core.quotepath` 默认开启 | `git config --global core.quotepath false` |
| 提交后发现漏了文件 | 未 `git add` | `git add <文件>` → `git commit --amend --no-edit`（未推送时）或补一次提交 |
| 需要撤销本次提交（未推送） | — | `git reset --soft HEAD~1` |
| 需要撤销推送（已推送） | — | 优先 `git revert <commit>` 生成反向提交，避免强推影响他人 |

---

## 9. 一次完整的推送流程（可直接复制）

```bash
cd "D:/编程/ICT_Re_predict/mysite"

python manage.py check
python manage.py test RE_predict_webapp

git status --short
git add -A
git status --short
git commit -m "RE_predict_webapp v1.1.1：前端多页面改版 + 站点模型查看 + 数据来源栏目（含 v1.1.0 匹配升级）"
git tag -a v1.1.1 -m "RE_predict_webapp v1.1.1"
git push origin main
git push origin v1.1.1
```

对应的 PowerShell 写法（路径含中文时更稳妥）：

```powershell
Set-Location "D:\编程\ICT_Re_predict\mysite"
python manage.py check
python manage.py test RE_predict_webapp

git status --short
git add -A
git status --short
git commit -m "RE_predict_webapp v1.1.1：前端多页面改版 + 站点模型查看 + 数据来源栏目（含 v1.1.0 匹配升级）"
git tag -a v1.1.1 -m "RE_predict_webapp v1.1.1"
git push origin main
git push origin v1.1.1
```
