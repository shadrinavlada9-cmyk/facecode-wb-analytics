"""Share a rolling limit across sessions in the same application container."""
from contextlib import closing
from pathlib import Path
import sqlite3
from tempfile import gettempdir
from time import time

WINDOW = 60
LIMIT = 8
STATE = Path(gettempdir()) / "facecode-analytics-login-v1.sqlite3"


def attempt(compare, path=STATE, clock=time):
    try:
        with closing(sqlite3.connect(path, timeout=3)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS failures (occurred REAL NOT NULL)")
            db.execute("BEGIN IMMEDIATE")
            now = clock()
            db.execute("DELETE FROM failures WHERE occurred <= ?", (now - WINDOW,))
            if db.execute("SELECT COUNT(*) FROM failures").fetchone()[0] >= LIMIT:
                return "limited"
            if compare():
                return "accepted"
            db.execute("INSERT INTO failures VALUES (?)", (now,))
            return "invalid"
    except sqlite3.Error:
        return "limited"
