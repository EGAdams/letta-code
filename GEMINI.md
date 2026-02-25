---
description: Always use the Python interpreter at /home/adamsl/planner/.venv/bin/python to run Python scripts. For other operations, prefer Bun.
globs: "*.ts, *.tsx, *.js, *.jsx, *.json, *.md, *.mdx, *.txt, *.yml, *.yaml, *.toml"
alwaysApply: false
---

## Python Environment

Always use the Python interpreter located at `/home/adamsl/planner/.venv/bin/python` for running Python scripts. This ensures consistency with the project's virtual environment.

## General Operations

For all other operations, such as package management, script execution, and testing, prefer `bun`.

- Use `bun install` for installing dependencies.
- Use `bun run <script>` for running scripts defined in `package.json`.
- Use `bun test` for running tests.
- Use `bun <file>` to execute TypeScript/JavaScript files.

## Code Style and Formatting

Adhere to the project's established code style and formatting rules, typically enforced by Biome (as indicated by `biome.json`). Run `bun biome format --write .` and `bun biome lint --apply-unsafe .` regularly.

## Project Structure

Maintain consistency with the existing project structure and conventions. Refer to neighboring files and `CONTRIBUTING.md` for guidance.