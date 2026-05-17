# Repository Guidelines

## Project Structure & Module Organization
- `browser_server.py` is the only tracked source file and runs the Flask API that drives Chrome via Selenium/`undetected_chromedriver`.
- The repository currently has no dedicated `src/`, `tests/`, or build directories.
- Treat the Chrome profile/data directory under `C:\Users\YourName\AppData\Local\Google\Chrome\User Data` as local runtime state, not project source. Do not edit or commit generated browser data.

## Build, Test, and Development Commands
- `python browser_server.py`: start the local server on port `5001` and open ChatGPT in the controlled browser session.
- `curl -X POST http://127.0.0.1:5001/open -H 'Content-Type: application/json' -d '{"url":"https://example.com"}'`: open a page through the API.
- `curl -X POST http://127.0.0.1:5001/type -H 'Content-Type: application/json' -d '{"text":"hello"}'`: send text to the active prompt.
- `curl http://127.0.0.1:5001/read_thread`: inspect the current conversation thread.
- There is no automated test suite or build step in the repository today; verify changes manually against the Flask endpoints and browser behavior.

## Coding Style & Naming Conventions
- Use Python 3 with 4-space indentation and standard library imports first, then third-party imports.
- Prefer small helper functions and simple Flask routes over broad abstractions.
- Use descriptive snake_case names for functions, variables, and route handlers, for example `get_driver()` and `read_thread()`.
- Keep selectors and browser actions explicit; avoid hiding UI behavior behind generic wrappers unless they reduce duplication.

## Testing Guidelines
- Add tests only if you introduce non-trivial logic that can be exercised without a live browser.
- If you add tests, prefer `pytest`-style naming such as `test_open_url.py` or `test_read_thread.py`.
- For now, validate behavior by starting the server and calling the endpoints directly, especially `/open`, `/type`, `/send`, `/get_response`, and `/quit`.

## Commit & Pull Request Guidelines
- Follow the existing conventional style seen in history: `fix: ...`, `docs: ...`, `chore: ...`.
- Keep commits focused on one change and include any manual verification notes in the PR description.
- For user-visible behavior changes, include a brief before/after example or the relevant `curl` command sequence.

## Security & Configuration Tips
- Do not commit secrets, cookies, browser profiles, screenshots, or other Chrome state.
- Review changes to the hard-coded Chrome options and profile paths carefully; they directly affect local browser automation.
