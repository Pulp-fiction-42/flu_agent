# seqkit 使用指南

## 简介

seqkit 是一个轻量级的 FASTA/FASTQ 文件处理工具箱，使用 Go 语言开发，速度快、功能丰富。

## 安装

```bash
# conda/mamba
conda install -c bioconda seqkit

# 直接下载
wget https://github.com/shenwei356/seqkit/releases/download/v2.12.0/seqkit_darwin_amd64.tar.gz
tar -zxvf seqkit_darwin_amd64.tar.gz
mv seqkit /usr/local/bin/
```

## 常用命令

### 1. 序列统计 (stats)
```bash
seqkit stats input.fasta
# 输出：序列数、总长度、最小/最大/平均长度、GC含量

# 详细输出
seqkit stats -a input.fasta
# 包含每个序列的详细信息

# 批量统计多个文件
seqkit stats *.fasta -o summary.tsv
```

### 2. 格式转换 (fx2tab)
```bash
# 转为表格（包含ID和长度）
seqkit fx2tab input.fasta

# 包含序列内容
seqkit fx2tab -w input.fasta

# FASTQ 包含质量分数
seqkit fx2tab -q input.fastq
```

### 3. 序列搜索 (grep)
```bash
# 按 ID 搜索
seqkit grep -p "ATP synthase" input.fasta

# 正则表达式
seqkit grep -r -p "gene\d+" input.fasta

# 忽略大小写
seqkit grep -i -p "helicase" input.fasta
```

### 4. 序列去重 (rmdup)
```bash
# 按序列内容去重
seqkit rmdup -d seq input.fasta

# 按 ID 去重
seqkit rmdup -d name input.fasta
```

### 5. 序列排序 (sort)
```bash
# 按名称排序
seqkit sort input.fasta -o sorted.fasta

# 按长度排序
seqkit sort -s length input.fasta

# 倒序
seqkit sort -r -s length input.fasta
```

### 6. 提取序列 (subseq)
```bash
# 按 ID 提取
seqkit subseq input.fasta -i ID1,ID2

# 按基因组位置提取
seqkit subseq input.fasta --gtf annotation.gtf
```

### 7. 序列翻译 (translate)
```bash
# 翻译为蛋白质
seqkit translate input.fasta

# 选择密码子表
seqkit translate --codon-table vertebrate_mitochondrial input.fasta
```

## 输出格式说明

| 字段 | 说明 |
|------|------|
| seq | 序列 ID |
| len | 序列长度 |
| gc | GC 含量 (%) |
| gc1/2/3 | 各位置的 GC 含量 |

## 性能提示

- 使用 `-j` 参数指定线程数加速处理
- 大文件建议分批处理
- 使用管道连接多个命令
