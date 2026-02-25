#!/usr/bin/env python3
"""Create a timestamped mysqldump backup of nonprofit_finance."""
import os
import argparse
import subprocess
from datetime import datetime

parser = argparse.ArgumentParser()
parser.add_argument("--output", help="Full path to output .sql file")
args = parser.parse_args()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("NON_PROFIT_USER")
DB_PASS = os.getenv("NON_PROFIT_PASSWORD")
DB_NAME = os.getenv("NON_PROFIT_DB_NAME", "nonprofit_finance")
BACKUP_DIR = os.getenv("BACKUP_DIR", "/home/adamsl/rol_finances/backups")

if not DB_USER or not DB_PASS:
    raise SystemExit("Missing NON_PROFIT_USER or NON_PROFIT_PASSWORD env vars.")

os.makedirs(BACKUP_DIR, exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
default_path = os.path.join(BACKUP_DIR, f"{DB_NAME}_{timestamp}.sql")
out_path = args.output or default_path

cmd = [
    "mysqldump",
    "-h",
    DB_HOST,
    "-P",
    str(DB_PORT),
    "-u",
    DB_USER,
    DB_NAME,
]

env = os.environ.copy()
env["MYSQL_PWD"] = DB_PASS

with open(out_path, "wb") as f:
    result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, env=env)

if result.returncode != 0:
    raise SystemExit(f"mysqldump failed: {result.stderr.decode('utf-8', errors='ignore')}")

print(f"Backup created: {out_path}")