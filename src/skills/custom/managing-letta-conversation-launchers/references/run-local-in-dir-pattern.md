# `run-local-in-dir.sh` Pattern

## Purpose

Wrap Letta startup so the script can:
- switch to a target directory
- set the correct Letta server URL
- do a network preflight
- optionally create/print/save a new `conversation_id`

## Recommended modes

### Interactive

Just launch Letta in the target directory.

### `--new-id-only`

Create a new conversation and print only the new `conversation_id`.

### `--new-with-id`

Create a new conversation, print/log the `conversation_id`, save it to file(s), then open that conversation interactively.

## Recommended saved files

- `${TARGET_DIR}/.last_letta_conversation_id`
- `${HOME}/.last_letta_conversation_id`

## Example user-facing patterns

```bash
run-local-in-dir.sh /path/to/project --new-id-only --agent <agent-id>
run-local-in-dir.sh /path/to/project --new-with-id --agent <agent-id>
run-local-in-dir.sh /path/to/project --conversation <conv-id>
```

## Common pitfalls

- Do not rely on plain interactive startup if a script must know the `conversation_id`.
- Avoid mixing `--new-id-only` or `--new-with-id` with incompatible flags such as `--conversation`.
- If the wrapper runs in a remote non-interactive shell, ensure `node` / `bun` are on PATH.

## Conversation flag detail learned in practice

On at least one Letta build, this form caused the conversation ID to be parsed incorrectly during startup:

```bash
--conversation "$CONV_ID"
```

The safer form was:

```bash
--conversation="$CONV_ID"
```

If a conversation lookup error shows an ID rendered like a list (for example `['conv-...']`), switch to the equals-sign form.

If the script accepts user-provided arguments, normalize both of these inputs to the equals-sign form before calling Letta:

```bash
--conversation <conv-id>
--conversation=<conv-id>
```

This avoids inconsistent parsing in downstream startup code.

## Fallback when direct `--conversation` resume is broken

On some builds, even normalized `--conversation=<conv-id>` can still be misread during startup.

If that happens, use this fallback pattern in the startup script instead:

1. Update Letta session state files so the requested conversation becomes the active saved session for that server.
2. Launch Letta with:

```bash
--continue
```

This avoids the broken direct conversation flag path while still opening the requested conversation.

## Another real-world failure mode

Even after fixing local conversation parsing bugs, a conversation ID may still fail to resume on another machine if that conversation is not available in that machine's current server/auth context.

Symptoms:
- startup gets far enough to try resume
- then reports that the conversation was not found

In that case, do not keep patching the launcher blindly. First verify that the target conversation is actually available in the current Letta server/account context, and if needed get a fresh conversation ID from the target agent on that machine/server.

## Useful implementation detail

If the wrapper should remember the last conversation it created, save the ID to both:

```bash
${TARGET_DIR}/.last_letta_conversation_id
${HOME}/.last_letta_conversation_id
```

This makes later shell reuse easy.