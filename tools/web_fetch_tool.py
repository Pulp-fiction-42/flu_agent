"""
网页抓取工具 - 获取网页全文内容
支持微信公众号、通用网页的内容提取
"""
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse
from .base import ToolBase, ToolRegistry


class WebFetchTool(ToolBase):
    """网页抓取工具 - 提取网页正文内容"""

    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return """抓取指定URL的网页内容，提取正文文本。支持微信公众号文章、新闻、博客等各类网页。

**使用场景：**
- 用户发送URL并要求总结内容
- 需要获取网页全文进行解读
- 提取文章的主要内容

**参数：**
- url: 要抓取的网页URL（必填）
- max_length: 返回内容最大长度，默认8000字符"""

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "要抓取的网页URL"
                },
                "max_length": {
                    "type": "integer",
                    "description": "返回内容的最大长度（字符数），默认8000",
                    "default": 8000
                }
            },
            "required": ["url"]
        }

    def __init__(self, config=None):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def execute(self, url: str, max_length: int = 8000, **kwargs) -> str:
        """执行网页抓取"""
        if not url:
            return "错误: URL不能为空"

        # 验证URL格式
        if not url.startswith(('http://', 'https://')):
            return f"错误: 无效的URL格式: {url}"

        try:
            # 发送请求
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            # 解析网页
            soup = BeautifulSoup(response.content, 'html.parser')

            # 提取正文
            content = self._extract_content(soup, url)

            # 截断超长内容
            if len(content) > max_length:
                content = content[:max_length] + f"\n\n[内容已截断，完整内容约 {len(content)} 字符]"

            # 提取标题
            title = self._extract_title(soup)

            return f"## {title}\n\n{content}\n\n来源: {url}"

        except requests.exceptions.Timeout:
            return f"错误: 请求超时，请检查URL是否可用: {url}"
        except requests.exceptions.RequestException as e:
            return f"错误: 请求失败: {str(e)}"
        except Exception as e:
            return f"错误: 抓取失败: {str(e)}"

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取网页标题"""
        # 优先使用og:title
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content'].strip()

        # 然后使用title标签
        title_tag = soup.find('title')
        if title_tag:
            return title_tag.get_text().strip()

        # 最后使用h1
        h1 = soup.find('h1')
        if h1:
            return h1.get_text().strip()

        return "无标题"

    def _extract_content(self, soup: BeautifulSoup, url: str) -> str:
        """提取网页正文内容"""

        # 微信公众号特殊处理
        if 'mp.weixin.qq.com' in url:
            return self._extract_wechat_content(soup)

        # 通用网页处理
        return self._extract_generic_content(soup)

    def _extract_wechat_content(self, soup: BeautifulSoup) -> str:
        """提取微信公众号文章内容"""
        # 微信公众号文章通常在 id="js_content" 的div中
        content_div = soup.find('div', id='js_content')
        if content_div:
            return self._clean_text(content_div.get_text())

        # 备选方案：查找文章主体区域
        article = soup.find('article')
        if article:
            return self._clean_text(article.get_text())

        # 最后尝试通用方法
        return self._extract_generic_content(soup)

    def _extract_generic_content(self, soup: BeautifulSoup) -> str:
        """提取通用网页正文"""
        # 移除脚本和样式
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()

        # 尝试查找主要内容区域
        content = None

        # 方法1: 查找article标签
        article = soup.find('article')
        if article:
            content = article.get_text()

        # 方法2: 查找main标签
        if not content:
            main = soup.find('main')
            if main:
                content = main.get_text()

        # 方法3: 查找class包含content/article/post的div
        if not content:
            for cls in ['content', 'article', 'post', 'entry', 'main-content', 'article-content']:
                div = soup.find('div', class_=lambda x: x and cls in x.lower() if x else False)
                if div:
                    content = div.get_text()
                    break

        # 方法4: 查找body中的最大文本块
        if not content:
            body = soup.find('body')
            if body:
                # 获取所有段落
                paragraphs = body.find_all('p')
                if paragraphs:
                    content = '\n\n'.join([p.get_text().strip() for p in paragraphs if p.get_text().strip()])
                else:
                    content = body.get_text()

        return self._clean_text(content) if content else ""

    def _clean_text(self, text: str) -> str:
        """清理文本，去除多余空白"""
        if not text:
            return ""

        # 去除多余空白
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        text = text.strip()

        return text


def register_all_tools():
    """注册网页抓取工具"""
    try:
        ToolRegistry.register(WebFetchTool(None))
    except Exception as e:
        print(f"[FluAgent] 加载 WebFetchTool 失败: {e}")
