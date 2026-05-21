# Useful Letta Startup Patterns

## Scissari agent

Agent ID:

```bash
agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

## Get a brand-new conversation ID only

```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --new-id-only --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

## Open a new interactive conversation and print its ID first

```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --new-with-id --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

## Reopen a known conversation directly

```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --conversation <conv-id>
```

## Current known Scissari conversations

Clean handoff confirmation conversation:

```bash
conv-5e450cce-9f6b-47d1-989e-efbbbef629e8
```

Example newly created conversation from testing:

```bash
conv-48318f9e-ee28-4308-84b5-0b44a3bb1a0b
```

## Conversation ID files written by the script

When using `--new-id-only` or `--new-with-id`, the script now saves:

- `${TARGET_DIR}/.last_letta_conversation_id`
- `${HOME}/.last_letta_conversation_id`

So you can inspect the latest value with either:

```bash
cat /home/adamsl/letta-code/.last_letta_conversation_id
```

or

```bash
cat ~/.last_letta_conversation_id
```

## Example flow

```bash
# Create and capture a conversation ID
CID=$(/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --new-id-only --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa)

# Reopen it later
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --conversation "$CID"
```