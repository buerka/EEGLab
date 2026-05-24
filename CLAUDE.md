# 金牛湖脑机实验室网站

## 项目概览
- 南京信息工程大学 · 金牛湖脑机实验室（Brain-Computer Interface Lab · NUIST）
- Astro 5 + React 18 静态网站，`@astrojs/react` 集成
- 暗色主题，矢车菊蓝主题色 `#5B8DEE`（RGB: 91, 141, 238）
- 10 个静态页面，`npm run dev` → localhost:4321

## 文件结构
```
src/
├── pages/
│   ├── index.astro            # 首页（Hero + Slogan + 5板块预览）
│   ├── achievements.astro     # 科研成果（论文筛选 + 奖项 + 展示）
│   ├── team.astro             # 团队成员完整页
│   ├── contact.astro          # 联系我们完整页
│   └── research/
│       ├── index.astro        # 研究方向总览（5个方向完整介绍）
│       └── [slug].astro       # 单个研究方向详情页
├── components/
│   ├── Nav.astro              # 导航栏（极简，仅 logo SVG + 4链接）
│   ├── Footer.astro           # 页脚
│   ├── HeroEEG.tsx            # React 脑电波形 Canvas 动画
│   └── PaperFilter.tsx        # React 论文分类筛选组件
├── data/
│   ├── papers.ts              # 论文数据（9篇），含 filterTags
│   ├── awards.ts              # 奖项数据（7项）
│   └── research.ts            # 研究方向数据（5个方向）
├── layouts/Layout.astro       # 全局布局（html head + slot）
└── styles/global.css          # 全局样式变量 + reset + 工具类
```

## 设计系统
- **背景**: 纯黑 `#000`，板块灰交替（`#080808`, `#040404`, `#020202`）
- **主题色**: `#5B8DEE`，相关 rgba 值 `rgba(91, 141, 238, ...)`
- **文字**: `#FFF` / `#A0A0A0` / `#707070`
- **圆角**: `--radius-lg: 20px`, `--radius-md: 12px`, `--radius-sm: 6px`
- **字体**: 系统 sans-serif（中文优先 PingFang SC）+ SF Mono 等宽
- **分区**: 每板块 `min-height: 100vh`，padding `clamp(100px, 12vw, 160px)`

## 关键交互
- **箭头动效**: `arrow-link` 类，双 SVG 叠放，hover 时 arrow-out 右上移淡出，arrow-in 从左下滑入变亮（主题色）
- **淡入动画**: `fade-up` + `delay-1~5`，IntersectionObserver 触发
- **移动端**: 导航变为汉堡菜单，2 列网格切换 1 列

## 页面路由
| 路由 | 页面 |
|------|------|
| `/` | 首页（各板块预览模式） |
| `/research` | 研究方向总览 |
| `/research/bci`, `/research/arm`, `/research/drone`, `/research/hand`, `/research/glove` | 研究方向详情 |
| `/team` | 团队成员 |
| `/achievements` | 科研成果 |
| `/contact` | 联系我们 |

## 遗留/注意事项
- 团队仅 1 名正式成员（许穆杨）+ 4 个占位卡
- 成果展示 6 张图均为占位
- 论文数据仅 9 篇代表作，实际有 60+ 篇尚未录入
- HeroEEG.tsx 4 通道 EEG 波形动画，通道标签 Fp1/C3/Pz/O2
- Nav 仅 logo SVG 无文字品牌名
- 首页 slogan: "从脑电信号到运动控制，让思想驱动未来"
- 联系标语: "汇聚跨学科智慧，诚邀各界英才共筑脑机未来"
