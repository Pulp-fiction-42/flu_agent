# 示例文件

本目录提供用于测试 BioAgent 工作流和工具的示例文件。

## 文件说明

### sample.fastq
模拟的 FASTQ 测序数据文件（合成数据，5条读段）。
可用于测试以下功能：
- 质控工作流（quality_check）
- seqkit 统计
- fastp/fastqc 质控工具

### sample_sequences.fasta
模拟的流感病毒序列文件（4条 HA/NA 基因片段）。
可用于测试以下功能：
- 系统发育分析工作流（phylogenetic_analysis）
- seqkit 统计/搜索/去重
- mafft 多序列比对
- iqtree2 建树

## 使用示例

在 BioAgent 交互界面中输入：

```
> 帮我统计 example/sample_sequences.fasta 的序列信息
> 对 example/sample_sequences.fasta 做多序列比对
> 用 example/sample_sequences.fasta 构建系统发育树
> 对 example/sample.fastq 进行质控分析
> 运行病毒分析工作流，输入文件 example/sample.fastq
```

## 自定义文件

你也可以使用自己的数据文件，只需在输入时提供完整路径：

```
> 统计 /path/to/your/data.fasta 的序列信息
> 对 /path/to/your/reads.fastq 进行质控
```
