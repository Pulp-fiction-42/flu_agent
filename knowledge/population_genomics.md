# 群体基因组学基础知识

## 概述

群体基因组学（Population Genomics）是研究物种内不同种群基因组变异规律的学科，结合了群体遗传学与基因组学的方法。

## 核心概念

### 1. 遗传多样性
- **核苷酸多样性（π）**: 种群内任意两个序列之间核苷酸差异的平均比例
- **θ（Theta）**: 基于突变率的遗传多样性估计
- **Tajima's D**: 检验中性进化假设的统计量

### 2. 选择信号
- **正向选择（Positive Selection）**: 有利突变在种群中频率增加
- **负向选择（Purifying Selection）**: 有害突变被清除
- **平衡选择（Balancing Selection）**: 维持多个等位基因

### 3. 种群结构
- **Fst（遗传分化指数）**: 衡量种群间遗传分化程度
- **连锁不平衡（LD）**: 不同位点之间的相关性
- **有效种群大小（Ne）**: 对遗传变异有实际贡献的种群大小

## 常用分析方法

### 群体遗传学分析
1. **SNP calling**: 从测序数据中识别单核苷酸多态性
2. **群体结构分析**: PCA、Admixture、TreeMix
3. **选择性扫描检测**: iHS, XP-EHH, Fst outlier

### 系统发育分析
1. **建树方法**: NJ, ML, BI
2. **多序列比对**: MAFFT, Muscle, ClustalW
3. **进化速率估计**: Molecular clock

## 常用工具

| 工具 | 用途 |
|------|------|
| GATK | SNP calling |
| VCFtools | 变异数据处理 |
| Plink | 群体遗传分析 |
| ADMIXTURE | 种群结构分析 |
| iqtree2 | 最大似然建树 |
| PAML | 分子进化分析 |
| MaFit/MEGA | 多序列比对 |

## 工作流程示例

### 1. 变异检测流程
```
原始数据 → 质控 → 比对 → SNP Calling → 过滤 → VCF
```

### 2. 群体结构分析流程
```
VCF → 过滤 → PCA/Admixture → 种群结构可视化
```

### 3. 选择信号检测流程
```
VCF → 计算统计量(iHS/Fst) → 候选区域筛选 → 功能注释
```

## 参考资料

- Nielsen R, et al. (2007) Recent progress in population genomics. Nature Reviews Genetics
- Cruickshank TE, Hahn MW (2014) Reanalyzing the genomic data. Molecular Ecology
