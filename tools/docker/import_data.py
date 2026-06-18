"""
Import stat_zone_min_113.csv into backend/data/data.sqlite.

CSV structure:
  Row 1: English column codes (machine-readable header)
  Row 2: Chinese descriptions (human-readable, skipped)
  Row 3+: data

Duplicate column handling:
  LINF01-06 col codes appear twice — first set = 屋齡分組, second = 建物型態分組.
  Second occurrence gets a '_c' suffix. See column_labels for correct Chinese names.
"""
import csv
import sqlite3
import sys
import os

CSV = "/workspace/backend/geojson/stat_zone_min_113.csv"
DB  = "/workspace/backend/data/data.sqlite"
TABLE = "stat_zone_stats_113"

os.makedirs(os.path.dirname(DB), exist_ok=True)

# ── resolve duplicate column names ──────────────────────────────────────────
def dedupe_cols(headers):
    seen = {}
    result = []
    for col in headers:
        if col in seen:
            seen[col] += 1
            result.append(f"{col}_c")   # _c = second occurrence (建物型態分組)
        else:
            seen[col] = 1
            result.append(col)
    return result

# ── infer value type ─────────────────────────────────────────────────────────
def coerce(val):
    if val == "" or val is None:
        return None
    try:
        i = int(val)
        return i
    except ValueError:
        pass
    try:
        f = float(val)
        return f
    except ValueError:
        pass
    return val

# ── main import ──────────────────────────────────────────────────────────────
with open(CSV, encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    raw_headers = next(reader)          # row 1: English codes
    next(reader)                        # row 2: Chinese desc — skip

    cols = dedupe_cols(raw_headers)

    # Build CREATE TABLE with TEXT columns; types are stored as-is in SQLite
    placeholders = ", ".join("?" * len(cols))
    col_defs     = ", ".join(f'"{c}" TEXT' for c in cols)

    if os.path.exists(DB):
        os.remove(DB)

    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute(f'CREATE TABLE "{TABLE}" ({col_defs})')

    batch = []
    total = 0
    for row in reader:
        batch.append([coerce(v) for v in row])
        if len(batch) >= 5000:
            cur.executemany(f'INSERT INTO "{TABLE}" VALUES ({placeholders})', batch)
            total += len(batch)
            batch = []
            print(f"  {total:,} rows inserted...", flush=True)

    if batch:
        cur.executemany(f'INSERT INTO "{TABLE}" VALUES ({placeholders})', batch)
        total += len(batch)

    cur.execute(f'CREATE INDEX idx_codebase ON "{TABLE}" (CODEBASE)')
    con.commit()
    con.close()

print(f"Done — {total:,} rows in {TABLE}")
print(f"Columns: {len(cols)} ({len(raw_headers)} original, {len(cols)-len(raw_headers)+len([c for c in raw_headers if raw_headers.count(c)>1])//2} deduped)")
