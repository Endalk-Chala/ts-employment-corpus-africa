"""
build_unified_corpus.py

Merges the three reconstructed platform arms into one posting-level table.

Why a unifier is needed
-----------------------
The three arms do not observe the same thing, and pretending they do is the
fastest way to produce a number that cannot be defended:

    Meta    schema.org JSON-LD survived, so title, employer, city and country
            are all present, and the posting text was codable.
    Google  no JSON-LD, but the rendered detail block survived on some
            captures, so title and location are present for a subset and the
            description supports coding.
    TikTok  the site is robots:noindex and client-rendered. Only the
            server-rendered <title> survived. There is no location field at
            all, and no posting body.

So every row carries an `evidence_level`:

    full_text     structured posting data and body text  (Meta)
    detail_only   rendered detail block, location present (Google subset)
    title_only    job title alone                         (TikTok, and the
                                                           Google captures
                                                           that were shells)

Every count downstream must state which evidence levels it draws on. A country
distribution computed over `title_only` rows is not a country distribution, it
is a count of the few titles that happened to name a city. Keeping that
distinction in a column rather than in a footnote is what stops it being lost.

A second rule applies to geography: one primary location per posting. Multi-
location advertisements are what previously allowed a country chart to sum to
more than its own platform total.

Usage
-----
    python scripts/build_unified_corpus.py
    python scripts/build_unified_corpus.py --include-dropped

Writes
------
    data_processed/unified_corpus.csv        one row per posting
    data_processed/unified_country_table.csv country counts, with denominators
"""

from pathlib import Path
from collections import Counter
import argparse
import csv
import re

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DP = ROOT / "data_processed"
csv.field_size_limit(10_000_000)

FIELDS = [
    "platform", "job_id", "source_url", "capture_date", "job_title",
    "employer", "location_raw", "primary_city", "primary_country",
    "region_group", "multi_location", "evidence_level", "screen_decision",
    "matched_terms", "african_language", "other_language", "market_named",
    "notes",
]

AFRICAN_COUNTRIES = {
    "Kenya", "Nigeria", "Ghana", "South Africa", "Egypt", "Morocco", "Tunisia",
    "Algeria", "Ethiopia", "Uganda", "Rwanda", "Tanzania", "Senegal",
    "Ivory Coast", "Angola", "Mozambique", "Zimbabwe", "Zambia", "Cameroon",
    "Botswana", "Namibia", "Mauritius",
}
HUBS = {"United States", "Singapore", "Ireland"}

# Country inference from a free-text location string. Deliberately explicit
# rather than clever: a wrong country here becomes a wrong figure.
CITY_COUNTRY = {
    "dublin": "Ireland", "singapore": "Singapore", "london": "United Kingdom",
    "berlin": "Germany", "amsterdam": "Netherlands", "paris": "France",
    "barcelona": "Spain", "madrid": "Spain", "lisbon": "Portugal",
    "milan": "Italy", "warsaw": "Poland", "stockholm": "Sweden",
    "zurich": "Switzerland", "zürich": "Switzerland", "istanbul": "Turkey",
    "tel aviv": "Israel", "dubai": "United Arab Emirates",
    "kuala lumpur": "Malaysia", "jakarta": "Indonesia", "manila": "Philippines",
    "taguig": "Philippines", "bangkok": "Thailand", "hanoi": "Vietnam",
    "ho chi minh": "Vietnam", "tokyo": "Japan", "osaka": "Japan",
    "seoul": "Korea", "taipei": "Taiwan", "shanghai": "China",
    "beijing": "China", "shenzhen": "China", "guangzhou": "China",
    "hangzhou": "China", "hong kong": "Hong Kong", "sydney": "Australia",
    "melbourne": "Australia", "mumbai": "India", "delhi": "India",
    "gurgaon": "India", "gurugram": "India", "bangalore": "India",
    "bengaluru": "India", "hyderabad": "India", "chennai": "India",
    "new york": "United States", "los angeles": "United States",
    "san jose": "United States", "san francisco": "United States",
    "san bruno": "United States", "mountain view": "United States",
    "sunnyvale": "United States", "seattle": "United States",
    "austin": "United States", "chicago": "United States",
    "washington": "United States", "culver city": "United States",
    "cambridge": "United States", "menlo park": "United States",
    "boulder": "United States", "atlanta": "United States",
    "toronto": "Canada", "vancouver": "Canada", "mexico city": "Mexico",
    "são paulo": "Brazil", "sao paulo": "Brazil", "buenos aires": "Argentina",
    "bogotá": "Colombia", "bogota": "Colombia", "lima": "Peru",
    "santiago": "Chile",
    "nairobi": "Kenya", "lagos": "Nigeria", "abuja": "Nigeria",
    "accra": "Ghana", "johannesburg": "South Africa",
    "cape town": "South Africa", "pretoria": "South Africa",
    "durban": "South Africa", "cairo": "Egypt", "casablanca": "Morocco",
    "rabat": "Morocco", "tunis": "Tunisia", "algiers": "Algeria",
    "addis ababa": "Ethiopia", "kampala": "Uganda", "kigali": "Rwanda",
    "dar es salaam": "Tanzania", "dakar": "Senegal", "abidjan": "Ivory Coast",
}
COUNTRY_WORDS = {
    "usa": "United States", "united states": "United States",
    "u.s.": "United States", "ireland": "Ireland", "singapore": "Singapore",
    "united kingdom": "United Kingdom", "uk": "United Kingdom",
    "germany": "Germany", "france": "France", "spain": "Spain",
    "netherlands": "Netherlands", "poland": "Poland", "india": "India",
    "japan": "Japan", "korea": "Korea", "south korea": "Korea",
    "china": "China", "taiwan": "Taiwan", "australia": "Australia",
    "canada": "Canada", "brazil": "Brazil", "mexico": "Mexico",
    "switzerland": "Switzerland", "türkiye": "Turkey", "turkey": "Turkey",
    "israel": "Israel", "united arab emirates": "United Arab Emirates",
    "indonesia": "Indonesia", "malaysia": "Malaysia", "thailand": "Thailand",
    "vietnam": "Vietnam", "philippines": "Philippines", "portugal": "Portugal",
    "italy": "Italy", "sweden": "Sweden", "kenya": "Kenya",
    "nigeria": "Nigeria", "ghana": "Ghana", "south africa": "South Africa",
    "egypt": "Egypt", "morocco": "Morocco", "ethiopia": "Ethiopia",
}


# The Meta arm carries its country column as parsed from the original JSON-LD,
# which is inconsistent: ISO-ish abbreviations, a Canadian province code, and a
# US state all appear alongside country names. Left alone these split a single
# country across two rows of the table, which is how "UK" and "United Kingdom"
# came to be counted separately.
COUNTRY_ALIASES = {
    "uk": "United Kingdom", "gb": "United Kingdom", "gbr": "United Kingdom",
    "us": "United States", "usa": "United States", "u.s.": "United States",
    "united states of america": "United States",
    "on": "Canada", "ontario": "Canada", "bc": "Canada",
    "british columbia": "Canada", "quebec": "Canada",
    "south korea": "Korea", "republic of korea": "Korea", "kr": "Korea",
    "prc": "China", "hk": "Hong Kong",
    "uae": "United Arab Emirates",
    "rsa": "South Africa",
}
# US states and territories that appear in place of a country
US_STATES = {
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota", "ohio",
    "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
    "south dakota", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "west virginia", "wisconsin", "wyoming",
    "district of columbia", "puerto rico",
}


def normalise_country(raw):
    """Map a raw country string onto one canonical name."""
    if not raw:
        return ""
    c = raw.strip().strip(".,")
    low = c.lower()
    if low in COUNTRY_ALIASES:
        return COUNTRY_ALIASES[low]
    if low in US_STATES:
        return "United States"
    if low in COUNTRY_WORDS:
        return COUNTRY_WORDS[low]
    return c


def region_of(country):
    if not country:
        return ""
    if country in AFRICAN_COUNTRIES:
        return "Africa"
    if country in HUBS:
        return "Hub"
    return "Other"


def split_locations(raw):
    """Multi-location postings arrive as 'Dublin, Ireland; London, UK' or with
    a trailing '+3 more'. Return the list, first element first."""
    if not raw:
        return []
    raw = re.sub(r"\+\s*\d+\s*more", "", raw, flags=re.I)
    parts = re.split(r"\s*;\s*|\s+or\s+", raw)
    return [p.strip(" ,;") for p in parts if p.strip(" ,;")]


def country_of(location):
    """Infer a country from one location string. City first, because a city
    name is unambiguous where a bare region name is not."""
    if not location:
        return ""
    low = location.lower()
    for city, country in CITY_COUNTRY.items():
        if re.search(r"(?<![\w])" + re.escape(city) + r"(?![\w])", low):
            return country
    # country names are checked longest-first so "south africa" beats "africa"
    for word in sorted(COUNTRY_WORDS, key=len, reverse=True):
        if re.search(r"(?<![\w])" + re.escape(word) + r"(?![\w])", low):
            return COUNTRY_WORDS[word]
    return ""


def read(path):
    if not path.exists():
        print(f"  missing: {path.name}")
        return []
    with path.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


# ------------------------------------------------------------------- Meta
def load_meta():
    rows = read(DP / "meta_arm_screened.csv")
    if not rows:
        rows = read(DP / "meta_arm_reconstructed.csv")
    out = []
    for r in rows:
        if "in_final_subset" in r and r["in_final_subset"] not in ("1", "True", "true", "yes"):
            decision = "drop"
        else:
            decision = "include"
        city = (r.get("city") or "").strip()
        country = normalise_country(r.get("country") or "")
        if not country:
            country = country_of(city)
        n = r.get("country_count") or "1"
        out.append({
            "platform": "Meta", "job_id": r.get("job_id", ""),
            "source_url": r.get("original_url", ""),
            "capture_date": r.get("capture_date", ""),
            "job_title": r.get("job_title", ""), "employer": "Meta",
            "location_raw": ", ".join(x for x in (city, country) if x),
            "primary_city": city, "primary_country": country,
            "region_group": region_of(country),
            "multi_location": "yes" if n not in ("", "0", "1") else "no",
            "evidence_level": "full_text", "screen_decision": decision,
            "matched_terms": r.get("ts_term_hits", ""),
            "african_language": "", "other_language": "", "market_named": "",
            "notes": f"role_class={r.get('role_class','')}; "
                     f"signal={r.get('signal_strength','')}",
        })
    return out


# ----------------------------------------------------------------- Google
def load_google():
    rows = read(DP / "google_wayback_postings.csv")
    out = []
    for r in rows:
        note = r.get("notes", "")
        m = re.search(r"page_status=(\w+)", note)
        page_status = m.group(1) if m else ""
        loc_raw = (r.get("location") or "").strip()
        locs = split_locations(loc_raw)
        primary = locs[0] if locs else ""
        country = normalise_country(country_of(primary))
        if page_status == "detail" and loc_raw:
            level = "detail_only"
        elif page_status == "detail":
            level = "detail_no_location"
        else:
            level = "title_only"
        decision = "include" if page_status == "detail" else "unusable"
        mt = re.search(r"matched=([^;]*)", note)
        out.append({
            "platform": "Google/YouTube", "job_id": r.get("job_id", ""),
            "source_url": r.get("source_url", ""),
            "capture_date": r.get("date_accessed", ""),
            "job_title": r.get("job_title", ""),
            "employer": r.get("company_name", ""),
            "location_raw": loc_raw, "primary_city": primary,
            "primary_country": country, "region_group": region_of(country),
            "multi_location": "yes" if len(locs) > 1 else "no",
            "evidence_level": level, "screen_decision": decision,
            "matched_terms": mt.group(1).strip() if mt else "",
            "african_language": "", "other_language": "",
            "market_named": "", "notes": f"page_status={page_status}",
        })
    return out


# ----------------------------------------------------------------- TikTok
def load_tiktok():
    rows = read(DP / "tiktok_title_registry.csv")
    out = []
    for r in rows:
        city = (r.get("city_named") or "").split(";")[0].strip()
        country = normalise_country((r.get("country_of_city") or "").split(";")[0])
        if city and not country:
            country = normalise_country(country_of(city))
        out.append({
            "platform": "TikTok", "job_id": r.get("job_id", ""),
            "source_url": r.get("source_url", ""),
            "capture_date": (r.get("timestamp", "")[:8] or ""),
            "job_title": r.get("job_title", ""), "employer": "TikTok",
            "location_raw": r.get("city_named", ""),
            "primary_city": city, "primary_country": country,
            "region_group": region_of(country),
            "multi_location": "no",
            "evidence_level": "title_only",
            "screen_decision": r.get("screen_decision", ""),
            "matched_terms": r.get("matched_terms", ""),
            "african_language": r.get("african_language", ""),
            "other_language": r.get("other_language", ""),
            "market_named": r.get("market_named", ""),
            "notes": f"page_status={r.get('page_status','')}",
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-dropped", action="store_true",
                    help="keep rows screened out, for the audit trail")
    args = ap.parse_args()

    print("loading arms")
    rows = load_meta() + load_google() + load_tiktok()
    print(f"  {len(rows)} rows total")

    # capture_date normalisation: some arms carry YYYYMMDD, some YYYY-MM-DD
    for r in rows:
        d = r["capture_date"]
        if re.fullmatch(r"\d{8}", d):
            r["capture_date"] = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

    out = DP / "unified_corpus.csv"
    keep = rows if args.include_dropped else [
        r for r in rows if r["screen_decision"] == "include"]
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(keep)
    print(f"\nwrote {len(keep)} rows to {out.name}")

    inc = [r for r in rows if r["screen_decision"] == "include"]
    print("\nscreened-in postings by platform:")
    for p, n in Counter(r["platform"] for r in inc).most_common():
        print(f"   {n:5d}  {p}")

    print("\nevidence level, screened-in only:")
    for lv, n in Counter(r["evidence_level"] for r in inc).most_common():
        print(f"   {n:5d}  {lv}")

    located = [r for r in inc if r["primary_country"]]
    print(f"\npostings with a primary country: {len(located)} of {len(inc)}")
    print("this is the denominator for every geographic claim.")

    print("\ncountry counts, screened-in and located:")
    ctab = Counter(r["primary_country"] for r in located)
    for c, n in ctab.most_common(20):
        print(f"   {n:5d}  {c}  ({region_of(c)})")

    print("\nregion:")
    for g, n in Counter(r["region_group"] for r in located).most_common():
        print(f"   {n:5d}  {g}")

    africa = [r for r in located if r["region_group"] == "Africa"]
    print(f"\npostings located in Africa: {len(africa)}")
    for r in africa[:20]:
        print(f"   {r['platform']:14s} {r['primary_country']:14s} "
              f"{r['job_title'][:56]}")

    print("\nAfrican-language roles across all arms:")
    afr_lang = [r for r in inc if r["african_language"]]
    print(f"   {len(afr_lang)} postings")
    for r in afr_lang:
        where = r["primary_city"] or r["market_named"] or "(no place named)"
        print(f"   {r['african_language'][:16]:16s} -> {where[:24]:24s} "
              f"| {r['job_title'][:52]}")

    # the guard that previously failed: a country total cannot exceed its
    # platform total
    print("\nintegrity check:")
    bad = False
    for p in {r["platform"] for r in inc}:
        tot = sum(1 for r in inc if r["platform"] == p)
        loc = sum(1 for r in located if r["platform"] == p)
        if loc > tot:
            print(f"   FAIL {p}: {loc} located exceeds {tot} total")
            bad = True
    print("   ok" if not bad else "   FIX BEFORE PUBLISHING")

    ct = DP / "unified_country_table.csv"
    with ct.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["country", "region", "meta", "google_youtube", "tiktok",
                    "total"])
        for c, _ in ctab.most_common():
            row = [c, region_of(c)]
            for p in ("Meta", "Google/YouTube", "TikTok"):
                row.append(sum(1 for r in located
                               if r["primary_country"] == c and r["platform"] == p))
            row.append(ctab[c])
            w.writerow(row)
    print(f"\nwrote {ct.name}: use this for both figures, not a hand-built file")


if __name__ == "__main__":
    main()
