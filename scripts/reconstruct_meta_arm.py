"""
reconstruct_meta_arm.py

Rebuilds the Meta arm of the employment corpus from the recovered Wayback
capture file, using the original classification rules.

The role-classification logic here is a faithful port of `classify_role()`,
`harm_exposure_flag_fn()` and `market_specific_flag_fn()` from
`create_meta_coded_file.R`. Same term lists, same precedence, same thresholds.
Nothing about how a role is classified has been changed.

One thing IS changed, deliberately: geography.

The R script parsed country with

    parts <- str_split(loc, ",")
    last_part <- parts[length(parts)]

on a location field shaped like

    Dublin, Ireland, {'@type': 'Country', 'name': ['IRL', 'GBR']}

so the last comma-separated element is `'name': ['IRL', 'GBR']}`, not a country.
That is why `region_group` is "Unknown" for all 805 rows in the coded output,
and why the processed summaries contain "Dublin, United Kingdom" and
"Shanghai, Taiwan". This script takes the prefix before the brace instead, which
is the posting's primary location, and keeps the ISO list separately.

Usage
-----
    python reconstruct_meta_arm.py data_raw/meta_jobs_jsonld_large.csv
"""

from pathlib import Path
from collections import Counter
import argparse
import csv
import re
import sys

csv.field_size_limit(10_000_000)

# ---------------------------------------------------------------- geography
ISO = {
    "USA": "United States", "GBR": "United Kingdom", "IRL": "Ireland",
    "SGP": "Singapore", "IND": "India", "ISR": "Israel", "DEU": "Germany",
    "FRA": "France", "ESP": "Spain", "ITA": "Italy", "NLD": "Netherlands",
    "CHE": "Switzerland", "BEL": "Belgium", "POL": "Poland", "GRC": "Greece",
    "SWE": "Sweden", "PRT": "Portugal", "CAN": "Canada", "MEX": "Mexico",
    "BRA": "Brazil", "ARG": "Argentina", "AUS": "Australia", "NZL": "New Zealand",
    "JPN": "Japan", "KOR": "South Korea", "CHN": "China", "HKG": "Hong Kong",
    "TWN": "Taiwan", "MYS": "Malaysia", "IDN": "Indonesia", "THA": "Thailand",
    "VNM": "Vietnam", "PHL": "Philippines", "ARE": "United Arab Emirates",
    "ZAF": "South Africa", "KEN": "Kenya", "NGA": "Nigeria", "GHA": "Ghana",
    "ETH": "Ethiopia", "EGY": "Egypt", "MAR": "Morocco",
}
US_STATES = set("AL AK AZ AR CA CO CT DC DE FL GA HI IA ID IL IN KS KY LA MA MD "
                "ME MI MN MO MS MT NC ND NE NH NJ NM NV NY OH OK OR PA RI SC SD "
                "TN TX UT VA VT WA WI WV WY".split())

REGION = {
    "United States": "North America", "Canada": "North America",
    "Ireland": "Western Europe", "United Kingdom": "Western Europe",
    "Germany": "Western Europe", "France": "Western Europe",
    "Spain": "Western Europe", "Italy": "Western Europe",
    "Netherlands": "Western Europe", "Switzerland": "Western Europe",
    "Belgium": "Western Europe", "Portugal": "Western Europe",
    "Greece": "Western Europe", "Sweden": "Western Europe",
    "Poland": "Eastern Europe",
    "Brazil": "Latin America", "Mexico": "Latin America", "Argentina": "Latin America",
    "Singapore": "Southeast Asia", "Malaysia": "Southeast Asia",
    "Indonesia": "Southeast Asia", "Thailand": "Southeast Asia",
    "Vietnam": "Southeast Asia", "Philippines": "Southeast Asia",
    "India": "South Asia",
    "Japan": "East Asia", "South Korea": "East Asia", "China": "East Asia",
    "Hong Kong": "East Asia", "Taiwan": "East Asia",
    "Israel": "Middle East & North Africa", "United Arab Emirates": "Middle East & North Africa",
    "Egypt": "Middle East & North Africa", "Morocco": "Middle East & North Africa",
    "South Africa": "Sub-Saharan Africa", "Kenya": "Sub-Saharan Africa",
    "Nigeria": "Sub-Saharan Africa", "Ethiopia": "Sub-Saharan Africa",
    "Ghana": "Sub-Saharan Africa",
    "Australia": "Oceania", "New Zealand": "Oceania",
}
AFRICAN = {c for c, r in REGION.items() if r == "Sub-Saharan Africa"}


def parse_location(raw):
    """(city, primary_country, all_countries, country_count) — prefix is authoritative."""
    raw = (raw or "").strip()
    codes = list(dict.fromkeys(re.findall(r"'([A-Z]{3})'", raw)))
    all_countries = [ISO.get(c, c) for c in codes]

    prefix = raw.split("{")[0].strip().rstrip(",").strip()
    parts = [p.strip() for p in prefix.split(",") if p.strip()]
    city = parts[0] if parts else "Unknown"

    primary = ""
    if len(parts) >= 2:
        tail = parts[-1]
        primary = "United States" if tail in US_STATES else tail
    if not primary and city in ISO.values():
        primary = city
    if not primary and all_countries:
        primary = all_countries[0]
    return city, (primary or "Unknown"), all_countries, len(codes)


# ------------------------------------------------- classification (ported)
CORE_TERMS = ["trust and safety", "trust & safety", "business integrity",
              "integrity outcomes", "integrity"]
REVIEW_TERMS = ["quality measurement", "quality expert review", "content review",
                "reviewing various types of content",
                "graphic and/or objectionable content", "objectionable content",
                "graphic content"]
POLICY_TERMS = ["policy enforcement", "community standards", "advertiser policies",
                "advertiser policy", "content moderation", "content policy",
                "harmful content", "hate speech", "violent content",
                "dangerous organizations", "child exploitation", "self-injury",
                "animal abuse", "misinformation"]
OPS_TERMS = ["escalation", "risk support", "safety abuse", "vendor operations",
             "remediation plans"]

HARM_TERMS = ["graphic content", "objectionable content", "child exploitation",
              "graphic violence", "self-injury", "animal abuse", "hate speech",
              "violent content", "harmful content", "community standards",
              "advertiser policies"]

MARKET_TERMS = ["sub-saharan africa", "africa", "east africa", "west africa",
                "mena", "middle east", "north africa", "latam", "latin america",
                "emea", "apac", "asia pacific", "french", "arabic", "spanish",
                "portuguese", "swahili", "amharic", "oromo", "tigrinya",
                "multilingual", "market specific", "market-specific"]

SECURITY_CLASSES = {"core_integrity", "content_review_quality",
                    "policy_enforcement", "operations_support",
                    "possible_integrity"}


def split_hits(x):
    return [h.strip().lower() for h in (x or "").split(",") if h.strip()]


def has_hit(hits, pattern):
    return any(re.search(pattern, h) for h in hits)


def count_terms(text, terms):
    t = (text or "").lower()
    return sum(1 for term in terms if term in t)


def classify_role(title, text, ts_hits):
    title = (title or "").lower()
    text = (text or "").lower()
    hits = split_hits(ts_hits)

    if has_hit(hits, r"integrity|business integrity"):
        return "core_integrity", "high"
    if has_hit(hits, r"quality measurement|quality expert review|content review|"
                     r"graphic content|objectionable content"):
        return "content_review_quality", "high"
    if has_hit(hits, r"policy enforcement|community standards|advertiser policies|"
                     r"content moderation|misinformation|hate speech|"
                     r"child exploitation|self-injury|animal abuse"):
        return "policy_enforcement", "high"
    if has_hit(hits, r"escalation|vendor operations|remediation plans"):
        return "operations_support", "medium"

    if re.search(r"trust\s*&\s*safety|trust and safety|\bintegrity\b|business integrity", title):
        return "core_integrity", "high"
    if re.search(r"quality measurement|quality expert review|content reviewer|"
                 r"content review|review specialist|market specialist", title):
        return "content_review_quality", "high"
    if re.search(r"policy enforcement|content policy|community standards|advertiser policy", title):
        return "policy_enforcement", "high"
    if re.search(r"escalation|risk operations|abuse operations", title):
        return "operations_support", "high"

    scores = {
        "core_integrity": count_terms(text, CORE_TERMS),
        "content_review_quality": count_terms(text, REVIEW_TERMS),
        "policy_enforcement": count_terms(text, POLICY_TERMS),
        "operations_support": count_terms(text, OPS_TERMS),
    }
    best = max(scores, key=scores.get)
    top = scores[best]
    if top >= 3:
        return best, "high"
    if top == 2:
        return best, "medium"
    if top == 1:
        return "possible_integrity", "low"
    return "non_integrity", "none"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    src = Path(args.input)
    rows = list(csv.DictReader(open(src, encoding="utf-8-sig", errors="replace")))
    print(f"captures: {len(rows)}")

    TEXT_COLS = ["job_title", "description", "responsibilities", "qualifications",
                 "skills", "experience_requirements", "education_requirements"]

    for r in rows:
        combined = " ".join(r.get(c, "") or "" for c in TEXT_COLS)
        cls, strength = classify_role(r.get("job_title", ""), combined,
                                      r.get("ts_term_hits", ""))
        city, country, allc, ncount = parse_location(r.get("location", ""))
        r["_class"] = cls
        r["_strength"] = strength
        r["_security_relevant"] = "yes" if cls in SECURITY_CLASSES else "no"
        r["_harm"] = "yes" if (count_terms(combined, HARM_TERMS)
                               or has_hit(split_hits(r.get("ts_term_hits", "")),
                                          r"graphic content|objectionable content|"
                                          r"child exploitation|self-injury|animal abuse|"
                                          r"hate speech|violent content|community standards|"
                                          r"advertiser policies")) else "no"
        r["_market"] = "yes" if count_terms(combined, MARKET_TERMS) else "no"
        r["_city"], r["_country"] = city, country
        r["_all_countries"] = "; ".join(allc)
        r["_country_count"] = ncount
        r["_region"] = REGION.get(country, "Unknown")

    # deduplicate by job identifier, earliest capture wins
    by_job = {}
    for r in rows:
        jid = r.get("job_id") or r.get("original_url")
        if jid not in by_job or r.get("capture_timestamp", "") < by_job[jid].get("capture_timestamp", "z"):
            by_job[jid] = r
    uniq = list(by_job.values())
    print(f"distinct postings: {len(uniq)}")

    sec = [r for r in uniq if r["_security_relevant"] == "yes"]
    print(f"security-relevant (original rule): {len(sec)}")
    print("\nclass distribution:")
    for c, n in Counter(r["_class"] for r in uniq).most_common():
        print(f"   {n:5d}  {c}")

    print("\nregion of security-relevant postings "
          "(the R pipeline returned Unknown for all of these):")
    for reg, n in Counter(r["_region"] for r in sec).most_common():
        print(f"   {n:5d}  {reg}")

    print("\ncountry of security-relevant postings:")
    for c, n in Counter(r["_country"] for r in sec).most_common(15):
        print(f"   {n:5d}  {c}")

    africa = [r for r in uniq if r["_country"] in AFRICAN]
    print(f"\npostings located in Africa: {len(africa)}")
    af_market = [r for r in sec if r["_market"] == "yes"]
    print(f"security-relevant postings with a market/language signal: {len(af_market)}")

    out = Path(args.out) if args.out else src.with_name("meta_arm_reconstructed.csv")
    fields = ["job_id", "job_title", "city", "country", "region", "all_countries",
              "country_count", "date_posted", "capture_date", "capture_year",
              "employment_type", "original_url", "ts_term_count", "ts_term_hits",
              "role_class", "signal_strength", "security_relevant",
              "harm_exposure_flag", "market_specific_flag"]
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in uniq:
            w.writerow({
                "job_id": r.get("job_id", ""), "job_title": r.get("job_title", ""),
                "city": r["_city"], "country": r["_country"], "region": r["_region"],
                "all_countries": r["_all_countries"], "country_count": r["_country_count"],
                "date_posted": r.get("date_posted", ""), "capture_date": r.get("capture_date", ""),
                "capture_year": r.get("capture_year", ""),
                "employment_type": r.get("employment_type", ""),
                "original_url": r.get("original_url", ""),
                "ts_term_count": r.get("ts_term_count", ""),
                "ts_term_hits": r.get("ts_term_hits", ""),
                "role_class": r["_class"], "signal_strength": r["_strength"],
                "security_relevant": r["_security_relevant"],
                "harm_exposure_flag": r["_harm"], "market_specific_flag": r["_market"],
            })
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
