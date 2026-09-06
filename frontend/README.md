# 网站前端

腾讯云国内站从**仓库根目录**导入 Makers，使用根目录的 `edgeone.json` 和 `npm run build`，
同步部署 Python API。详见 [部署指南](../docs/tencent-makers.md)。

金牛湖脑机实验室网站的独立前端应用，使用 Astro 6、React 18 和 TypeScript 构建。生产输出为静态文件，论文数据与访问统计在浏览器运行时从后端 `/api` 获取。

## 技术栈

- Astro：静态页面、布局和大部分组件。
- React：交互式论文组件和 EEG Canvas 动画。
- 原生 CSS：全局设计系统与组件样式。
- Nginx：生产环境静态托管和 `/api/` 反向代理。

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

要求 Node.js 22 或兼容版本。

```powershell
cd frontend
Copy-Item .env.example .env
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
```

任何 OpenAlex、SerpAPI 或管理密钥都只能配置在 `backend/.env`，不能使用 `PUBLIC_` 前缀放进前端。

## 常用命令

```powershell
npm run dev       # 开发服务器
npm run build     # 生成 dist/
npm run preview   # 本地预览生产输出
npm run clean     # 清理 dist/ 和 .astro/
```

## 论文数据

前端通过 `src/lib/publications.ts` 请求：

- `GET /api/papers`
- `GET /api/researchers`
- `GET /api/sync/status`

论文列表支持成员、代表作、标签和关键词筛选，并显示 OpenAlex/Google Scholar 双来源状态。论文更新发生在后端 SQLite 快照中，不需要修改 TOML 或重新构建前端。

## 访问统计

`src/layouts/Layout.astro` 会在每个公开页面加载时上报页面访问，
`src/components/Footer.astro` 展示累计浏览、今日访问和今日访客。统计请求保持同域，
不使用 Cookie；Do Not Track、Global Privacy Control 或本地 opt-out 生效时不发送。
统计数字来自运行时 API，因此数字刷新不需要重新构建前端。

## 页面与资源维护

- 新页面放在 `src/pages/`，Astro 会根据文件路径生成路由。
- 可交互组件放在 `src/components/`；只有确实需要客户端状态时才使用 React。
- 图片放入 `public/images/` 对应子目录，页面中使用 `/images/...` 引用。
- 视频放入 `public/videos/`。
- 奖项与图库内容分别维护在 `src/data/awards.toml` 和 `src/data/gallery.toml`。

## Docker 构建

前端镜像的构建上下文是本目录：

```powershell
docker build -t eeglab-frontend .
```

镜像第一阶段运行 Astro 构建，第二阶段由 Nginx 提供静态资源。在完整环境中应从项目根目录使用 `docker compose up -d --build`，以便 Nginx 能通过服务名访问 `paper-api`。
