# 金牛湖脑机实验室网站

## 新会话接管入口

先读 [项目接管说明](docs/handoff.md)，再运行 `git status --short`、`git branch --show-current`、`git log -5 --oneline`，确认当前分支和已有修改。本文与接管说明记录截至 2026-09-06 的状态，线上资源和数据需按任务重新核对；不要将历史验证当作实时结果。

审计报告、扫描明细和复现结果只保存在 Git 已忽略的 `output/`，不要提交或推送到仓库，除非用户明确要求。

## 项目概览
- 南京信息工程大学 · 金牛湖脑机实验室（Brain-Computer Interface Lab · NUIST）
- Astro 6 + React 18 静态网站，React 用于动态论文组件；HeroEEG.tsx 保留但当前页面未引用
- **亮色主题**（Neuralink 风格），主题色 `#0057FF`（蓝）
- 前端位于 `frontend/`，10 个静态页面；`cd frontend && npm run dev` → localhost:4321
- 正式地址：`https://eeg.yanyinglab.cn`；腾讯云国内站 Makers 托管网页/API、上海 SCF 每天北京时间 03:30 同步、COS 私有存储
- 后端位于 `backend/`，共享 Python 业务逻辑；Starlette、CLI、常驻调度器及 `docker-compose.yml` 用于本地/Docker
- Node.js 使用 `22.21.1`，最低 `22.12.0`；云端 Python 3.10；文档核对日期 2026-09-06

## 文件结构
```
frontend/src/
├── pages/
│   ├── index.astro            # 首页（全屏滚动：hero / statement / research / team / papers / contact）
│   ├── achievements.astro     # 科研成果（论文筛选 + 奖项时间线 + 成果图库筛选）
│   ├── team.astro             # 团队成员完整页
│   ├── contact.astro          # 联系我们完整页
│   └── research/
│       ├── index.astro        # 研究方向总览（5个方向完整介绍）
│       └── [slug].astro       # 单个研究方向详情页
├── components/
│   ├── Nav.astro              # 导航栏（logo SVG + 4链接 + 2机构外链 NUIST/AHJZU）
│   ├── Footer.astro           # 页脚
│   ├── HeroEEG.tsx            # 保留的 React Canvas 组件，当前页面未引用
│   ├── PublicationsExplorer.tsx # 成果页研究者、代表作、标签和关键词筛选
│   ├── FeaturedPublications.tsx # 首页代表论文
│   ├── RelatedPublications.tsx  # 研究页相关论文
│   ├── PublicationCount.tsx     # 首页论文数量
│   └── GalleryFilter.astro    # 成果图库分类筛选（纯 Astro + 原生 JS）
├── data/
│   ├── awards.toml            # 奖项数据（17条）
│   ├── gallery.toml           # 图库数据（42条 grid + 16条 waterfall_a + 14条 waterfall_b）
│   └── research.ts            # 研究方向数据（5个方向）
├── lib/publications.ts        # 论文 API 客户端和类型
├── layouts/Layout.astro       # 全局布局和匿名访问统计上报
└── styles/global.css          # 全局 CSS 变量 + reset
```

## 设计系统（亮色主题）
- **背景**: `--bg: #FFFFFF` / `--bg-surface: #F5F5F5` / `--bg-elevated: #EEEEEE`
- **深色区**: `--bg-dark: #0A0A0A`（首页 hero / statement / contact 板块）
- **主题色**: `--accent: #0057FF`，dim `rgba(0,87,255,0.08)`，mid `rgba(0,87,255,0.2)`
- **文字**: `--text: #0A0A0A` / `--text-2: #444444` / `--text-3: #888888` / `--text-inv: #FFFFFF`
- **边框**: `--border: rgba(0,0,0,0.08)` / `--border-md: rgba(0,0,0,0.15)`
- **圆角**: `--radius-lg: 18px` / `--radius-md: 10px` / `--radius-sm: 4px` / `--radius-pill: 999px`
- **字体**: `--font-sans`: 系统 sans-serif（中文优先 PingFang SC）；`--font-mono`: SF Mono / Fira Code

## 数据文件说明

### 论文数据（后端与 COS）

- 前端论文 TOML 和两个旧 PaperFilter 组件已删除；不要恢复前端构建时导入论文 TOML 的方式。
- `backend/data/papers.toml` 有 136 条原始种子；`researchers.toml` 有 1 位研究者；`scholar_reviews.toml` 有 32 条审核规则和 1 条合并规则。
- 原始论文种子只导入空库，修改它不会自动改变已有生产快照；研究者种子和审核规则在写入初始化时应用，须更新两端部署并经后续同步提交。
- 种子数量、审核合并后数量和在线快照数量不同。2026-09-06 上线时 API 返回 157 条，后续以 `/api/papers` 为准，不写死数量。
- OpenAlex 提供规范元数据，Google Scholar 经 SerpAPI 提供核验和引用指标；人工字段、代表作和审核决定必须保留。
- 生产数据保存在 COS 不可覆盖快照中；SQLite 只作为每次云函数调用的临时工作区。写冲突返回 409，失败不覆盖旧快照。
- 公开接口：`/api/papers`、`/api/researchers`、`/api/papers/version`、`/api/sync/status`、`/api/analytics/summary`；统计上报为 `POST /api/analytics/pageview`。

### awards.toml（17条）
```toml
[[awards]]
year = 2025
name = "奖项名称"
description = "描述"
```

### gallery.toml
- `[[waterfall_a]]` / `[[waterfall_b]]`：首页瀑布流左/右列，各自只需 `src`
- `[[grid]]`：成果页图库，需 `src` + `label` + `tag`
- tag 取值：`产品` / `演示` / `临床` / `合作` / `专利` / `论文` / `获奖`（共 7 类）

## 图片资产
```
frontend/public/images/
├── achievements/   # 42张（产品/演示/临床/合作/专利/论文/获奖）
│   └── award-*    # 18张获奖证书/现场图，命名规范 award-{描述}.{ext}
├── research/       # 每方向各 .webp + -diagram.webp（arm/diagnosis/drone/glove/hand）
├── team/           # 核心 2 人、顾问 6 人、本科生 6 人、研究生 5 人照片
├── nuist-logo.webp / nuist-logo-photo.webp
└── ahjzu-logo.webp

frontend/public/videos/
├── demo-eeg-cap.mp4   # 脑电帽演示素材，当前未接入页面
└── promo.mp4          # 首页 Hero 背景视频，约 20.5 MB，旧版本由 Git 保留
```

## 页面路由
| 路由 | 页面 |
|------|------|
| `/` | 首页（全屏滚动，6 个 section） |
| `/research` | 研究方向总览 |
| `/research/diagnosis` | 研究详情：脑疾病诊断 |
| `/research/arm` | 研究详情：脑控机械臂 |
| `/research/drone` | 研究详情：脑控无人机 |
| `/research/hand` | 研究详情：脑控灵巧手 |
| `/research/glove` | 研究详情：脑控气动手套 |
| `/team` | 团队成员 |
| `/achievements` | 科研成果 |
| `/contact` | 联系我们 |

## 当前页面团队数据
- **核心**：严颖（学术核心）、刘娜（临床核心）
- **顾问 6 人**：方申存、蔡骏、Adrian David Cheok、吴奇、Peter B. Luh、Krishna R. Pattipati
- **实验室成员**（11人）：许穆杨、刘浩淼、田帅、章子涵、王昊、刘志、朱家琦、宗禹胄、陆思语、王宇森、沈培涵

## 关键交互
- **首页全屏滚动**：`#fp-container` 内 6 个 `.fp-section`，`#section-nav` 侧边点状导航
- **打字动画**：`#tw-word` 循环切换词汇，`.tw-cursor` 光标闪烁
- **论文筛选**：PublicationsExplorer.tsx，React 状态筛选，支持加载、错误与重试
- **图库筛选**：GalleryFilter.astro，`data-tag` 属性 + 原生 JS，无 React
- **淡入动画**：`.fade-up` + `.delay-1~5`，IntersectionObserver 触发
- **箭头动效**：`.arrow-link` 类，hover 时双 SVG 位移淡入淡出

## 维护注意事项
- 首页 Hero 使用宣传视频；`HeroEEG.tsx` 虽有 Fp1/C3/Pz/O2 四通道动画，但当前未接入页面。
- 首页与团队页分别维护团队数组，修改时同步两处；文档记录页面内容，不替代人员信息确认。
- 首页 statement slogan：「让**思想**驱动未来」（`#tw-word` 轮换词汇）
- 联系标语：「汇聚跨学科智慧，诚邀各界英才共同探索脑机接口前沿」
- Nav 含 NUIST（www.nuist.edu.cn）和 AHJZU（www.ahjzu.edu.cn）外链
- 新增图片统一放入 `frontend/public/temp/` 后，按规范命名移至对应 `frontend/public/images/` 子目录，并同步更新 `gallery.toml` 和 `README.md`
- 所有单个静态文件不超过 25 MB，部署输入检查包含该门禁；成果媒体清单见 `frontend/public/images/achievements/README.md`。

## 开发、验证与发布

- 本地：后端安装 `requirements-dev.txt`，运行 `python -m app.cli init` 和 `python -m uvicorn app.main:app --reload --port 8000`；前端 `/api` 开发代理指向本地 8000。已有 `.env` 时不要用模板覆盖。
- 根目录验证命令：`npm run test:backend`、`npm run build`、`python scripts/check_deployment.py`；云端测试依赖还包括 `cloud-functions/requirements.txt`。核对时共 29 项后端测试。
- Makers 必须导入仓库根目录：安装 `npm --prefix frontend ci`，构建 `npm run build`，输出 `frontend/dist`。`edgeone.json` 指定上海云函数。
- `cloud-functions/api/[[default]].py` 提供 `/api/*`；`scripts/prepare-makers.mjs` 生成私有 `_vendor`，不得提交或放入静态公开目录。
- Handler 必须显式定义 `do_GET`、`do_POST` 等方法，不能使用链式赋值别名；Makers 构建器会漏掉该方式声明的请求方法。
- `PAPERS_ALLOWED_ORIGINS` 必须包含实际站点 HTTPS 来源；回源 Host 不一定等于公开域名。Makers 健康接口为 `/api/health`，本地/Docker 为 `/health`。
- GitHub `.github/workflows/ci.yml` 只负责验证、构建检查和 SCF 打包，不持有云密钥。Makers 的 `main` 自动发布与 CI 独立，当前没有 CI 发布门禁。
- 预览分支自动部署关闭，生产凭据仅在生产环境生效；开启预览前须配置独立前缀和权限。
- SCF 入口为 `deploy/scf/index.py` 的 `index.main_handler`，每天北京时间 03:30 运行；512 MB、300 秒、最大并发 1，无预置实例。
- 修改 SCF 业务代码、依赖或种子后，仍须上传 CI 生成的内部 ZIP；Git 推送不会自动更新 SCF。Windows `--source-only` 包仅供审阅，部署包需 Linux Python 3.10 构建。
- COS 必须使用从未开启版本控制的私有桶。云端统计按 30 秒固定窗口去重，SCF 汇总后清理超过 32 天的已结算匿名记录；不保存原始 IP / User-Agent。
- `PUBLIC_ICP_NUMBER` 只填写确认的真实备案号，留空不显示；密钥不能使用 `PUBLIC_` 前缀。

## 文档维护

以根目录 `README.md` 和 `docs/handoff.md` 为接管入口，设计见 `docs/publications-platform.md`，操作步骤见 `docs/tencent-makers.md`，生产配置和验收记录见 `docs/tencent-production.md`。部署、数据流、环境变量、组件和媒体变更时同步相关文档；完成事项同步 `todo.md`，历史验证注明时间与范围。
