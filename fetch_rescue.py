#!/usr/bin/env python3
"""Collect person reports from the government rescue portal into rescue.json.

rescue.opmcm.gov.np is where the flood's lost/found reports actually live —
~25,000 of them, roughly half in Devanagari and half in Latin script, with no
name search of any kind on the portal itself (its ?q= parameter is ignored).

Large fields are dropped: every record carries a base64 `thumbnail` that would
add hundreds of megabytes. `imageUrl` is kept so photos can be linked instead.
"""
import json, time, pathlib, urllib.request

BASE = "https://rescue.opmcm.gov.np/api/person-reports"
HERE = pathlib.Path(__file__).parent
PAGE = 500          # server caps here
DELAY = 1.5

KEEP = ("type", "status", "fullName", "approximateAge", "gender",
        "locationText", "createdAt", "imageUrl", "isDuplicate", "verified")


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "khoj-family-tracing/1.0 (humanitarian mirror of public register)",
        "Accept": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception:
            if attempt == 4:
                raise
            time.sleep(min(30, 3 * (2 ** attempt)))


def slim(r):
    out = {"id": r.get("_id", "")}
    for k in KEEP:
        v = r.get(k, "")
        if v not in ("", None, False):
            out[k] = v
    d = (r.get("description") or "").strip()
    if d:
        out["description"] = d[:180]
    return out


def save(recs):
    (HERE / "rescue.json").write_text(json.dumps(
        {"source": BASE,
         "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "count": len(recs), "records": recs}, ensure_ascii=False), encoding="utf-8")


def main():
    first = get(f"{BASE}?page=1&limit={PAGE}")["data"]
    total = first["total"]
    pages = -(-total // PAGE)
    print(f"rescue portal total={total} pages={pages}", flush=True)

    seen, recs = set(), []
    for p in range(1, pages + 1):
        data = first if p == 1 else get(f"{BASE}?page={p}&limit={PAGE}")["data"]
        items = data.get("items", [])
        new = [slim(r) for r in items if r.get("_id") not in seen]
        seen.update(r.get("_id") for r in items)
        recs.extend(new)
        print(f"  page {p}/{pages}  +{len(new)}  total={len(recs)}", flush=True)
        save(recs)          # checkpoint every page
        if not items:
            break
        if p < pages:
            time.sleep(DELAY)
    print(f"wrote rescue.json ({len(recs)} records)")


if __name__ == "__main__":
    main()
