#!/usr/bin/env python3
"""Inject records.json into page.html and emit a pure-ASCII page.

Every Devanagari character becomes an HTML numeric entity (in markup) or a \\u
escape (in script), so the page renders names correctly even when it is served
without a charset header or through a proxy that mangles encodings.

Publishing is refused if the record count collapses against the page being
replaced. Either register can be unreachable on any given run, and a page that
quietly loses thousands of people is worse than yesterday's page: someone
searching for a name would be told it is not on the list.
"""
import json, re, sys, pathlib

HERE = pathlib.Path(__file__).parent
args = [a for a in sys.argv[1:] if not a.startswith("-")]
flags = {a for a in sys.argv[1:] if a.startswith("-")}
data_file = HERE / (args[0] if args else "records.json")
out_file = HERE / (args[1] if len(args) > 1 else "khoj.html")

KEEP_FRACTION = 0.9     # a real day-to-day change never approaches this

data = json.loads(data_file.read_text(encoding="utf-8"))
page = (HERE / "page.html").read_text(encoding="utf-8")


def published_count(path):
    """Records carried by the page we are about to overwrite, 0 if there is none."""
    if not path.exists():
        return 0
    m = re.search(r"const DATA\s*=\s*(\{.*?\});\s*\n", path.read_text(encoding="utf-8"), re.S)
    if not m:
        return 0
    try:
        return len(json.loads(m.group(1)).get("records", []))
    except Exception:
        return 0


new = len(data.get("records", []))
old = published_count(out_file)
if old and new < old * KEEP_FRACTION and "--allow-shrink" not in flags:
    sys.exit(f"refusing to publish {out_file.name}: {new:,} records would replace "
             f"{old:,} ({new/old*100:.0f}% of the live page). Keeping the page that "
             f"is already up. Pass --allow-shrink if the drop is genuine.")

# ensure_ascii=True -> all non-ASCII already \u-escaped inside the JSON literal
page = page.replace("__RECORDS__", json.dumps(data, ensure_ascii=True))


def armor(text, in_script):
    def rep(m):
        cp = ord(m.group(0))
        return ("\\u%04x" % cp) if in_script else ("&#x%04X;" % cp)
    return re.sub(r"[^\x00-\x7F]", rep, text)


parts, pos, out = [], 0, []
for m in re.finditer(r"<script\b[^>]*>.*?</script>", page, re.S):
    out.append(armor(page[pos:m.start()], False))
    out.append(armor(m.group(0), True))
    pos = m.end()
out.append(armor(page[pos:], False))
html = "".join(out)

assert all(ord(c) < 128 for c in html), "non-ASCII survived"
out_file.write_text(html, encoding="ascii")
print(f"{out_file.name}: {len(html):,} bytes, {new:,} records, pure ASCII"
      + (f" (was {old:,})" if old else ""))
