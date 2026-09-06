# 论文同步与访问统计后端

生产站 [eeg.yanyinglab.cn](https://eeg.yanyinglab.cn) 使用腾讯云国内站。配置步骤见 [Makers + SCF + COS 指南](../docs/tencent-makers.md)，实际资源和验收见 [生产部署记录](../docs/tencent-production.md)。文档核对日期：2026-09-06。

共享后端负责研究者配置、OpenAlex + Google Scholar 双源同步、人工字段保护、访问统计和公开 JSON API。Astro 前端不接触任何上游 Key，也不直接读取论文 TOML。

## 两种运行方式

| 项目 | 当前生产：Makers / SCF | 本地 / 可选 Docker |
| --- | --- | --- |
| API | `cloud-functions/api/[[default]].py` → `app/cloud_api.py` | Starlette `app/main.py` |
| 同步 | SCF `index.main_handler` → `app/cloud_runtime.py`，每天北京时间 03:30 | CLI `app.cli sync` 或常驻 `app.scheduler` |
| 论文存储 | COS 压缩 SQLite 快照；每次请求在临时目录解包，结束后删除临时文件 | 持久 SQLite `papers.db` |
| 统计存储 | COS 匿名事件对象、每日聚合及累计数 | 独立 SQLite `analytics.db` |
| 健康检查 | `/api/health` | `/health` |
| 环境模板 | `deploy/tencent/.env.example` | `backend/.env.example` |

两种入口复用业务代码，但本地 CLI 不读写生产 COS。Makers API 和 SCF 不依赖 Starlette 生命周期、后台线程或函数本地持久文件。云端代码需兼容 Python 3.10。

Makers Handler 必须显式定义 HTTP 方法，不能使用链式赋值别名。生产 `PAPERS_ALLOWED_ORIGINS` 必须配置正式 HTTPS 来源，避免平台回源 Host 与公开域名不同导致统计请求被拒绝。

## 双源策略

- **OpenAlex 是规范元数据源**：标题、DOI、作者、期刊、年份、分类和论文所属关系都以 OpenAlex 为准。
- **Google Scholar 是核验与引用来源**：后端通过 SerpAPI 的 `google_scholar_author` 接口读取作者论文、总引用、h-index 和 i10-index，不直接抓取 Scholar 页面。
- 每条 Scholar 论文先按“标准化标题 + 年份（允许相差 1 年）”精确匹配；否则进行标题相似度匹配。默认阈值为 `0.94`，并要求第一名至少领先第二名 `0.03`。
- 匹配成功的论文标记为 `confirmed`，API 同时返回 OpenAlex 和 Scholar 两套引用数。两套数字不会相加，也不会静默覆盖来源。
- 未匹配或有歧义的 Scholar 条目写入 `scholar_candidates`，不会自动发布到前端，以免错误认领同名作者的论文。
- OpenAlex 异常会拒绝生成新快照；Scholar 异常只会记录警告并保留上一次 Scholar 数据，不影响 OpenAlex 正常刷新。
- Scholar 返回空列表，或相对上次快照低于 `SCHOLAR_MINIMUM_RATIO`（默认 0.5）时，也按上游异常处理，避免配额/分页故障把大量论文误标为缺失。
- 一次 Scholar 同步每位作者至少消耗一次 SerpAPI 请求，每 100 篇增加一页。应根据账户配额设置同步间隔；默认每天一次。

## 本地启动

```powershell
cd backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
python -m pip install -r requirements-dev.txt
python -m app.cli init
python -m uvicorn app.main:app --reload --port 8000
```

若要启用 Google Scholar 双源核验，在 `backend/.env` 填入：

```dotenv
SERPAPI_API_KEY=你的服务端密钥
```

不填写时系统仍会只用 OpenAlex 工作，并在同步状态中把 Scholar 标记为 `disabled`。密钥只保存在后端环境变量中，不能使用 `PUBLIC_` 前缀。
本地 CLI 和开发服务器会自动读取 `backend/.env`；Docker Compose 则通过 `env_file` 注入同一文件。系统环境变量的优先级高于 `.env`。

另开终端，从仓库根目录启动前端（Node.js `22.21.1`）：

```powershell
cd frontend
npm ci
npm run dev
```

Astro 开发服务器会把 `/api` 代理到 `http://localhost:8000`。

## 添加研究者

首选通过受保护接口添加：

```http
POST /api/admin/researchers
Authorization: Bearer <PAPERS_SYNC_TOKEN>
Content-Type: application/json

{
  "slug": "member-name",
  "name": "成员姓名",
  "nameEn": "Member Name",
  "openalexAuthorId": "A123456789",
  "orcid": "0000-0000-0000-0000",
  "googleScholarId": "...",
  "affiliation": "南京信息工程大学",
  "avatarUrl": "/images/team/member.webp"
}
```

也可以向 `data/researchers.toml` 追加 TOML 格式种子，字段格式参考现有文件；更新线上种子后需要重新部署 Makers 和 SCF，并由后续写入/同步应用。已有生产数据优先通过上述接口维护。同步服务会遍历所有 `active` 研究者；共同论文只保存一次，通过 `researcher_papers` 关联多人。

## 手动同步与代码发布

本地数据库同步：

```powershell
cd backend
python -m app.cli sync
```

生产完整同步可在同名 SCF 函数中使用 `{}` 测试事件执行。每日成功后再执行会跳过当天上游同步，统计汇总仍可运行。需要当天强制重跑时可调用受保护 API：

```http
POST /api/admin/sync
Authorization: Bearer <PAPERS_SYNC_TOKEN>
```

Makers 手动同步预算为 70 秒；SCF 同步预算为 200 秒，总任务预算 250 秒，函数超时为 300 秒。OpenAlex 失败或超时不替换当前快照，写入竞争返回 409；Scholar 降级行为见双源策略。

修改 `backend/app` 中用于云端的模块、`backend/data` 种子、`cloud-functions/requirements.txt` 或 `deploy/scf/index.py` 后，Git 推送会更新 Makers，但 **SCF 仍须上传 CI 生成的内部 ZIP**。完整包在 Linux Python 3.10 下生成；Windows `--source-only` 包不可部署。仅修改 Makers 的 `cloud_api.py` 或 HTTP Handler 不需要更新 SCF，因为它们不包含在 SCF 包内。

## 公开 API

- `GET /api/health`（Makers）；`GET /health`（本地/Docker）
- `GET /api/researchers`
- `GET /api/papers`
- `GET /api/papers?researcher=ying-yan`
- `GET /api/papers?researcher=ying-yan,another-member`
- `GET /api/papers?representative=true&limit=3`
- `GET /api/papers?tag=EEG&year=2026`
- `GET /api/papers/version`
- `GET /api/sync/status`
- `POST /api/analytics/pageview`
- `GET /api/analytics/summary`

论文接口返回 `ETag` 和可配置的 `Cache-Control`。默认 `public, max-age=0, s-maxage=60, stale-while-revalidate=300`：浏览器请求会重新验证，CDN 新鲜期 60 秒，再验证时允许最多 300 秒的过期窗口。已打开页面不持续轮询；刷新或重新打开页面才会重新取数。

单篇论文还会返回：

```json
{
  "citedByCount": 88,
  "citationSource": "googleScholar",
  "citationSources": { "openalex": 73, "googleScholar": 88 },
  "sourceStatus": "confirmed"
}
```

`GET /api/sync/status` 会给出两侧抓取数量、Scholar 匹配数、候选数和降级警告。

## 隐私友好访问统计

全局布局会向
`POST /api/analytics/pageview` 上报当前页面路径，页脚再从
`GET /api/analytics/summary` 读取累计浏览、今日访问和今日访客。

- 不使用 Cookie，不保存原始 IP、User-Agent 或 Referer。
- 服务端使用 `HMAC(日期 + IP + User-Agent)` 生成仅当天有效的匿名访客标识。
- 云端为 30 秒固定窗口去重；本地 SQLite 使用滑动时间间隔。可通过 `ANALYTICS_DEDUPE_SECONDS` 调整，跨固定窗口可能再次计数。
- 只接受站内 10 个公开页面路径，并过滤常见机器人 User-Agent。
- 云端持久保存匿名事件对象，每日 SCF 先汇总统计再同步论文，分批清理超过 32 天且已汇总的事件；调度停止时清理也会停止。永久保存每日聚合数和累计数。
- 本地使用独立 `analytics.db`，在记录访问时清理过期匿名访客明细；不和论文同步共用同一个数据库事务。
- 汇总接口允许 CDN 短缓存，上报接口始终返回 `Cache-Control: no-store`。

生产 `ANALYTICS_HMAC_SECRET` 和 `PAPERS_SYNC_TOKEN` 使用不同的随机值，各至少 32 字符。云端统计缺少足够长的有效密钥时返回 503，不使用固定开发值；实现保留回退到管理口令的兼容逻辑，但已部署环境使用独立密钥。仅本地开发且两者都未设置时才使用固定开发值。若需要排除
管理员自己的浏览器，可在控制台执行：

```js
localStorage.setItem('eeglab.analytics.optout', '1')
```

删除该键即可恢复统计。浏览器启用 Do Not Track 或 Global Privacy Control 时，
前端也不会发送访问记录。

需要人工检查未匹配/歧义记录时，可使用受保护接口：

```http
GET /api/admin/scholar-candidates
Authorization: Bearer <PAPERS_SYNC_TOKEN>
```

已审核决定保存在 `data/scholar_reviews.toml` 并同步写入
`scholar_review_rules`。`accept` 会永久确认并关联论文，`exclude` 会永久排除
撤稿或重复版本；数据库重建或后续同步时不会再次进入候选队列。

## 可选的独立服务器 / Docker 部署

以下不是当前生产站的部署方式；生产 COS 资源不使用这些数据库路径。

复制并填写后端环境文件：

```powershell
if (!(Test-Path backend/.env)) { Copy-Item backend/.env.example backend/.env }
```

然后：

```powershell
docker compose up -d --build
```

服务结构：

- `frontend`：Nginx 托管 Astro 静态文件，并反向代理 `/api/`。
- `paper-api`：Starlette + Uvicorn，只提供 API。
- `paper-scheduler`：独立进程，启动后立即同步，之后按间隔同步。
- `paper-data`：同时持久化 `papers.db` 与独立的 `analytics.db`。

外层 CDN 应长期缓存 `/_astro/` 指纹资源、短缓存 HTML，并尊重 `/api/papers` 的 `ETag` 与 `Cache-Control`。

论文刷新不需要重新构建 Astro，也不需要让浏览器读取 TOML。更新后的 `snapshot_version` 与 `ETag` 会变化；新请求按上述缓存策略重新验证。

## 验证

从仓库根目录安装本地及云端测试依赖后执行：

```powershell
python -m pip install -r backend/requirements-dev.txt -r cloud-functions/requirements.txt
npm run test:backend
```

2026-09-06 的 GitHub CI 在 Linux Python 3.10 上通过 29 项测试。上线验证同时覆盖真实 COS 读写、上海 SCF 双源同步、统计 POST / OPTIONS、来源检查和管理鉴权；这不代表未来定时执行已提前验证，需按生产记录检查最新执行状态。
