import{j as a}from"./jsx-runtime.DhNDwAgn.js";import{r as p}from"./index.CBFZI7UH.js";const n=[{num:"01",year:2026,title:"Interpretable Gradient-Scored Sparse Polynomial Network for Seizure Detection",authors:"Y. Yan, J. Zhu, Y. Cao, J. Cai, S. Fang, S. Rong, A. D. Cheok",journal:"Information Sciences",quartile:"一区",impactFactor:6.8,isTop:!0,tags:["癫痫检测","EEG分类","一区"],type:"journal"},{num:"02",year:2026,title:"Residual Multi-Dimensional Taylor Network for Epileptic Electroencephalography Detection",authors:"Y. Yan, G. Liu, H. Cai, E. Q. Wu, J. Cai, A. D. Cheok, N. Liu, A. Song",journal:"Engineering Applications of AI",quartile:"一区",impactFactor:8,isTop:!0,tags:["癫痫检测","EEG分类","一区"],type:"journal"},{num:"03",year:2025,title:"A Neuromorphic Approach for Brain-Machine Interface Using Spiking Neural Networks",authors:"G. Liu, Y. Yan, S. He, J. Cai, A. D. Cheok, E. Q. Wu, A. Song",journal:"IEEE EMBC 2025",tags:["脑机接口","SNN","会议"],type:"conference"},{num:"04",year:2025,title:"A More Rational and Efficient Kalman Filter Design for Motor Brain-Machine Interfaces",authors:"G. Liu, Y. Yan, J. Cai, A. D. Cheok, E. Q. Wu, A. Song",journal:"IEEE EMBC 2025",tags:["脑机接口","运动解码","会议"],type:"conference"},{num:"05",year:2025,title:"Polynomial Gated Network: An Intelligent Classification Method for Driver Fatigue Based on EEG Analysis",authors:"C. Huangfu, Y. Yan, N. Liu, J. Cai, S. Fang, E. Q. Wu, C. Hua, A. Song",journal:"Measurement",quartile:"二区",impactFactor:5.6,tags:["疲劳检测","EEG分类","二区"],type:"journal"},{num:"06",year:2024,title:"GCD: Graph Contrastive Denoising Module for GNNs in EEG Classification",authors:"G. Liu, Y. Yan, J. Cai, E. Q. Wu, S. Fang, A. D. Cheok, A. Song",journal:"Expert Systems with Applications",quartile:"一区",impactFactor:7.5,isTop:!0,tags:["EEG分类","图神经网络","一区"],type:"journal"},{num:"07",year:2024,title:"A Review of Graph Theory-Based Diagnosis of Neurological Disorders Based on EEG and MRI",authors:"Y. Yan, G. Liu, H. Cai, E. Q. Wu, J. Cai, A. D. Cheok, N. Liu, T. Li, Z. Fan",journal:"Neurocomputing",quartile:"二区",impactFactor:5.5,tags:["综述","EEG分类","二区"],type:"journal"},{num:"08",year:2024,title:"WKLD-Based Feature Extraction for Diagnosis of Epilepsy Based on EEG",authors:"H. Cai, Y. Yan, G. Liu, J. Cai, A. D. Cheok, N. Liu, C. Hua, J. Lian, Z. Fan, A. Chen",journal:"IEEE Access",tags:["癫痫检测","EEG分类"],type:"journal"},{num:"09",year:2023,title:"VR Vertigo Level Classification Using a Multi-Dimensional Taylor Network Approach",authors:"Z. Wang, Y. Yan, J. Cai, C. Hua, N. Liu, Q. Chen, M. Li, D. Zhang",journal:"IEEE Access",tags:["VR眩晕","EEG分类"],type:"journal"}],c=["全部","脑机接口","EEG分类","癫痫检测","运动解码","疲劳检测","图神经网络","综述","VR眩晕","一区","二区","会议"];function u(i){return i.replace(/(Y\. Yan)/g,"<mark>$1</mark>")}function m(){const[i,s]=p.useState("全部"),t=i==="全部"?n:n.filter(e=>e.tags.includes(i)),l=[...new Set(t.map(e=>e.year))].sort((e,r)=>r-e);return a.jsxs("div",{children:[a.jsx("div",{className:"filter-bar",children:c.map(e=>a.jsx("button",{className:`filter-chip ${i===e?"active":""}`,onClick:()=>s(e),children:e},e))}),a.jsxs("div",{className:"paper-list",children:[l.map(e=>a.jsxs("div",{children:[a.jsx("div",{className:"year-divider",children:a.jsx("span",{children:e})}),t.filter(r=>r.year===e).map(r=>a.jsxs("div",{className:"paper-row",children:[a.jsx("div",{className:"pr-num",children:r.num}),a.jsxs("div",{className:"pr-body",children:[a.jsx("div",{className:"pr-title",children:r.title}),a.jsx("div",{className:"pr-authors",dangerouslySetInnerHTML:{__html:u(r.authors)}}),a.jsxs("div",{className:"pr-tags",children:[a.jsx("span",{className:"pr-tag venue",children:r.journal}),r.impactFactor&&a.jsxs("span",{className:"pr-tag if",children:["IF ",r.impactFactor]}),r.quartile&&a.jsxs("span",{className:`pr-tag rank ${r.isTop?"top":""}`,children:[r.quartile,r.isTop?" Top":""]}),r.tags.filter(o=>!["一区","二区","会议"].includes(o)).map(o=>a.jsx("span",{className:"pr-tag topic",children:o},o))]})]}),a.jsx("div",{className:"pr-year",children:r.year})]},r.num))]},e)),t.length===0&&a.jsx("p",{className:"no-results",children:"该分类下暂无论文"})]}),a.jsx("style",{children:`
        .filter-bar {
          display: flex;
          flex-wrap: wrap;
          gap: 6px;
          margin-bottom: 48px;
        }
        .filter-chip {
          padding: 6px 16px;
          font-size: 12px;
          font-weight: 400;
          border-radius: 100px;
          border: 1px solid rgba(255,255,255,0.14);
          background: transparent;
          color: #888;
          cursor: pointer;
          transition: background 0.15s, color 0.15s, border-color 0.15s;
          font-family: inherit;
          letter-spacing: 0.2px;
          line-height: 1.5;
        }
        .filter-chip:hover {
          border-color: rgba(255,255,255,0.3);
          color: #bbb;
        }
        .filter-chip.active {
          background: rgba(91,141,238,0.12);
          border-color: rgba(91,141,238,0.3);
          color: #8FB0F2;
        }
        .paper-list {
          display: flex;
          flex-direction: column;
        }
        .year-divider {
          display: flex;
          align-items: center;
          gap: 16px;
          padding: 24px 16px 10px;
          font-size: 11px;
          letter-spacing: 3px;
          color: #555;
          font-family: 'SF Mono', monospace;
        }
        .year-divider::after {
          content: '';
          flex: 1;
          height: 1px;
          background: rgba(255,255,255,0.08);
        }
        .paper-row {
          display: grid;
          grid-template-columns: 44px 1fr auto;
          gap: 20px;
          align-items: start;
          padding: 20px 16px;
          border-radius: 8px;
          transition: background 0.15s;
        }
        .paper-row:hover {
          background: rgba(255,255,255,0.02);
        }
        .pr-num {
          font-size: 11px;
          color: #555;
          font-family: 'SF Mono', monospace;
          padding-top: 3px;
          font-variant-numeric: tabular-nums;
        }
        .pr-title {
          font-size: 15px;
          font-weight: 500;
          line-height: 1.55;
          margin-bottom: 6px;
          color: #EBEBF0;
          letter-spacing: -0.01em;
        }
        .pr-authors {
          font-size: 12px;
          color: #888;
          margin-bottom: 10px;
          line-height: 1.6;
        }
        .pr-authors mark {
          background: none;
          color: #8FB0F2;
          font-weight: 600;
        }
        .pr-tags {
          display: flex;
          flex-wrap: wrap;
          gap: 5px;
        }
        .pr-tag {
          display: inline-block;
          font-size: 11px;
          padding: 2px 8px;
          border-radius: 4px;
          font-family: 'SF Mono', monospace;
        }
        .pr-tag.venue {
          background: rgba(91,141,238,0.08);
          color: #A2BFF5;
          border: 1px solid rgba(91,141,238,0.15);
        }
        .pr-tag.if {
          background: rgba(255,255,255,0.06);
          color: #888;
        }
        .pr-tag.rank {
          background: rgba(255,255,255,0.06);
          color: #888;
        }
        .pr-tag.rank.top {
          background: rgba(80,200,120,0.08);
          color: #6DD09B;
        }
        .pr-tag.topic {
          background: transparent;
          color: #666;
          border: 1px solid rgba(255,255,255,0.1);
        }
        .pr-year {
          font-size: 11px;
          color: #555;
          font-family: 'SF Mono', monospace;
          padding-top: 3px;
          white-space: nowrap;
          font-variant-numeric: tabular-nums;
        }
        .no-results {
          color: #666;
          font-size: 14px;
          padding: 40px 16px;
          text-align: center;
        }
        @media (max-width: 560px) {
          .paper-row { grid-template-columns: 1fr; gap: 8px; }
          .pr-num, .pr-year { display: none; }
        }
      `})]})}export{m as default};
