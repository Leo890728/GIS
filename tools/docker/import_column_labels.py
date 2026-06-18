"""
Import CSV row 2 (Chinese descriptions) into data.sqlite as column_labels.
Duplicate col_codes get the same _c suffix used in the main table.
"""
import csv
import sqlite3

CSV = "/workspace/backend/geojson/stat_zone_min_113.csv"
DB  = "/workspace/backend/data/data.sqlite"

with open(CSV, encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    raw_codes = next(reader)   # row 1: English codes
    raw_names = next(reader)   # row 2: Chinese descriptions

# dedupe col_codes the same way import_data.py does
seen = {}
col_codes = []
for code in raw_codes:
    if code in seen:
        seen[code] += 1
        col_codes.append(f"{code}_c")
    else:
        seen[code] = 1
        col_codes.append(code)

con = sqlite3.connect(DB)
cur = con.cursor()
cur.execute("DROP TABLE IF EXISTS column_labels")
cur.execute("""
    CREATE TABLE column_labels (
        col_code    TEXT PRIMARY KEY,
        col_name_zh TEXT
    )
""")
cur.executemany(
    "INSERT INTO column_labels VALUES (?, ?)",
    zip(col_codes, raw_names)
)
con.commit()
con.close()

print(f"Done — {len(col_codes)} labels written to column_labels")
