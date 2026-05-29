"""
论文自动分类脚本
================
从 OpenAlex API 缓存数据中读取严颖的 134 篇论文，
按研究方向和细分标签自动分类，输出为 papers.toml 格式。

使用方法：
  1. 先用 curl 抓取数据（见 README.md）
  2. python3 tools/paper_fetch/classify_papers.py

分类策略：
  基于论文标题 + journal 名称 + OpenAlex concepts 做关键词匹配，
  按优先级从高到低逐层判定：
    脑机接口 > 电机控制 > 暖通 > 遥感 > 能源 > 雷达 > 控制理论 > 机器学习 > 综述 > 其他
"""

import json, sys
from collections import Counter

# ── 加载 OpenAlex 缓存 ────────────────────────────────
CACHE_PATH = '/tmp/papers_min.json'
try:
    with open(CACHE_PATH) as f:
        works = json.load(f)['results']
    print(f"Loaded {len(works)} papers from {CACHE_PATH}")
except FileNotFoundError:
    print(f"缓存文件不存在: {CACHE_PATH}")
    print("请先运行: curl -s -m 60 --compressed 'https://api.openalex.org/works?...' -o {CACHE_PATH}")
    sys.exit(1)


def esc(s):
    """转义 TOML 字符串中的特殊字符"""
    return s.replace('\\', '\\\\').replace('"', '\\"')


def classify(paper):
    """
    分类一篇论文，返回 (研究方向, [标签列表])
    
    优先级（从上到下递减）：
    1. 脑机接口 — EEG/BCI 相关关键词
    2. 电机控制 — motor/electric 相关
    3. 暖通故障诊断 — HVAC/building 相关
    4. 遥感 — remote sensing/cloud 相关
    5. 能源电力 — energy/power 相关
    6. 雷达信号处理 — radar 相关
    7. 控制理论 — control/fault 相关
    8. 机器学习 — ML/DL 通用论文
    9. 综述 — review/survey
    10. 其他 — 未归类
    """
    title = (paper.get('title') or '').lower()
    src = paper.get('primary_location') or {}
    journal = (src.get('source') or {}).get('display_name', '').lower()
    concepts = [c.get('display_name','').lower() for c in (paper.get('concepts') or [])]
    all_text = title + ' ' + ' '.join(concepts) + ' ' + journal

    # ── 1. 脑机接口 ──
    eeg_kw = ['eeg', 'electroencephalog', 'brain-computer', 'brain-machine',
              'motor imagery', 'sensorimotor', 'bci ', 'brain machine', 'seizure', 'epilep']
    if any(kw in all_text for kw in eeg_kw):
        tags = ['EEG']
        if any(kw in all_text for kw in ['seizure detect', 'epilep']): tags.append('癫痫检测')
        if any(kw in all_text for kw in ['fatigue', 'drowsiness', 'vigilance']): tags.append('疲劳检测')
        if any(kw in all_text for kw in ['vr vertigo', 'virtual reality motion', 'vr sickness', 'motion sickness']): tags.append('VR眩晕')
        if any(kw in all_text for kw in ['brain-machine', 'brain-computer', 'motor brain', 'neuromorphic', 'spiking neural']): tags.append('运动解码')
        if any(kw in all_text for kw in ['graph neural', 'gnn', 'graph contrastive']): tags.append('图神经网络')
        if any(kw in all_text for kw in ['interpretab', 'explainab']): tags.append('可解释AI')
        if any(kw in all_text for kw in ['review', 'survey']) and 'overview' not in title: tags.append('综述')
        if any(kw in all_text for kw in ['classification', 'recogni']): tags.append('EEG分类')
        if any(kw in all_text for kw in ['feature extraction', 'wkld', 'laplace']): tags.append('特征提取')
        if any(kw in all_text for kw in ['taylor network', 'polynomial']): tags.append('泰勒网络')
        if any(kw in all_text for kw in ['deep learning', 'cnn ', 'lstm ', 'convlstm']): tags.append('深度学习')
        if any(kw in all_text for kw in ['machine learning']): tags.append('机器学习')
        if any(kw in all_text for kw in ['signal process']): tags.append('信号处理')
        if any(kw in all_text for kw in ['emotion']): tags.append('情绪识别')
        return ('脑机接口', tags)

    # ── 2. 电机控制 ──
    if any(kw in all_text for kw in ['motor ', 'reluctance motor', 'electric motor',
              'permanent magnet', 'commutation', 'sensorless control', 'switched reluctance',
              'pmsm', 'induction motor', 'torque', 'magnetic bear', 'rotor', 'stator']):
        tags = ['电机']
        if 'fault' in all_text: tags.append('故障诊断')
        if 'sensorless' in all_text: tags.append('无传感器控制')
        if 'control' in all_text: tags.append('控制理论')
        if 'optim' in all_text: tags.append('优化')
        return ('电机控制', tags)

    # ── 3. 暖通故障诊断 ──
    if any(kw in all_text for kw in ['hvac', 'air handling', 'air condit',
              'building energ', 'building simulat', 'ahu ', 'variable air volume',
              'cooling coil', 'chiller', 'building and environ']):
        tags = ['HVAC']
        if 'fault' in all_text: tags.append('故障诊断')
        if 'energy' in all_text: tags.append('建筑节能')
        if 'deep learning' in all_text: tags.append('深度学习')
        if 'neural network' in all_text: tags.append('神经网络')
        return ('暖通故障诊断', tags)

    # ── 4. 遥感 ──
    if any(kw in all_text for kw in ['remote sens', 'cloud segment', 'cloud and snow',
              'cloud shadow', 'satellite image', 'aerial']):
        tags = ['遥感']
        if 'segment' in all_text: tags.append('图像分割')
        if 'cloud' in all_text: tags.append('云检测')
        if 'deep learning' in all_text: tags.append('深度学习')
        return ('遥感', tags)

    # ── 5. 能源电力 ──
    if any(kw in all_text for kw in ['renewable energy', 'power system', 'energy system',
              'integrated energy', 'power electron', 'electricity market', 'wind power',
              'solar', 'photovoltaic', 'microgrid', 'energy storage']):
        tags = ['能源电力']
        if 'renewable' in all_text: tags.append('可再生能源')
        if 'optim' in all_text: tags.append('优化')
        if 'forecast' in all_text or 'predict' in all_text: tags.append('预测')
        return ('能源电力', tags)

    # ── 6. 雷达信号处理 ──
    if any(kw in all_text for kw in ['radar signal', 'radar']):
        tags = ['雷达']
        tags.append('信号处理')
        if 'modulation' in all_text: tags.append('调制识别')
        return ('雷达信号处理', tags)

    # ── 7. 控制理论 ──
    if any(kw in all_text for kw in ['fault detect', 'fault diagnos',
              'sliding mode', 'control theory', 'observer']):
        tags = []
        if 'fault' in all_text: tags.append('故障诊断')
        if 'sliding' in all_text: tags.append('滑模控制')
        if 'control' in all_text: tags.append('控制理论')
        if 'taylor network' in all_text or 'polynomial' in all_text: tags.append('泰勒网络')
        return ('控制理论', tags)

    # ── 8. 机器学习 ──
    if any(kw in all_text for kw in ['deep learning', 'machine learning', 'neural network',
              'artificial intelligence', 'cnn ', 'lstm ', 'classification',
              'segment', 'detection', 'predict', 'forecast', 'generative',
              'optimization', 'feature', 'recognition']):
        tags = []
        if 'deep learning' in all_text: tags.append('深度学习')
        if 'machine learning' in all_text: tags.append('机器学习')
        if 'neural network' in all_text: tags.append('神经网络')
        if 'classification' in all_text: tags.append('分类')
        if 'segment' in all_text: tags.append('分割')
        if 'predict' in all_text or 'forecast' in all_text: tags.append('预测')
        if 'fault' in all_text: tags.append('故障诊断')
        if 'taylor network' in all_text or 'polynomial' in all_text: tags.append('泰勒网络')
        if 'optim' in all_text: tags.append('优化')
        return ('机器学习', tags)

    # ── 9. 综述 ──
    if any(kw in all_text for kw in ['review', 'survey', 'overview']):
        return ('综述', ['综述'])

    # ── 10. 其他 ──
    return ('其他', ['其他'])


# ── 主流程 ──
results = []
for w in works:
    title = w.get('title') or 'Untitled'
    year = w.get('publication_year', 0)
    is_conf = w.get('type', '') in ('proceedings-article', 'conference')
    src = w.get('primary_location') or {}
    journal_name = (src.get('source') or {}).get('display_name', '')
    authorships = w.get('authorships') or []
    authors = [(a.get('author') or {}).get('display_name','') for a in authorships]
    authors = [a for a in authors if a]

    # 判断严颖是否一作或通讯
    is_lead = False
    for a in authorships:
        if (a.get('author') or {}).get('display_name','') == 'Ying Yan':
            if a.get('is_corresponding') or (authorships and a == authorships[0]):
                is_lead = True

    doi = (w.get('doi') or '').replace('https://doi.org/', '')
    field, tags = classify(w)
    t = 'conference' if is_conf else 'journal'

    results.append({
        'title': title, 'year': year, 'authors': ', '.join(authors),
        'journal': journal_name, 'doi': doi, 'type': t,
        'field': field, 'tags': tags, 'is_lead': is_lead
    })

results.sort(key=lambda x: (x['year'] or 0), reverse=True)

# ── 生成 TOML ──
all_tags = set()
for r in results:
    for t in r['tags']:
        all_tags.add(t)
filter_tags = ['全部'] + sorted(all_tags)

lines = [f'filter_tags = {json.dumps(filter_tags, ensure_ascii=False)}', '']
for i, r in enumerate(results):
    lines.append('[[papers]]')
    lines.append(f'num = "{i+1:02d}"')
    lines.append(f'year = {r["year"]}')
    lines.append(f'title = "{esc(r["title"])}"')
    lines.append(f'authors = "{esc(r["authors"])}"')
    lines.append(f'journal = "{esc(r["journal"])}"')
    if r['doi']:
        lines.append(f'doi = "{esc(r["doi"])}"')
    lines.append(f'type = "{r["type"]}"')
    lines.append(f'field = "{r["field"]}"')
    if r['is_lead']:
        lines.append(f'lead = true')
    lines.append(f'tags = {json.dumps(r["tags"], ensure_ascii=False)}')
    lines.append('')

out = '\n'.join(lines)

# 输出路径：相对于项目根目录
OUTPUT_PATH = 'src/data/papers_all.toml'
with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    f.write(out)

# ── 统计 ──
fcount = Counter(r['field'] for r in results)
print(f"\n共 {len(results)} 篇论文，分类如下：\n")
for f, c in fcount.most_common():
    print(f"  {f}: {c}篇")
print(f"\n筛选标签: {', '.join(filter_tags)}")
print(f"已写入: {OUTPUT_PATH}")
