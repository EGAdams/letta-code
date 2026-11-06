# Notes ADW shared control contract

`dashboard/notes_adw_gateway.py` is the shared control plane for ChatGPT and
Toyota. Both clients send the same versioned JSON envelope:

```json
{"version":"notes-adw.v1","command":"notes.record.start","task_id":"t_4412b1b5df933e6ccdd32a10","correlation_id":"c1","role":"chatgpt","args":{"note_id":"n1"},"idempotency_key":"voice-c1"}
```

Commands are `notes.open`, `notes.create({title})`, `notes.rename({note_id,title})`,
`notes.record.start({note_id})`, `notes.record.stop({note_id})`,
`notes.save({note_id})`, and read-only `notes.status`. The injected transport
maps these names to the existing Notes page handlers (`openNew`, name box,
Save Note, Record notes, Stop recording and save), never to caller-supplied DOM
selectors. Every result is JSON-safe, task/correlation tagged, authorized by
role, logged without note text, and replayed for duplicate idempotency keys.

Recording remains browser-local: the transport must return an acknowledgement
and `browser_permission_required` when the page needs a user gesture or
microphone permission. A server cannot truthfully start a browser microphone.

The actual StarTrekBridge tool registration and its on-PC browser transport are
not present in this writable checkout. An authorized agent must register the
tool to call this gateway; no deployment or claim of live ChatGPT dispatch was
made here. The existing token-protected filesystem bridge remains a separate
data API and is not used as a substitute for Notes controls.
