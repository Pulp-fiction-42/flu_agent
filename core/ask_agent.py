"""
Ask Agent - 需求理解与多轮澄清
"""
import json
from typing import Dict, List, Any, Optional


class AskAgent:
    """
    Ask Agent：需求理解与多轮澄清
    
    职责：
    - 理解用户输入的生物信息学分析需求
    - 识别需求中的模糊点，进行多轮澄清
    - 需求明确后，生成结构化需求摘要传递给 Plan Agent
    """
    
    def __init__(
        self,
        llm_client,
        max_rounds: int = 3,
    ):
        self.llm_client = llm_client
        self.max_rounds = max_rounds
        self.clarification_history: List[Dict[str, str]] = []
    
    def process(self, user_input: str, conversation_history: List[Dict] = None) -> Dict[str, Any]:
        """
        处理用户需求，进行多轮澄清
        
        Args:
            user_input: 用户输入
            conversation_history: 对话历史
            
        Returns:
            {
                "status": "clarify" | "ready",
                "questions": [...]  # 如果需要澄清
                "summary": "...",   # 如果已明确
                "message": "..."   # 返回给用户的文本
            }
        """
        from .prompts import ASK_AGENT_PROMPT
        
        # 构建对话历史
        history_text = ""
        if conversation_history:
            for msg in conversation_history[-6:]:  # 最近3轮对话
                role = msg.get("role", "user")
                content = msg.get("content", "")
                history_text += f"{role}: {content}\n"
        
        # 构建提示词
        prompt = ASK_AGENT_PROMPT.format(
            conversation_history=history_text or "（无历史对话）",
            user_input=user_input,
            max_rounds=self.max_rounds,
        )
        
        messages = [{"role": "system", "content": prompt}]
        
        # 如果有之前的澄清历史，加入上下文
        if self.clarification_history:
            for item in self.clarification_history:
                if item.get("type") == "question":
                    messages.append({"role": "user", "content": f"用户回答: {item.get('answer', '')}"})
        
        # 调用 LLM
        result = self.llm_client(messages)
        
        if "error" in result:
            return {
                "status": "error",
                "message": f"LLM调用失败: {result['error']}"
            }
        
        content = self._extract_content(result)
        
        # 解析输出
        return self._parse_response(content, user_input)
    
    def _extract_content(self, result: Dict) -> str:
        """从响应中提取内容"""
        choices = result.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return message.get("content", "")
    
    def _parse_response(self, content: str, original_input: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        content = content.strip()
        
        # 检查是否需要澄清
        if "[CLARIFY]" in content:
            # 提取问题列表
            questions = []
            lines = content.split("\n")
            in_clarify = False
            for line in lines:
                line = line.strip()
                if line == "[CLARIFY]":
                    in_clarify = True
                    continue
                if in_clarify and line.startswith("-"):
                    questions.append(line[1:].strip())
            
            return {
                "status": "clarify",
                "questions": questions,
                "message": "我需要澄清一些问题：\n" + "\n".join(questions) if questions else content
            }
        
        # 需求已明确
        if "[READY]" in content or "需求摘要" in content:
            # 提取摘要
            summary = content
            if "[READY]" in content:
                summary = content.split("[READY]")[-1].strip()
            
            return {
                "status": "ready",
                "summary": summary,
                "message": f"好的，我理解您的需求了。\n{summary}"
            }
        
        # 默认处理：假设已理解
        return {
            "status": "ready",
            "summary": original_input,
            "message": content
        }
    
    def add_clarification(self, question: str, answer: str):
        """记录一次澄清问答"""
        self.clarification_history.append({
            "type": "question",
            "question": question,
            "answer": answer,
        })
    
    def reset(self):
        """重置澄清历史"""
        self.clarification_history = []
