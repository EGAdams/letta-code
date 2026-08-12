"""Policy and adapters for displayable Letta thoughts."""

import json


def message_text(message):
    content = message.get('content', '')
    if isinstance(content, list):
        content = ' '.join(
            item.get('text', '') for item in content if isinstance(item, dict))
    tool_call = message.get('tool_call', {})
    if tool_call:
        arguments = tool_call.get('arguments', {})
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except Exception:
                pass
        pairs = arguments.items() if isinstance(arguments, dict) else []
        rendered = ', '.join(f'{key}={str(value)[:80]}' for key, value in pairs)
        return f'{tool_call.get("name", "?")}({rendered})'
    tool_return = message.get('tool_return', '')
    if tool_return:
        if isinstance(tool_return, dict):
            return str(tool_return.get('content', ''))[:300]
        return str(tool_return)[:300]
    approvals = message.get('tool_calls') or []
    if approvals and isinstance(approvals, list):
        names = [
            call.get('name', '?') for call in approvals if isinstance(call, dict)]
        if names:
            return 'approval requested: ' + ', '.join(names)
    return message.get('reasoning', '') or str(content)


def select_thoughts(messages, text_of, date_of):
    reasoning = _rows(messages, {'reasoning_message': 'thought'}, text_of, date_of)
    if reasoning:
        return reasoning
    assistants = _rows(messages, {'assistant_message': None}, text_of, date_of)
    if assistants:
        return assistants
    return _rows(messages, {
        'tool_call_message': 'tool',
        'tool_return_message': 'tool',
        'approval_request_message': 'approval',
        'approval_response_message': 'approval',
        'user_message': 'user',
    }, text_of, date_of)


def _rows(messages, accepted_types, text_of, date_of):
    rows = []
    for message in messages:
        message_type = message.get('message_type', '')
        if message_type not in accepted_types:
            continue
        text = text_of(message)
        if not text.strip():
            continue
        row = {'date': date_of(message), 'text': text}
        row_type = accepted_types[message_type]
        if row_type:
            row['type'] = row_type
        rows.append(row)
    return rows
