# 4. 变异检测 (Variant Calling)

## 概述
病毒基因组变异检测工具用于识别SNP、InDel和其他变异。

## 常用工具

### 通用变异检测
- **FreeBayes**: 贝叶斯变异检测
- **GATK**: 基因组分析工具包
- **VarScan**: 癌症和种系变异
- **LoFreq**: 低频变异检测
- **iVar**: 病毒变异分析

### 病毒特异性
- **ViReMa**: 病毒重组检测
- **ViralVariantCaller**: 病毒变异调用
- **CoV-Glue**: SARS-CoV-2 变异分析

### 变异注释
- **SnpEff**: 变异注释
- **ANNOVAR**: 功能注释
- **VEP**: 变异效应预测

### 变异过滤
- **Vcftools**: VCF 文件处理
- **BCFtools**: BCF/VCF 工具

## 使用场景
- 病毒群体遗传分析
- 耐药突变检测
- 传播链追踪

## 注意事项
- 病毒高度变异需特殊处理
- 混合感染样本的复杂性
- 最低覆盖度要求
