export interface Award {
  year: number;
  name: string;
  description: string;
}

export const awards: Award[] = [
  {
    year: 2025,
    name: '中国技协职工技术创新成果二等奖',
    description: '基于脑电信号与新型可解释机器学习方法的脑科疾病诊断研究，第一完成人，2025年2月',
  },
  {
    year: 2024,
    name: '大学生创新大赛国际赛道国家铜奖',
    description: 'NeuroLynx — Portable Monitoring and Diagnosis Device for Neurological Disorders，指导老师：严颖',
  },
  {
    year: 2024,
    name: '全省职工"五小"活动省级入库项目',
    description: '第一完成人，2024年9月',
  },
  {
    year: 2024,
    name: '江北新区"科创江北"高价值专利培育大赛一等奖',
    description: '第四届"科创江北、搏动未来"高价值专利培育大赛，南京，2024年4月',
  },
  {
    year: 2024,
    name: '金牛湖产教融合园区"优秀双创导师"',
    description: '2024年度"双创之星"评定，金牛湖产教融合园区',
  },
  {
    year: 2023,
    name: 'IEEE PHM 最佳会议论文奖（Best Paper Award）',
    description: '第14届 IEEE Global Reliability & Prognostics and Health Management Conference，杭州，2023年10月',
  },
  {
    year: 2023,
    name: '江苏省自动化学会科学技术奖三等奖',
    description: '智能建筑暖通空调系统的故障诊断与预测研究，第一完成人，南京，2024年2月',
  },
];
