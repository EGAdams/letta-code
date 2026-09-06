"""Does Mazda actually hold the tools its source says it should?

Mazda's tools are defined once, in ``LETTA_TOOL_FUNCTIONS`` over in
rol_finances. ``mcp_server.py`` serves exactly that list over MCP, and
``registry.py`` attaches exactly that list to the agent. Three copies of one
fact, on three hosts, kept in step by a script somebody has to remember to run.

Nothing checked that they agreed, so this module does. It compares what the
MCP server advertises against what the agent actually carries and reports the
difference in the System Status page, with the command that closes the gap.

Two details that are easy to get wrong and cost real time when they are:

  * **Page the tool list.** ``/v1/agents/{id}/tools`` returns 10 rows unless
    asked otherwise. Reading one page made a 19-tool agent look like a 10-tool
    agent, which is how a phantom "6 tools missing" was diagnosed and chased.
    Every list call here passes an explicit limit and keeps reading.
  * **Compare by name, not by count, and scope by MCP server.** The agent
    also carries `run_claude_code_sdk`, `web_search`, and `executor_run` from
    the separate `executor_server`. Only tools whose provenance
    (`metadata_.mcp.server_name`) is this server are in scope; everything else
    attached to the agent is somebody else's business.

Reachability is a separate answer from agreement. An unreachable Letta server
is `ok: False`; a reachable one whose agent is missing tools is `ok: False`
with the missing names spelled out; agreement with extra unrelated tools
attached is plain green.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from health.probe import probe

#: Where the Letta runtime lives. The Mazda MCP tool server is a *different*
#: host (the dashboard/executor box on :8791) — this is the agent runtime.
LETTA_BASE_URL = os.environ.get('LETTA_BASE_URL', 'http://100.80.49.10:8283')
MAZDA_AGENT_ID = os.environ.get(
    'MAZDA_AGENT_ID', 'agent-6b536cf4-ec88-4290-b595-fed21d14bd8e')
MCP_SERVER_NAME = 'mazda_self_improvement'

#: The remediation. Printed verbatim in the report so nobody has to go find it.
REMEDIATION = (
    'cd /home/adamsl/rol_finances/tools/self_improving_agent && '
    f'LETTA_BASE_URL={LETTA_BASE_URL} MAZDA_TEST_AGENT_ID={MAZDA_AGENT_ID} '
    '/home/adamsl/rol_finances/.venv/bin/python -m '
    'agent_self_improvement.implementations.letta_tools.registry'
)

_PAGE = 100
_TIMEOUT = 12


def _get_json(url):
    request = urllib.request.Request(url, headers={'Accept': 'application/json'})
    with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
        return json.loads(response.read().decode('utf-8'))


def _served_tool_names(base_url):
    """Tool names the Mazda MCP server currently advertises to Letta."""
    served = _get_json(
        f'{base_url}/v1/tools/mcp/servers/{MCP_SERVER_NAME}/tools')
    return {tool['name'] for tool in served}


def _mcp_server_name(tool):
    """Which MCP server served this tool, or '' for a custom/builtin one."""
    metadata = tool.get('metadata_') or {}
    return ((metadata.get('mcp') or {}).get('server_name')) or ''


def _attached_tools(base_url, agent_id):
    """Every tool attached to the agent, as {name: mcp_server_name}, all pages.

    Termination is on an *empty* page, not on a short one. A short page looks
    like the end only if the server honoured the limit we asked for; a server
    that caps pages lower than `_PAGE` would end the walk early and hand back a
    truncated set — which is the original bug wearing a different hat. The
    `seen` guard covers the opposite failure: a server that ignores `after` and
    replays page one forever.
    """
    tools = {}
    seen = set()
    cursor = ''
    while True:
        url = f'{base_url}/v1/agents/{agent_id}/tools?limit={_PAGE}'
        if cursor:
            url += f'&after={cursor}'
        page = _get_json(url)
        if not page:
            return tools
        ids = [tool['id'] for tool in page]
        if seen.issuperset(ids):
            # No progress: the cursor is being ignored. Stop rather than spin.
            return tools
        seen.update(ids)
        tools.update({tool['name']: _mcp_server_name(tool) for tool in page})
        cursor = ids[-1]


def reconcile(base_url=None, agent_id=None):
    """Compare Mazda's served tool set against its attached tool set.

    Returns a probe payload plus the detail the System Status panel renders:
    the two sets, what is missing either way, and how to fix it.
    """
    base_url = (base_url or LETTA_BASE_URL).rstrip('/')
    agent_id = agent_id or MAZDA_AGENT_ID

    try:
        served = _served_tool_names(base_url)
        attached = _attached_tools(base_url, agent_id)
    except (urllib.error.URLError, urllib.error.HTTPError, OSError, ValueError, KeyError) as exc:
        report = probe(False, f'Cannot reach Letta at {base_url}: {exc}', hard=True)
        report.update({'reachable': False, 'served': [], 'attached': [],
                       'missing': [], 'stale': [], 'remediation': REMEDIATION,
                       'agent_id': agent_id, 'base_url': base_url})
        return report

    attached_names = set(attached)
    missing = sorted(served - attached_names)
    # Attached from *this* MCP server but no longer served by it: a tool
    # dropped from the source list that nobody detached. Calling it fails at
    # runtime. Tools from other MCP servers are not this check's business.
    stale = sorted(
        name for name, server in attached.items()
        if server == MCP_SERVER_NAME and name not in served)

    if missing:
        text = (f'{len(attached_names & served)}/{len(served)} Mazda tools attached — '
                f'missing: {", ".join(missing)}')
        report = probe(False, text)
    elif stale:
        text = (f'All {len(served)} Mazda tools attached, but {len(stale)} no longer '
                f'served: {", ".join(stale)}')
        report = probe(True, text, concern=True)
    else:
        text = f'All {len(served)} Mazda tools served and attached'
        report = probe(True, text)

    report.update({
        'reachable': True,
        'agent_id': agent_id,
        'base_url': base_url,
        'served': sorted(served),
        'attached': sorted(attached_names),
        'other_attached': sorted(attached_names - served),
        'missing': missing,
        'stale': stale,
        'remediation': REMEDIATION,
    })
    return report
