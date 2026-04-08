# 工具使用模式与最佳实践

## 序列分析工具使用指南

### SeqKit - 序列处理利器

SeqKit 是处理 FASTA/FASTQ 文件的瑞士军刀。

#### 常用命令

```bash
# 序列统计
seqkit stats file.fasta

# 序列提取
seqkit subseq --chr chr1:1000-2000 file.fasta

# 序列筛选（按长度）
seqkit seq -m 100 file.fasta

# 格式转换
seqkit fq2fa file.fastq

# 去重
seqkit rmdup file.fasta
```

#### 使用场景

| 需求 | 推荐命令 |
|------|----------|
| 快速查看文件信息 | `seqkit stats -a` |
| 提取特定序列 | `seqkit grep -s -i "pattern"` |
| 序列排序 | `seqkit sort -l` |
| 随机抽样 | `seqkit sample -n 1000` |

---

## 质控工具使用指南

### Fastp - 快速质控

```bash
# 基本质控
fastp -i input.fq -o output.fq

# 带报告
fastp -i input.fq -o output.fq -h report.html -j report.json

# 过滤低质量
fastp -i input.fq -o output.fq --cut_mean_quality 20
```

### FastQC - 质量报告

```bash
# 基本使用
fastqc input.fq

# 多文件
fastqc *.fq -o output_dir/
```

---

## 组装工具使用指南

### SPAdes - 基因组组装

```bash
# 细菌基因组
spades.py -k 21,33,55,77 -careful -s reads.fq -o output/

# 混合组装
spades.py -k 21,33,55 --sc -1 pe1.fq -2 pe2.fq -s se.fq -o output/
```

### MEGAHIT -宏基因组组装

```bash
megahit -1 pe1.fq -2 pe2.fq -o output/
```

---

## 比对工具使用指南

### BWA - 序列比对

```bash
# 建立索引
bwa index ref.fasta

# 比对
bwa mem ref.fasta reads.fq > alignment.sam
```

### Minimap2 - 长读长比对

```bash
# DNA 比对
minimap2 -ax map-pb ref.fasta reads.fq > alignment.sam

# RNA 比对
minimap2 -ax splice ref.fasta reads.fq > alignment.sam
```

---

## 进化分析工具使用指南

### MAFFT - 多序列比对

```bash
# 快速比对
mafft input.fasta > output.fasta

# 精确比对
mafft --localpair --maxiterate 1000 input.fasta > output.fasta
```

### IQ-TREE2 - 最大似然建树

```bash
# 自动选择最佳模型
iqtree2 -s alignment.fasta -bb 1000 -alrt 1000

# 指定模型
iqtree2 -s alignment.fasta -m GTR+G -bb 1000
```

---

## 最佳实践

### 1. 数据预处理
1. 先做质控（fastp/fastqc）
2. 根据质量报告决定过滤参数
3. 保留原始数据备份

### 2. 工具选择
- 小基因组（细菌）：SPAdes
- 大基因组：Canu/Flye
- 宏基因组：MEGAHit

### 3. 参数优化
- k-mer 大小：根据测序读长调整
- 覆盖度：影响组装质量
- 质量阈值：根据下游分析需求

### 4. 结果验证
- 检查 N50、L50 统计
- 使用 QUAST 评估
- 与参考基因组比对验证
