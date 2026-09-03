#!/usr/bin/env python3
"""Rebuild records.json from the last published page.

The runner starts from a clean checkout and records.json is never committed, so
after a failed police-register fetch there would be nothing to fall back on and
thousands of people would drop off the page. index.html is committed, and it
already carries those records, so recover them from there.
"""
import json, pathlib, re, sys

HERE = pathlib.Path(__file__).parent
page = HERE / "index.html"
out = HERE / "records.json"

if out.exists() or not page.exists():
    sys.exit(0)

m = re.search(r"const DATA\s*=\s*(\{.*?\});\s*\n", page.read_text(encoding="utf-8"), re.S)
if not m:
    print("could not read the previous page; continuing without it")
    sys.exit(0)

try:
    data = json.loads(m.group(1))
except Exception as e:
    print(f"previous page unreadable ({e}); continuing without it")
    sys.exit(0)

recs = [
    {"id": i, "name": r.get("n", ""), "age": r.get("a", ""), "gender": r.get("g", ""),
     "home": "", "last_seen": r.get("l", ""), "date": r.get("d", "")}
    for i, r in enumerate(data.get("records", []))
    if r.get("s") == "p"
]
out.write_text(json.dumps(
    {"source": "recovered from the last published page",
     "fetched": data.get("police_snapshot", ""), "count": len(recs), "records": recs},
    ensure_ascii=False), encoding="utf-8")
print(f"recovered {len(recs)} police records from the last published page")
