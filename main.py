#!/usr/bin/env python3
"""
Proxy MCP Server - 通过云端代理访问外网的 MCP 服务

提供 6 个工具：
1. proxy_fetch - 网页抓取，返回 Markdown
2. proxy_search - 网络搜索 (DuckDuckGo)
3. proxy_browser_navigate - 浏览器打开页面
4. proxy_browser_snapshot - 获取页面快照/截图
5. proxy_request - 通用 HTTP 代理
6. proxy_health - 健康检查

部署在 HF Spaces，通过 Streamable HTTP 暴露 MCP 端点。
"""

import json
import logging
import os
import base64
from typing import Optional

import requests
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
BROWSER_TIMEOUT = 60

mcp = FastMCP(
    name="proxy-mcp",
    version="1.0.0",
    instructions=(
        "Proxy MCP Server - 通过云端代理访问外网。"
        "提供网页抓取、网络搜索、浏览器自动化和通用 HTTP 代理功能。"
        "适用于访问被网络限制的网站（如 X/Twitter、Google 等）。"
    ),
)


# ============================================================
# 工具 1: proxy_fetch - 网页抓取
# ============================================================

def _html_to_markdown(html: str, url: str) -> str:
    """将 HTML 转换为 Markdown"""
    try:
        from turndown import TurndownConverter
        tc = TurndownConverter(
            heading_style="atx",
            code_blocks=True,
            strip=True,
        )
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript", "meta", "link", "head"]):
            tag.decompose()
        clean_html = str(soup.get_body() or soup)
        md = tc.convert(clean_html)
        return md
    except ImportError:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text


@mcp.tool()
async def proxy_fetch(
    url: str,
    format: str = "markdown",
    timeout: int = REQUEST_TIMEOUT,
) -> str:
    """抓取指定 URL 的网页内容，返回 Markdown 或纯文本。

    Args:
        url: 要抓取的网页 URL（支持 http/https）
        format: 输出格式，"markdown" 或 "text"（默认 markdown）
        timeout: 请求超时时间，秒（默认 30）

    Returns:
        网页内容的 Markdown 或纯文本
    """
    logger.info(f"[proxy_fetch] Fetching: {url}")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
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
            result = _html_to_markdown(html, url)

        if len(result) > CHAR_LIMIT:
            result = result[:CHAR_LIMIT] + f"\n\n... [内容已截断，共 {len(result)} 字符]"

        return result

    except requests.exceptions.Timeout:
        return f"Error: 请求超时（{timeout}秒），请增加 timeout 参数或检查 URL 是否可访问"
    except requests.exceptions.ConnectionError:
        return f"Error: 无法连接到 {url}，请检查 URL 是否正确"
    except requests.exceptions.HTTPError as e:
        return f"Error: HTTP {e.response.status_code} - {str(e)}"
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
            results = list(ddgs.text(
                query,
                max_results=max_results,
                region=region,
            ))

        if not results:
            return f"未找到与 '{query}' 相关的结果"

        lines = [f"# 搜索结果: {query}", f"共找到 {len(results)} 条结果\n"]

        for i, r in enumerate(results, 1):
            title = r.get("title", "无标题")
            href = r.get("href", "")
            body = r.get("body", "")
            lines.append(f"## {i}. {title}")
            lines.append(f"- **链接**: {href}")
            if body:
                lines.append(f"- **摘要**: {body}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return f"Error: 搜索失败 - {str(e)}"


# ============================================================
# 工具 3 & 4: 浏览器自动化 (Playwright)
# ============================================================

_browser = None
_browser_page = None
_playwright_instance = None


async def _get_browser_page():
    """懒加载 Playwright 浏览器"""
    global _browser, _browser_page, _playwright_instance
    if _browser is None:
        try:
            from playwright.async_api import async_playwright
            _playwright_instance = await async_playwright().start()
            _browser = await _playwright_instance.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
            )
            _browser_page = await _browser.new_page(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
            )
            logger.info("[Browser] Playwright browser launched")
        except Exception as e:
            logger.error(f"[Browser] Failed to launch: {e}")
            return None
    return _browser_page


@mcp.tool()
async def proxy_browser_navigate(
    url: str,
    wait_seconds: float = 3.0,
) -> str:
    """使用无头浏览器打开指定 URL 并等待页面加载。

    Args:
        url: 要访问的网页 URL
        wait_seconds: 页面加载后等待时间，秒（默认 3，动态页面可增加）

    Returns:
        页面加载状态和基本信息
    """
    logger.info(f"[proxy_browser_navigate] Navigating to: {url}")

    page = await _get_browser_page()
    if page is None:
        return "Error: 浏览器未启动，请检查 Playwright 是否正确安装"

    try:
        response = await page.goto(url, timeout=BROWSER_TIMEOUT * 1000, wait_until="domcontentloaded")

        import asyncio
        await asyncio.sleep(wait_seconds)

        status = response.status if response else "unknown"
        title = await page.title()
        final_url = page.url

        return (
            f"页面加载成功\n"
            f"- **状态码**: {status}\n"
            f"- **标题**: {title}\n"
            f"- **最终 URL**: {final_url}\n"
            f"- **等待时间**: {wait_seconds}s\n\n"
            f"提示: 使用 proxy_browser_snapshot 获取页面内容或截图"
        )

    except Exception as e:
        return f"Error: 页面加载失败 - {str(e)}"


@mcp.tool()
async def proxy_browser_snapshot(
    mode: str = "content",
    selector: str = "",
) -> str:
    """获取当前浏览器页面的内容快照或截图。

    Args:
        mode: 输出模式
            - "content": 提取页面文本内容（默认）
            - "html": 获取页面 HTML
            - "screenshot": 返回 base64 截图
        selector: CSS 选择器，仅提取匹配元素的内容（可选，如 "article", ".content"）

    Returns:
        页面内容（文本/HTML）或 base64 截图数据
    """
    logger.info(f"[proxy_browser_snapshot] Mode: {mode}, Selector: {selector}")

    page = await _get_browser_page()
    if page is None:
        return "Error: 浏览器未启动"

    try:
        if mode == "screenshot":
            screenshot_bytes = await page.screenshot(full_page=False)
            b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
            return f"data:image/png;base64,{b64}"

        elif mode == "html":
            if selector:
                elements = await page.query_selector_all(selector)
                if not elements:
                    return f"未找到匹配 '{selector}' 的元素"
                html_parts = []
                for el in elements:
                    html_parts.append(await el.inner_html())
                result = "\n".join(html_parts)
            else:
                result = await page.content()

            if len(result) > CHAR_LIMIT:
                result = result[:CHAR_LIMIT] + "\n\n... [HTML 已截断]"
            return result

        else:  # content
            if selector:
                elements = await page.query_selector_all(selector)
                if not elements:
                    return f"未找到匹配 '{selector}' 的元素"
                text_parts = []
                for el in elements:
                    text = await el.inner_text()
                    text_parts.append(text.strip())
                result = "\n\n".join(text_parts)
            else:
                result = await page.inner_text("body")

            if len(result) > CHAR_LIMIT:
                result = result[:CHAR_LIMIT] + "\n\n... [内容已截断]"
            return result

    except Exception as e:
        return f"Error: 获取快照失败 - {str(e)}"


# ============================================================
# 工具 5: proxy_request - 通用 HTTP 代理
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
        headers: JSON 格式的请求头（可选，如 '{"Authorization": "Bearer xxx"}'）
        body: 请求体（POST/PUT 时使用，可选）
        timeout: 超时时间，秒（默认 30）
        follow_redirects: 是否跟随重定向（默认 true）

    Returns:
        响应状态码、响应头和响应体
    """
    logger.info(f"[proxy_request] {method} {url}")

    try:
        req_headers = {}
        if headers:
            req_headers = json.loads(headers)

        if not req_headers.get("User-Agent"):
            req_headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            )

        resp = requests.request(
            method=method.upper(),
            url=url,
            headers=req_headers,
            data=body,
            timeout=timeout,
            allow_redirects=follow_redirects,
        )

        resp_headers = dict(resp.headers)
        for h in ["set-cookie", "x-rate-limit-remaining"]:
            resp_headers.pop(h, None)

        result = (
            f"## HTTP Response\n"
            f"- **Status**: {resp.status_code} {resp.reason}\n"
            f"- **URL**: {resp.url}\n"
            f"- **Content-Type**: {resp.headers.get('content-type', 'unknown')}\n\n"
        )

        important_headers = ["content-type", "content-length", "cache-control", "server", "x-request-id"]
        header_lines = [f"  - **{k}**: {v}" for k, v in resp_headers.items() if k.lower() in important_headers]
        if header_lines:
            result += "### Response Headers\n" + "\n".join(header_lines) + "\n\n"

        body_text = resp.text
        if len(body_text) > CHAR_LIMIT:
            body_text = body_text[:CHAR_LIMIT] + f"\n\n... [响应体已截断，共 {len(resp.text)} 字符]"

        result += f"### Response Body\n```\n{body_text}\n```"

        return result

    except json.JSONDecodeError:
        return "Error: headers 参数必须是有效的 JSON 格式"
    except requests.exceptions.Timeout:
        return f"Error: 请求超时（{timeout}秒）"
    except requests.exceptions.ConnectionError:
        return f"Error: 无法连接到 {url}"
    except Exception as e:
        return f"Error: {str(e)}"


# ============================================================
# 工具 6: proxy_health - 健康检查
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
    results.append("- **版本**: 1.0.0")
    results.append("- **运行环境**: HuggingFace Spaces\n")

    for name, url in test_urls:
        try:
            resp = requests.get(url, timeout=5, allow_redirects=True)
            status = "✅ 可访问" if resp.status_code < 400 else f"⚠️ HTTP {resp.status_code}"
        except Exception:
            status = "❌ 不可访问"
        results.append(f"- **{name}**: {status}")

    page = await _get_browser_page()
    results.append(f"- **Playwright 浏览器**: {'✅ 已启动' if page else '❌ 未启动'}")

    return "\n".join(results)


# ============================================================
# 启动服务
# ============================================================

if __name__ == "__main__":
    mcp.run(transport="streamable-http", host="0.0.0.0", port=7860)
