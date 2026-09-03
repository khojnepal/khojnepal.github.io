#!/usr/bin/env python3
"""Merge both registers, precompute cross-script leads, emit combined.json.

Field names are single letters and text is trimmed: every Devanagari character
costs six bytes once the page is ASCII-armoured, and the whole thing has to fit
in one file that opens on a cheap phone.

  n name   s source (p=police register, r=rescue portal)
  t type   (m=missing/lost, f=found, r=rescued)
  a age    g gender (M/F)   l location   d date (YYYY-MM-DD)
"""
import json, re, sys, collections, pathlib, time
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from translit import phonetic_key, levenshtein, deva_to_latin

HERE = pathlib.Path(__file__).parent
LOC = 52


def clean(s, n=LOC):
    s = re.sub(r"\s+", " ", (s or "").strip())
    return s[:n].rstrip(" ,·-")


def age_of(r):
    m = re.search(r"\d+", str(r.get("a", "") or ""))
    return int(m.group()) if m else None


recs = []

police = json.loads((HERE / "records.json").read_text(encoding="utf-8"))
for r in police["records"]:
    n = clean(r.get("name", ""), 60)
    if not n:
        continue
    rec = {"n": n, "s": "p", "t": "m"}
    if r.get("age"): rec["a"] = clean(str(r["age"]), 4)
    g = (r.get("gender") or "")[:1].upper()
    if g in "MF": rec["g"] = g
    loc = clean(r.get("last_seen") or r.get("home") or "")
    if loc: rec["l"] = loc
    if r.get("date"): rec["d"] = r["date"][:10]
    recs.append(rec)

rescue = json.loads((HERE / "rescue.json").read_text(encoding="utf-8"))
for r in rescue["records"]:
    n = clean(r.get("fullName", ""), 60)
    if not n:
        continue
    typ = r.get("type", "")
    rec = {"n": n, "s": "r", "t": "f" if typ == "found" else "m"}
    if r.get("status") == "resolved": rec["x"] = 1
    if r.get("approximateAge"): rec["a"] = clean(str(r["approximateAge"]), 4)
    g = (r.get("gender") or "")[:1].upper()
    if g in "MF": rec["g"] = g
    loc = clean(r.get("locationText"))
    if loc: rec["l"] = loc
    if r.get("createdAt"): rec["d"] = r["createdAt"][:10]
    recs.append(rec)

print(f"records: {len(recs)}")

# ---- precompute cross-register leads: a missing report vs a found person ----
for r in recs:
    r["_k"] = phonetic_key(r["n"])
miss = [i for i, r in enumerate(recs) if r["t"] == "m" and len(r["_k"]) >= 2]
fnd = [i for i, r in enumerate(recs) if r["t"] == "f" and len(r["_k"]) >= 2]
idx = collections.defaultdict(list)
for i in fnd:
    for t in set(recs[i]["_k"]):
        idx[t].append(i)


def score(qk, ck):
    used, tot = set(), 0.0
    for qt in qk:
        best, bi = 0.0, None
        for i, ct in enumerate(ck):
            if i in used:
                continue
            sim = 1 - levenshtein(qt, ct) / max(len(qt), len(ct), 1)
            if sim > best:
                best, bi = sim, i
        if bi is not None and best > 0.34:
            used.add(bi); tot += best
    return tot / len(qk)


DEVA = re.compile(r"[ऀ-ॿ]")
t0 = time.time()
leads, seen_pair = [], set()
for li in miss:
    L = recs[li]
    cand = set()
    for t in set(L["_k"]):
        lst = idx.get(t, [])
        if len(lst) > 4000:
            continue
        cand.update(lst)
    la, lg = age_of(L), L.get("g")
    for fi in cand:
        F = recs[fi]
        if len(L["_k"]) != len(F["_k"]):
            continue
        s = min(score(L["_k"], F["_k"]), score(F["_k"], L["_k"]))
        if s < 0.97:
            continue
        fa, fg = age_of(F), F.get("g")
        if lg and fg and lg != fg:
            continue
        if la is not None and fa is not None and abs(la - fa) > 8:
            continue
        agree = (1 if (la is not None and fa is not None and abs(la - fa) <= 8) else 0) \
              + (1 if (lg and fg and lg == fg) else 0)
        cross = 1 if bool(DEVA.search(L["n"])) != bool(DEVA.search(F["n"])) else 0
        key = (L["n"].lower(), F["n"].lower())
        if key in seen_pair:
            continue
        seen_pair.add(key)
        leads.append([li, fi, round(s, 3), agree, cross])

leads.sort(key=lambda x: (-x[4], -x[3], -x[2]))
print(f"leads: {len(leads)} ({sum(1 for l in leads if l[4])} cross-script) in {time.time()-t0:.0f}s")

for r in recs:
    del r["_k"]

out = {"fetched": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
       "police_snapshot": police["fetched"], "police_total": 9364,
       "rescue_snapshot": rescue["fetched"],
       "records": recs, "leads": leads}
(HERE / "combined.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
n = len(json.dumps(out, ensure_ascii=True))
print(f"combined.json: {n/1e6:.1f}MB ascii-escaped")
