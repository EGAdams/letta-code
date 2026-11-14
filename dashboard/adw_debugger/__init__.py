"""Live ADW Sequence Debugger -- the backend half.

One read-only feed over the SSSF trace database, for the Terminal tab's
sequence diagram. `ports.py` holds the interfaces, `feed.py` is the composition
root, and nothing outside `sqlite_repository.py` knows the store is SQLite.
Design notes: dashboard/adw_debugger_ui/DESIGN.md.
"""
