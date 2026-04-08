"""
Web Search Tool - 上网搜索工具
当知识库不完备时，自动联网搜索相关信息
"""
import requests
import json
import re
from typing import Dict, Any, Optional, List
from tools.base import ToolBase


class SearchTool(ToolBase):
    """联网搜索工具"""
    
    @property
    def name(self) -> str:
        return "web_search"
    
    @property
    def description(self) -> str:
        return """在网上搜索相关信息。当本地知识库无法回答或信息可能过时时使用。

**使用场景：**
- 用户询问最新的研究进展或技术
- 知识库中没有相关信息
- 需要验证最新数据或方法

**参数：**
- query: 搜索关键词（必填）"""
    
    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索关键词或问题"
                }
            },
            "required": ["query"]
        }
    
    def __init__(self, config=None):
        super().__init__()
        self.search_api = "https://duckduckgo.com/"
        self.timeout = 30
    
    def execute(self, query: str, **kwargs) -> str:
        """执行搜索"""
        if not query:
            return "错误: 搜索关键词不能为空"
        
        try:
            # 使用 DuckDuckGo HTML 搜索（无需 API Key）
            url = "https://html.duckduckgo.com/html/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            data = {"q": query, "b": ""}
            
            response = requests.post(url, data=data, headers=headers, timeout=self.timeout)
            response.raise_for_status()
            
            # 解析结果
            results = self._parse_results(response.text)
            
            if not results:
                return f"未找到与 '{query}' 相关的搜索结果"
            
            # 格式化输出
            output = [f"搜索结果: '{query}'\n"]
            for i, r in enumerate(results[:5], 1):
                output.append(f"\n{i}. {r['title']}")
                output.append(f"   {r['url']}")
                output.append(f"   {r['snippet'][:150]}...")
            
            return "\n".join(output)
            
        except requests.Timeout:
            return "错误: 搜索超时，请稍后重试"
        except requests.RequestException as e:
            return f"错误: 搜索失败 - {str(e)}"
        except Exception as e:
            return f"错误: 搜索异常 - {str(e)}"
    
    def _parse_results(self, html: str) -> List[Dict[str, str]]:
        """解析搜索结果 HTML"""
        results = []
        
        # 提取结果卡片
        pattern = r'<a class="result__a" href="([^"]+)"[^>]*>(.+?)</a>.*?<a class="result__snippet"[^>]*>(.+?)</a>'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for url, title, snippet in matches:
            # 清理 HTML 标签
            title = re.sub(r'<[^>]+>', '', title)
            snippet = re.sub(r'<[^>]+>', '', snippet)
            results.append({
                "title": title.strip(),
                "url": url,
                "snippet": snippet.strip()
            })
        
        return results
    
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
                        "query": {
                            "type": "string",
                            "description": "搜索关键词或问题"
                        }
                    },
                    "required": ["query"]
                }
            }
        }


def get_instance(config=None) -> SearchTool:
    """获取工具实例"""
    return SearchTool(config)
