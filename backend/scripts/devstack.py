"""Development data stack bootstrap.

Boots a local PostgreSQL server (pgserver — real PostgreSQL binaries) when the
host has no system PostgreSQL. Creates the `avascho` and `avascho_test`
databases if missing.

Usage:
    python scripts/devstack.py start   # boot postgres, print DSN, keep running
    python scripts/devstack.py status  # print current socket DSN
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

PGDATA = Path(os.environ.get("AVASCHO_PGDATA", Path.home() / ".cache" / "avascho-pg"))


def dsn(database: str = "avascho") -> str:
    return f"postgresql+psycopg2://postgres@/{database}?host={PGDATA}"


def status() -> int:
    try:
        import psycopg2

        conn = psycopg2.connect(dbname="postgres", host=str(PGDATA), user="postgres")
        conn.close()
        print(f"postgres running — {dsn()}")
        print(f"test db      — {dsn('avascho_test')}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"postgres not reachable: {exc}")
        return 1


def start() -> None:
    import pgserver

    srv = pgserver.get_server(str(PGDATA), cleanup_mode=None)
    print("postgres booted via pgserver:", srv.get_uri())
    import psycopg2

    for _ in range(20):
        try:
            conn = psycopg2.connect(dbname="postgres", host=str(PGDATA), user="postgres")
            conn.autocommit = True
            break
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    else:  # pragma: no cover
        raise RuntimeError("postgres did not accept connections")
    for dbname in ("avascho", "avascho_test"):
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (dbname,))
        if cur.fetchone() is None:
            cur.execute(f'CREATE DATABASE "{dbname}"')
            print("created database", dbname)
    conn.close()
    print(dsn())


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else "status"
    if command == "start":
        start()
        print("devstack running. keep this process alive or run with cleanup_mode=None already persisted.")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:  # pragma: no cover
            pass
    else:
        raise SystemExit(status())
