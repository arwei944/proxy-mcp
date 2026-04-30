---
title: Proxy MCP Server
emoji: 🌐
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# Proxy MCP Server

> 通过 HuggingFace Spaces 代理访问外网的 MCP 服务

## 功能

| 工具 | 说明 |
|------|------|
| `proxy_fetch` | 网页抓取，返回 Markdown |
| `proxy_search` | DuckDuckGo 网络搜索 |
| `proxy_browser_navigate` | 浏览器打开页面 |
| `proxy_browser_snapshot` | 获取页面内容/截图 |
| `proxy_request` | 通用 HTTP 代理 |
| `proxy_health` | 健康检查 |

## MCP 接入

### SOLO / Hermes

通过 Hermes 的 `add_mcp_server` 注册：

```
URL: https://arwei944-proxy-mcp.hf.space/mcp
```

### Trae / Claude Desktop

```json
{
  "mcpServers": {
    "proxy": {
      "url": "https://arwei944-proxy-mcp.hf.space/mcp"
    }
  }
}
```

### API 端点

| 端点 | 说明 |
|------|------|
| `POST /mcp` | MCP Streamable HTTP |
| `GET /api/health` | 健康检查 |
| `GET /` | 服务信息 |

## 本地开发

```bash
pip install -r requirements.txt
playwright install chromium
python main.py
```
