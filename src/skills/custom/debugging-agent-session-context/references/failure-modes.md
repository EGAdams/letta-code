# Common Failure Modes

## 1. Memory exists but agent says it has no context

Possible causes:
- current session did not surface the relevant memory
- prompt was too vague
- agent replied from immediate session context only

## 2. Conversation works on one machine but not another

Possible causes:
- different server/auth context
- conversation unavailable in that environment
- startup tooling or resume path bug

## 3. Agent-to-agent reply is too weak

Possible causes:
- sender asked only “are you up to speed?”
- sender did not request factual verification
- sender assumed the target would automatically recall prior memory

## 4. Fix pattern

Use a stronger message with explicit facts and a structured requested reply.