# 金牛湖脑机实验室网站

南京信息工程大学金牛湖脑机实验室网站。项目采用前后端分目录结构：Astro 静态前端负责页面展示，Starlette 后端负责 OpenAlex + Google Scholar 论文同步、隐私友好访问统计与公开 API。

## 目录结构

```text
EEGLab/
├── frontend/              # Astro 6 + React 18 静态站点
│   ├── src/               # 页面、组件、样式和前端数据
│   ├── public/            # 图片、视频和 favicon
│   ├── deploy/            # 前端 Nginx 配置
│   ├── Dockerfile
│   └── README.md
├── backend/               # Starlette API、同步器、SQLite 和测试
│   ├── app/
│   ├── data/
│   ├── tests/
│   └── README.md
├── docs/                  # 跨服务设计文档
└── docker-compose.yml     # 前端、API、调度器和持久卷编排
```

## 本地开发

先启动后端：

```powershell
cd backend
Copy-Item .env.example .env
python -m pip install -r requirements-dev.txt
python -m app.cli init
python -m uvicorn app.main:app --reload --port 8000
```

再开一个终端启动前端：

```powershell
cd frontend
Copy-Item .env.example .env
npm ci
npm run dev
```

访问 `http://localhost:4321`。开发服务器会把 `/api` 代理到 `http://localhost:8000`。

## 论文同步

论文同步完全由后端处理，前端不保存 API Key，也不需要在论文更新后重新构建：

```powershell
cd backend
python -m app.cli sync
```

OpenAlex 提供规范论文元数据，Google Scholar（经 SerpAPI）用于第二来源核验和引用指标。详细设计、环境变量及审核接口见 [backend/README.md](backend/README.md)。

## 生产部署

### 腾讯云国内站（低费用方案）

已支持 **EdgeOne Makers 托管网页/API + SCF 定时同步 + 国内 COS 私有存储**，无需常驻数据库。
详细配置见 [腾讯云国内站部署指南](docs/tencent-makers.md)，环境变量模板见
[deploy/tencent/.env.example](deploy/tencent/.env.example)。
GitHub Actions 负责测试及 SCF 打包，Makers 负责网站构建发布。

### 自有服务器 / Docker

填写 `backend/.env` 后，在项目根目录执行：

```powershell
docker compose up -d --build
```

服务包括：

- `frontend`：Nginx 托管静态站点，并把 `/api/` 反向代理到后端。
- `paper-api`：公开论文 API 和受保护的管理接口。
- `paper-scheduler`：启动后立即同步，此后按配置周期执行。
- `paper-data`：SQLite 持久卷。

默认访问地址为 `http://localhost:8080`。前端资源使用指纹长期缓存，HTML 和论文 API 使用短缓存与 `ETag`，因此后端生成新快照后 CDN 会自动重新验证。

## 验证

```powershell
cd frontend
npm run build

cd ../backend
python -m unittest discover -s tests -v
```

更多说明：

- [前端开发说明](frontend/README.md)
- [论文后端说明](backend/README.md)
- [论文平台设计](docs/publications-platform.md)

## 版权

Copyright © 2026 buerka. All rights reserved. 本项目为专有项目，未经版权所有者事先书面许可，不得使用、复制、修改或分发。详见 [LICENSE](LICENSE)。
