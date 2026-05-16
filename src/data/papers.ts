export interface Paper {
  num: string;
  year: number;
  title: string;
  authors: string;
  journal: string;
  quartile?: string;
  impactFactor?: number;
  isTop?: boolean;
  tags: string[];
  type: 'journal' | 'conference';
}

export const papers: Paper[] = [
  {
    num: '01',
    year: 2026,
    title: 'Interpretable Gradient-Scored Sparse Polynomial Network for Seizure Detection',
    authors: 'Y. Yan, J. Zhu, Y. Cao, J. Cai, S. Fang, S. Rong, A. D. Cheok',
    journal: 'Information Sciences',
    quartile: '一区',
    impactFactor: 6.8,
    isTop: true,
    tags: ['癫痫检测', 'EEG分类', '一区'],
    type: 'journal',
  },
  {
    num: '02',
    year: 2026,
    title: 'Residual Multi-Dimensional Taylor Network for Epileptic Electroencephalography Detection',
    authors: 'Y. Yan, G. Liu, H. Cai, E. Q. Wu, J. Cai, A. D. Cheok, N. Liu, A. Song',
    journal: 'Engineering Applications of AI',
    quartile: '一区',
    impactFactor: 8.0,
    isTop: true,
    tags: ['癫痫检测', 'EEG分类', '一区'],
    type: 'journal',
  },
  {
    num: '03',
    year: 2025,
    title: 'A Neuromorphic Approach for Brain-Machine Interface Using Spiking Neural Networks',
    authors: 'G. Liu, Y. Yan, S. He, J. Cai, A. D. Cheok, E. Q. Wu, A. Song',
    journal: 'IEEE EMBC 2025',
    tags: ['脑机接口', 'SNN', '会议'],
    type: 'conference',
  },
  {
    num: '04',
    year: 2025,
    title: 'A More Rational and Efficient Kalman Filter Design for Motor Brain-Machine Interfaces',
    authors: 'G. Liu, Y. Yan, J. Cai, A. D. Cheok, E. Q. Wu, A. Song',
    journal: 'IEEE EMBC 2025',
    tags: ['脑机接口', '运动解码', '会议'],
    type: 'conference',
  },
  {
    num: '05',
    year: 2025,
    title: 'Polynomial Gated Network: An Intelligent Classification Method for Driver Fatigue Based on EEG Analysis',
    authors: 'C. Huangfu, Y. Yan, N. Liu, J. Cai, S. Fang, E. Q. Wu, C. Hua, A. Song',
    journal: 'Measurement',
    quartile: '二区',
    impactFactor: 5.6,
    tags: ['疲劳检测', 'EEG分类', '二区'],
    type: 'journal',
  },
  {
    num: '06',
    year: 2024,
    title: 'GCD: Graph Contrastive Denoising Module for GNNs in EEG Classification',
    authors: 'G. Liu, Y. Yan, J. Cai, E. Q. Wu, S. Fang, A. D. Cheok, A. Song',
    journal: 'Expert Systems with Applications',
    quartile: '一区',
    impactFactor: 7.5,
    isTop: true,
    tags: ['EEG分类', '图神经网络', '一区'],
    type: 'journal',
  },
  {
    num: '07',
    year: 2024,
    title: 'A Review of Graph Theory-Based Diagnosis of Neurological Disorders Based on EEG and MRI',
    authors: 'Y. Yan, G. Liu, H. Cai, E. Q. Wu, J. Cai, A. D. Cheok, N. Liu, T. Li, Z. Fan',
    journal: 'Neurocomputing',
    quartile: '二区',
    impactFactor: 5.5,
    tags: ['综述', 'EEG分类', '二区'],
    type: 'journal',
  },
  {
    num: '08',
    year: 2024,
    title: 'WKLD-Based Feature Extraction for Diagnosis of Epilepsy Based on EEG',
    authors: 'H. Cai, Y. Yan, G. Liu, J. Cai, A. D. Cheok, N. Liu, C. Hua, J. Lian, Z. Fan, A. Chen',
    journal: 'IEEE Access',
    tags: ['癫痫检测', 'EEG分类'],
    type: 'journal',
  },
  {
    num: '09',
    year: 2023,
    title: 'VR Vertigo Level Classification Using a Multi-Dimensional Taylor Network Approach',
    authors: 'Z. Wang, Y. Yan, J. Cai, C. Hua, N. Liu, Q. Chen, M. Li, D. Zhang',
    journal: 'IEEE Access',
    tags: ['VR眩晕', 'EEG分类'],
    type: 'journal',
  },
];

export const filterTags = ['全部', '脑机接口', 'EEG分类', '癫痫检测', '运动解码', '疲劳检测', '图神经网络', '综述', 'VR眩晕', '一区', '二区', '会议'] as const;
export type FilterTag = typeof filterTags[number];
