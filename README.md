# Khoj — cross-script name search for Nepal's flood registers

Nepal keeps two public registers of people missing and found after the August 2026
Trishuli valley flood:

- **The government rescue portal**, `rescue.opmcm.gov.np` — ~25,200 person reports
  (12,392 lost, 12,820 found/rescued). This is where the flood data actually lives.
- **Nepal Police's missing register**, `udb.nepalpolice.gov.np/missing` — ~9,400
  standing missing-person records, of which only ~141 are dated on or after the flood.

**The problem.** The two registers, and the records inside them, are written in
different scripts. The police register is Devanagari-only — its English toggle
translates the field labels but not the data, so a relative abroad sees `Name:-`
followed by a name in Devanagari. The rescue portal is mixed: **7,007 lost reports are in
Latin script while 11,459 found/rescued records are in Devanagari.** Those two groups
cannot find each other by any search that exists. The rescue portal has no name search
at all — its `?q=` parameter is accepted and ignored. Nepali names also romanise
inconsistently (Shrestha / Shreshtha / Sthresta, Bishnu / Vishnu), so exact matching
fails even between people reading the same script.

Khoj lets someone type a name **in either script, spelled however they know it**, and
searches all 32,769 records at once.

## What it is not

It is **not** a place to report a missing person, and a match is **not** confirmation.
A parallel registry fragments tracing effort, delays official identification and
attracts fraud. Reports go to the rescue portal, Nepal Police (100 / 1660-014-1516),
and the Red Cross Restoring Family Links service. The "no results" screen says
explicitly that absence means neither safety nor death.

## How the matching works

Three layers, in `translit.py`, mirrored in JS inside the page:

1. **Transliteration** — Devanagari to Latin, honouring the inherent schwa and dropping
   the unpronounced word-final one (`शर्मा` → `sharma`, `कृष्ण` → `krishn`).
2. **Phonetic key** — collapses what Nepali romanisation does not preserve: aspirates
   (`kh`→`k`, `bh`→`b`), sibilants (`sh`/`ss`→`s`), retroflex vs dental, `v`/`w`→`b`.
   Vowels drop to a consonant skeleton, keeping a stable leading vowel.
3. **Edit distance** over those keys, matched token by token, so a partial name still
   scores — surnames and middle names are frequently omitted or added.

Illustrated with invented names, not records from the register:

| Typed by a relative | Register record | Score |
|---|---|---|
| Bishnu Bahadur | विष्णु बहादुर | 1.00 |
| Vishnu Bahadur | विष्णु बहादुर | 1.00 |
| Shrestha / Shreshtha | श्रेष्ठ | 1.00 |
| Sthresta | श्रेष्ठ | 0.80 |
| Ram Adhikari | राम प्रसाद अधिकारी | 1.00 |
| Sita (first name only) | सीता राई | 0.75 |
| John Smith | सीता राई | 0.00 |

## Leads: matching missing reports against found people

`prepare.py` also cross-matches every missing report against every found/rescued record,
which is the actual reunification problem — and impossible today, because the two sides
are written in different scripts. Pairs are kept only at ≥0.97 similarity both ways,
with equal token counts, no gender conflict, and no age gap over 8 years. That yields
**1,271 candidate pairs, 529 of them across scripts**. The shape of a cross-script
pair, written here with invented names rather than real records:

    lost  राम बहादुर (32, M)  ↔  found  Ram Bahadur
    lost  Sita Rai (29, F)    ↔  found  सीता राई (29, F)

Real pairs are deliberately not reproduced in this repository. They name
identifiable missing people, and a pair is an unverified guess — publishing one
outside the tool, stripped of its warnings, is exactly the harm the tool is
built to avoid. They are visible only in the page itself, framed as leads.

These are **leads for a person to verify, never assertions**. Two people sharing a
common name is extremely frequent in this data. The page says so before showing any.

## Files

- `fetch_rescue.py` — collects the rescue portal (~51 requests; drops the base64
  thumbnails that would otherwise add hundreds of MB).
- `fetch.py` — collects the police register (~94 requests, rate limited, checkpointed).
  Builds its own `chain.pem` to work around the server's missing TLS intermediate.
- `translit.py` — transliteration, phonetic keys, scoring.
- `prepare.py` — merges both registers, precomputes leads, emits `combined.json`.
- `build.py` — injects the data into `page.html` and emits pure-ASCII `khoj.html`.
- `refresh.sh` — the whole pipeline. `--full` includes the slow police register.
- `TLS-BUG.md`, `DISCLOSURE-EMAIL.md` — a server fault found while building this.

Personal data is **never committed**. `records.json`, `rescue.json` and `combined.json`
are gitignored; both registers are fetched at runtime.

## Why the page is one pure-ASCII file

Every Devanagari character costs six bytes as `\uXXXX`, so fields are trimmed and
single-lettered to fit 32,769 records under the 16 MB limit. It is ASCII rather than
UTF-8 because the page must render names correctly even when served without a charset
header — and gzip was rejected because `DecompressionStream` fails on exactly the old
Android phones this is meant to reach. Search runs in ~100 ms and works offline.

## Coverage — read before trusting a result

The rescue portal copies cleanly. The police register does not: it reorders as entries
are added, so paginating a live list loses rows. The last run captured **7,557 of its
9,364**. `fetch.py` dedupes by record ID but cannot recover what shifted past it. The
page states its own snapshot time and coverage. An empty result means very little.

## Refreshing

    ./refresh.sh          # rescue portal only (~6 min) — the flood data
    ./refresh.sh --full   # also the police register (~45 min, slow server)

Then republish `khoj.html` to the existing artifact URL.

## A bug found in the official portal

`udb.nepalpolice.gov.np` serves a valid GlobalSign certificate but **omits the
intermediate**, so clients that do not fetch intermediates themselves — most Android
browsers, in-app browsers, curl, and most API clients — cannot reach the register at
all. Desktop Chrome hides the fault, which is likely why it went unnoticed. Diagnosis
and the one-line fix are in `TLS-BUG.md`; a disclosure draft is in `DISCLOSURE-EMAIL.md`.
