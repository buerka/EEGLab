# 论文平台前后端分离改造

## 当前问题

1. 旧实现中的 `frontend/src/data/papers.toml` 会在 Astro 构建阶段被解析并写进 HTML，论文更新必须重新构建整站。
2. 首页、成果页、研究总览和研究详情页都直接导入同一份 TOML，前端与数据存储强耦合。
3. OpenAlex 作者 ID 写死为严颖老师，数据结构不能自然表达多位实验室研究者及共同论文。
4. 自动元数据与分区、影响因子、Top、代表作等人工字段混在一起，自动更新存在覆盖风险。
5. 旧同步脚本直接重写前端数据文件，没有数据库事务、同步历史、数量异常门禁和稳定快照。
6. 旧请求使用 `per-page=200`，超过 OpenAlex 当前单页最大 100 条的限制。
7. 会议类型判断过于简单，部分会议论文可能被标为期刊论文。
8. 旧流程依赖尚未启用的 GitHub Actions；当前仓库也没有 Git remote。
9. CDN 缓存的是构建后的 HTML，而不是 `frontend/src/data/papers.toml`，无法只刷新论文数据。
10. 前端没有加载失败兜底、数据版本、更新时间或多研究者筛选界面。

## 目标边界

- 后端独占 OpenAlex Key、研究者配置、论文存储、人工覆盖字段和同步历史。
- 前端只依赖公开 JSON API，不读取或解析服务端 TOML。
- 一篇论文可关联多位研究者；增加研究者不修改 API 或前端数据结构。
- OpenAlex 同步失败时继续提供最后一次成功快照。
- 论文 API 使用 ETag 和可配置 CDN 缓存策略，论文更新不要求重新构建 Astro。
- 静态图片、CSS 和 JS 继续使用 CDN 长缓存。

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

## 验收标准

1. `rg "papersData|frontend/src/data/papers.toml" frontend/src` 无匹配。
2. API 可返回研究者列表，并能用一个或多个研究者 ID 筛选论文。
3. 同一篇共同论文在论文表中只保存一次，同时关联多位研究者。
4. OpenAlex 缺失记录不会在单次同步中被物理删除。
5. 人工分区、IF、Top、代表作和标签不会被同步覆盖。
6. 同步异常不会替换当前可用快照。
7. 后端返回 `ETag`、`Cache-Control` 和最后同步时间。
8. 后端不可用时前端显示明确错误和重试入口，而不是空白页面。
9. Astro 构建不需要 OpenAlex API Key，也不需要后端在线。
10. 不存在 GitHub Actions 论文同步依赖。

## 验收记录

- `python -m unittest discover -s tests -v`：4 项测试通过。
- `cd frontend && npm run build`：10 个静态路由构建通过，构建过程无需 API 在线或 OpenAlex Key。
- `docker compose config --quiet`：部署配置校验通过。
- Playwright：成果页全量、标签、搜索、移动端、API 离线与重试恢复通过；首页、研究总览、研究详情动态论文通过。
- API：136 篇种子数据、`ETag`、`Cache-Control`、最后更新时间和不受分页影响的类型计数通过。
