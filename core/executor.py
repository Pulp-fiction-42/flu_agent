"""
Executor 模块 - 工具执行
参考 POPGENAGENT 的 core/executor 设计
"""
import json
import requests
from typing import Dict, List, Any
from .prompts import EXECUTOR_PROMPT


class Executor:
    """
    工具执行器
    负责按照计划逐步执行工具，收集结果
    """
    
    def __init__(
        self,
        llm_base_url: str,
        model: str,
        temperature: float = 0.7,
        timeout: int = 300,
        tools: List[Dict] = None,
    ):
        self.llm_base_url = llm_base_url
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
        self.tools = tools or []
    
    def execute(
        self,
        steps: List[Dict],
        context: str,
        system_prompt: str,
    ) -> List[Dict]:
        """
        执行分析计划
        
        Args:
            steps: 分析步骤列表
            context: 原始需求上下文
            system_prompt: 系统提示词
        
        Returns:
            [
                {
                    "step_id": 1,
                    "tool": "工具名",
                    "result": "执行结果",
                    "success": true/false,
                    "error": "错误信息（如果有）"
                }
            ]
        """
        # 格式化步骤
        steps_text = self._format_steps(steps)
        
        prompt = EXECUTOR_PROMPT.format(
            context=context,
            system_prompt=system_prompt,
            steps=steps_text,
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_llm(messages)
        
        if "error" in result:
            return [{"error": result["error"]}]
        
        # 解析执行结果
        try:
            content = self._extract_content(result)
            exec_results = self._parse_results(content, steps)
            return exec_results
        except Exception as e:
            return [{"error": f"解析执行结果失败: {str(e)}"}]
    
    def _format_steps(self, steps: List[Dict]) -> str:
        """格式化步骤列表"""
        lines = []
        for step in steps:
            step_id = step.get("step_id", step.get("id", "?"))
            tool = step.get("tool", "?")
            desc = step.get("description", "")
            inp = step.get("input", "")
            out = step.get("expected_output", "")
            
            lines.append(f"步骤 {step_id}: {tool}")
            lines.append(f"  描述: {desc}")
            lines.append(f"  输入: {inp}")
            lines.append(f"  预期输出: {out}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _call_llm(self, messages: List[Dict]) -> Dict[str, Any]:
        """调用 LLM"""
        headers = {"Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": False
        }
        
        try:
            response = requests.post(
                f"{self.llm_base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            return {"error": f"LLM调用失败: {str(e)}"}
    
    def _extract_content(self, result: Dict) -> str:
        """提取响应内容"""
        choices = result.get("choices", [])
        if not choices:
            return ""
        
        message = choices[0].get("message", {})
        return message.get("content", "")
    
    def _parse_results(self, content: str, original_steps: List[Dict]) -> List[Dict]:
        """解析执行结果"""
        import re
        
        results = []
        
        # 尝试提取 JSON
        try:
            data = json.loads(content)
            if "executed_steps" in data:
                return data["executed_steps"]
            return [data]
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json 包裹的内容
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if "executed_steps" in data:
                    return data["executed_steps"]
                return [data]
            except json.JSONDecodeError:
                pass
        
        # 简单解析：按步骤解析
        for i, step in enumerate(original_steps):
            results.append({
                "step_id": step.get("step_id", i + 1),
                "tool": step.get("tool", "unknown"),
                "result": "执行结果见上方",
                "success": True,
                "error": None
            })
        
        return results
    
    def execute_single_tool(self, tool_name: str, args: Dict) -> Dict:
        """执行单个工具"""
        from tools import execute_tool
        
        try:
            result = execute_tool(tool_name, **args)
            return {
                "tool": tool_name,
                "result": result,
                "success": True,
                "error": None
            }
        except Exception as e:
            return {
                "tool": tool_name,
                "result": None,
                "success": False,
                "error": str(e)
            }
