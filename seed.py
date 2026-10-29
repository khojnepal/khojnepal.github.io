#!/usr/bin/env python3
"""Rebuild records.json and rescue.json from the last published page.

The runner starts from a clean checkout and neither file is ever committed, so
after a failed fetch there would be nothing to fall back on and thousands of
people would drop off the page. index.html is committed and already carries
both registers, so recover them from there.

Each recovered copy keeps the snapshot date it was originally fetched on, never
today's, so a register that has stopped updating still reads as stale on the
rebuilt page instead of looking current.
"""
import json, pathlib, re, sys

HERE = pathlib.Path(__file__).parent
page = HERE / "index.html"

if not page.exists():
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

published = data.get("records", [])


def write(out, fetched, recs, label):
    """Only seed what a fetch has not already produced."""
    if out.exists():
        return
    out.write_text(json.dumps(
        {"source": "recovered from the last published page",
         "fetched": fetched, "count": len(recs), "records": recs},
        ensure_ascii=False), encoding="utf-8")
    print(f"recovered {len(recs)} {label} from the last published page")


police = [r for r in published if r.get("s") == "p"]
rescue = [r for r in published if r.get("s") == "r"]

write(HERE / "records.json", data.get("police_snapshot", ""), [
    {"id": i, "name": r.get("n", ""), "age": r.get("a", ""), "gender": r.get("g", ""),
     "home": "", "last_seen": r.get("l", ""), "date": r.get("d", "")}
    for i, r in enumerate(police)
], "police records")

# Mapped back into the portal's own field names, which is what prepare.py reads.
write(HERE / "rescue.json", data.get("rescue_snapshot", ""), [
    {"fullName": r.get("n", ""),
     "type": "found" if r.get("t") == "f" else "lost",
     "status": "resolved" if r.get("x") else "",
     "approximateAge": r.get("a", ""), "gender": r.get("g", ""),
     "locationText": r.get("l", ""), "createdAt": r.get("d", "")}
    for r in rescue
], "rescue-portal records")
