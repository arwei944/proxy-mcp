---
title: Proxy MCP Server
emoji: 🔌
colorFrom: blue
sdk: docker
app_port: 7860
pinned: false
---

# Proxy MCP Server

通过云端代理访问外网的 MCP Server，部署在 HuggingFace Spaces。

## 功能

- **proxy_fetch**: 网页抓取
- **proxy_search**: DuckDuckGo 搜索
- **proxy_request**: 通用 HTTP 代理
- **proxy_health**: 健康检查

## MCP 端点

```
https://arwei944-proxy-mcp.hf.space/mcp
```

## 连接方式

### Streamable HTTP

```json
{
  "mcpServers": {
    "proxy-mcp": {
      "url": "https://arwei944-proxy-mcp.hf.space/mcp",
      "transport": "streamable-http"
    }
  }
}
```