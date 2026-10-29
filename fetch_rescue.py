#!/usr/bin/env python3
"""Collect person reports from the government rescue portal into rescue.json.

rescue.opmcm.gov.np is where the flood's lost/found reports actually live —
~25,000 of them, roughly half in Devanagari and half in Latin script, with no
name search of any kind on the portal itself (its ?q= parameter is ignored).

Large fields are dropped: every record carries a base64 `thumbnail` that would
add hundreds of megabytes. `imageUrl` is kept so photos can be linked instead.

The portal either answers in a few seconds or not at all, so the retry budget is
deliberately small: a dead host costs ~50s and says why, instead of burning
eight and a half minutes of runner time to produce a bare urllib traceback.
"""
import json, socket, sys, time, pathlib, urllib.parse, urllib.request

BASE = "https://rescue.opmcm.gov.np/api/person-reports"
HERE = pathlib.Path(__file__).parent
OUT = HERE / "rescue.json"
PART = HERE / "rescue.json.part"
PAGE = 500          # server caps here
DELAY = 1.5
TIMEOUT = 15
TRIES = 2

KEEP = ("type", "status", "fullName", "approximateAge", "gender",
        "locationText", "createdAt", "imageUrl", "isDuplicate", "verified")


def probe():
    """Record whether the portal is reachable at all, before fetching.

    A week of failures logged nothing but a urllib traceback, which does not
    distinguish dead DNS from a filtered port from a merely slow API. Resolve
    and open a socket explicitly so the log names the actual fault.
    """
    host = urllib.parse.urlsplit(BASE).hostname
    try:
        ips = sorted({ai[4][0] for ai in
                      socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)})
    except OSError as e:
        print(f"portal dns FAILED {host}: {e}", flush=True)
        return
    print(f"portal dns {host} -> {', '.join(ips)}", flush=True)
    for ip in ips:
        t0 = time.time()
        try:
            socket.create_connection((ip, 443), timeout=TIMEOUT).close()
            print(f"portal tcp {ip}:443 open in {time.time()-t0:.1f}s", flush=True)
        except OSError as e:
            print(f"portal tcp {ip}:443 FAILED after {time.time()-t0:.1f}s: {e}",
                  flush=True)


def get(url):
    req = urllib.request.Request(url, headers={
        "User-Agent": "khoj-family-tracing/1.0 (humanitarian mirror of public register)",
        "Accept": "application/json"})
    for attempt in range(TRIES):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            if attempt == TRIES - 1:
                raise
            print(f"  {type(e).__name__}: {e} — retrying once", flush=True)
            time.sleep(3)


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


def save(recs, path):
    path.write_text(json.dumps(
        {"source": BASE,
         "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
         "count": len(recs), "records": recs}, ensure_ascii=False), encoding="utf-8")


def main():
    probe()
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
        # Checkpoint beside the real file, never over it: a fetch that dies at
        # page 40 of 94 must not publish a list with half the people missing.
        save(recs, PART)
        if not items:
            break
        if p < pages:
            time.sleep(DELAY)

    PART.replace(OUT)       # only a complete pass replaces the last good copy
    print(f"wrote rescue.json ({len(recs)} records)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # refresh.sh decides what to do about this; it only needs the reason.
        print(f"rescue portal fetch failed ({type(e).__name__}: {e})", flush=True)
        PART.unlink(missing_ok=True)
        sys.exit(1)
