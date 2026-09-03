#!/usr/bin/env python3
"""Devanagari <-> Latin transliteration and fuzzy phonetic keys for Nepali names.

The official register stores names in Devanagari only. Relatives abroad search in
Latin script, and romanise inconsistently (Shrestha / Shreshtha / Sthresta,
Bishnu / Vishnu). Matching therefore needs three layers:

  1. transliterate Devanagari -> Latin, honouring the inherent schwa
  2. reduce both sides to a phonetic key that collapses the distinctions Nepali
     romanisation does not preserve (aspirates, sibilants, retroflex/dental, b/v)
  3. edit distance over those keys, for whatever the key still misses
"""
import re, unicodedata

# Indic scripts were encoded parallel to Devanagari, so subtracting a block
# offset turns most of them into Devanagari and the existing rules then apply.
INDIC_OFFSETS = {
    'bn': 0x080,  # Bengali / Assamese
    'pa': 0x100,  # Gurmukhi
    'gu': 0x180,  # Gujarati
    'or': 0x200,  # Odia
    'ta': 0x280,  # Tamil
    'te': 0x300,  # Telugu
    'kn': 0x380,  # Kannada
    'ml': 0x400,  # Malayalam
}

# Tamil writes voiced and unvoiced consonants with the same letter, so a name
# transliterates ambiguously: தாஸ் is both "Tas" and "Das". We try both.
TAMIL_VOICED = str.maketrans({'ऩ': 'न', 'च': 'स', 'त': 'द', 'क': 'ग', 'प': 'ब', 'ट': 'ड'})


def to_devanagari(text):
    """Fold any supported Indic script into Devanagari."""
    for off in INDIC_OFFSETS.values():
        lo, hi = 0x0900 + off, 0x097F + off
        if any(lo <= ord(c) <= hi for c in text):
            return ''.join(chr(ord(c) - off) if lo <= ord(c) <= hi else c for c in text)
    return text


def script_variants(text):
    """Devanagari forms worth trying for this input (Tamil yields two)."""
    dev = to_devanagari(text)
    out = [dev]
    if any(0x0B80 <= ord(c) <= 0x0BFF for c in text):
        v = dev.translate(TAMIL_VOICED)
        if v != dev:
            out.append(v)
    return out


CONS = {
    'क':'k','ख':'kh','ग':'g','घ':'gh','ङ':'ng',
    'च':'ch','छ':'chh','ज':'j','झ':'jh','ञ':'ny',
    'ट':'t','ठ':'th','ड':'d','ढ':'dh','ण':'n',
    'त':'t','थ':'th','द':'d','ध':'dh','न':'n',
    'प':'p','फ':'ph','ब':'b','भ':'bh','म':'m',
    'य':'y','र':'r','ल':'l','व':'w','श':'sh','ष':'sh','स':'s','ह':'h',
    'ळ':'l','क़':'k','ख़':'kh','ग़':'g','ज़':'z','ड़':'r','ढ़':'rh','फ़':'f',
}
IND_VOWEL = {
    'अ':'a','आ':'aa','इ':'i','ई':'ee','उ':'u','ऊ':'oo','ए':'e','ऐ':'ai',
    'ओ':'o','औ':'au','ऋ':'ri','ॠ':'ri','ऑ':'o','ऍ':'e',
}
MATRA = {
    'ा':'aa','ि':'i','ी':'ee','ु':'u','ू':'oo','े':'e','ै':'ai',
    'ो':'o','ौ':'au','ृ':'ri','ॉ':'o','ॅ':'e',
}
SIGN = {'ं':'n','ँ':'n','ः':'h','ऽ':''}
VIRAMA = '्'
DIGITS = {'०':'0','१':'1','२':'2','३':'3','४':'4','५':'5','६':'6','७':'7','८':'8','९':'9'}


def deva_to_latin(text):
    """Transliterate Devanagari to a readable Latin form."""
    out, i, n = [], 0, len(text)
    while i < n:
        ch = text[i]
        if ch in CONS:
            out.append(CONS[ch])
            nxt = text[i + 1] if i + 1 < n else ''
            if nxt == VIRAMA:
                i += 2
                continue
            if nxt in MATRA:
                out.append(MATRA[nxt])
                i += 2
                continue
            out.append('a')          # inherent schwa
            i += 1
            continue
        if ch in IND_VOWEL:
            out.append(IND_VOWEL[ch]); i += 1; continue
        if ch in MATRA:
            out.append(MATRA[ch]); i += 1; continue
        if ch in SIGN:
            out.append(SIGN[ch]); i += 1; continue
        if ch in DIGITS:
            out.append(DIGITS[ch]); i += 1; continue
        out.append(ch); i += 1
    s = ''.join(out)
    # word-final schwa is not pronounced in Nepali: शर्मा -> sharmaa, राम -> raam(a)
    s = re.sub(r'(?<=[a-z])a\b', '', s)
    return re.sub(r'\s+', ' ', s).strip()


# --- phonetic key -----------------------------------------------------------
# Ordered rewrites collapsing the contrasts Latin spellings of Nepali do not
# preserve. Longest patterns first.
_COLLAPSE = [
    ('ksh','x'), ('chh','c'), ('sch','s'), ('shr','sr'),
    ('kh','k'), ('gh','g'), ('ch','c'), ('jh','j'), ('th','t'), ('dh','d'),
    ('ph','f'), ('bh','b'), ('sh','s'), ('ss','s'), ('cs','x'), ('ks','x'),
    ('ng','n'), ('ny','n'), ('gy','g'), ('ee','i'), ('oo','u'), ('ai','e'),
    ('au','o'), ('aa','a'), ('ya','a'), ('w','b'), ('v','b'), ('z','j'),
    ('q','k'), ('f','p'), ('c','k'), ('x','ks'),
]
_VOWELS = set('aeiou')


MAX_TOKENS, MAX_TOKEN_LEN = 8, 24


def phonetic_key(text):
    """Reduce a name (either script) to a comparable consonant skeleton.

    Token count and length are capped: matching is O(query tokens x record
    tokens) across tens of thousands of records, so an over-long input would
    otherwise lock up a phone for a minute.
    """
    text = to_devanagari(str(text)[:200])
    if re.search(r'[ऀ-ॿ]', text):
        text = deva_to_latin(text)
    s = unicodedata.normalize('NFKD', text.lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-z\s]', '', s)
    keys = []
    for word in s.split()[:MAX_TOKENS]:
        w = word[:MAX_TOKEN_LEN]
        for a, b in _COLLAPSE:
            w = w.replace(a, b)
        w = re.sub(r'(.)\1+', r'\1', w)        # de-double
        lead = w[0] if w else ''
        skel = ''.join(c for c in w if c not in _VOWELS)
        if lead in _VOWELS:
            skel = lead + skel                  # keep a leading vowel: it is stable
        keys.append(skel or lead)
    return keys


def levenshtein(a, b):
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def name_score(query, candidate):
    """0..1 similarity between two names, in any supported script."""
    c = phonetic_key(candidate)
    return max(_score_keys(phonetic_key(v), c) for v in script_variants(str(query)[:200]))


def _score_keys(q, c):
    if not q or not c:
        return 0.0
    used, total = set(), 0.0
    for qt in q:
        best, bi = 0.0, None
        for i, ct in enumerate(c):
            if i in used:
                continue
            d = levenshtein(qt, ct)
            sim = 1 - d / max(len(qt), len(ct), 1)
            if sim > best:
                best, bi = sim, i
        if bi is not None and best > 0.34:
            used.add(bi)
            total += best
    # score against the query's own token count, so a partial name still matches
    return round(total / len(q), 4)
