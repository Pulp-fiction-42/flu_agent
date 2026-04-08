# 2. 病毒比对与映射 (Viral Alignment)

## 概述
病毒序列比对工具用于将测序reads或组装序列与参考基因组进行比对。

## 常用工具

### 短读比对
- **BWA**: Burrows-Wheeler比对器
- **Bowtie2**: 快速比对工具
- **STAR**: RNA-seq 比对器
- **HISAT2**: 快速RNA-seq比对

### 长读比对
- **Minimap2**: 长读长比对工具
- **BLASR**: PacBio 比对器
- **NGMLR**: 纳米孔比对

### 病毒特异性比对
- **ViReMa**: 病毒reads映射
- **ViralConsensus**: 病毒共识序列
- **iVar**: 病毒变异分析

### 工具
- **Samtools**: SAM/BAM 处理
- **BamTools**: BAM 文件工具
- **Picard**: NGS 工具集

## 使用场景
- 变异检测前的reads映射
- 病毒覆盖度分析
- 整合检测

## 注意事项
- 选择合适的参考基因组
- 考虑使用病毒特异性的比对参数
- 深度覆盖影响检测灵敏度
