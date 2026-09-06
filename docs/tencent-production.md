# 腾讯云国内站生产部署记录

部署日期：2026-09-06。此文件只记录非敏感配置；不保存 API 密钥、管理口令或签名预览链接。

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
| 计费 | 按量计费，未订购资源包或包月套餐；SCF 未开启 CLS 日志投递 |

## 凭据和权限

运行时使用程序用户 `eeglab-runtime`，仅绑定 `EEGLabCOSRuntime`。该策略允许读取目标桶的列表和版本状态、读写生产前缀对象，删除权限仅限 `eeglab/production/analytics/events/*`。Makers 和 SCF 已分别配置运行所需凭据；SCF 当前使用专用程序用户密钥，未配置执行角色。

腾讯云首次使用 SCF 创建的 `SCF_QcsRole` 是服务管理角色，与函数执行角色不同。Makers 的生产凭据不应分配给预览环境。GitHub Actions 不持有腾讯云凭据。

管理接口的随机口令及统计 HMAC 密钥使用不同值。已忽略的本地 `output/tencent-production.env` 保存部署用非 COS 环境变量；不要提交该文件。COS API 密钥不保存在仓库文件中。

## 验证记录

- GitHub Actions 在 Linux Python 3.10 下通过 29 项后端测试，构建 10 个静态页面并生成含依赖的 SCF 包。
- 初次 SCF 手动测试于北京时间 22:12:44 开始，22:12:59 成功；OpenAlex 和 Google Scholar 均成功，无同步警告；新增 12 条、更新 135 条记录。
- Makers 从 COS 读取新快照，公开论文接口返回 157 条。该数量包含种子及保留记录，不等于本次上游抓取数量。
- 初始快照版本：`1756194e170e453e9f3dcf350c81fcb8`。后续定时任务会正常更新版本。
- 显式定义 Python HTTP 方法后，匿名访问统计可返回 204 并在 COS 中累计；无口令的管理同步接口返回 401。
- 域名归属 TXT 已验证，访问 CNAME 已通过公共 DNS 查询确认；HTTPS 和浏览器访问的最终验证在上线时补充。

## 日常更新

前端及 Makers API 修改推送到 `main` 后自动构建发布。SCF 后端代码修改还需要从成功的 Actions 下载最新 artifact，解出内部 ZIP 并更新同名函数，保留环境变量及定时器。GitHub CI 的打包步骤不会自动更新 SCF。

论文同步无需重建网页。可查看 `/api/sync/status` 的 `lastAttempt.status` 与 `lastSyncAt`，失败时网站继续读取上次完整快照。

保留访问 CNAME，以保障正式网站访问和免费证书自动续期。域名的 TXT 归属验证记录当前保留；证书采用 CNAME 自动验证，不需要额外 DNS 委派记录。
