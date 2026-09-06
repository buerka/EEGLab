# 腾讯云国内站部署：Makers + SCF + COS

本方案针对 `console.cloud.tencent.com/edgeone/makers`。默认使用上海地域和北京时间，不依赖海外数据库，也不需要常驻服务器。网页和公开 API 在 Makers，论文同步在腾讯云 SCF，所有持久化数据在国内 COS 私有桶。

## CI 与发布的分工

| 平台 | 职责 |
| --- | --- |
| GitHub | 保存代码；Actions 运行测试、前端构建检查，生成带依赖的 SCF ZIP |
| EdgeOne Makers | 从 GitHub 导入仓库，执行生产构建和网站/API 自动部署 |
| 腾讯云 SCF | 运行每日同步与访问统计汇总，不负责构建网站 |

`.github/workflows/ci.yml` 不持有云密钥，也不上传网站。Makers 的 Git 自动部署和 GitHub CI 独立；若希望生产发布必须经过测试，应对生产分支设置保护，要求 `validate` 成功后才能合并。Makers 预览部署使用独立的 `COS_PREFIX`（如 `eeglab/preview`）及测试密钥，不能与生产共用前缀。

## 1. 创建一个 COS 私有桶

在国内站 COS 控制台创建普通存储桶：

- 地域：上海 `ap-shanghai`，与函数地域一致。
- 访问权限：私有读写，不开启公共访问；浏览器通过 Makers API 读取数据。
- **使用从未开启版本控制的独立桶。** 代码用 `x-cos-forbid-overwrite` 实现原子创建；COS 在开启版本控制时会忽略该限制，代码会拒绝写入 Enabled/Suspended 桶。
- 桶名必须包含 APPID，例如 `lab-data-1250000000`。
- 不对整个 `eeglab/production` 前缀设置自动过期规则，否则可能删除最新论文快照或累计统计。

Makers 配置一个专用 CAM 子账号密钥，仅授权这个桶/前缀。所需操作为 `cos:GetBucketVersioning`、`cos:GetBucket`（列举）、`cos:GetObject`、`cos:PutObject`、`cos:DeleteObject`（删除已汇总且过期的匿名统计）。桶级列举/版本检查与对象级权限应分别配置。SCF 建议使用执行角色，配置相同权限，使用运行时注入的临时凭据。

数据布局：

```text
eeglab/production/
  papers/snapshots/    # 压缩 SQLite 完整快照，文件名倒序编号，最小键是最新版本
  papers/runs/         # 同步成功/失败记录；失败仅保存异常类型
  analytics/initial.json
  analytics/events/   # 日期 / 当日匿名访客 HMAC / 页面哈希与时间窗口
  analytics/rollups/  # 已结算日期的累计数及每日聚合
```

SQLite 仅在每次函数调用的临时目录中用于查询/核验。写入者从版本 N 生成同名版本 N+1，COS 条件创建保证只接受一个；冲突返回 409，失败不会覆盖旧快照。请求结束即关闭连接并移除临时文件。

## 2. 导入 Makers 项目

选择「导入 Git 仓库」，根目录必须选仓库根目录，不能选 `frontend`。

| 配置 | 值 |
| --- | --- |
| 根目录 | `./` |
| 框架 | Astro；若预设覆盖字段，以以下自定义值为准 |
| 安装命令 | `npm --prefix frontend ci` |
| 构建命令 | `npm run build` |
| 输出目录 | `frontend/dist` |
| Node.js | `22.21.1`（Astro 6 要求 ≥22.12） |
| Cloud Functions | Python 3.10，上海，120 秒 |
| 加速区域 | 按实际域名选择中国大陆；该控制台设置不由 `edgeone.json` 代填 |

根目录 `edgeone.json` 已保存构建与函数配置。构建时 `scripts/prepare-makers.mjs` 将共享后端模块和三个种子 TOML 文件复制到云函数私有目录。它不会复制 `.env`、实时数据库或其他本机文件。Makers 的 Python 构建器从 `cloud-functions/requirements.txt` 安装依赖。不要把 `_vendor` 或 `cloud-functions` 复制进 `frontend/public` / `frontend/dist`。

所有 API 由 `cloud-functions/api/[[default]].py` 处理，公开路径保持 `/api/papers`、`/api/researchers`、`/api/analytics/*`。健康检查为 `/api/health`。管理入口要求 `Authorization: Bearer <PAPERS_SYNC_TOKEN>`。

宣传视频 `frontend/public/videos/promo.mp4` 已从约 33 MB 压缩至约 20.5 MB，分辨率与时长保持不变，AAC 音轨直接复制，旧版本可通过 Git 找回。CI 会拒绝任何超过 25 MB 的静态文件，避免后续上传失败。参考 [国内站限制与配额](https://cloud.tencent.com/document/product/1552/132789)。

## 3. 环境变量

按 `deploy/tencent/.env.example` 填写到 Makers 的生产环境变量和 SCF 环境变量。

必需：`COS_REGION`、`COS_BUCKET`、`COS_PREFIX`，COS 凭据（或 SCF 执行角色），至少 32 字符的 `PAPERS_SYNC_TOKEN` 和 `ANALYTICS_HMAC_SECRET`。可以用下面命令在本机生成随机值，分别生成两次：

```sh
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

`PAPERS_ALLOWED_ORIGINS` 填实际站点 HTTPS 地址。`PUBLIC_PAPERS_API_URL` 保持 `/api`；`PUBLIC_ICP_NUMBER` 仅填写已取得的真实备案号，留空则页脚不显示。

`OPENALEX_API_KEY` / `SERPAPI_API_KEY` 在 SCF 配置。若希望 Makers 的受保护手动同步也可用，在 Makers 也配置相同上游密钥。不配置 SerpAPI 时继续使用 OpenAlex，Scholar 标记为 disabled。

SCF 若使用执行角色，不配置 `COS_SECRET_ID` / `COS_SECRET_KEY`，由 SDK 读取 `TENCENTCLOUD_SECRETID` / `TENCENTCLOUD_SECRETKEY` / `TENCENTCLOUD_SESSIONTOKEN`。每次事件重新创建客户端，避免复用过期凭据。

不要把本地 `PAPERS_DATABASE_PATH`、`ANALYTICS_DATABASE_PATH` 或 Docker 卷路径当作云端存储设置。COS 前缀才是数据环境的标识。

## 4. 创建 SCF 每日同步函数

代码推送后，打开 GitHub Actions 的 `Validate and package`，成功后下载 `eeglab-scf-python310` artifact，解出内部的 `eeglab-scf-python310.zip`。**上传这个内部 ZIP，而不是 GitHub 下载的外层 artifact ZIP。**

国内站 SCF 控制台创建事件函数：

| 配置 | 建议值 |
| --- | --- |
| 地域 | 上海 |
| 运行时 | Python 3.10 |
| 代码上传 | `eeglab-scf-python310.zip`，依赖已包含 |
| 执行方法 | `index.main_handler` |
| 超时 | 300 秒 |
| 内存 | 512 MB |
| 最大并发实例 | 1 |
| 触发器 | 定时触发器，每天北京时间 03:30 |
| HTTP 触发器 | 不需要 |

环境变量与 Makers 共用生产桶/前缀。先在控制台用 `{}` 测试事件执行一次，再启用每日定时触发。每日成功后重复事件会跳过上游同步；人工需要重跑时可调用 Makers 受保护的 `POST /api/admin/sync`，其同步预算为 70 秒。SCF 同步预算为 200 秒，总任务预算 250 秒，为快照提交和清理留出时间。

SCF 定时触发器与 Makers `schedules` 是两个不同入口，本项目只启用前者，不要再增加第二个每日任务。上游分页与重试共享时间预算；超时则继续提供上次完整快照。网络连通性和上游配额仍需在实际上海函数环境中确认。

若在本机 Linux Python 3.10 构建，可运行 `python scripts/package_scf.py`。Windows 上 `--source-only` 只生成审阅源码包，不包含 Linux 运行依赖，不能直接作为部署包。

## 5. 访问统计与费用

云端统计采用默认 30 秒的**固定时间窗口**去重。同一天同一匿名访客、同一页面、同一窗口只写一个不可覆盖对象；跨窗口可能再次计数，与本地 SQLite 的滑动 30 秒去重略有不同。今日访客按当日 HMAC 去重，原始 IP、User-Agent 不写入存储。

SCF 每日先汇总统计，再同步论文；因此上游论文服务出错也不会阻断已执行的汇总。已汇总且超过 32 天的匿名记录由任务分批清理，累计/每日聚合永久保存。若定时任务停用，清理也会停止，应检查 SCF 失败告警。最近未汇总事件一次最多扫描 50000 条，超过时返回明确错误而不展示错误计数；该方案面向访问量较低的实验室网站，大访问量应迁移到数据库/专门统计服务。

没有常驻数据库费用，但 COS 存储/请求、SCF 执行和 SerpAPI 配额按各自账户套餐计算，不承诺永久免费。论文快照每天约一个版本，保留历史便于回滚。

## 6. 上线验证

1. 确认 Actions 验证成功、Makers 构建生成 10 个静态页面和 Python API。
2. 访问 `/api/health` 检查路由，再访问 `/api/papers` 检查真实 COS 访问（健康接口不探测存储）。首次未同步时使用仓库种子和人工审核规则作为初始数据。
3. SCF 测试事件执行成功后，检查 COS 的 `papers/snapshots` 和 `papers/runs`。
4. 再访问 `/api/papers/version`，确认版本更新；页面论文列表应无需重建而更新。
5. 打开两个页面，确认 `/api/analytics/summary` 与页脚累计数更新；生产环境验证 EO 转发的访客 IP 头，避免所有访客被合并为 unknown。
6. 检查未携带口令的 `/api/admin/sync` 返回 401，以及预览环境没有写入生产前缀。

国内加速绑定自定义域名时，按 Makers 控制台完成域名备案与所有权验证，再填写备案号。代码不能代办备案或替代控制台的域名验证。

## 国内站官方文档

- [Makers 构建指南](https://cloud.tencent.com/document/product/1552/127392)
- [Makers Python](https://cloud.tencent.com/document/product/1552/130012)
- [Makers 云函数与限制](https://cloud.tencent.com/document/product/1552/127418)
- [edgeone.json](https://cloud.tencent.com/document/product/1552/127389)
- [COS 条件创建与版本控制限制](https://cloud.tencent.com/document/product/436/7749)
- [SCF 定时触发器](https://cloud.tencent.com/document/product/583/9708)

配置和文档核对日期：2026-09-06。实际资源创建、凭据配置、国内地域联网和正式部署需要在腾讯云账户中验证。
