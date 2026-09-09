"""
code_postings.py

Applies the posting-level coding schema to collected job advertisements,
filling the signal columns that the collectors leave blank.

The schema is the one in posting_level_corpus_filled.csv: 21 columns ending in
africa_facing_signal, africa_facing_text, languages_named, language_signal,
moderation_signal, integrity_signal, policy_enforcement_signal, vendor_signal,
worker_risk_signal and offshore_relative_to_market.

Important
---------
This is a FIRST PASS, not a substitute for coding. It is deterministic and
auditable: every flag it sets is backed by the exact matched string, written
into the notes column, so a human coder can confirm or overturn each decision
in seconds rather than reading the whole advertisement. That is what makes a
second-coder reliability check tractable at n = 279.

Treat the output as machine-proposed codes to be reviewed, and keep the review
record. A kappa computed between this script and a human is a measure of the
script, not of intercoder reliability between two researchers.

Usage
-----
    python code_postings.py data_processed/meta_wayback_postings.csv
    python code_postings.py data_processed/google_postings.csv --out coded_google.csv
    python code_postings.py data_processed/*.csv --merge data_processed/postings_master.csv

Writes <input>_coded.csv next to the input unless --out is given.
"""

from pathlib import Path
import argparse
import csv
import re
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

csv.field_size_limit(10_000_000)

# ----------------------------
# Dictionaries
# ----------------------------
AFRICA_TERMS = [
    "africa", "african", "sub-saharan", "subsaharan", "sub saharan",
    "east africa", "west africa", "southern africa", "north africa",
    "mena", "middle east and north africa",
    "kenya", "nairobi", "ethiopia", "addis ababa", "nigeria", "lagos", "abuja",
    "ghana", "accra", "south africa", "johannesburg", "cape town", "pretoria",
    "senegal", "dakar", "tanzania", "uganda", "kampala", "rwanda", "kigali",
    "somalia", "sudan", "morocco", "egypt", "cairo", "tunisia", "algeria",
    "cote d'ivoire", "ivory coast", "abidjan", "cameroon", "zimbabwe", "zambia",
]

AFRICAN_LANGUAGES = [
    "amharic", "afaan oromo", "oromo", "tigrinya", "tigrigna", "somali",
    "swahili", "kiswahili", "hausa", "yoruba", "igbo", "zulu", "xhosa",
    "afrikaans", "shona", "wolof", "twi", "akan", "lingala", "kinyarwanda",
    "luganda", "sesotho", "setswana", "fulfulde", "bambara", "tigray",
]

OTHER_LANGUAGES = [
    "arabic", "french", "portuguese", "spanish", "english", "mandarin",
    "cantonese", "hindi", "urdu", "bengali", "tamil", "indonesian", "malay",
    "thai", "vietnamese", "turkish", "russian", "german", "italian", "dutch",
    "japanese", "korean", "hebrew", "persian", "farsi", "burmese", "khmer",
]

MODERATION_TERMS = [
    "content moderation", "content moderator", "content review",
    "community standards", "community guidelines", "moderation",
    "reviewing content", "content policy", "harmful content", "objectionable content",
]

INTEGRITY_TERMS = [
    "integrity", "inauthentic behavior", "inauthentic behaviour",
    "misinformation", "disinformation", "civic integrity", "election integrity",
    "business integrity", "platform integrity",
]

POLICY_ENFORCEMENT_TERMS = [
    "policy enforcement", "enforcement", "escalation", "appeals",
    "trust and safety", "trust & safety", "t&s", "abuse", "investigations",
    "risk operations", "safety operations",
]

VENDOR_TERMS = [
    "vendor", "vendors", "bpo", "outsourc", "third-party partner",
    "partner operations", "vendor operations", "vendor management",
    "service provider", "contractor",
]

WORKER_RISK_TERMS = [
    "graphic", "objectionable", "disturbing", "child exploitation",
    "self-injury", "self injury", "animal abuse", "graphic violence",
    "distressing", "sensitive content", "psychological", "wellbeing support",
    "resilience", "exposure to",
]

# Locations that are governance hubs rather than the markets they serve.
OFFSHORE_HUBS = [
    "dublin", "ireland", "singapore", "london", "united kingdom",
    "menlo park", "mountain view", "san francisco", "san jose", "sunnyvale",
    "new york", "seattle", "austin", "los angeles", "united states", "usa",
    "warsaw", "poland", "barcelona", "spain", "lisbon", "portugal",
    "amsterdam", "netherlands", "berlin", "germany", "tel aviv", "israel",
    "kuala lumpur", "malaysia", "tokyo", "japan", "seoul", "sydney",
]

AFRICA_LOCATIONS = [
    "nairobi", "kenya", "lagos", "nigeria", "accra", "ghana",
    "johannesburg", "cape town", "south africa", "addis", "ethiopia",
    "cairo", "egypt", "casablanca", "morocco", "dakar", "senegal",
    "kampala", "uganda", "kigali", "rwanda", "abidjan", "dar es salaam",
]


def hits(text, terms):
    low = (text or "").lower()
    found = [t for t in terms if t in low]
    # drop terms that are substrings of a longer match, e.g. "africa" inside "sub-saharan africa"
    out = []
    for t in sorted(set(found), key=len, reverse=True):
        if not any(t in longer and t != longer for longer in out):
            out.append(t)
    return sorted(out)


def yn(lst):
    return "yes" if lst else "no"


def africa_phrases(text, terms):
    """
    Return the Africa references as they actually appear in the advertisement,
    not as dictionary stems. "French Sub-Saharan Africa" is more useful evidence
    for a human coder than "africa", and it is what a hand-coded corpus records.

    For each matched term we capture up to two preceding capitalised words, then
    drop any phrase wholly contained in a longer one.
    """
    if not text:
        return []
    found = []
    for term in terms:
        pattern = re.compile(
            r"((?:[A-Z][\w'’-]*[\s/-]+){0,2}" + re.escape(term) + r")",
            re.IGNORECASE,
        )
        for m in pattern.finditer(text):
            phrase = re.sub(r"\s+", " ", m.group(1)).strip(" -/,;.")
            if phrase:
                found.append(phrase)

    # strip leading connectives and job-title debris, e.g. "with French Sub-Saharan"
    lead_noise = {"with", "and", "the", "for", "in", "of", "a", "an", "on", "to",
                  "specialist", "manager", "analyst", "lead", "associate", "-", "–"}
    cleaned = []
    for p in found:
        words = p.split()
        while words and words[0].lower().strip("-–,") in lead_noise:
            words.pop(0)
        if words:
            cleaned.append(" ".join(words).strip(" -–/,;."))

    # a usable phrase names a place: keep those, drop fragments like "French Sub-Saharan"
    core = tuple(AFRICA_LOCATIONS) + ("africa", "mena")
    placed = [p for p in cleaned if any(c in p.lower() for c in core)]
    pool = placed or cleaned

    # keep the longest form of each overlapping phrase
    uniq = []
    for p in sorted(set(pool), key=len, reverse=True):
        low = p.lower()
        if not any(low in q.lower() and low != q.lower() for q in uniq):
            uniq.append(p)
    return sorted(uniq, key=len, reverse=True)


def code_row(row):
    text = " ".join([
        row.get("job_title", ""), row.get("job_text", ""),
        row.get("team_function", ""), row.get("location", ""),
    ])
    location = row.get("location", "") or ""

    africa = hits(text, AFRICA_TERMS)
    afr_lang = hits(text, AFRICAN_LANGUAGES)
    oth_lang = hits(text, OTHER_LANGUAGES)
    all_lang = afr_lang + oth_lang

    moderation = hits(text, MODERATION_TERMS)
    integrity = hits(text, INTEGRITY_TERMS)
    enforcement = hits(text, POLICY_ENFORCEMENT_TERMS)
    vendor = hits(text, VENDOR_TERMS)
    risk = hits(text, WORKER_RISK_TERMS)

    in_africa = bool(hits(location, AFRICA_LOCATIONS))
    in_hub = bool(hits(location, OFFSHORE_HUBS))
    # Offshore means: the advertisement is scoped to an African market but the
    # post itself sits in a governance hub elsewhere.
    if africa and in_hub and not in_africa:
        offshore = "yes"
    elif africa and in_africa:
        offshore = "no"
    else:
        offshore = ""

    evidence = []
    if africa:
        evidence.append("africa=" + ",".join(africa[:4]))
    if all_lang:
        evidence.append("lang=" + ",".join(all_lang[:6]))
    if moderation:
        evidence.append("mod=" + moderation[0])
    if integrity:
        evidence.append("int=" + integrity[0])
    if enforcement:
        evidence.append("enf=" + enforcement[0])
    if vendor:
        evidence.append("ven=" + vendor[0])
    if risk:
        evidence.append("risk=" + risk[0])

    prior = row.get("notes", "")
    row.update({
        "africa_facing_signal": yn(africa),
        "africa_facing_text": "; ".join(africa_phrases(text, africa)[:6]),
        "languages_named": "; ".join(l.title() for l in all_lang),
        "language_signal": yn(all_lang),
        "moderation_signal": yn(moderation),
        "integrity_signal": yn(integrity),
        "policy_enforcement_signal": yn(enforcement),
        "vendor_signal": yn(vendor),
        "worker_risk_signal": yn(risk),
        "offshore_relative_to_market": offshore,
        "notes": (prior + " | " if prior else "") + "AUTOCODE " + "; ".join(evidence),
    })
    return row


POSTING_FIELDS = [
    "record_id", "company_name", "job_id", "source_url", "capture_mode",
    "date_accessed", "job_title", "location", "team_function", "job_text",
    "africa_facing_signal", "africa_facing_text", "languages_named",
    "language_signal", "moderation_signal", "integrity_signal",
    "policy_enforcement_signal", "vendor_signal", "worker_risk_signal",
    "offshore_relative_to_market", "notes",
]


def read_rows(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("--out", default=None, help="single output path")
    ap.add_argument("--merge", default=None,
                    help="also write one deduplicated master file to this path")
    args = ap.parse_args()

    merged = {}
    total_in = 0

    for path in args.inputs:
        p = Path(path)
        if not p.exists():
            print(f"skip (missing): {p}")
            continue
        rows = read_rows(p)
        total_in += len(rows)
        coded = [code_row(dict(r)) for r in rows]

        out = Path(args.out) if args.out and len(args.inputs) == 1 \
            else p.with_name(p.stem + "_coded.csv")
        with out.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=POSTING_FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(coded)

        n_africa = sum(1 for r in coded if r["africa_facing_signal"] == "yes")
        n_afrlang = sum(1 for r in coded
                        if any(l.lower() in [x.lower() for x in AFRICAN_LANGUAGES]
                               for l in r["languages_named"].split("; ") if l))
        print(f"{p.name}: {len(rows)} rows -> {out.name} "
              f"({n_africa} Africa-facing, {n_afrlang} naming an African language)")

        for r in coded:
            key = (r.get("company_name", ""), r.get("job_id", "") or r.get("source_url", ""))
            if key not in merged:
                merged[key] = r

    if args.merge:
        mp = Path(args.merge)
        mp.parent.mkdir(parents=True, exist_ok=True)
        rows = list(merged.values())
        for i, r in enumerate(rows, 1):
            r["record_id"] = i
        with mp.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=POSTING_FIELDS, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        print(f"\nMaster: {total_in} rows in, {len(rows)} after deduplication "
              f"by (company, job_id) -> {mp}")

        from collections import Counter
        print("\nBy company:")
        for c, n in Counter(r["company_name"] for r in rows).most_common():
            print(f"    {c}: {n}")
        print("\nAfrica-facing:",
              sum(1 for r in rows if r["africa_facing_signal"] == "yes"))
        print("Offshore relative to market (yes):",
              sum(1 for r in rows if r["offshore_relative_to_market"] == "yes"))


if __name__ == "__main__":
    main()
