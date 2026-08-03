from __future__ import annotations


def classify(work: dict) -> tuple[str, list[str]]:
    """根据标题、来源和 OpenAlex topics 生成一个研究方向和多个标签。"""
    title = (work.get('title') or '').lower()
    source = (work.get('primary_location') or {}).get('source') or {}
    venue = (source.get('display_name') or '').lower()
    topic_text: list[str] = []
    for topic in work.get('topics') or []:
        topic_text.append((topic.get('display_name') or '').lower())
        for level in ('subfield', 'field', 'domain'):
            topic_text.append(((topic.get(level) or {}).get('display_name') or '').lower())
    text = f'{title} {venue} {" ".join(topic_text)}'

    eeg_terms = (
        'eeg', 'electroencephalog', 'brain-computer', 'brain-machine',
        'motor imagery', 'sensorimotor', 'bci ', 'brain machine', 'seizure', 'epilep',
    )
    if any(term in text for term in eeg_terms):
        tags = ['EEG']
        _append(tags, '癫痫检测', text, 'seizure detect', 'epilep')
        _append(tags, '疲劳检测', text, 'fatigue', 'drowsiness', 'vigilance')
        _append(tags, 'VR眩晕', text, 'vr vertigo', 'vr sickness', 'motion sickness')
        _append(tags, '运动解码', text, 'brain-machine', 'brain-computer', 'motor imagery', 'neuromorphic')
        _append(tags, '图神经网络', text, 'graph neural', 'gnn', 'graph contrastive')
        _append(tags, '可解释AI', text, 'interpretab', 'explainab')
        _append(tags, 'EEG分类', text, 'classification', 'recognition')
        _append(tags, '特征提取', text, 'feature extraction', 'wkld', 'laplace')
        _append(tags, '泰勒网络', text, 'taylor network', 'polynomial')
        _append(tags, '深度学习', text, 'deep learning', 'cnn ', 'lstm ', 'convlstm')
        _append(tags, '机器学习', text, 'machine learning')
        _append(tags, '信号处理', text, 'signal process')
        _append(tags, '情绪识别', text, 'emotion')
        if any(term in text for term in ('review', 'survey')) and 'overview' not in title:
            tags.append('综述')
        return '脑机接口', tags

    if any(term in text for term in (
        'motor ', 'reluctance motor', 'electric motor', 'permanent magnet',
        'commutation', 'sensorless control', 'switched reluctance', 'pmsm',
        'induction motor', 'torque', 'magnetic bearing', 'rotor', 'stator',
    )):
        tags = ['电机']
        _append(tags, '故障诊断', text, 'fault')
        _append(tags, '无传感器控制', text, 'sensorless')
        _append(tags, '控制理论', text, 'control')
        _append(tags, '优化', text, 'optim')
        return '电机控制', tags

    if any(term in text for term in (
        'hvac', 'air handling', 'air conditioning', 'building energy',
        'building simulation', 'ahu ', 'variable air volume', 'cooling coil',
        'chiller', 'building and environment',
    )):
        tags = ['HVAC']
        _append(tags, '故障诊断', text, 'fault')
        _append(tags, '建筑节能', text, 'energy')
        _append(tags, '深度学习', text, 'deep learning')
        _append(tags, '神经网络', text, 'neural network')
        return '暖通故障诊断', tags

    if any(term in text for term in (
        'remote sensing', 'cloud segment', 'cloud and snow', 'cloud shadow',
        'satellite image', 'aerial image',
    )):
        tags = ['遥感']
        _append(tags, '图像分割', text, 'segment')
        _append(tags, '云检测', text, 'cloud')
        _append(tags, '深度学习', text, 'deep learning')
        return '遥感', tags

    if any(term in text for term in (
        'renewable energy', 'power system', 'energy system', 'integrated energy',
        'power electronics', 'electricity market', 'wind power', 'solar',
        'photovoltaic', 'microgrid', 'energy storage',
    )):
        tags = ['能源电力']
        _append(tags, '可再生能源', text, 'renewable')
        _append(tags, '优化', text, 'optim')
        _append(tags, '预测', text, 'forecast', 'predict')
        return '能源电力', tags

    if 'radar' in text:
        tags = ['雷达', '信号处理']
        _append(tags, '调制识别', text, 'modulation')
        return '雷达信号处理', tags

    if any(term in text for term in (
        'fault detection', 'fault diagnosis', 'sliding mode', 'control theory', 'observer',
    )):
        tags: list[str] = []
        _append(tags, '故障诊断', text, 'fault')
        _append(tags, '滑模控制', text, 'sliding')
        _append(tags, '控制理论', text, 'control')
        _append(tags, '泰勒网络', text, 'taylor network', 'polynomial')
        return '控制理论', tags or ['控制理论']

    if any(term in text for term in (
        'deep learning', 'machine learning', 'neural network', 'artificial intelligence',
        'classification', 'segmentation', 'detection', 'prediction', 'forecast',
        'generative', 'optimization', 'feature', 'recognition',
    )):
        tags = []
        _append(tags, '深度学习', text, 'deep learning')
        _append(tags, '机器学习', text, 'machine learning')
        _append(tags, '神经网络', text, 'neural network')
        _append(tags, '分类', text, 'classification')
        _append(tags, '分割', text, 'segment')
        _append(tags, '预测', text, 'predict', 'forecast')
        _append(tags, '故障诊断', text, 'fault')
        _append(tags, '泰勒网络', text, 'taylor network', 'polynomial')
        _append(tags, '优化', text, 'optim')
        return '机器学习', tags or ['机器学习']

    if any(term in text for term in ('review', 'survey', 'overview')):
        return '综述', ['综述']
    return '其他', ['其他']


def _append(tags: list[str], tag: str, text: str, *terms: str) -> None:
    if any(term in text for term in terms) and tag not in tags:
        tags.append(tag)
