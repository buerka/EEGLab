# 论文平台架构与改造记录

本文描述当前代码的数据流，并保留改造背景。核对日期：2026-09-06。生产站已部署到腾讯云国内站；接管项目先读 [接管说明](handoff.md)，具体操作见 [部署指南](tencent-makers.md)。

## 当前架构

| 层 | 当前实现 |
| --- | --- |
| 静态页面 | Astro 6 + React 18，10 个页面，由 Makers 发布 |
| 浏览器数据 | `frontend/src/lib/publications.ts` 请求 `/api/papers`，页面不直接导入论文 TOML |
| 公开 API | Makers Python Handler → `backend/app/cloud_api.py` |
| 定时任务 | 上海 SCF → `cloud_runtime.scheduled_job`，每天北京时间 03:30 |
| 持久化 | COS 私有桶；压缩 SQLite 完整快照、同步记录、匿名统计对象与聚合 |
| 本地开发 | Starlette、SQLite、CLI；可选 Docker 常驻调度器 |
| CI / 发布 | GitHub 验证和 SCF 打包；Makers 随 `main` 发布；SCF ZIP 单独上传更新 |

读请求从 COS 找到最新快照，在临时目录解压查询并清理临时文件。写请求从版本 N 生成 N+1；两个写入者竞争同一个对象键，条件创建只接受一个，冲突返回 409。COS 桶必须从未开启版本控制，失败不能覆盖旧快照。

每日 SCF 先汇总匿名统计，再同步论文；当天已成功的上游同步会跳过重复调用。OpenAlex 失败阻止发布新快照；Scholar 失败只记录警告并保留旧 Scholar 数据。Makers 的人工同步预算为 70 秒，SCF 同步预算 200 秒，总任务预算 250 秒。

## 改造前的问题（已解决的历史背景）

1. 旧实现中的 `frontend/src/data/papers.toml` 会在 Astro 构建阶段被解析并写进 HTML，论文更新必须重新构建整站。
2. 首页、成果页、研究总览和研究详情页都直接导入同一份 TOML，前端与数据存储强耦合。
3. OpenAlex 作者 ID 写死为严颖老师，数据结构不能自然表达多位实验室研究者及共同论文。
4. 自动元数据与分区、影响因子、Top、代表作等人工字段混在一起，自动更新存在覆盖风险。
5. 旧同步脚本直接重写前端数据文件，没有数据库事务、同步历史、数量异常门禁和稳定快照。
6. 旧请求使用 `per-page=200`，改造后使用 100 条 cursor 分页。
7. 会议类型判断过于简单，部分会议论文可能被标为期刊论文。
8. 旧阶段没有可用的远端和自动化；现在已连接 `buerka/EEGLab`，GitHub CI 和 Makers Git 自动发布均已运行。
9. CDN 缓存的是构建后的 HTML，而不是 `frontend/src/data/papers.toml`，无法只刷新论文数据。
10. 前端没有加载失败兜底、数据版本、更新时间或多研究者筛选界面。

## 已实现的职责边界

- 后端独占 OpenAlex Key、研究者配置、论文存储、人工覆盖字段和同步历史。
- 前端只依赖公开 JSON API，不读取或解析服务端 TOML。
- 一篇论文可关联多位研究者；增加研究者不修改 API 或前端数据结构。
- OpenAlex 同步失败时继续提供最后一次成功快照。
- 论文 API 使用 ETag 和可配置 CDN 缓存策略，论文更新不要求重新构建 Astro。
- 静态图片、CSS 和 JS 继续使用 CDN 长缓存。

## 数据与前端行为

- 原始论文种子位于 `backend/data/papers.toml`，共 136 条；只有空库会导入这些论文。现有生产快照不会因为修改该文件而自动重写已有论文字段。
- `researchers.toml` 当前有 1 条研究者种子，按 slug 更新；`scholar_reviews.toml` 有 32 条审核规则和 1 条合并规则，会在初始化/写入工作区时应用。更新两端函数包后，还需后续写入/同步提交新快照。
- 研究者、论文及多对多关系分开存储，人工分区、IF、Top、代表作和标签不会被 OpenAlex 刷新覆盖。
- Google Scholar 经 SerpAPI 核验和补充引用数；未匹配记录进入候选表，只有审核接受的记录才可作为 Scholar 独有论文发布。撤稿和重复项可用审核规则排除。
- 成果页使用 `PublicationsExplorer.tsx`；首页使用 `FeaturedPublications.tsx` / `PublicationCount.tsx`；研究页使用 `RelatedPublications.tsx`。React 组件均通过运行时 API 取数。
- 页面内相同 URL 请求会合并；没有自动轮询。成果页加载失败有重试按钮，相关论文组件请求失败时隐藏该区块，不能把这些行为写成所有组件都有重试。
- 默认论文缓存为 `max-age=0, s-maxage=60, stale-while-revalidate=300`。新数据无需重建页面，但 CDN 再验证期间可以继续提供旧快照。
- 云端统计按 30 秒固定窗口及每日访客 HMAC 去重，本地 SQLite 按滑动间隔去重。COS 保存匿名事件，原始 IP / User-Agent 不落盘；已汇总超过 32 天的事件由 SCF 分批清理。

## 实施清单

- [x] 审计现有论文数据流、缓存行为和未启用的自动化。
- [x] 建立独立后端目录、配置、SQLite 数据库和迁移逻辑。
- [x] 建立多研究者、论文、关联关系、人工覆盖和同步历史数据模型。
- [x] 将现有 136 篇论文及人工字段迁移为后端种子数据。
- [x] 实现 OpenAlex cursor 分页、重试、分类、去重、异常门禁和事务同步。
- [x] 实现研究者、论文、同步状态和受保护手动同步 API。
- [x] 改造成果页为 API 驱动的多研究者论文浏览器。
- [x] 改造首页代表论文和研究页相关论文为 API 驱动组件。
- [x] 移除前端对 `papers.toml` 的全部直接依赖。
- [x] 增加独立 scheduler、Docker Compose、Nginx/CDN 缓存配置。
- [x] 删除 GitHub Actions 论文同步工作流和旧的一次性同步入口。
- [x] 完成后端测试、前端构建和端到端验收。
- [x] 增加 Makers Python HTTP 适配、COS 不可覆盖快照与 SCF 事件入口。
- [x] 将匿名访问统计适配到 COS，SCF 每日汇总及清理。
- [x] GitHub CI 使用 Linux Python 3.10 验证，并生成含依赖的 SCF 包。
- [x] 部署国内 Makers、上海 SCF、私有 COS，绑定正式域名及 HTTPS。

## 验收标准

1. `rg "papersData|frontend/src/data/papers.toml" frontend/src` 无匹配。
2. API 可返回研究者列表，并能用一个或多个研究者 ID 筛选论文。
3. 同一篇共同论文在论文表中只保存一次，同时关联多位研究者。
4. OpenAlex 缺失记录不会在单次同步中被物理删除。
5. 人工分区、IF、Top、代表作和标签不会被同步覆盖。
6. 同步异常不会替换当前可用快照。
7. 后端返回 `ETag`、`Cache-Control` 和最后同步时间。
8. 后端不可用时成果页显示明确错误和重试入口；其他页面主体仍可访问，相关论文区块允许隐藏。
9. Astro 构建不需要 OpenAlex API Key，也不需要后端在线。
10. GitHub Actions 只做验证和打包；论文定时同步由 SCF 完成，不依赖 Actions 定时工作流。

11. 生产 POST / OPTIONS 进入 Makers Handler，统计来源验证与管理口令鉴权有效。
12. 生产 COS 凭据不分配给预览环境，预览分支自动部署关闭。

## 2026-09-06 上线验收记录

- GitHub CI 在 Linux Python 3.10 上运行 29 项后端测试通过；根目录构建生成 10 个静态页面并通过部署输入检查。
- SCF 首次手动执行约 15 秒，OpenAlex 和 Scholar 均成功，无同步警告，新增 12 条、更新 135 条。
- 在线公开 API 返回 157 条，数量包含种子、审核接受及保留记录，不等于本次抓取数或原始种子数。
- 正式域名 10 个页面返回 200，TLS 校验正常，HTTP 跳转 HTTPS；浏览器首页的团队及动态论文已验证。
- 正式来源统计 POST / OPTIONS 返回 204；不允许来源返回 403；无口令管理同步返回 401；匿名统计真实写入 COS。

本次记录没有声称首个凌晨定时触发、长期计费、故障告警或所有浏览器回归已完成。待验证项见 [待办清单](../todo.md)，资源与详细记录见 [生产部署记录](tencent-production.md)。早期本地/Docker 的验收记录可通过 Git 历史查阅。
