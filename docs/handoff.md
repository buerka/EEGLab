# 项目接管说明

更新时间：2026-09-06。本文供没有聊天上下文的新会话或 agent 使用，描述已完成的实现、生产状态和后续修改路径。它是带日期的交接快照；代码、Git 和控制台状态可能继续变化，接管时先核对，不把历史结果当作实时状态。

## 先读这些，再动代码

1. 在仓库根目录读取 [AGENTS.md](../AGENTS.md) 和本文。
2. 执行 `git status --short`、`git branch --show-current`、`git log -5 --oneline`，识别现有未提交修改；不要覆盖他人的工作。
3. 根据任务读取 [前端说明](../frontend/README.md)、[后端说明](../backend/README.md) 或 [部署指南](tencent-makers.md)。
4. 需要操作线上环境时，读取 [生产记录](tencent-production.md) 并核对现有资源，不重新创建一套同名服务。
5. 待办从 [todo.md](../todo.md) 获取；没有勾选的项目不能视为已完成，也不能因本文列出就擅自扩大本次用户任务。

## 现在是什么状态

| 项目 | 已确认状态 |
| --- | --- |
| 正式网站 | [eeg.yanyinglab.cn](https://eeg.yanyinglab.cn)，HTTPS 正常，HTTP 自动跳转 HTTPS |
| 代码仓库 | `buerka/EEGLab`，SSH remote `git@github.com:buerka/EEGLab.git`，生产分支 `main` |
| 本机历史工作目录 | `D:\Repositories\EEGLab`；其他机器应使用自己的仓库路径 |
| 前端 | Astro 6 + React 18，10 个静态页面，Node.js `22.21.1` |
| 网站/API | 国内 EdgeOne Makers 项目 `eeglab`，ID `makers-aodrs9egexxf`，中国大陆加速，Python 3.10 / 上海 / 120 秒配置 |
| 每日同步 | 上海 SCF `eeglab-paper-sync`，命名空间 `default`，Python 3.10、512 MB、300 秒、最大并发 1，无预置实例 |
| 定时器 | `eeglab-daily-0330`，每天北京时间 03:30，已启用，默认流量别名 |
| 存储 | COS `eeglab-data-1302558698`，地域 `ap-shanghai`，前缀 `eeglab/production`，私有读写，从未开启版本控制 |
| 数据库 | 不购买/运行常驻数据库；云端 SQLite 仅为每次函数调用的临时查询工作区 |
| CI | GitHub Actions `Validate and package`：后端测试、10 页构建、部署输入检查、含依赖的 SCF 打包 |
| 自动发布 | Makers 随 `main` 发布，和 GitHub CI 独立；预览分支自动部署关闭；SCF 包更新仍需单独上传 |

采用国内站和少运维、低费用方案是用户明确选择。原始大视频无需在仓库中另存备份，旧版本保留在 Git。页面视觉风格、现有团队资料和其他待办，不应因重新接管部署而被改写。

## 已验证与尚未验证

2026-09-06 已完成：

- Linux Python 3.10 下 29 项后端测试通过；Makers 构建及正式域名 10 个页面正常。
- 首次 SCF 手动执行北京时间 22:12:44–22:12:59 成功；OpenAlex 和 Scholar 均成功，无同步警告，新增 12 条、更新 135 条。
- 同步后公开 API 返回 157 条。该值是上线时快照，包含种子、审核接受与保留记录，不能作为以后页面的固定值。
- 正式域名 TLS 校验及 HTTP → HTTPS 跳转通过；浏览器首页的团队与动态代表论文正常。
- 正式来源统计 POST / OPTIONS 返回 204；其他来源返回 403；无口令的管理同步返回 401；统计成功写入 COS。
- Makers 的 COS、SerpAPI、管理口令和统计 HMAC 凭据已限定生产范围，预览自动部署关闭。

尚不能宣称完成：首个凌晨定时触发的运行结果、长期费用核对、项目失败通知/告警、不同网络下真实独立访客计数验证。本次上线也不等于所有页面的移动端及所有浏览器回归都完成。SCF 当前未开启 CLS 日志投递，不能依赖控制台执行日志一定有内容；同步状态优先查 `/api/sync/status` 和 COS `papers/runs/`。

## 哪些改动需要发布到哪里

| 想改什么 | 主要文件 | 必要发布动作 |
| --- | --- | --- |
| 文案、样式、布局、团队资料 | `frontend/src/pages/`、`components/`、`styles/` | 提交 `main` 后 Makers 自动构建；无需更新 SCF |
| 奖项、图库、研究方向 | `frontend/src/data/` 与 `frontend/public/` | 更新数据和资源清单，Makers 构建；新增资源满足单文件 25 MB 限制 |
| 论文展示/筛选 | 四个 Publications React 组件及 `frontend/src/lib/publications.ts` | Makers 构建；接口字段变更还需同步后端 |
| Makers API 路由/鉴权/HTTP 兼容 | `backend/app/cloud_api.py`、`cloud-functions/api/[[default]].py` | Makers 构建；这两个文件不在 SCF 包中 |
| 同步、存储、统计汇总等共享逻辑 | `backend/app/` 中被打包的共享模块 | 更新 Makers，并另行上传最新 SCF 包，验证两端兼容 |
| 仅 SCF 入口 | `deploy/scf/index.py` | CI 生成新包后上传 SCF；Git 推送本身不会更新该函数 |
| 云端依赖 | `cloud-functions/requirements.txt` | Makers 安装新依赖，SCF 必须更新含 Linux Python 3.10 依赖的 ZIP |
| 本地 Starlette / CLI / 常驻调度器 | `backend/app/main.py`、`cli.py`、`scheduler.py` | 仅本地/Docker入口；三个文件不包含在云端部署中 |
| 云端环境变量 | Makers 生产环境、SCF 函数环境 | 各自保存；Makers 变量需重新部署才生效，SCF 不读取本机 `.env` |

首页与团队页分别维护团队数组，人员信息需要同步两处。研究方向实际名称为脑疾病诊断、脑控机械臂、脑控无人机、脑控灵巧手、脑控气动手套；不要使用早期文档中的旧路由描述。

### 后端种子不是线上实时数据库

- `backend/data/papers.toml` 是 136 条原始论文种子，只有空库会导入。只改该文件不能更新已有生产快照中的论文字段，也不要为此清空 COS 重建数据。
- `researchers.toml` 当前有 1 位研究者，初始化时按 slug 更新；`scholar_reviews.toml` 有 32 条审核规则和 1 条合并规则，会在写入工作区初始化时应用。
- 种子或审核规则修改需同步两端代码包，并经后续写入/同步提交新快照；已存在数据的字段调整要设计受保护的数据更新/迁移。当前 API 只有添加研究者、手动同步和查询 Scholar 候选等管理入口，没有通用论文编辑后台。
- 添加新研究者优先用受保护 `POST /api/admin/researchers`；确保使用已核对的作者标识，不凭姓名猜测 OpenAlex/Scholar ID。
- 前端论文 TOML、旧 `PaperFilter.astro` / `PaperFilter.tsx` 和旧 GitHub 定时同步流程已移除。保留的 Docker 方案仅用于本地/自有服务器，不能当成线上部署状态。

## 凭据在哪里

| 设置 | 当前存放与用途 |
| --- | --- |
| COS API 密钥 | 已配置于 Makers 生产环境和 SCF；来自仅程序访问的 `eeglab-runtime` 用户 |
| COS 权限 | `EEGLabCOSRuntime`：仅目标桶列举/版本检查、生产前缀读写、匿名事件前缀删除 |
| 管理口令 | `PAPERS_SYNC_TOKEN`，服务端随机值，管理请求使用 Bearer 鉴权 |
| 统计密钥 | 独立的 `ANALYTICS_HMAC_SECRET`，不与管理口令混用 |
| SerpAPI | `SERPAPI_API_KEY` 已在 Makers 生产和 SCF 配置；OpenAlex Key 在初次部署时未配置，实际同步已成功 |
| 允许来源 | Makers 生产的 `PAPERS_ALLOWED_ORIGINS` 已配置正式域名和生产签名预览域名 |
| 前端 API | Makers `PUBLIC_PAPERS_API_URL=/api` |
| 备案展示 | `PUBLIC_ICP_NUMBER` 尚未填写，不编造备案号 |

服务端密钥不能以 `PUBLIC_` 开头，不能提交到 Git、输出日志或放入前端 `public`。接管时先确认控制台中已有变量，不要求用户重新粘贴已有凭据，也不为排查问题创建新密钥。

本机 `backend/.env` 是本地开发配置；忽略的 `output/tencent-production.env` 只是一份本机部署辅助备份，不包含 COS API 密钥，且后续控制台配置可能已变化。它不随 Git 分发，不能当作线上配置的唯一来源。新机器没有这些文件是正常的，应使用模板配置本地开发，并通过已授权的控制台管理线上环境。

SCF 当前没有配置执行角色，实际使用专用程序用户密钥。腾讯云创建的 `SCF_QcsRole` 是服务管理角色，不是已绑定的函数执行角色。代码支持执行角色注入临时凭据，但不能把“支持”写成“已启用”。

## 域名与证书

- `yanyinglab.cn` 的 DNS 由另一个账号维护，不在当前部署账号中。DNS 变更应由该账号操作，不修改部署账号下其他不相关域名。
- 访问记录：主机 `eeg`，类型 `CNAME`，值 `eeg.yanyinglab.cn.pages.dnsoe5.com`，TTL 600。保留此记录以支持访问和免费证书续期。
- `edgeonereclaim.eeg` 的 TXT 归属验证已通过，交接时建议保留；没有取得平台关于验证后删除不再复核的明确说明，不能直接承诺可删。
- HTTPS 使用平台免费证书、CNAME 自动验证；没有额外配置 `_dnsauth` 委派记录。正式访问用自定义域名，`edgeone.cool` 只是限时签名预览，不能当长期网址。

## 验证与排障入口

以下命令在仓库根目录执行，依赖安装不需要线上密钥：

```powershell
python -m pip install -r backend/requirements-dev.txt -r cloud-functions/requirements.txt
npm --prefix frontend ci
npm run test:backend
npm run build
python scripts/check_deployment.py
```

根目录构建先生成私有 `_vendor`，再输出 `frontend/dist`。单独 `cd frontend` 构建只准备静态页面。`_vendor`、`output`、`.env`、实时 SQLite 和缓存都不提交。

线上读取检查：

- `/api/health` 只验证 Makers 路由，不探测 COS；必须同时检查 `/api/papers`。
- `/api/papers/version` 查看当前版本和最后同步时间。
- `/api/sync/status` 的 `lastAttempt.status` 与 `lastSyncAt` 用于区分最近尝试和最后成功。时间字符串通常为 UTC，定时器按北京时间运行。
- `/api/analytics/summary` 是短缓存摘要，统计上报后可能暂时不更新；不要因此直接重置数据。
- 同源统计 403：核对 Makers 的 `PAPERS_ALLOWED_ORIGINS` 并重新部署，不能只依赖回源 Host。
- POST 405：检查 Handler 是否显式定义 `do_POST`。链式赋值声明曾导致平台构建器只识别 GET，修复在 `ecd0317`。
- SCF 当天重复测试返回 `already_synced_today` 是正常幂等行为；完整定时入口不接受 HTTP 事件。需当天重跑上游时使用受保护 API，注意 70 秒预算。
- 公开读取正常但同步失败：先查状态和上游配额/联网，旧完整快照会继续服务；不要删除快照、开启 COS 版本控制或扩大权限来试错。

完整包从成功的 GitHub `Validate and package` 下载 `eeglab-scf-python310` artifact，再解出内部 `eeglab-scf-python310.zip` 上传。Artifacts 仅保留 14 天，过期后可重新运行工作流；Windows `--source-only` 只供审阅，不能部署。首次 SCF 使用 `6dce05a` 对应包，后续 HTTP 修复未改变 SCF 包内业务代码。

## 当前待完善内容与交接习惯

运行和产品待办以 [todo.md](../todo.md) 为准。已知工程余项包括失败通知、SCF 自动发版、可选 CI 发布门禁，以及构建器提示的 `cloudFunctions` 字段弃用迁移。当前字段与国内文档/构建器存在版本差异，已有配置已部署验证；修改时核对实际地域、超时及构建结果。

继续工作后，至少同步本说明、[生产记录](tencent-production.md) 和相关前后端文档；更新验证日期、实际改动和未完成项。仅改文档时核对链接、路径和事实即可，不把旧测试或手动执行写成新验证；部署、权限或计费变化按当次用户授权与工具规则处理。
