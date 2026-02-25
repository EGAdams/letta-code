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
- Server: `/home/adamsl/server_tools/executor_server.py`
- Log (set by EXECUTOR_DEBUG_LOG): `executor_server.log` (often in workspace dir)
- Codex bridge: `node_executables/codex_coder_bridge.mjs` (relative to workspace root)

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
1. Stop executor server process.
2. Restart with correct env vars:
   - `EXECUTOR_TOKEN`, `EXECUTOR_WORKSPACE_ROOT`, `EXECUTOR_ALLOW_CMDS`
3. Re-test with a minimal codex request.

## References
Add detailed procedures in `references/` if needed.