---
name: using-tmux
description: Manage tmux sessions for long-running development jobs, durable terminal workflows, and shared log visibility. Use when you need to start, monitor, reattach, restart, or debug background processes (especially process_e2e defaults) without losing state.
---

# using-tmux

Use `tmux` to keep long-running tasks alive across disconnects and preserve terminal history.

## When to Use
- Running long jobs that must survive terminal disconnects.
- Reattaching to ongoing work without restarting commands.
- Sharing logs and terminal output across sessions.
- Restarting background jobs with consistent session names.

## Quick Start
Run from this skill directory and provide a required `--cmd`:

```bash
./scripts/start_tmux_session.sh --cmd "python -m e_two_e_processing.process"
```

Optional flags often used with `process_e2e`:

```bash
./scripts/start_tmux_session.sh \
  --cmd "python -m e_two_e_processing.process" \
  --py-path "/home/adamsl/rol_finances" \
  --restart
```

## Common Commands
List sessions:

```bash
tmux ls
```

Attach to the default session:

```bash
tmux attach -t process_e2e
```

Restart by replacing an existing session:

```bash
./scripts/start_tmux_session.sh --cmd "python -m e_two_e_processing.process" --restart
```

Tail the log path printed by the script:

```bash
tail -f /home/adamsl/rol_finances/readable_documents/reports/process_run_<timestamp>.log
```

## Advanced Ops
Send a command to an attached or detached session:

```bash
tmux send-keys -t process_e2e "python -m e_two_e_processing.process" C-m
```

Capture recent pane output to review/debug:

```bash
tmux capture-pane -t process_e2e -p | tail -n 100
```

Stream pane output to a file in real time:

```bash
tmux pipe-pane -t process_e2e -o 'cat >> /tmp/process_e2e.pipe.log'
```

Split windows to watch logs beside an active process:

```bash
tmux split-window -t process_e2e -h "tail -f /tmp/process_e2e.pipe.log"
```

Rename a session after role changes:

```bash
tmux rename-session -t process_e2e ingestion_run
```

## Python Execution Notes
- Set `PYTHONPATH` when code lives outside the current directory.
- Prefer `python -m <module>` from the repository root so imports resolve consistently.
- Match the repo root with `--cwd` (or `cd`) before launching tmux jobs.

## Helpful Options
Show script help:

```bash
./scripts/start_tmux_session.sh --help
```

Use a custom session, cwd, or log path when needed:

```bash
./scripts/start_tmux_session.sh --session my_job --cwd /tmp/project --cmd "./run.sh" --log /tmp/my_job.log
```
