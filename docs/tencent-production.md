# 腾讯云国内站生产部署记录

部署日期：2026-09-06；最近复验：2026-11-05。此文件是当次已验证生产状态的记录，不是实时监控。新会话接管先读 [接管说明](handoff.md)。此文件只记录非敏感配置，不保存 API 密钥、管理口令或签名预览链接。

| 项目 | 生产配置 |
| --- | --- |
| 正式域名 | `eeg.yanyinglab.cn` |
| DNS | 由域名所属的另一账号维护 |
| 访问 CNAME | `eeg.yanyinglab.cn.pages.dnsoe5.com` |
| Makers 项目 | `eeglab` / `makers-aodrs9egexxf` |
| 加速区域 | 中国大陆 |
| Git 仓库及分支 | `buerka/EEGLab`，`main` 自动部署；预览分支自动部署关闭 |
| COS | `eeglab-data-1302558698`，上海，私有读写，从未开启版本控制 |
| 数据前缀 | `eeglab/production` |
| SCF | `eeglab-paper-sync`，上海，命名空间 `default` |
| 函数配置 | Python 3.10、512 MB、300 秒，最大并发 1，无预置实例 |
| 执行方法 | `index.main_handler` |
| 定时器 | `eeglab-daily-0330`，每天北京时间 03:30，默认流量别名 |
| Makers Git / CI | `main` 自动发布，GitHub 验证与发布独立，未配置 CI 发布门禁；SCF ZIP 手动更新 |
| 计费 | 按量计费，未订购资源包或包月套餐；SCF 未开启 CLS 日志投递 |

## 凭据和权限

运行时使用程序用户 `eeglab-runtime`，仅绑定 `EEGLabCOSRuntime`。该策略允许读取目标桶的列表和版本状态、读写生产前缀对象，删除权限仅限 `eeglab/production/analytics/events/*`。Makers 和 SCF 已分别配置运行所需凭据；SCF 当前使用专用程序用户密钥，未配置执行角色。

腾讯云首次使用 SCF 创建的 `SCF_QcsRole` 是服务管理角色，与函数执行角色不同。Makers 的生产凭据不应分配给预览环境。GitHub Actions 不持有腾讯云凭据。

管理接口的随机口令及统计 HMAC 密钥使用不同值。已忽略的本地 `output/tencent-production.env` 保存不含 COS API 密钥的部署辅助变量（含 COS 桶/地域等非敏感配置）；不要提交该文件。后续控制台修改不会自动回写本机备份，新机器也不会从 Git 获得它，线上配置以控制台为准。COS API 密钥不保存在仓库文件中。

## 验证记录

- GitHub Actions 在 Linux Python 3.10 下通过 29 项后端测试，构建 10 个静态页面并生成含依赖的 SCF 包。
- 初次 SCF 手动测试于北京时间 22:12:44 开始，22:12:59 成功；OpenAlex 和 Google Scholar 均成功，无同步警告；新增 12 条、更新 135 条记录。
- Makers 从 COS 读取新快照，公开论文接口返回 157 条。该数量包含种子及保留记录，不等于本次上游抓取数量。
- 首次成功同步后的快照版本：`1756194e170e453e9f3dcf350c81fcb8`。后续成功同步会更新版本。
- 显式定义 Python HTTP 方法后，匿名访问统计可返回 204 并在 COS 中累计；无口令的管理同步接口返回 401。
- 域名归属 TXT 已验证，访问 CNAME 已通过公共 DNS 查询确认。免费证书已部署，正常 TLS 校验通过，HTTP 自动跳转 HTTPS。
- 正式域名的 10 个页面均返回 200，浏览器首页正常渲染团队和动态论文。正式来源的统计 POST / OPTIONS 返回 204，其他来源返回 403，无口令的管理同步返回 401。
- `PAPERS_ALLOWED_ORIGINS` 已包含正式域名和生产签名预览域名；COS、SerpAPI、管理口令及统计 HMAC 凭据的生效范围均限定为生产。来源配置应用后的正式统计写入已验证。
- `e9de3a1` 对应 GitHub CI 成功；`ecd0317` 是此次部署最后的运行代码修复（Makers HTTP 方法），随后为文档更新。

### 2026-11-05 同步恢复

- OpenAlex 现在要求无 Key 请求不能使用 cursor 翻页；作者论文超过 100 篇时第二页返回 401。SCF 已配置 `OPENALEX_API_KEY`，SerpAPI 配置不变。
- 修复 `papers.doi` 唯一约束冲突：当 OpenAlex 的重复记录把 DOI 指向另一条已存在论文时，更新保留原 DOI，不再中断整次同步；新增回归测试。
- 北京时间 13:02–13:03 手动执行 SCF 测试事件成功：OpenAlex 136 篇、Scholar 110 篇（匹配 92、候选 5），更新 136 条，无同步警告；`lastSyncAt=2026-11-05T05:03:02Z`，快照版本 `15a852505aa746e1ba410c74337c4eff`。
- `/api/papers/version` 已返回新版本；网站继续读取 COS 快照，无需重建前端。
- 修复通过 30 项后端测试（本地无 COS SDK 时 4 项契约测试跳过），Linux Python 3.10 CI 构建的 SCF 包已上传并部署成功。
- Makers 生产环境已新增 `OPENALEX_API_KEY`（仅生产），并通过新建部署 `dpldteldhmt` 生效；Makers 受保护手动同步与 SCF 使用同一 Key。
- 云监控已创建并启用 `eeglab-sync-error` 告警策略：对象为上海 `default` 命名空间的 `eeglab-paper-sync`，条件包含内存超限、执行超时、资源超限和错误次数 > 0，通知使用系统预设模板（账号默认 1 个接收人）。策略已保存，尚未经过真实失败触发验证。

## 验证边界与待办

SCF 已验证手动执行和定时器启用。2026-11-05 已恢复同步并手动验证成功，修复后的首个北京时间 03:30 定时运行仍需核对；Makers 的受保护手动同步若也要使用，需要在其生产环境配置同一 `OPENALEX_API_KEY` 并重新部署。当前没有配置项目失败通知，CLS 日志投递关闭；费用、长期配额、跨网络独立访客计数和全面浏览器回归没有在本次上线中完成。`PUBLIC_ICP_NUMBER` 尚未填写，需确认真实号码。完整待办见 [todo.md](../todo.md)。

快速入口：

- [Makers 项目](https://console.cloud.tencent.com/edgeone/makers/project/makers-aodrs9egexxf/index)
- [上海 SCF 函数](https://console.cloud.tencent.com/scf/list-detail?rid=4&ns=default&id=eeglab-paper-sync&tab=codeTab)
- [GitHub Actions](https://github.com/buerka/EEGLab/actions)
- [生产同步状态](https://eeg.yanyinglab.cn/api/sync/status)

## 日常更新

前端及 Makers API 修改推送到 `main` 后自动构建发布。SCF 后端代码修改还需要从成功的 Actions 下载最新 artifact，解出内部 ZIP 并更新同名函数，保留环境变量及定时器。GitHub CI 的打包步骤不会自动更新 SCF。

论文同步无需重建网页。可查看 `/api/sync/status` 的 `lastAttempt.status` 与 `lastSyncAt`，失败时网站继续读取上次完整快照。

保留访问 CNAME，以保障正式网站访问和免费证书自动续期。域名的 TXT 归属验证记录当前保留；证书采用 CNAME 自动验证，不需要额外 DNS 委派记录。
