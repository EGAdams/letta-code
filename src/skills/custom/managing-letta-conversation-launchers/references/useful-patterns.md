# Useful Letta Launcher Patterns

## Scissari agent

```bash
agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

## Get a new conversation ID only

```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --new-id-only --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

## Open a new conversation and log its ID first

```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --new-with-id --agent agent-5955b0c2-7922-4ffe-9e43-b116053b80fa
```

## Reopen a known conversation

```bash
/home/adamsl/letta-code-upstream/scripts/run-local-in-dir.sh /home/adamsl/letta-code --conversation <conv-id>
```

If the launcher script is constructing the flag internally, prefer:

```bash
--conversation="<conv-id>"
```

over:

```bash
--conversation "<conv-id>"
```

when debugging weird parsing of conversation IDs.

If the launcher passes through user arguments, rewrite any incoming conversation flag to the equals-sign form before `exec`:

```bash
--conversation=<conv-id>
```

If direct `--conversation` resume is still broken on a specific Letta build, update the saved session state and then launch with:

```bash
--continue
```

## Known Scissari conversation

```bash
conv-5e450cce-9f6b-47d1-989e-efbbbef629e8
```

## Save latest conversation ID

Recommended files:

```bash
${TARGET_DIR}/.last_letta_conversation_id
${HOME}/.last_letta_conversation_id
```