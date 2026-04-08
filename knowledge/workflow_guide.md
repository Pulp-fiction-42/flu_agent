# 工作流使用指南

## 什么是工作流

工作流是多个生信工具的自动化编排流水线。用户只需提供一个输入文件，系统就会按照预设的步骤顺序执行，自动完成从原始数据到分析报告的全流程。

## 可用工作流

### 1. virus_analysis（病毒全流程分析）
**描述**: fastq质控 → de novo组装 → 序列统计 → 病毒鉴定  
**触发关键字**: 病毒分析、流程分析、分析fastq、病毒鉴定、全流程  
**参数**:
- `input_file`（必填）: FASTQ 文件路径
- `output_dir`（可选）: 输出目录

### 2. quality_check（质控报告流水线）
**描述**: fastp质控 → fastqc报告 → seqkit统计 → multiqc汇总  
**触发关键字**: 质控、质量检查、QC、quality check  
**参数**:
- `input_file`（必填）: FASTQ 文件路径
- `output_dir`（可选）: 输出目录

### 3. phylogenetic_analysis（系统发育分析）
**描述**: 序列统计 → mafft多序列比对 → trimal裁剪 → iqtree建树  
**触发关键字**: 系统发育、进化分析、进化树、系统发育树  
**参数**:
- `input_file`（必填）: 多序列 FASTA 文件
- `output_dir`（可选）: 输出目录
- `strategy`（可选）: mafft 比对策略（auto/localpair/globalpair）

## 使用方式

### 方式一：自然语言触发
直接描述你的需求，LLM 会自动选择合适的工作流：
```
> 对 example/sample.fastq 进行质控分析
> 帮我分析这个 fastq 文件，从质控到组装到鉴定
> 用 example/sample_sequences.fasta 构建系统发育树
```

### 方式二：命令触发
输入 `workflows` 查看所有可用工作流，然后直接描述需求即可。

### 方式三：自定义流程
在 `workflow/` 目录下创建 YAML 文件定义自己的工作流：

```yaml
name: my_workflow
description: "我的自定义分析流程"
triggers:
  - 我的工作流
params:
  - name: input_file
    type: string
    required: true
    description: "输入文件"
steps:
  - name: step1
    description: "第一步"
    tool: seqkit_stats
    params:
      file: "${params.input_file}"
    on_error: continue
```

## YAML 工作流语法

### 基本结构
```yaml
name: workflow_name          # 工作流唯一标识
description: "描述信息"       # 工作流描述
triggers:                     # 触发关键字列表
  - 关键字1
  - 关键字2
params:                       # 参数定义
  - name: param1
    type: string
    required: true
    description: "参数说明"
steps:                        # 步骤列表（顺序执行）
  - name: step_name
    description: "步骤描述"
    tool: registered_tool_name  # 必须是已注册的工具名
    params:                     # 传递给工具的参数
      key: value
    on_error: abort|continue|skip  # 错误处理策略
```

### 参数传递
步骤间通过 `${step_name.output}` 引用上一步的输出：
```yaml
steps:
  - name: align
    tool: mafft_align
    params:
      input_file: "${params.input_file}"
  - name: trim
    tool: trimal_trim
    params:
      input_file: "${align.output}"  # 引用 align 步骤的输出
```

### 错误处理
- `abort`: 步骤失败时终止整个工作流（默认）
- `continue`: 步骤失败时继续执行后续步骤
- `skip`: 步骤失败时跳过并继续

### 条件执行
```yaml
steps:
  - name: step2
    condition: "step1.success"  # 仅当 step1 成功时执行
```

## 新增工具到工作流

1. 在 `tools/` 目录下创建工具文件（如 `my_tool.py`）
2. 继承 `ToolBase` 基类，实现 `name`、`description`、`parameters`、`execute`
3. 在 `tools/__init__.py` 的 `TOOL_MODULES` 中添加模块名
4. 在工作流 YAML 中通过 `tool: your_tool_name` 引用
