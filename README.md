# 金牛湖脑机实验室网站

南京信息工程大学金牛湖脑机实验室网站，正式地址：**[eeg.yanyinglab.cn](https://eeg.yanyinglab.cn)**。

Astro 6 + React 18 提供 10 个静态页面，论文数据和访问统计通过运行时 API 加载。生产环境使用腾讯云**国内站 EdgeOne Makers + 上海 SCF + COS 私有桶**，无需常驻服务器或数据库。Starlette、CLI 和常驻调度器保留为本地/Docker 运行方式。

**新会话或空白 agent 接管：先读 [AGENTS.md](AGENTS.md) 和 [项目接管说明](docs/handoff.md)**，再根据本次任务查看具体开发文档。接管说明包含已验证/未验证状态、配置位置和不同改动的发布路径。

## 目录结构

```text
EEGLab/
├── frontend/              # Astro 6 + React 18 静态站点
│   ├── src/               # 页面、组件、样式和前端数据
│   ├── public/            # 图片、视频和 favicon
│   ├── deploy/            # 可选 Docker 部署的 Nginx 配置
│   ├── Dockerfile
│   └── README.md
├── backend/               # 共享 Python 业务逻辑、云端适配及本地 Starlette API
│   ├── app/
│   ├── data/
│   ├── tests/
│   └── README.md
├── cloud-functions/       # Makers Python Handler 及云端依赖
├── deploy/scf/            # SCF 事件入口 index.main_handler
├── deploy/tencent/        # 云端环境变量模板
├── scripts/               # Makers 准备、部署输入检查、SCF 打包
├── .github/workflows/ci.yml # GitHub 验证与打包
├── edgeone.json           # 仓库根目录构建及上海函数配置
├── docs/                  # 架构、部署指南、生产部署记录
└── docker-compose.yml     # 本地/自有服务器可选编排
```

## 本地开发

Node.js 使用 `22.21.1` 与 CI/Makers 对齐，最低 `22.12.0`；云端代码按 Python 3.10 验证。本地开发使用独立 SQLite，不会自动写入生产 COS。

从仓库根目录启动后端，已有 `.env` 时保留原文件：

```powershell
cd backend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
python -m pip install -r requirements-dev.txt
python -m app.cli init
python -m uvicorn app.main:app --reload --port 8000
```

另开终端，从仓库根目录启动前端：

```powershell
cd frontend
if (!(Test-Path .env)) { Copy-Item .env.example .env }
npm ci
npm run dev
```

访问 `http://localhost:4321`。开发服务器会把 `/api` 代理到 `http://localhost:8000`。

## 论文同步

论文同步完全由后端处理，前端不保存 API Key，也不需要在论文更新后重新构建。以下命令只更新本地数据库：

```powershell
cd backend
python -m app.cli sync
```

OpenAlex 提供规范论文元数据，Google Scholar（经 SerpAPI）用于第二来源核验和引用指标。生产完整同步由 SCF 每天北京时间 03:30 执行；受保护的 `POST /api/admin/sync` 可用于有时间预算的人工重跑。详细设计、环境变量及审核接口见 [backend/README.md](backend/README.md)。

## 生产部署

### 腾讯云国内站（低费用方案）

当前生产站采用 **EdgeOne Makers 托管网页/API + SCF 定时同步 + 国内 COS 私有存储**，无需常驻数据库。
详细配置见 [腾讯云国内站部署指南](docs/tencent-makers.md)，环境变量模板见
[deploy/tencent/.env.example](deploy/tencent/.env.example)。
GitHub Actions 负责测试及 SCF 打包，Makers 从 `main` 自动构建发布网站/API，预览分支自动部署关闭。两者独立运行，CI 当前不是生产发布的前置门禁。

**SCF 代码不会随 Git 推送自动更新**。修改同步模块、依赖或种子数据后，仍需从成功的 Actions 下载 artifact，解出内部 ZIP 并更新同名 SCF 函数，保留环境变量和定时器。

2026-09-06 上线验证：29 项后端测试通过、10 个页面和 HTTPS 正常、统计可持久写入，首次云函数同步成功。上线时论文 API 返回 157 条，后续以运行时 API 为准。资源、DNS、证书和运维步骤见 [生产部署记录](docs/tencent-production.md)。

### 自有服务器 / Docker

这是保留的可选方案，不用于当前腾讯云生产站。填写 `backend/.env` 后，在项目根目录执行：

```powershell
docker compose up -d --build
```

服务包括：

- `frontend`：Nginx 托管静态站点，并把 `/api/` 反向代理到后端。
- `paper-api`：公开论文 API 和受保护的管理接口。
- `paper-scheduler`：启动后立即同步，此后按配置周期执行。
- `paper-data`：SQLite 持久卷。

默认访问地址为 `http://localhost:8080`。前端指纹资源使用长期缓存，论文 API 使用 `ETag`、60 秒 CDN 新鲜期和最多 300 秒的后台再验证过期窗口。缓存期间可能仍看到旧快照，刷新论文不需要重建页面。

## 验证

以下命令从仓库根目录执行：

```powershell
python -m pip install -r backend/requirements-dev.txt -r cloud-functions/requirements.txt
npm --prefix frontend ci
npm run test:backend
npm run build
python scripts/check_deployment.py
```

根目录构建准备 Makers 私有代码并生成 `frontend/dist`；只在 `frontend` 构建不会准备 Python API。完整 SCF 包由 Linux Python 3.10 下的 CI 生成，Windows `--source-only` 包不能用于部署。

更多说明：

- [新会话 / 空白 agent 接管说明](docs/handoff.md)
- [前端开发说明](frontend/README.md)
- [论文后端说明](backend/README.md)
- [论文平台设计](docs/publications-platform.md)
- [腾讯云部署指南](docs/tencent-makers.md)
- [生产部署记录](docs/tencent-production.md)
- [项目维护约定](AGENTS.md)
- [待办清单](todo.md)
- [成果图片和视频清单](frontend/public/images/achievements/README.md)

## 版权

Copyright © 2026 buerka. All rights reserved. 本项目为专有项目，未经版权所有者事先书面许可，不得使用、复制、修改或分发。详见 [LICENSE](LICENSE)。
