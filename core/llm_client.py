"""
LLM 客户端 - 统一的 LLM API 调用层
封装请求构建、错误处理、响应解析
"""
import json
import requests
from typing import Dict, List, Any, Optional, Union


class LLMClient:
    """统一的 LLM API 客户端"""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen3:4b",
        api_key: str = "",
        temperature: float = 0.7,
        timeout: int = 300,
        max_tokens: int = 4096,
    ):
        self.base_url = base_url
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout
        self.max_tokens = max_tokens
        
        # 构建 API URL
        self.api_url = self._build_api_url()
    
    def _build_api_url(self) -> str:
        """构建 API URL"""
        if self.base_url.endswith("/v1/chat/completions"):
            return self.base_url
        elif self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        else:
            return f"{self.base_url}/v1/chat/completions"
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        temperature: Optional[float] = None,
        model: Optional[str] = None,
        stream: bool = False,
    ) -> Dict[str, Any]:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            tools: 工具定义列表
            temperature: 温度参数
            model: 模型名称
            stream: 是否流式响应
        
        Returns:
            API 响应字典
        """
        # 构建请求头
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        # 构建请求体
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "stream": stream,
        }
        
        if self.max_tokens:
            payload["max_tokens"] = self.max_tokens
        
        if tools:
            payload["tools"] = tools
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            data = response.json()
            
            # 标准化响应格式
            return self._normalize_response(data)
            
        except requests.exceptions.Timeout:
            return {"error": f"LLM调用超时（{self.timeout}s）", "error_type": "timeout"}
        except requests.exceptions.ConnectionError:
            return {"error": "无法连接LLM服务", "error_type": "connection_error"}
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 401:
                return {"error": "API Key 认证失败", "error_type": "auth_error"}
            return {"error": f"HTTP错误: {str(e)}", "error_type": "http_error"}
        except requests.exceptions.RequestException as e:
            return {"error": f"请求失败: {str(e)}", "error_type": "request_error"}
        except json.JSONDecodeError:
            return {"error": "响应 JSON 解析失败", "error_type": "parse_error"}
    
    def _normalize_response(self, data: Dict) -> Dict:
        """标准化响应格式"""
        # 标准 OpenAI 格式
        if "choices" in data:
            return data
        
        # 心流等 API 错误格式
        if "msg" in data or "error" in data or "status" in data:
            err_msg = data.get("msg") or data.get("error", {}).get("message", "")
            status = data.get("status", "")
            return {"error": f"API 错误 (status={status}): {err_msg}", "error_type": "api_error"}
        
        # 嵌套结构: {"message": {"content": "..."}}
        if "message" in data and "content" in data["message"]:
            return {"choices": [{"message": data["message"]}]}
        
        # 简单结构: {"content": "..."}
        if "content" in data:
            return {"choices": [{"message": {"role": "assistant", "content": data["content"]}}]}
        
        # Ollama 原生格式: {"response": "..."}
        if "response" in data:
            return {"choices": [{"message": {"role": "assistant", "content": data["response"]}}]}
        
        # 无法解析
        return {
            "error": f"无法解析的响应格式: {json.dumps(data, ensure_ascii=False)[:500]}",
            "error_type": "unknown_format"
        }
    
    def chat_with_functions(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict],
        max_rounds: int = 10,
    ) -> Union[str, Dict]:
        """
        执行完整的 Function Calling 对话
        
        Args:
            messages: 初始消息列表
            tools: 工具定义
            max_rounds: 最大调用轮次
        
        Returns:
            最终响应内容或包含 tool_calls 的结果
        """
        current_messages = messages.copy()
        
        for round_idx in range(max_rounds):
            result = self.chat(current_messages, tools=tools)
            
            if "error" in result:
                return result
            
            choices = result.get("choices", [])
            if not choices:
                return {"error": "LLM 未返回有效响应", "error_type": "empty_response"}
            
            message = choices[0].get("message", {})
            tool_calls = message.get("tool_calls", [])
            
            if not tool_calls:
                # 无工具调用，返回最终回复
                return message.get("content", "")
            
            # 有工具调用，添加到消息中（供下一次调用）
            current_messages.append(message)
        
        # 达到最大轮次
        return {"error": "已达到最大工具调用轮次", "error_type": "max_rounds"}


class StreamingLLMClient(LLMClient):
    """流式响应客户端"""
    
    def stream_chat(
        self,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict]] = None,
        temperature: Optional[float] = None,
    ):
        """流式聊天"""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "stream": True,
        }
        
        if tools:
            payload["tools"] = tools
        
        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout,
                stream=True
            )
            response.raise_for_status()
            
            for line in response.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data = line[6:]
                        if data == '[DONE]':
                            break
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue
                            
        except requests.exceptions.RequestException as e:
            yield {"error": str(e)}


def create_llm_client(config: Dict = None) -> LLMClient:
    """
    工厂函数：从配置创建 LLM 客户端
    
    Args:
        config: 配置字典，包含 base_url, model, api_key, temperature, timeout
    
    Returns:
        LLMClient 实例
    """
    if config is None:
        from config_loader import get_llm_config
        config = get_llm_config()
    
    return LLMClient(
        base_url=config.get("base_url", "http://localhost:11434"),
        model=config.get("model", "qwen3:4b"),
        api_key=config.get("api_key", ""),
        temperature=config.get("temperature", 0.7),
        timeout=config.get("timeout", 300),
        max_tokens=config.get("max_tokens", 4096),
    )
