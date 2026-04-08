"""
Plan Agent - 技术路线规划
"""
import json
from typing import Dict, List, Any, Optional


class PlanAgent:
    """
    Plan Agent：技术路线规划
    
    职责：
    - 根据明确的需求制定详细分析计划
    - 校验数据流的完整性
    - 识别潜在问题并反馈
    """
    
    def __init__(
        self,
        llm_client,
        tools: List[Dict] = None,
        validate_dataflow: bool = True,
    ):
        self.llm_client = llm_client
        self.tools = tools or []
        self.validate_dataflow = validate_dataflow
    
    def process(self, user_input: str, knowledge: str = "") -> Dict[str, Any]:
        """
        制定技术路线计划
        
        Args:
            user_input: 明确的需求
            knowledge: 知识库内容
            
        Returns:
            {
                "status": "success" | "error",
                "plan": {...},
                "message": "..."
            }
        """
        from .prompts import PLAN_AGENT_PROMPT
        
        # 构建工具列表
        tools_info = "\n".join([
            f"- {t['function']['name']}: {t['function']['description'][:80]}"
            for t in self.tools
        ])
        
        # 构建提示词
        prompt = PLAN_AGENT_PROMPT.format(
            user_input=user_input,
            available_tools=tools_info,
            knowledge=knowledge or "无",
        )
        
        messages = [{"role": "system", "content": prompt}]
        
        # 调用 LLM
        result = self.llm_client(messages)
        
        if "error" in result:
            return {
                "status": "error",
                "message": f"LLM调用失败: {result['error']}"
            }
        
        content = self._extract_content(result)
        
        # 解析 JSON 计划
        try:
            # 尝试提取 JSON 部分
            plan = self._extract_json(content)
            
            if not plan:
                return {
                    "status": "error",
                    "message": "无法解析计划，请重试"
                }
            
            # 校验数据流
            dataflow_result = self._validate_dataflow(plan) if self.validate_dataflow else {"valid": True}
            plan["dataflow_check"] = dataflow_result
            
            return {
                "status": "success",
                "plan": plan,
                "message": f"计划制定完成：{plan.get('plan', '')}"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "message": f"计划解析失败: {str(e)}",
                "raw_content": content
            }
    
    def _extract_content(self, result: Dict) -> str:
        """从响应中提取内容"""
        choices = result.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return message.get("content", "")
    
    def _extract_json(self, content: str) -> Optional[Dict]:
        """从内容中提取 JSON"""
        content = content.strip()
        
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json ... ``` 块
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                pass
        
        # 尝试提取 ``` ... ``` 块
        if "```" in content:
            for block in content.split("```"):
                if "{" in block and "}" in block:
                    try:
                        return json.loads(block)
                    except json.JSONDecodeError:
                        continue
        
        return None
    
    def _validate_dataflow(self, plan: Dict) -> Dict[str, Any]:
        """校验数据流的完整性"""
        issues = []
        
        steps = plan.get("steps", [])
        if not steps:
            return {"valid": False, "issues": ["计划中没有步骤"]}
        
        # 检查每个步骤
        for i, step in enumerate(steps, 1):
            tool = step.get("tool", "")
            input_desc = step.get("input", "")
            output_desc = step.get("output", "")
            
            # 检查工具是否存在
            if tool and not self._tool_exists(tool):
                issues.append(f"步骤{i}: 工具 '{tool}' 不存在")
            
            # 检查输入输出
            if i > 1:
                prev_output = steps[i-2].get("output", "")
                if input_desc and prev_output and not self._check_io_compatible(prev_output, input_desc):
                    issues.append(f"步骤{i}: 输入输出可能不匹配")
        
        return {
            "valid": len(issues) == 0,
            "issues": issues
        }
    
    def _tool_exists(self, tool_name: str) -> bool:
        """检查工具是否存在"""
        for t in self.tools:
            if t['function']['name'] == tool_name:
                return True
        return False
    
    def _check_io_compatible(self, output: str, input_desc: str) -> bool:
        """检查输出输入是否兼容（简单匹配）"""
        output = output.lower()
        input_desc = input_desc.lower()
        
        # 简单检查：输出文件类型和输入描述是否匹配
        output_ext = ""
        for ext in [".fa", ".fasta", ".fastq", ".fq", ".sam", ".bam", ".vcf", ".txt"]:
            if ext in output:
                output_ext = ext
                break
        
        if output_ext:
            return output_ext in input_desc
        
        return True  # 无法判断时默认兼容
