#!/usr/bin/env python3
"""
Proxy MCP Server v1.1 - 通过云端代理访问外网

工具：
1. proxy_fetch - 网页抓取，返回纯文本/Markdown
2. proxy_search - DuckDuckGo 网络搜索
3. proxy_request - 通用 HTTP 代理
4. proxy_health - 健康检查

部署在 HF Spaces，使用 FastMCP streamable-http 传输。
"""

import json
import logging
import re
from typing import Optional

import requests as http_requests
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
from mcp.server.fastmcp import FastMCP

# ============================================================
# 配置
# ============================================================

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("proxy-mcp")

CHAR_LIMIT = 50000
REQUEST_TIMEOUT = 30

mcp = FastMCP(
    "proxy-mcp",
    instructions=(
        "Proxy MCP Server - 通过云端代理访问外网。"
        "提供网页抓取、网络搜索和通用 HTTP 代理功能。"
        "适用于访问被网络限制的网站（如 X/Twitter、Google 等）。"
    ),
    host="0.0.0.0",
    port=7860,
)


# ============================================================
# 工具 1: proxy_fetch - 网页抓取
# ============================================================

def _html_to_text(html: str) -> str:
    """将 HTML 转换为干净的文本（简易 Markdown 风格）"""
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript", "meta", "link", "head", "svg", "img"]):
        tag.decompose()
    for level in range(1, 7):
        for tag in soup.find_all(f"h{level}"):
            tag.replace_with(f"\n{'#' * level} {tag.get_text(strip=True)}\n")
    for tag in soup.find_all("a"):
        href = tag.get("href", "")
        text = tag.get_text(strip=True)
        if text and href:
            tag.replace_with(f"[{text}]({href})")
    for tag in soup.find_all(["br", "p", "div", "li", "tr"]):
        tag.insert_after("\n")
    for tag in soup.find_all("li"):
        tag.insert_before("- ")
    text = soup.get_text(separator="\n")
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


@mcp.tool()
async def proxy_fetch(
    url: str,
    format: str = "text",
    timeout: int = REQUEST_TIMEOUT,
) -> str:
    """抓取指定 URL 的网页内容，返回文本或简易 Markdown。

    Args:
        url: 要抓取的网页 URL（支持 http/https）
        format: 输出格式，"text" 纯文本或 "markdown" 简易 Markdown（默认 text）
        timeout: 请求超时时间，秒（默认 30）

    Returns:
        网页内容
    """
    logger.info(f"[proxy_fetch] Fetching: {url}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    }
    try:
        resp = http_requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type and "text/plain" not in content_type:
            return f"Error: Unsupported content type: {content_type}"
        if resp.encoding and resp.encoding.lower() not in ("utf-8", "utf8"):
            resp.encoding = resp.apparent_encoding or "utf-8"
        html = resp.text
        if format == "text":
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(["script", "style", "noscript"]):
                tag.decompose()
            result = soup.get_text(separator="\n", strip=True)
        else:
            result = _html_to_text(html)
        if len(result) > CHAR_LIMIT:
            result = result[:CHAR_LIMIT] + f"\n\n... [内容已截断，共 {len(result)} 字符]"
        return result
    except http_requests.exceptions.Timeout:
        return f"Error: 请求超时（{timeout}秒）"
    except http_requests.exceptions.ConnectionError:
        return f"Error: 无法连接到 {url}"
    except http_requests.exceptions.HTTPError as e:
        return f"Error: HTTP {e.response.status_code}"
    except Exception as e:
        return f"Error: {str(e)}"


# ============================================================
# 工具 2: proxy_search - 网络搜索
# ============================================================

@mcp.tool()
async def proxy_search(
    query: str,
    max_results: int = 10,
    region: str = "wt-wt",
) -> str:
    """使用 DuckDuckGo 搜索引擎进行网络搜索。

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数（默认 10，最大 20）
        region: 搜索区域（默认 "wt-wt" 全球，"zh-cn" 中国，"us-en" 美国）

    Returns:
        搜索结果列表，包含标题、链接、摘要
    """
    logger.info(f"[proxy_search] Searching: {query}")
    max_results = min(max_results, 20)
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, region=region))
        if not results:
            return f"未找到与 '{query}' 相关的结果"
        lines = [f"# 搜索结果: {query}", f"共找到 {len(results)} 条结果\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"## {i}. {r.get('title', '无标题')}")
            lines.append(f"- **链接**: {r.get('href', '')}")
            if r.get("body"):
                lines.append(f"- **摘要**: {r['body']}")
            lines.append("")
        return "\n".join(lines)
    except Exception as e:
        return f"Error: 搜索失败 - {str(e)}"


# ============================================================
# 工具 3: proxy_request - 通用 HTTP 代理
# ============================================================

@mcp.tool()
async def proxy_request(
    url: str,
    method: str = "GET",
    headers: Optional[str] = None,
    body: Optional[str] = None,
    timeout: int = REQUEST_TIMEOUT,
    follow_redirects: bool = True,
) -> str:
    """通过云端代理发送通用 HTTP 请求。

    Args:
        url: 请求的 URL
        method: HTTP 方法（GET/POST/PUT/DELETE/PATCH，默认 GET）
        headers: JSON 格式的请求头（可选）
        body: 请求体（POST/PUT 时使用，可选）
        timeout: 超时时间，秒（默认 30）
        follow_redirects: 是否跟随重定向（默认 true）

    Returns:
        响应状态码和响应体
    """
    logger.info(f"[proxy_request] {method} {url}")
    try:
        req_headers = {}
        if headers:
            req_headers = json.loads(headers)
        if not req_headers.get("User-Agent"):
            req_headers["User-Agent"] = "Mozilla/5.0 (compatible; ProxyMCP/1.1)"
        resp = http_requests.request(
            method=method.upper(), url=url, headers=req_headers,
            data=body, timeout=timeout, allow_redirects=follow_redirects,
        )
        result = f"## HTTP Response\n- **Status**: {resp.status_code} {resp.reason}\n- **URL**: {resp.url}\n- **Content-Type**: {resp.headers.get('content-type', 'unknown')}\n\n"
        body_text = resp.text
        if len(body_text) > CHAR_LIMIT:
            body_text = body_text[:CHAR_LIMIT] + f"\n\n... [响应体已截断，共 {len(resp.text)} 字符]"
        result += f"### Response Body\n```\n{body_text}\n```"
        return result
    except json.JSONDecodeError:
        return "Error: headers 参数必须是有效的 JSON 格式"
    except Exception as e:
        return f"Error: {str(e)}"


# ============================================================
# 工具 4: proxy_health - 健康检查
# ============================================================

@mcp.tool()
async def proxy_health() -> str:
    """检查 Proxy MCP Server 的运行状态和网络连通性。"""
    test_urls = [
        ("Google", "https://www.google.com"),
        ("X/Twitter", "https://x.com"),
        ("GitHub", "https://github.com"),
    ]
    results = ["## Proxy MCP Server 状态\n"]
    results.append("- **版本**: 1.1.0")
    results.append("- **运行环境**: HuggingFace Spaces\n")
    for name, url in test_urls:
        try:
            resp = http_requests.get(url, timeout=5, allow_redirects=True)
            status = "✅ 可访问" if resp.status_code < 400 else f"⚠️ HTTP {resp.status_code}"
        except Exception:
            status = "❌ 不可访问"
        results.append(f"- **{name}**: {status}")
    return "\n".join(results)


# ============================================================
# 启动
# ============================================================

if __name__ == "__main__":
    mcp.run(transport="streamable-http")
