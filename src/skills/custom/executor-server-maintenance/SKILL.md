---
name: executor-server-maintenance
description: Maintains and debugs executor_server.py (Letta executor), including codex bridge behavior, logging, and safe restart steps. Use when executor_run/executor_codex fail or when codex claims success but files aren’t written.
---

# Executor Server Maintenance

## When to Use
- `executor_run` or `executor_codex` fails or returns inconsistent results
- Codex reports success but files are not written
- Need to debug `/home/adamsl/server_tools/executor_server.py`

## Key Files
- Startup script: `/home/adamsl/rol_finances/tools/receipt_scanning_tools/server_tools/start_executor_server.sh`
- Server: `/home/adamsl/rol_finances/tools/receipt_scanning_tools/server_tools/executor_server.py`
- MCP bridge: `/home/adamsl/rol_finances/tools/receipt_scanning_tools/server_tools/mcp_executor_bridge.py`
- uvicorn log: `/tmp/executor_8787.log`
- Codex bridge: `/home/adamsl/rol_finances/tools/receipt_scanning_tools/server_tools/node_executables/codex_coder_bridge.mjs`

## Ports
| Port | What |
|------|------|
| 8787 | uvicorn REST backend |
| 8789 | mcp-proxy MCP front door (Letta connects here) |

## Python venv
`/home/adamsl/rol_finances/.venv` — requires `uvicorn`, `fastapi`, `mcp[cli]` (all installed as of 2026-06-09).

## mcp-proxy binary
`/home/adamsl/.nvm/versions/node/v24.13.0/lib/node_modules/task-master-ai/node_modules/.bin/mcp-proxy`

## Diagnostics Workflow
1. **Check server log**
   - Look for “Bridge stdout” and “Bridge stderr”.
   - If Codex claims success but files aren’t written, check for notes mentioning `apply_patch` (bridge didn’t execute it).
2. **Inspect server code**
   - `executor_server.py` → `codex()` route
   - Confirm it only logs bridge output and doesn’t apply patches.
3. **Confirm workspace root**
   - `EXECUTOR_WORKSPACE_ROOT` controls allowed path tree.
   - `codex` writes to `base_dir / req.file_name`.
4. **Verify bridge path**
   - `CODEX_NODE_BRIDGE` or `{workspace}/node_executables/codex_coder_bridge.mjs`.
5. **Test codex end-to-end**
   - Use a tiny spec to write a file and confirm it exists.

## Fix Strategy (Codex not writing files)
- **Preferred**: Update Node bridge to actually write files (not just return patch text).
- **Alternative**: Modify `executor_server.py` to detect patch payload in `bridge_result["notes"]` and apply it.
- **Avoid**: silently claiming success without writing files.

### Known Failure Pattern (Bridge Corruption)
- If codex “succeeds” but no files appear, check the bridge file for corruption.
- Example symptoms: duplicate shebangs, indented `import` lines, or mixed content in the file.
- Fix by rewriting the bridge file cleanly at:
  `/home/adamsl/server_tools/node_executables/codex_coder_bridge.mjs`
- Validate with: `node -c /home/adamsl/server_tools/node_executables/codex_coder_bridge.mjs`

## Safe Restart Steps
1. Kill existing processes:
   ```bash
   pkill -f "uvicorn.*:8787" || true
   pkill -f "mcp-proxy.*--port 8789" || true
   pkill -f "mcp_executor_bridge.py" || true
   ```
2. Restart via the startup script (handles all env vars):
   ```bash
   bash /home/adamsl/rol_finances/tools/receipt_scanning_tools/server_tools/start_executor_server.sh &
   ```
3. Verify both ports are up:
   ```bash
   ss -tlnp | grep -E "8787|8789"
   ```
4. Smoke test:
   ```bash
   curl -s http://localhost:8787/run -X POST \
     -H "Authorization: Bearer 6c9f1e4b5a2d8f7c0b3e9a4d7f2c1e8" \
     -H "Content-Type: application/json" \
     -d '{"command":"echo ok","cwd":"."}' \
   | python3 -m json.tool
   ```
5. Re-test with a minimal executor_run from the agent.

## References
Add detailed procedures in `references/` if needed.