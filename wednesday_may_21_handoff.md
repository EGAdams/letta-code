# Wednesday May 21 Handoff

## Objective
Make the dashboard "Log Viewer" area show the same live viewer experience as `http://localhost:8080/` from `/home/adamsl/the-factory`, instead of just showing links.

## Current Status
- Confirmed dashboard source being edited is:
  - `/home/adamsl/planner/dashboard/public/index.html`
- In that file, current behavior is link-only:
  - `http://localhost:8080`
  - `http://localhost:8080/office/`
- No code change for embedding has been applied yet.

## What Went Wrong This Shift
- Several searches were too broad and pulled in huge/minified/generated content, causing noisy/truncated output.
- Need to use narrow, file-targeted reads only.

## Proven Operating Workflow (important)
- User has copy/paste issues with long inline PowerShell from chat.
- Best workflow:
  1. Write a `.ps1` script under `/home/adamsl/letta-code/`.
  2. Copy it to Windows Desktop via SSH/SCP.
  3. Give one exact run command (`powershell -ExecutionPolicy Bypass -File ...`).
- This pattern worked reliably for user execution.

## Windows/Tunnel Notes
- Tailnet URL verified working:
  - `https://desktop-shdbati-1.tailb8fc54.ts.net/` (HTTP 200 observed)
- Local expectation from user:
  - `http://localhost:8080/`
- Public internet tunnel script iterations were created; latest available script on Desktop is `windows10-public-internet-url-logviewer-v3.ps1`.

## Next Shift: Exact Steps
1. **Step 1 (finish): locate exact UI section to change**
   - Open `/home/adamsl/planner/dashboard/public/index.html`
   - Find the two anchor tags near top section linking to localhost:8080.

2. **Step 2: replace link-only block with embedded panel**
   - Add a dedicated "Log Viewer" section using an `<iframe>`.
   - iframe `src` default should be `http://localhost:8080/`.
   - Include fallback text + an "Open in new tab" link.

3. **Step 3: keep style consistent**
   - Use existing Tailwind-ish card/section styling used elsewhere in same file.
   - Give iframe full width and a fixed visible height (e.g. 70vh).

4. **Step 4: build and run**
   - In `/home/adamsl/planner/dashboard`:
     - `npm run build:components`
     - `npm run build:backend` (if backend touched)
     - restart dashboard process

5. **Step 5: verify with user**
   - Confirm "Log Viewer" area now renders live content inline.
   - Confirm no regressions in agent/server/port monitor sections.

## Guardrails for Next Shift
- Do not do broad recursive grep over whole trees when a specific file is known.
- Keep user instructions short and single-step where possible.
- Prefer creating `.ps1` files over inline multiline command blocks for Windows tasks.

## Useful Paths
- Dashboard HTML: `/home/adamsl/planner/dashboard/public/index.html`
- Desired viewer source project: `/home/adamsl/the-factory`
- Handoff scripts location: `/home/adamsl/letta-code/*.ps1`
