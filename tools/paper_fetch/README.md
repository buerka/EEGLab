# 论文自动抓取与分类

## 数据源

**OpenAlex API**（免费，无需 API Key，无限速）
- 文档：https://docs.openalex.org
- 严颖 OpenAlex ID：`A5101638873`
- ORCID：`0000-0002-3609-0496`

## 为什么选 OpenAlex

| 平台 | 优点 | 缺点 |
|------|------|------|
| **OpenAlex** | 免费、无限速、作者已消歧、支持 concept 过滤 | 无 IF / 分区 |
| Semantic Scholar | 有引用数据 | 需申请 API Key、有频率限制 |
| Google Scholar | 覆盖最全 | 反爬严重，不适合自动化 |
| ResearchGate | 可看全文 | 需手动上传，不全 |
| ORCID | 最权威身份标识 | 需作者手动维护 |

## 使用方法

### 步骤 1：抓取数据

```bash
# 用 curl 批量下载（建议加 select 参数减小体积）
curl -s -m 60 --compressed \
  "https://api.openalex.org/works?filter=authorships.author.id:A5101638873&per_page=200&sort=publication_date:desc&select=title,publication_year,type,doi,authorships,primary_location,concepts" \
  -o /tmp/papers_min.json
```

### 步骤 2：分类并生成 TOML

```bash
python3 tools/paper_fetch/classify_papers.py
```

输出：`src/data/papers_all.toml`

## 字段说明

| 字段 | 说明 |
|------|------|
| `field` | 研究方向（脑机接口/电机控制/暖通故障诊断/遥感/能源电力/机器学习/控制理论/综述/其他） |
| `tags` | 细分标签（EEG、癫痫检测、疲劳检测、VR眩晕、运动解码 等 30 个标签） |
| `type` | journal / conference |
| `lead` | 严颖是否一作或通讯 |
| `doi` | DOI（可补全 IF 和分区） |

## 局限性

1. **134 篇包含大量合作挂名论文**（电机控制、遥感、HVAC 等），需手动筛选 BCI 相关
2. **无 IF / 分区 / quartile**，需从其他来源补充
3. **部分期刊批量变化**：OpenAlex 收录预印本（bioRxiv、arXiv、SSRN），需注意区分
4. **标签为关键词自动匹配**，可能存在少量误分类
