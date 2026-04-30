if __name__ == "__main__":
    import os
    os.environ["MCP_STREAMABLE_HTTP_HOST"] = "0.0.0.0"
    os.environ["MCP_STREAMABLE_HTTP_PORT"] = "7860"
    mcp.run(transport="streamable-http")
