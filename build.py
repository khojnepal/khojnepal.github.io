#!/usr/bin/env python3
"""Inject records.json into page.html and emit a pure-ASCII page.

Every Devanagari character becomes an HTML numeric entity (in markup) or a \\u
escape (in script), so the page renders names correctly even when it is served
without a charset header or through a proxy that mangles encodings.
"""
import json, re, sys, pathlib

HERE = pathlib.Path(__file__).parent
data_file = HERE / (sys.argv[1] if len(sys.argv) > 1 else "records.json")
out_file = HERE / (sys.argv[2] if len(sys.argv) > 2 else "khoj.html")

data = json.loads(data_file.read_text(encoding="utf-8"))
page = (HERE / "page.html").read_text(encoding="utf-8")

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
print(f"{out_file.name}: {len(html):,} bytes, {len(data.get("records",[])):,} records, pure ASCII")
