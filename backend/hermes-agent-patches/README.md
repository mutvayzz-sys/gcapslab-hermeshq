# Hermes agent runtime patches

The runtime image clones `https://github.com/NousResearch/hermes-agent.git` during `backend/runtime.Dockerfile`.
These patches are applied immediately after clone and before `pip install -e`.

## 0001-reload-mcp-from-config.patch

Adds `tools.mcp_tool.reload_mcp_from_config()`, a context-free helper that refreshes the process-global MCP server/tool registry from the current config file. The Agent37 gateway worker calls this through its JSONL `mcp.reload` request after console integrations register new MCP servers.
