#!/usr/bin/env python3
import json
import sys
from pathlib import Path

sys.path.insert(0, '/home/adamsl/rol_finances')
from tools.self_improving_agent.agent_self_improvement.implementations.letta_tools.startup import run_claude_code_sdk

prompt = sys.stdin.read()
full_task = (
    "You are being used as a JSON-only document text classifier fallback inside ROL Finances. "
    "Return ONLY raw JSON, no markdown, no explanation. "
    "Schema: {\"doc_kind\":\"statement|receipt|unknown\",\"vendor\":\"chase|fifth_third|diners_club|jetblue|choice_privileges|moms_ledger|unknown\","
    "\"routing_key\":\"statement.chase_credit_card|statement.fifth_third_bank|statement.diners_club|statement.jetblue_business|statement.choice_privileges|statement.moms_ledger|receipt.generic|unknown\","
    "\"confidence\":0.0,\"reasons\":[\"...\"]}. "
    "Rules: Diners Club statements => statement.diners_club. Choice Privileges branded statements => choice_privileges even if Wells Fargo appears. Mom ledger/check-history pages => statement.moms_ledger. If uncertain, return unknown.\n\n"
    + prompt
)
res = run_claude_code_sdk(task=full_task, context='', working_dir='/home/adamsl/rol_finances', model='sonnet')
msg = res.get('message','').strip()
if msg.startswith('```'):
    parts = msg.split('\n')
    if parts and parts[0].startswith('```'):
        parts = parts[1:]
    if parts and parts[-1].strip() == '```':
        parts = parts[:-1]
    msg = '\n'.join(parts).strip()
if msg.startswith('json'):
    msg = msg[4:].strip()
obj = json.loads(msg)
print(json.dumps(obj))
