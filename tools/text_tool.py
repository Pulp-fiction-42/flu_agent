"""
Text Processing Tool - 文本处理工具
处理用户上传的文献/PDF，自动解读总结并动态更新知识库
"""
import os
import re
from typing import Dict, Any, Optional, List
from pathlib import Path
from tools.base import ToolBase


class TextProcessingTool(ToolBase):
    """文本处理工具 - 文献/PDF 解读"""
    
    @property
    def name(self) -> str:
        return "text_processing"
    
    @property
    def description(self) -> str:
        return """处理和分析用户上传的文本/文献文件。支持 PDF、TXT、MD 等格式。

**使用场景：**
- 用户上传文献、PDF、txt 文件需要分析
- 需要从文献中提取关键信息
- 将文献内容添加到知识库

**参数：**
- file_path: 文件路径（必填）
- action: 操作类型，extract(提取要点)/summary(生成摘要)/add_knowledge(添加到知识库)
- max_length: 最大处理长度（默认 5000 字符）"""
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "要处理的文件路径"
                },
                "action": {
                    "type": "string",
                    "description": "操作类型",
                    "enum": ["extract", "summary", "add_knowledge"]
                },
                "max_length": {
                    "type": "integer",
                    "description": "最大处理长度，默认 5000 字符"
                }
            },
            "required": ["file_path"]
        }
    
    def __init__(self, config=None):
        super().__init__()
        self.default_max_length = 5000
    
    def execute(self, file_path: str, action: str = "summary", max_length: int = 5000, **kwargs) -> str:
        """执行文本处理"""
        if not file_path:
            return "错误: 文件路径不能为空"
        
        # 检查文件是否存在
        if not os.path.isfile(file_path):
            return f"错误: 文件不存在: {file_path}"
        
        # 获取文件扩展名
        ext = Path(file_path).suffix.lower()
        
        try:
            if ext == '.pdf':
                content = self._extract_pdf(file_path, max_length)
            elif ext in ['.txt', '.md', '.json', '.yaml', '.yml']:
                content = self._read_text_file(file_path, max_length)
            else:
                return f"错误: 不支持的文件格式: {ext}"
            
            if not content:
                return "错误: 无法读取文件内容"
            
            # 根据动作执行
            if action == "extract":
                result = self._extract_key_points(content)
            elif action == "add_knowledge":
                result = self._add_to_knowledge(content, file_path)
            else:  # summary
                result = self._generate_summary(content)
            
            return result
            
        except Exception as e:
            return f"错误: 处理失败 - {str(e)}"
    
    def _read_text_file(self, file_path: str, max_length: int) -> str:
        """读取文本文件"""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(max_length)
        return content
    
    def _extract_pdf(self, file_path: str, max_length: int) -> str:
        """提取 PDF 内容"""
        try:
            import PyPDF2
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                text = ""
                for page in reader.pages[:20]:  # 最多读取20页
                    text += page.extract_text() + "\n"
                    if len(text) > max_length:
                        break
                return text[:max_length]
        except ImportError:
            # 如果没有 PyPDF2，尝试用 pdfplumber
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    text = ""
                    for page in pdf.pages[:20]:
                        text += page.extract_text() or ""
                        if len(text) > max_length:
                            break
                    return text[:max_length]
            except ImportError:
                return "PDF 处理需要安装 PyPDF2 或 pdfplumber"
        except Exception as e:
            return f"PDF 读取失败: {str(e)}"
    
    def _extract_key_points(self, content: str) -> str:
        """提取关键要点"""
        # 简单提取逻辑：按段落分割，提取包含关键词的段落
        paragraphs = content.split('\n\n')
        key_points = []
        
        keywords = ['结论', '结果', '方法', '目的', '背景', 'abstract', 'conclusion', 'result', 'method']
        
        for para in paragraphs[:30]:  # 最多处理30段
            para = para.strip()
            if not para:
                continue
            # 检查是否包含关键词
            if any(kw.lower() in para.lower() for kw in keywords):
                key_points.append(para[:500])  # 每段最多500字符
        
        if not key_points:
            return "未找到关键段落"
        
        output = [f"提取到 {len(key_points)} 个关键段落:\n"]
        for i, kp in enumerate(key_points[:10], 1):
            output.append(f"\n{i}. {kp[:300]}...")
        
        return "\n".join(output)
    
    def _generate_summary(self, content: str) -> str:
        """生成摘要"""
        # 简单摘要逻辑：取开头 + 结尾 + 关键句子
        lines = [l.strip() for l in content.split('\n') if l.strip()]
        
        # 提取前5行和后5行
        summary_parts = lines[:5]
        if len(lines) > 10:
            summary_parts.append("...")
            summary_parts.extend(lines[-5:])
        
        summary = '\n'.join(summary_parts)
        
        return f"=== 文档摘要 (原文长度: {len(content)} 字符) ===\n\n{summary[:2000]}"
    
    def _add_to_knowledge(self, content: str, file_path: str) -> str:
        """添加到知识库"""
        # 动态创建知识文件
        from config_loader import get_skill_dir
        
        skill_dir = get_skill_dir()
        knowledge_dir = os.path.join(skill_dir, "knowledge", "user_uploaded")
        
        # 创建用户上传目录
        os.makedirs(knowledge_dir, exist_ok=True)
        
        # 生成文件名
        base_name = Path(file_path).stem
        safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', base_name)
        timestamp = str(int(os.path.getmtime(file_path)))
        md_file = os.path.join(knowledge_dir, f"{safe_name}_{timestamp}.md")
        
        # 写入知识文件
        with open(md_file, 'w', encoding='utf-8') as f:
            f.write(f"# {base_name}\n\n")
            f.write(f"**来源**: {file_path}\n\n")
            f.write(f"**添加时间**: {timestamp}\n\n")
            f.write("---\n\n")
            f.write(content)
        
        return f"成功: 已将内容添加到知识库\n文件路径: {md_file}"
    
    def to_openai_functions(self) -> Dict[str, Any]:
        """转换为 OpenAI Function Calling 格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "要处理的文件路径"
                        },
                        "action": {
                            "type": "string",
                            "description": "操作类型",
                            "enum": ["extract", "summary", "add_knowledge"]
                        },
                        "max_length": {
                            "type": "integer",
                            "description": "最大处理长度，默认 5000 字符"
                        }
                    },
                    "required": ["file_path"]
                }
            }
        }


def get_instance(config=None) -> TextProcessingTool:
    """获取工具实例"""
    return TextProcessingTool(config)
