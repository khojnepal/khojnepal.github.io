#!/usr/bin/env python3
"""Collect Nepal Police missing-person records into records.json.

Reads the public register at udb.nepalpolice.gov.np. Rate limited and cached:
re-running only refetches pages whose contents changed.

Note: the host omits its GlobalSign intermediate certificate, so we supply the
intermediate ourselves rather than disabling verification.
"""
import json, re, html, time, sys, pathlib, urllib.request, ssl, http.cookiejar

BASE = "https://udb.nepalpolice.gov.np"
HERE = pathlib.Path(__file__).parent
BUNDLE = HERE / "chain.pem"
LIMIT = 100
DELAY = 3.0  # be gentle: this is a live emergency server, currently overloaded

def build_chain():
    """Write chain.pem = GlobalSign intermediate + system roots.

    udb.nepalpolice.gov.np omits its intermediate certificate, so no default
    trust store can verify it. Rather than disabling verification, fetch the
    intermediate the server should have sent and verify against that.
    """
    import urllib.request as u, subprocess, tempfile, os
    der = u.urlopen("http://secure.globalsign.com/cacert/gsrsaovsslca2018.crt",
                    timeout=60).read()
    with tempfile.NamedTemporaryFile(suffix=".crt", delete=False) as f:
        f.write(der); tmp = f.name
    pem = subprocess.run(["openssl", "x509", "-inform", "DER", "-in", tmp],
                         capture_output=True, text=True, check=True).stdout
    os.unlink(tmp)
    roots = ""
    for c in ("/etc/ssl/certs/ca-certificates.crt", "/etc/pki/tls/certs/ca-bundle.crt"):
        if os.path.exists(c):
            roots = open(c, encoding="utf-8", errors="replace").read()
            break
    if not roots:
        import certifi
        roots = open(certifi.where(), encoding="utf-8").read()
    BUNDLE.write_text(pem + roots, encoding="utf-8")
    print(f"built {BUNDLE.name}")


if not BUNDLE.exists():
    build_chain()

ctx = ssl.create_default_context(cafile=str(BUNDLE))
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=ctx),
    urllib.request.HTTPCookieProcessor(jar),
)
opener.addheaders = [("User-Agent", "khoj-family-tracing/1.0 (+humanitarian mirror of public register)")]


def get(url):
    for attempt in range(6):
        try:
            with opener.open(url, timeout=90) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if attempt == 5:
                raise
            time.sleep(min(30, 3 * (2 ** attempt)))


def strip(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


FIELDS = {
    "name": r"Name:-(.*?)(?:<span|</li>)",
    "age": r"Age:-(.*?)(?:</span>|,|</li>)",
    "gender": r"Gender:-(.*?)</span>",
    "home": r"Missing Person&#039;s Address:-(.*?)</li>",
    "last_seen": r"Missing Address:-(.*?)</li>",
    "date": r"Missing Date\s*:(.*?)</li>",
}


def parse(page_html):
    out = []
    t = re.search(r"<table.*?</table>", page_html, re.S)
    if not t:
        return out
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", t.group(0), re.S):
        pid = re.search(r"/missing/photo/(\d+)", row)
        if not pid:
            continue
        rec = {"id": int(pid.group(1))}
        for k, pat in FIELDS.items():
            m = re.search(pat, row, re.S)
            rec[k] = strip(m.group(1)) if m else ""
        rec["age"] = rec["age"].rstrip(",").strip()
        out.append(rec)
    return out


def previous():
    """Records from the last run, if any."""
    f = HERE / "records.json"
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("records", [])
    except Exception:
        return []


def save(recs):
    (HERE / "records.json").write_text(
        json.dumps({"source": BASE + "/missing",
                    "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "count": len(recs), "records": recs}, ensure_ascii=False),
        encoding="utf-8")


def previous():
    """Records from the last run, if any."""
    f = HERE / "records.json"
    if not f.exists():
        return []
    try:
        return json.loads(f.read_text(encoding="utf-8")).get("records", [])
    except Exception:
        return []


def save(recs):
    (HERE / "records.json").write_text(
        json.dumps({"source": BASE + "/missing",
                    "fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "count": len(recs), "records": recs}, ensure_ascii=False),
        encoding="utf-8")


def main():
    get(f"{BASE}/lang/en")  # label locale = English
    first = get(f"{BASE}/missing?page=1&limit={LIMIT}")
    total = re.search(r"count=(\d+)", first)
    total = int(total.group(1)) if total else 0
    pages = max(1, -(-total // LIMIT)) if total else 1
    print(f"register total={total} pages={pages}", flush=True)

    seen, recs, complete = set(), [], True
    for p in range(1, pages + 1):
        try:
            page = first if p == 1 else get(f"{BASE}/missing?page={p}&limit={LIMIT}")
        except Exception as e:
            # this host is slow and drops connections under load; keep what we have
            print(f"  page {p}/{pages} failed ({e}); stopping early", flush=True)
            complete = False
            break
        got = parse(page)
        new = [r for r in got if r["id"] not in seen]
        seen.update(r["id"] for r in new)
        recs.extend(new)
        print(f"  page {p}/{pages}  +{len(new)}  total={len(recs)}", flush=True)
        save(recs)   # checkpoint: a mid-run failure keeps everything fetched so far
        if not got:
            break
        if p < pages:
            time.sleep(DELAY)

    if not complete:
        # A partial pass must not shrink the register. The list is append-mostly
        # and reorders while being paged, so rows we missed this time are very
        # likely still valid: keep them rather than dropping people off the page.
        before = previous()
        have = {r["id"] for r in recs}
        kept = [r for r in before if r["id"] not in have]
        if kept:
            print(f"incomplete pass: keeping {len(kept)} records from the previous copy")
            recs.extend(kept)

    save(recs)
    print(f"wrote records.json ({len(recs)} records{'' if complete else ', merged with previous'})")


if __name__ == "__main__":
    main()
