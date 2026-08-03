# 论文后端

独立后端负责研究者配置、OpenAlex + Google Scholar 双源同步、人工字段保护、SQLite 持久化和公开 JSON API。Astro 前端不接触任何上游 Key，也不直接读取论文 TOML。

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
Copy-Item .env.example .env
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

另开终端启动前端：

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

也可以在首次建库前向 `data/researchers.toml` 追加同结构条目。同步服务会遍历所有 `active` 研究者；共同论文只保存一次，通过 `researcher_papers` 关联多人。

## 手动同步

```powershell
cd backend
python -m app.cli sync
```

或调用：

```http
POST /api/admin/sync
Authorization: Bearer <PAPERS_SYNC_TOKEN>
```

## 公开 API

- `GET /health`
- `GET /api/researchers`
- `GET /api/papers`
- `GET /api/papers?researcher=ying-yan`
- `GET /api/papers?researcher=ying-yan,another-member`
- `GET /api/papers?representative=true&limit=3`
- `GET /api/papers?tag=EEG&year=2026`
- `GET /api/papers/version`
- `GET /api/sync/status`

论文接口返回 `ETag` 和可配置的 `Cache-Control`。默认 CDN 最多缓存 60 秒，浏览器每次会重新验证。

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

需要人工检查未匹配/歧义记录时，可使用受保护接口：

```http
GET /api/admin/scholar-candidates
Authorization: Bearer <PAPERS_SYNC_TOKEN>
```

已审核决定保存在 `data/scholar_reviews.toml` 并同步写入
`scholar_review_rules`。`accept` 会永久确认并关联论文，`exclude` 会永久排除
撤稿或重复版本；数据库重建或后续同步时不会再次进入候选队列。

## 独立部署

复制并填写后端环境文件：

```powershell
Copy-Item backend/.env.example backend/.env
```

然后：

```powershell
docker compose up -d --build
```

服务结构：

- `frontend`：Nginx 托管 Astro 静态文件，并反向代理 `/api/`。
- `paper-api`：Starlette + Uvicorn，只提供 API。
- `paper-scheduler`：独立进程，启动后立即同步，之后按间隔同步。
- `paper-data`：SQLite 持久卷。

外层 CDN 应长期缓存 `/_astro/` 指纹资源、短缓存 HTML，并尊重 `/api/papers` 的 `ETag` 与 `Cache-Control`。

论文刷新不需要重新构建 Astro，也不需要让浏览器读取 TOML。调度器更新 SQLite 后，`snapshot_version` 与 `ETag` 会变化；CDN 最多保留 `s-maxage` 指定的旧 JSON（默认 60 秒），随后会自动重新验证。
