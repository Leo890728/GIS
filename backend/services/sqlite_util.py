"""Shared SQLite connection helper.

Capture (the standalone worker) and the web process both write ``cache.sqlite``
and ``history.sqlite``. WAL mode lets readers and a writer proceed concurrently,
and a busy timeout makes a brief writer-lock contention wait-and-retry instead of
failing with "database is locked".
"""

import sqlite3


def connect(path, *, timeout=5.0):
    conn = sqlite3.connect(path, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn
