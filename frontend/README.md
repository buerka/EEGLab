# 网站前端

腾讯云国内站从**仓库根目录**导入 Makers，使用根目录的 `edgeone.json` 和 `npm run build`，
同步部署 Python API。正式站点：[eeg.yanyinglab.cn](https://eeg.yanyinglab.cn)。详见 [部署指南](../docs/tencent-makers.md) 和 [生产记录](../docs/tencent-production.md)。文档核对日期：2026-09-06。

金牛湖脑机实验室网站的独立前端应用，使用 Astro 6、React 18 和 TypeScript 构建。生产输出为静态文件，论文数据与访问统计在浏览器运行时从后端 `/api` 获取。

## 技术栈

- Astro：静态页面、布局和大部分组件。
- React：论文浏览器、代表论文、相关论文和数量组件。`HeroEEG.tsx` 是保留的 Canvas 组件，当前页面未引用；首页 Hero 使用宣传视频。
- 原生 CSS：全局设计系统与组件样式。
- Makers：当前生产静态托管及 `/api/` 云函数；Nginx 用于可选 Docker 方案。

## 目录结构

```text
frontend/
├── src/
│   ├── pages/             # 10 个页面路由
│   ├── components/        # 导航、论文、图库及动画组件
│   ├── layouts/           # 全局 HTML 布局
│   ├── styles/            # 全局设计变量和 reset
│   ├── data/              # 奖项、图库和研究方向等静态内容
│   └── lib/               # 论文 API 客户端与类型
├── public/
│   ├── images/            # 团队、成果和研究方向图片
│   └── videos/            # 演示与宣传视频
├── deploy/nginx.conf      # 静态站点与 API 反向代理配置
├── astro.config.mjs       # React、TOML 和开发代理配置
├── Dockerfile
└── package.json
```

## 启动开发服务器

Node.js 与 CI/Makers 对齐为 `22.21.1`，最低 `22.12.0`。以下命令从仓库根目录开始，已有 `.env` 时保留原文件。

```powershell
cd frontend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm ci
npm run dev
```

默认访问 `http://localhost:4321`。论文后端应运行在 `http://localhost:8000`。

## 环境变量

```dotenv
# 浏览器访问论文 API 的公开地址。同域部署时保持 /api。
PUBLIC_PAPERS_API_URL=/api

# 仅供本地 Astro/Vite 开发代理使用，不会注入浏览器代码。
PAPERS_API_DEV_TARGET=http://localhost:8000

# 只填写已确认的真实备案号；留空则页脚不显示。
PUBLIC_ICP_NUMBER=
```

本地密钥配置在 `backend/.env`；云端密钥配置在 Makers/SCF 服务端环境变量。OpenAlex、SerpAPI、COS、管理口令及统计 HMAC 密钥均不能使用 `PUBLIC_` 前缀或放进公开目录。

## 常用命令

```powershell
npm run dev       # 开发服务器
npm run build     # 生成 dist/
npm run preview   # 本地预览生产输出
npm run clean     # 清理 dist/ 和 .astro/
```

以上命令在 `frontend` 目录执行。Makers 完整发布必须在仓库根目录运行 `npm run build`，该命令还会生成私有 Python `_vendor`；输出目录仍为 `frontend/dist`。`npm run preview` 仅预览本机构建，不能代替实际 Makers/COS 验证。

## 论文数据

`src/lib/publications.ts` 通过 `GET /api/papers` 获取论文、研究者列表、版本和更新时间，页面内合并相同 URL 的请求；错误后可重试。`/api/researchers` 和 `/api/sync/status` 是后端额外提供的查询接口。

| 组件 | 使用位置 |
| --- | --- |
| `PublicationsExplorer.tsx` | 成果页：研究者、代表作/全部、标签和关键词筛选 |
| `FeaturedPublications.tsx` | 首页代表论文 |
| `RelatedPublications.tsx` | 研究总览和详情页相关论文 |
| `PublicationCount.tsx` | 首页论文数量 |

生产论文更新发生在 COS 完整快照中，本地使用 SQLite。无需修改前端 TOML 或重新构建前端；前端论文 TOML 和旧 PaperFilter 组件已经移除。页面不持续轮询数据，刷新或重新打开后按 API 缓存策略取数。157 条仅为 2026-09-06 上线快照数量，不能作为页面常量。

## 访问统计

`src/layouts/Layout.astro` 会在每个公开页面加载时上报页面访问，
`src/components/Footer.astro` 展示累计浏览、今日访问和今日访客。统计请求保持同域，
不使用 Cookie；Do Not Track、Global Privacy Control 或本地 opt-out 生效时不发送。
统计数字来自运行时 API，因此数字刷新不需要重新构建前端。

生产环境需在 Makers 配置 `PAPERS_ALLOWED_ORIGINS=https://eeg.yanyinglab.cn`；如需允许生产签名预览，可用逗号追加其准确 HTTPS 来源。Makers 回源 Host 可能不是公开域名，缺少来源配置会导致上报返回 403。统计摘要有短缓存，数字不会保证每次上报后立即变化。

## 页面与资源维护

- 新页面放在 `src/pages/`，Astro 会根据文件路径生成路由。
- 可交互组件放在 `src/components/`；只有确实需要客户端状态时才使用 React。
- 图片放入 `public/images/` 对应子目录，页面中使用 `/images/...` 引用。
- 视频放入 `public/videos/`。
- 奖项与图库内容分别维护在 `src/data/awards.toml` 和 `src/data/gallery.toml`。
- 当前有 17 条奖项、42 条图库记录；首页瀑布流两列分别为 16 / 14 条，复用已有图片。
- 新图片先放 `public/temp/`，整理命名后移至对应目录，同步图库数据与 [媒体清单](public/images/achievements/README.md)。该临时目录不提交。
- `promo.mp4` 为首页背景视频，已压缩至 20,535,541 字节，旧版本通过 Git 查阅；`demo-eeg-cap.mp4` 目前仅保存为素材。
- Makers 单个静态文件不超过 25 MB，根目录 `scripts/check_deployment.py` 会检查。
- 首页与团队页各有一份团队数组，人员修改需同步两处。研究方向名称及 slug 以 `src/data/research.ts` 为准。

## 生产发布

`main` 提交后由 Makers 自动构建发布，GitHub CI 独立验证并打包 SCF，当前不作为发布前置门禁。预览分支自动部署关闭，生产密钥只分配给生产环境。环境变量修改需重新部署才生效。

只更新页面、样式或图片不需要更新 SCF；同步逻辑、云端依赖或后端种子变化则需另行上传 CI 生成的 SCF ZIP，详见生产记录。

## Docker 构建

前端镜像的构建上下文是本目录：

```powershell
docker build -t eeglab-frontend .
```

镜像第一阶段运行 Astro 构建，第二阶段由 Nginx 提供静态资源。在完整环境中应从项目根目录使用 `docker compose up -d --build`，以便 Nginx 能通过服务名访问 `paper-api`。
