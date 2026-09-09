"""
clean_meta_jsonld.py

Cleans the Meta JSON-LD capture file into an analysis-ready posting table, and
prints the screening funnel so every count in the paper can be traced.

Why this exists
---------------
The raw location field looks like this:

    Dublin, Ireland, {'@type': 'Country', 'name': ['IRL', 'GBR']}

The prefix before the brace is the posting's PRIMARY location. The ISO list is
every office the posting is attached to. Two failure modes follow, and both are
visible in the existing processed files:

1. Splitting the field on commas puts fragments such as "'name': ['USA']}" into
   the country column, and occasionally assigns the wrong country entirely,
   which is where "Dublin, United Kingdom" and "Tel Aviv, France" came from.
2. Counting every ISO code inflates country totals relative to platform totals,
   because one posting is counted once per office.

This script parses the prefix for the primary location, keeps the full ISO list
separately, and deduplicates by job identifier.

Usage
-----
    python clean_meta_jsonld.py meta_jobs_jsonld_large.csv
    python clean_meta_jsonld.py meta_jobs_jsonld_large.csv --out meta_clean.csv
"""

from pathlib import Path
from collections import Counter
import argparse
import csv
import re
import sys

csv.field_size_limit(10_000_000)

ISO = {
    "USA": "United States", "GBR": "United Kingdom", "IRL": "Ireland",
    "SGP": "Singapore", "IND": "India", "ISR": "Israel", "DEU": "Germany",
    "FRA": "France", "ESP": "Spain", "ITA": "Italy", "NLD": "Netherlands",
    "CHE": "Switzerland", "BEL": "Belgium", "POL": "Poland", "GRC": "Greece",
    "SWE": "Sweden", "DNK": "Denmark", "NOR": "Norway", "PRT": "Portugal",
    "CAN": "Canada", "MEX": "Mexico", "BRA": "Brazil", "ARG": "Argentina",
    "AUS": "Australia", "NZL": "New Zealand", "JPN": "Japan", "KOR": "South Korea",
    "CHN": "China", "HKG": "Hong Kong", "TWN": "Taiwan", "MYS": "Malaysia",
    "IDN": "Indonesia", "THA": "Thailand", "VNM": "Vietnam", "PHL": "Philippines",
    "ARE": "United Arab Emirates", "ZAF": "South Africa", "KEN": "Kenya",
    "NGA": "Nigeria", "GHA": "Ghana", "ETH": "Ethiopia", "EGY": "Egypt",
}

AFRICAN = {"South Africa", "Kenya", "Nigeria", "Ghana", "Ethiopia", "Egypt"}

TS_TERMS = [
    "trust and safety", "content moderation", "content review",
    "community standards", "community guidelines", "policy enforcement",
    "integrity", "misinformation", "inauthentic", "harmful content",
    "objectionable content", "abuse", "escalation",
]


def parse_location(raw):
    """
    Return (city, primary_country, all_countries, country_count).

    The prefix before the JSON blob is authoritative for the primary location.
    The ISO list is retained but never used to assign the primary country.
    """
    raw = (raw or "").strip()
    codes = re.findall(r"'([A-Z]{3})'", raw)
    distinct = list(dict.fromkeys(codes))
    all_countries = [ISO.get(c, c) for c in distinct]

    prefix = raw.split("{")[0].strip().rstrip(",").strip()
    parts = [p.strip() for p in prefix.split(",") if p.strip()]

    city = parts[0] if parts else ""
    primary = ""
    if len(parts) >= 2:
        tail = parts[-1]
        # "Menlo Park, CA" style: a two-letter state means the US
        if len(tail) == 2 and tail.isupper():
            primary = "United States"
        else:
            primary = tail
    # a bare city that is also a country, e.g. Singapore
    if not primary and city in ISO.values():
        primary = city
    # fall back to the first ISO code only when the prefix gave nothing
    if not primary and all_countries:
        primary = all_countries[0]

    return city, primary, all_countries, len(distinct)


def ts_hits(row):
    text = " ".join([
        row.get("job_title", ""), row.get("description", ""),
        row.get("responsibilities", ""), row.get("qualifications", ""),
        row.get("skills", ""),
    ]).lower()
    return [t for t in TS_TERMS if t in text]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"No such file: {src}")
        sys.exit(1)

    with src.open(encoding="utf-8-sig", newline="", errors="replace") as f:
        rows = list(csv.DictReader(f))

    print(f"captures read: {len(rows)}")

    # parse locations
    for r in rows:
        city, primary, allc, n = parse_location(r.get("location", ""))
        r["_city"] = city
        r["_primary_country"] = primary
        r["_all_countries"] = "; ".join(allc)
        r["_country_count"] = n
        r["_ts_hits"] = "; ".join(ts_hits(r))
        r["_ts_hit_count"] = len(ts_hits(r))

    multi = sum(1 for r in rows if r["_country_count"] > 1)
    print(f"captures whose location lists more than one country: {multi}")

    # deduplicate by job identifier, keeping the earliest capture
    by_job = {}
    for r in rows:
        jid = r.get("job_id") or r.get("identifier") or r.get("original_url")
        ts = r.get("capture_timestamp", "")
        if jid not in by_job or ts < by_job[jid].get("capture_timestamp", "z"):
            by_job[jid] = r
    unique = list(by_job.values())
    print(f"distinct postings after deduplication by job_id: {len(unique)}")

    ts_any = [r for r in unique if r["_ts_hit_count"] >= 1]
    ts_two = [r for r in unique if r["_ts_hit_count"] >= 2]
    print(f"  with at least one T&S term: {len(ts_any)}")
    print(f"  with two or more T&S terms: {len(ts_two)}")

    print("\nprimary country, all distinct postings:")
    for c, n in Counter(r["_primary_country"] for r in unique).most_common(12):
        print(f"   {n:5d}  {c}")

    print("\nprimary country, postings with a T&S term:")
    for c, n in Counter(r["_primary_country"] for r in ts_any).most_common(12):
        print(f"   {n:5d}  {c}")

    in_africa = [r for r in unique if r["_primary_country"] in AFRICAN]
    print(f"\npostings located in Africa: {len(in_africa)}")

    # a country table that cannot double count
    out = Path(args.out) if args.out else src.with_name(src.stem + "_clean.csv")
    fields = ["job_id", "job_title", "city", "primary_country", "all_countries",
              "country_count", "date_posted", "capture_date", "capture_year",
              "employment_type", "original_url", "ts_hit_count", "ts_hits"]
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in unique:
            w.writerow({
                "job_id": r.get("job_id", ""),
                "job_title": r.get("job_title", ""),
                "city": r["_city"],
                "primary_country": r["_primary_country"],
                "all_countries": r["_all_countries"],
                "country_count": r["_country_count"],
                "date_posted": r.get("date_posted", ""),
                "capture_date": r.get("capture_date", ""),
                "capture_year": r.get("capture_year", ""),
                "employment_type": r.get("employment_type", ""),
                "original_url": r.get("original_url", ""),
                "ts_hit_count": r["_ts_hit_count"],
                "ts_hits": r["_ts_hits"],
            })
    print(f"\nwrote {len(unique)} deduplicated postings to {out}")

    # sanity check: country counts must not exceed the posting total
    naive = sum(r["_country_count"] for r in unique)
    print(f"\nif every listed country were counted: {naive} "
          f"(vs {len(unique)} postings, inflation of {naive - len(unique)})")


if __name__ == "__main__":
    main()
