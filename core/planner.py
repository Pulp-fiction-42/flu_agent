"""
Planner 模块 - 任务分析与步骤规划
参考 POPGENAGENT 的 core/planner 设计
"""
import json
import requests
from typing import Dict, List, Any, Optional
from .prompts import PLANNER_PROMPT


class Planner:
    """
    任务规划器
    负责分析用户需求，制定分析计划，分解为具体步骤
    """
    
    def __init__(
        self,
        llm_base_url: str,
        model: str,
        temperature: float = 0.7,
        timeout: int = 300,
    ):
        self.llm_base_url = llm_base_url
        self.model = model
        self.temperature = temperature
        self.timeout = timeout
    
    def plan(
        self,
        user_input: str,
        system_prompt: str,
        available_tools: List[Dict],
    ) -> Dict[str, Any]:
        """
        制定分析计划
        
        Args:
            user_input: 用户需求
            system_prompt: 系统提示词
            available_tools: 可用工具列表
        
        Returns:
            {
                "plan": "整体分析思路",
                "steps": [
                    {"step_id": 1, "tool": "工具名", "description": "...", "input": "...", "expected_output": "..."}
                ],
                "reasoning": "规划解释"
            }
        """
        # 格式化可用工具列表
        tools_info = "\n".join([
            f"- {t['function']['name']}: {t['function']['description']}"
            for t in available_tools
        ])
        
        prompt = PLANNER_PROMPT.format(
            user_input=user_input,
            available_tools=tools_info,
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_llm(messages)
        
        if "error" in result:
            return {"error": result["error"]}
        
        # 解析 JSON 响应
        try:
            content = self._extract_content(result)
            
            # 尝试提取 JSON
            plan_data = self._parse_json(content)
            
            return plan_data
        except Exception as e:
            return {"error": f"解析计划失败: {str(e)}"}
    
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
    
    def _parse_json(self, content: str) -> Dict[str, Any]:
        """解析 JSON 内容"""
        # 尝试直接解析
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass
        
        # 尝试提取 ```json 或 ``` 包裹的 JSON
        import re
        json_match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass
        
        # 尝试提取 { } 包裹的内容
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass
        
        # 返回原始内容作为 plan
        return {
            "plan": content,
            "steps": [],
            "reasoning": "无法解析为结构化JSON"
        }
    
    def is_simple_task(self, user_input: str, system_prompt: str) -> bool:
        """判断是否为简单任务（单步操作）"""
        from .prompts import SIMPLE_TASK_PROMPT
        
        prompt = SIMPLE_TASK_PROMPT.format(user_input=user_input)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        result = self._call_llm(messages)
        
        if "error" in result:
            return True  # 默认按简单任务处理
        
        content = self._extract_content(result).strip().upper()
        return content == "YES"
