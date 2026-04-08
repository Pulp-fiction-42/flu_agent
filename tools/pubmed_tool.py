"""
PubMed 搜索工具 - 搜索 PubMed 文献并获取摘要
支持直接搜索和按 PMID 获取详情
"""
import requests
from bs4 import BeautifulSoup
import re
import time
from typing import List, Dict, Optional
from urllib.parse import quote_plus
from .base import ToolBase, ToolRegistry


class PubMedTool(ToolBase):
    """PubMed 文献搜索工具"""

    @property
    def name(self) -> str:
        return "pubmed_search"

    @property
    def description(self) -> str:
        return """搜索 PubMed 文献数据库，获取文献摘要和元信息。

**使用场景：**
- 搜索特定疾病、基因或蛋白相关文献
- 获取某个 PMID 的文献详情
- 了解某个研究领域的最新进展

**参数：**
- query: 搜索关键词（必填），支持 PubMed 高级搜索语法
- max_results: 最大返回结果数，默认 5 篇
- pmid: 直接获取指定 PMID 的文献详情（可选，如果提供则忽略 query）

**使用示例：**
- 搜索: pubmed_search(query="influenza HA gene evolution")
- 详情: pubmed_search(pmid="32948265")
"""

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "PubMed 搜索关键词，支持布尔逻辑如 'influenza AND HA AND evolution'"
                },
                "max_results": {
                    "type": "integer",
                    "description": "最大返回结果数，默认 5",
                    "default": 5
                },
                "pmid": {
                    "type": "string",
                    "description": "直接获取指定 PMID 的文献，如果提供则忽略 query"
                }
            }
        }

    def __init__(self, config=None):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        self.base_url = "https://pubmed.ncbi.nlm.nih.gov"
        self.search_url = "https://pubmed.ncbi.nlm.nih.gov/?term="

    def execute(self, query: str = None, max_results: int = 5, pmid: str = None, **kwargs) -> str:
        """执行 PubMed 搜索或详情获取"""
        # 如果提供了 PMID，直接获取详情
        if pmid:
            return self._get_article_details(pmid)

        if not query:
            return "错误: 必须提供搜索关键词 query 或 PMID"

        # 执行搜索
        return self._search_pubmed(query, max_results)

    def _search_pubmed(self, query: str, max_results: int = 5) -> str:
        """搜索 PubMed"""
        try:
            # 构建搜索 URL
            encoded_query = quote_plus(query)
            search_url = f"{self.search_url}{encoded_query}"

            # 发送请求
            response = requests.get(search_url, headers=self.headers, timeout=30)
            response.raise_for_status()

            # 解析结果
            articles = self._parse_search_results(response.text)

            if not articles:
                return self._fallback_search(query)

            # 返回结果
            results = []
            for i, article in enumerate(articles[:max_results], 1):
                results.append(f"""
### {i}. {article['title']}
- **PMID**: {article['pmid']}
- **期刊**: {article.get('journal', 'N/A')}
- **发表日期**: {article.get('date', 'N/A')}
- **作者**: {article.get('authors', 'N/A')}
- **摘要**: {article.get('abstract', '暂无摘要')[:500]}{'...' if len(article.get('abstract', '')) > 500 else ''}
- **链接**: https://pubmed.ncbi.nlm.nih.gov/{article['pmid']}/
""")

            return f"## PubMed 搜索结果: \"{query}\"\n\n找到 {len(articles)} 篇相关文献，显示前 {min(max_results, len(articles))} 篇:\n\n" + "\n---\n".join(results)

        except requests.exceptions.Timeout:
            return f"错误: PubMed 请求超时，请检查网络连接\n\n**解决方案：**\n1. 检查网络代理设置\n2. 尝试使用 search_tool 进行 DuckDuckGo 搜索 PubMed\n3. 稍后重试"
        except requests.exceptions.RequestException as e:
            return f"错误: PubMed 搜索失败: {str(e)}\n\n**解决方案：**\n1. 检查网络连接\n2. 可能需要设置代理: export HTTP_PROXY=http://your-proxy:port\n3. 或使用 search_tool 搜索 PubMed 相关信息"
        except Exception as e:
            return f"错误: PubMed 搜索失败: {str(e)}"

    def _parse_search_results(self, html: str) -> List[Dict]:
        """解析 PubMed 搜索结果页面"""
        articles = []
        soup = BeautifulSoup(html, 'html.parser')

        # 查找文章列表 - PubMed 使用 article 属性
        article_containers = soup.find_all('article', class_='full-viewport-height')

        if not article_containers:
            # 备选：查找带有 pmid 的元素
            article_containers = soup.find_all('div', class_=lambda x: x and 'search-result' in x.lower() if x else False)

        for container in article_containers:
            try:
                article = {}

                # 提取 PMID
                pmid_link = container.find('a', href=re.compile(r'/葵葵/\d+/'))
                if not pmid_link:
                    pmid_link = container.find('a', class_='docutils')
                if pmid_link:
                    pmid_match = re.search(r'(\d+)', pmid_link.get('href', ''))
                    if pmid_match:
                        article['pmid'] = pmid_match.group(1)

                # 提取标题
                title_elem = container.find('h1') or container.find('a', class_='title')
                if title_elem:
                    article['title'] = title_elem.get_text().strip()

                # 提取作者
                authors = []
                author_elems = container.find_all('a', class_='author')
                for author in author_elems[:5]:
                    authors.append(author.get_text().strip())
                article['authors'] = ', '.join(authors) + ('...' if len(author_elems) > 5 else '')

                # 提取期刊信息
                journal_elem = container.find('button', class_='journal-actions-trigger')
                if not journal_elem:
                    journal_elem = container.find('span', class_='jrnl')
                if journal_elem:
                    article['journal'] = journal_elem.get_text().strip()

                # 提取日期
                date_elem = container.find('span', class_='date')
                if date_elem:
                    article['date'] = date_elem.get_text().strip()

                # 提取摘要
                abstract_elem = container.find('div', class_='abstract-content')
                if not abstract_elem:
                    abstract_elem = container.find('p', class_='abstract')
                if abstract_elem:
                    article['abstract'] = abstract_elem.get_text().strip()

                if article.get('pmid') and article.get('title'):
                    articles.append(article)

            except Exception:
                continue

        return articles

    def _get_article_details(self, pmid: str) -> str:
        """获取指定 PMID 的文献详情"""
        try:
            url = f"{self.base_url}/{pmid}/"
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()

            return self._parse_article_page(response.text, pmid)

        except requests.exceptions.Timeout:
            return f"错误: PubMed 请求超时，请稍后重试\n\n**解决方案：**\n1. 检查网络连接\n2. 直接访问 https://pubmed.ncbi.nlm.nih.gov/{pmid}/ 查看"
        except requests.exceptions.RequestException as e:
            return f"错误: 获取文献详情失败: {str(e)}"
        except Exception as e:
            return f"错误: 获取文献详情失败: {str(e)}"

    def _parse_article_page(self, html: str, pmid: str) -> str:
        """解析 PubMed 文章详情页面"""
        soup = BeautifulSoup(html, 'html.parser')

        # 提取标题
        title_elem = soup.find('h1', class_='heading-title')
        if not title_elem:
            title_elem = soup.find('h1')
        title = title_elem.get_text().strip() if title_elem else "未知标题"

        # 提取作者
        authors = []
        author_section = soup.find('div', class_='authors-section')
        if author_section:
            author_elems = author_section.find_all('a', class_='author-name')
            for author in author_elems:
                authors.append(author.get_text().strip())
        article['authors'] = ', '.join(authors[:10]) + ('...' if len(authors) > 10 else '')

        # 提取期刊信息
        journal_info = ""
        journal_elem = soup.find('button', class_='journal-actions-trigger')
        if journal_elem:
            journal_info = journal_elem.get_text().strip()

        # 提取日期
        date_info = ""
        date_elem = soup.find('span', class_='date')
        if date_elem:
            date_info = date_elem.get_text().strip()

        # 提取 DOI
        doi = ""
        doi_link = soup.find('a', href=re.compile(r'doi\.org'))
        if doi_link:
            doi = doi_link.get('href', '')

        # 提取摘要
        abstract = ""
        abstract_section = soup.find('div', id='abstract')
        if abstract_section:
            abstract = abstract_section.get_text().strip()
        else:
            abstract_elem = soup.find('div', class_='abstract-content')
            if abstract_elem:
                abstract = abstract_elem.get_text().strip()

        # 提取关键词
        keywords = []
        kw_section = soup.find('div', class_='keywords')
        if kw_section:
            kw_elems = kw_section.find_all('a')
            keywords = [kw.get_text().strip() for kw in kw_elems]

        article = {
            'title': title,
            'pmid': pmid,
            'authors': ', '.join(authors[:10]) + ('...' if len(authors) > 10 else ''),
            'journal': journal_info,
            'date': date_info,
            'doi': doi,
            'abstract': abstract,
            'keywords': ', '.join(keywords) if keywords else '无'
        }

        return f"""## PubMed 文献详情

**标题**: {article['title']}

**PMID**: {article['pmid']}

**作者**: {article['authors']}

**期刊**: {article['journal']} ({article['date']})

**DOI**: {article['doi']}

**关键词**: {article['keywords']}

### 摘要

{article['abstract'] if article['abstract'] else '暂无摘要'}

---
来源: https://pubmed.ncbi.nlm.nih.gov/{pmid}/
"""

    def _fallback_search(self, query: str) -> str:
        """当 PubMed 直接搜索失败时的备选方案"""
        return f"""## PubMed 搜索结果

抱歉，无法直接访问 PubMed 网站（可能由于网络限制）。

**建议解决方案：**

1. **设置网络代理**（如果你在中国或其他有访问限制的地区）:
   ```bash
   export HTTP_PROXY=http://your-proxy:port
   export HTTPS_PROXY=http://your-proxy:port
   ```

2. **使用 WebSearch 工具搜索**:
   请尝试使用 search_tool 中的 web_search 功能搜索相关文献。

3. **直接访问 PubMed**:
   - 搜索页面: https://pubmed.ncbi.nlm.nih.gov/?term={quote_plus(query)}
   - 建议在浏览器中打开此链接

4. **使用 Europe PMC 或其他文献数据库**:
   - Europe PMC: https://europepmc.org/search?query={quote_plus(query)}

**搜索词**: "{query}"
"""


def register_all_tools():
    """注册 PubMed 搜索工具"""
    try:
        ToolRegistry.register(PubMedTool(None))
        print("[FluAgent] 已加载 PubMedTool")
    except Exception as e:
        print(f"[FluAgent] 加载 PubMedTool 失败: {e}")
