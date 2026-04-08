# 常见错误排查指南

## 工具执行错误

### 1. 命令找不到 (command not found)

**症状**: `shutil.which()` 返回 `None`

**原因**: 工具未安装或不在 PATH 中

**解决方案**:
```bash
# 检查工具是否存在
which tool_name

# 确认环境
echo $PATH

# 在 conda 环境中
conda activate mamba_env
which tool_name
```

### 2. 权限拒绝 (Permission denied)

**症状**: `[Errno 13] Permission denied`

**解决方案**:
```bash
chmod +x /path/to/tool
```

### 3. 动态库缺失

**症状**: `ImportError: libxxx.so: cannot open shared object file`

**解决方案**:
```bash
# 安装缺失的库
# Ubuntu/Debian
sudo apt-get install libxxx

# conda
conda install -c conda-forge libxxx
```

---

## 数据格式错误

### 1. FASTA/FASTQ 格式问题

**症状**: 解析失败或序列数量不对

**常见问题**:
- 序列名重复
- 特殊字符未转义
- 换行符格式不对 (Windows vs Linux)

**解决方案**:
```bash
# 检查格式
seqkit seq -n file.fasta

# 修复格式
seqkit seq -w 80 file.fasta > fixed.fasta
```

### 2. VCF 文件问题

**症状**: VCF 解析错误

**检查方法**:
```bash
# 验证 VCF
bcftools view -h file.vcf

# 修复索引
bcftools index file.vcf
```

---

## 内存与性能问题

### 1. 内存不足 (OOM)

**症状**: `MemoryError` 或系统 killed

**解决方案**:
- 减少线程数: `samtools view -@ 2`
- 分块处理大文件
- 使用流式处理

### 2. 磁盘空间不足

**症状**: `No space left on device`

**解决方案**:
- 清理临时文件
- 使用 `-T` 指定临时目录到有空间的位置
- 定期清理分析结果

---

## LLM 调用错误

### 1. Ollama 连接失败

**症状**: `Connection refused` 或超时

**检查**:
```bash
# 检查服务状态
curl http://localhost:11434/api/tags

# 重启服务
ollama serve
```

### 2. 模型不可用

**症状**: `model not found`

**解决方案**:
```bash
# 列出可用模型
ollama list

# 拉取模型
ollama pull model_name
```

### 3. 超时错误

**症状**: `timeout` 或响应慢

**解决方案**:
- 增加超时时间
- 使用更小的模型
- 检查网络延迟

---

## 工作流执行错误

### 1. 步骤失败

**症状**: 工作流中途停止

**排查**:
1. 检查日志输出
2. 验证输入文件是否存在
3. 检查工具返回码

### 2. 参数传递错误

**症状**: 步骤找不到上一步输出

**解决方案**:
- 检查参数格式: `${step.output}`
- 确认步骤 ID 正确

---

## 调试技巧

### 1. 启用详细日志
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 2. 测试单独工具
```bash
# 直接运行命令检查
/path/to/tool --help
```

### 3. 小数据集测试
先用一小部分数据验证流程，再处理完整数据

---

## 获取帮助

- 工具帮助: `tool_name --help`
- 查看日志: `tail -f bioagent.log`
- 社区支持: Biostars, SEQanswers
