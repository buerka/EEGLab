# 金牛湖脑机实验室网站

## 项目概览
- 南京信息工程大学 · 金牛湖脑机实验室（Brain-Computer Interface Lab · NUIST）
- Astro 5 + React 18 静态网站，`@astrojs/react` 集成（React 仅 HeroEEG.tsx 使用）
- **亮色主题**（Neuralink 风格），主题色 `#0057FF`（蓝）
- 10 个静态页面，`npm run dev` → localhost:4321

## 文件结构
```
src/
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
│   ├── HeroEEG.tsx            # React 脑电波形 Canvas 动画（client:load）
│   ├── PaperFilter.astro      # 论文分类筛选（纯 Astro + 原生 JS，实际使用）
│   ├── PaperFilter.tsx        # 论文筛选 React 版（已弃用，保留备用）
│   └── GalleryFilter.astro    # 成果图库分类筛选（纯 Astro + 原生 JS）
├── data/
│   ├── papers.toml            # 代表作论文（9篇），含 filterTags，achievements 页使用
│   ├── papers_all.toml        # 全量论文（134篇），暂未在页面上展示
│   ├── awards.toml            # 奖项数据（12条）
│   ├── gallery.toml           # 图库数据（42条 grid + 16条 waterfall_a + 14条 waterfall_b）
│   └── research.ts            # 研究方向数据（5个方向）
├── layouts/Layout.astro       # 全局布局（html head + slot）
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

### papers.toml（代表作，9篇）
`filter_tags = ["全部","脑机接口","EEG分类","癫痫检测","运动解码","疲劳检测","图神经网络","综述","VR眩晕","一区","二区","会议"]`

每条结构：
```toml
[[papers]]
num = "01"          # 序号（字符串）
year = 2026
title = "..."
authors = "..."     # Y. Yan 会被 PaperFilter 自动加粗
journal = "..."
quartile = "一区"   # 可选
impactFactor = 6.8  # 可选，≥7 金色，≥5 蓝色
isTop = true        # 可选
tags = ["癫痫检测","EEG分类","一区"]
type = "journal"    # "journal" | "conference"
```

### papers_all.toml（全量，134篇，待接入页面）
结构与 papers.toml 一致，但数据量大，目前未在任何页面渲染。

### awards.toml（12条）
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
public/images/
├── achievements/   # 42张（产品/演示/临床/合作/专利/论文/获奖）
│   └── award-*    # 18张获奖证书/现场图，命名规范 award-{描述}.{ext}
├── research/       # 每方向各 .jpg + .png（arm/diagnosis/drone/glove/hand）
├── team/           # 已有照片：yan-ying.png, 吴奇.png, Krishna Pattipati.jpg,
│                   #           朱家琦.jpg, 宗禹胄.jpg, 陆思语.jpg, 王宇森.jpg, 沈培涵.jpg
├── nuist-logo.png / nuist-logo.jpg
└── ahjzu-logo.png

public/videos/
├── demo-eeg-cap.mp4   # 脑电帽演示录屏
└── promo.mp4          # 宣传视频
```

## 页面路由
| 路由 | 页面 |
|------|------|
| `/` | 首页（全屏滚动，6 个 section） |
| `/research` | 研究方向总览 |
| `/research/diagnosis` | 研究详情：脑科疾病诊断 |
| `/research/arm` | 研究详情：机械臂控制 |
| `/research/drone` | 研究详情：无人机控制 |
| `/research/hand` | 研究详情：康复外骨骼手套 |
| `/research/glove` | 研究详情：柔性干电极脑电帽 |
| `/team` | 团队成员 |
| `/achievements` | 科研成果 |
| `/contact` | 联系我们 |

## 团队现状
- **PI**：严颖（硕士生导师 · 副教授）
- **学术顾问**：吴奇（教授）、Krishna R. Pattipati（教授）
- **实验室成员**（11人）：许穆杨、刘浩淼、田帅、章子涵、王昊、刘志、朱家琦、宗禹胄、陆思语、王宇森、沈培涵

## 关键交互
- **首页全屏滚动**：`#fp-container` 内 6 个 `.fp-section`，`#section-nav` 侧边点状导航
- **打字动画**：`#tw-word` 循环切换词汇，`.tw-cursor` 光标闪烁
- **论文筛选**：PaperFilter.astro，`data-tags` 属性 + 原生 JS，无 React
- **图库筛选**：GalleryFilter.astro，`data-tag` 属性 + 原生 JS，无 React
- **淡入动画**：`.fade-up` + `.delay-1~5`，IntersectionObserver 触发
- **箭头动效**：`.arrow-link` 类，hover 时双 SVG 位移淡入淡出

## 遗留/注意事项
- `papers_all.toml` 有 134 篇全量论文，尚未在任何页面展示，后续可做完整论文列表页
- `PaperFilter.tsx` 是 React 版筛选器，已被 Astro 版替代，可考虑删除
- 首页 statement slogan：「让**思想**驱动未来」（`#tw-word` 轮换词汇）
- 联系标语：「汇聚跨学科智慧，诚邀各界英才共筑脑机未来」
- HeroEEG.tsx 4 通道 EEG 波形动画，通道标签 Fp1/C3/Pz/O2
- Nav 含 NUIST（www.nuist.edu.cn）和 AHJZU（www.ahjzu.edu.cn）外链
- 新增图片统一放入 `public/temp/` 后，按规范命名移至对应 `public/images/` 子目录，并同步更新 `gallery.toml` 和 `README.md`
