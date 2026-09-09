"""
prepare_release.py

Turns the working corpus into the public release, and refuses to do so if the
data fails its integrity checks.

The checks are the point. One of them exists because the published figures for
this project disagreed with each other by nine roles: a country-level chart
counted multi-location postings once per location while the platform-level
chart counted them once per posting. That is an easy mistake and an invisible
one until someone adds up the bars. It cannot recur here without the release
failing loudly.

Usage
-----
    python scripts/prepare_release.py data/processed/postings_master.csv
    python scripts/prepare_release.py data/processed/postings_master.csv --text-mode excerpt
    python scripts/prepare_release.py data/processed/postings_master.csv --check-only

Writes into data/public/
    postings_public.csv                 one row per posting, coded variables
    counts_country_by_platform.csv      country x platform, deduplicated
    counts_hub_by_platform.csv          hub x platform, matching the article
    release_manifest.json               row counts, checksums, settings
"""

from pathlib import Path
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PUBLIC_DIR = REPO_ROOT / "data" / "public"

csv.field_size_limit(10_000_000)

HUBS = {
    "united states": "United States",
    "usa": "United States",
    "u.s.": "United States",
    "singapore": "Singapore",
    "ireland": "Ireland",
}

# Country detection for the location field, longest first so "south africa"
# is not swallowed by "africa".
COUNTRY_PATTERNS = [
    ("United States", ["united states", "usa", " ca,", "menlo park", "mountain view",
                       "san francisco", "san jose", "sunnyvale", "new york", "seattle",
                       "austin", "los angeles", "washington, dc"]),
    ("Singapore", ["singapore"]),
    ("Ireland", ["ireland", "dublin"]),
    ("United Kingdom", ["united kingdom", "london", "manchester", " uk"]),
    ("India", ["india", "bangalore", "bengaluru", "hyderabad", "gurgaon", "mumbai"]),
    ("Israel", ["israel", "tel aviv"]),
    ("Germany", ["germany", "berlin", "munich", "hamburg"]),
    ("Brazil", ["brazil", "sao paulo", "são paulo"]),
    ("Taiwan", ["taiwan", "taipei"]),
    ("Malaysia", ["malaysia", "kuala lumpur"]),
    ("Indonesia", ["indonesia", "jakarta"]),
    ("Thailand", ["thailand", "bangkok"]),
    ("Japan", ["japan", "tokyo"]),
    ("South Korea", ["south korea", "seoul"]),
    ("Poland", ["poland", "warsaw"]),
    ("Spain", ["spain", "barcelona", "madrid"]),
    ("Portugal", ["portugal", "lisbon"]),
    ("Netherlands", ["netherlands", "amsterdam"]),
    ("Australia", ["australia", "sydney", "melbourne"]),
    ("Canada", ["canada", "toronto", "vancouver", "montreal"]),
    ("Kenya", ["kenya", "nairobi"]),
    ("Nigeria", ["nigeria", "lagos", "abuja"]),
    ("Ghana", ["ghana", "accra"]),
    ("South Africa", ["south africa", "johannesburg", "cape town", "pretoria"]),
    ("Ethiopia", ["ethiopia", "addis"]),
    ("Egypt", ["egypt", "cairo"]),
    ("Morocco", ["morocco", "casablanca", "rabat"]),
    ("Senegal", ["senegal", "dakar"]),
]

AFRICAN_COUNTRIES = {"Kenya", "Nigeria", "Ghana", "South Africa", "Ethiopia",
                     "Egypt", "Morocco", "Senegal"}

PUBLIC_FIELDS = [
    "record_id", "company_name", "job_id", "source_url", "capture_mode",
    "date_accessed", "job_title", "location", "primary_country",
    "all_countries", "location_count", "team_function",
    "africa_facing_signal", "africa_facing_text", "languages_named",
    "language_signal", "moderation_signal", "integrity_signal",
    "policy_enforcement_signal", "vendor_signal", "worker_risk_signal",
    "offshore_relative_to_market", "job_text_sha256", "notes",
]


def countries_in(location):
    """Every country named in a location string, in order of first appearance."""
    low = " " + (location or "").lower() + " "
    found = []
    for country, cues in COUNTRY_PATTERNS:
        if any(c in low for c in cues) and country not in found:
            found.append(country)
    return found


def sha256(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


# ----------------------------
# Integrity checks
# ----------------------------
def run_checks(rows):
    """Return (list_of_failures, list_of_warnings, stats)."""
    fail, warn = [], []
    stats = {}

    # 1. duplicate job identifiers
    keys = [(r["company_name"], r["job_id"]) for r in rows if r.get("job_id")]
    dupes = [k for k, n in Counter(keys).items() if n > 1]
    if dupes:
        fail.append(f"{len(dupes)} duplicate (company, job_id) pairs; the article "
                    f"states deduplication by platform job identifier. First: {dupes[:3]}")

    # 2. missing job identifiers
    no_id = sum(1 for r in rows if not r.get("job_id"))
    if no_id:
        warn.append(f"{no_id} rows have no job_id, so they cannot be deduplicated "
                    f"by identifier and are deduplicated by source_url instead")

    # 3. THE FIGURE 1 CHECK.
    # A country-level count must never exceed the platform total. It will if a
    # multi-location posting is counted once per location.
    per_platform = Counter(r["company_name"] for r in rows)
    country_counts = Counter()
    multi = 0
    for r in rows:
        cs = countries_in(r.get("location", ""))
        if len(cs) > 1:
            multi += 1
        for c in cs:
            country_counts[(r["company_name"], c)] += 1

    stats["multi_location_rows"] = multi
    for platform, total in per_platform.items():
        naive = sum(n for (p, _), n in country_counts.items() if p == platform)
        if naive > total:
            fail.append(
                f"{platform}: summing countries gives {naive} but there are only "
                f"{total} postings. {multi} rows name more than one country. "
                f"Assign each posting a single primary country before charting, "
                f"or the country figure will contradict the platform figure."
            )

    # 4. unlocated rows
    unlocated = sum(1 for r in rows if not countries_in(r.get("location", "")))
    if unlocated:
        warn.append(f"{unlocated} rows have a location that matches no known country; "
                    f"extend COUNTRY_PATTERNS or they will be dropped from country charts")

    # 5. coding completeness
    signal_cols = ["africa_facing_signal", "language_signal", "moderation_signal",
                   "integrity_signal", "policy_enforcement_signal",
                   "vendor_signal", "worker_risk_signal"]
    uncoded = sum(1 for r in rows if any(not r.get(c) for c in signal_cols))
    if uncoded:
        warn.append(f"{uncoded} rows have at least one empty signal column; "
                    f"run code_postings.py, then review")

    # 6. the claim the article makes about Africa
    in_africa = [r for r in rows
                 if set(countries_in(r.get("location", ""))) & AFRICAN_COUNTRIES]
    stats["roles_located_in_africa"] = len(in_africa)

    # 7. no leaked text when it should be omitted
    stats["rows"] = len(rows)
    stats["by_platform"] = dict(per_platform)
    return fail, warn, stats


# ----------------------------
# Release
# ----------------------------
def build_public_rows(rows, text_mode):
    out = []
    for i, r in enumerate(sorted(rows, key=lambda x: (x.get("company_name", ""),
                                                      x.get("job_id", ""))), 1):
        cs = countries_in(r.get("location", ""))
        pub = {k: r.get(k, "") for k in PUBLIC_FIELDS if k in r}
        pub.update({
            "record_id": i,
            "primary_country": cs[0] if cs else "",
            "all_countries": "; ".join(cs),
            "location_count": len(cs),
            "job_text_sha256": sha256(r.get("job_text", "")),
        })
        if text_mode == "full":
            pub["job_text"] = r.get("job_text", "")
        elif text_mode == "excerpt":
            pub["job_text_excerpt"] = re.sub(r"\s+", " ", r.get("job_text", ""))[:300]
        out.append(pub)
    return out


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("--text-mode", choices=["omit", "excerpt", "full"], default="omit",
                    help="how much advertisement text to publish (see ETHICS.md)")
    ap.add_argument("--check-only", action="store_true")
    ap.add_argument("--force", action="store_true",
                    help="release even if checks fail; records the override in the manifest")
    args = ap.parse_args()

    src = Path(args.input)
    if not src.exists():
        print(f"No such file: {src}")
        sys.exit(1)

    with src.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    print(f"Read {len(rows)} rows from {src}\n")

    fail, warn, stats = run_checks(rows)

    for w in warn:
        print(f"  WARNING  {w}")
    for e in fail:
        print(f"  FAIL     {e}")
    if not fail and not warn:
        print("  All checks passed.")

    print(f"\n  rows: {stats['rows']}")
    for p, n in sorted(stats["by_platform"].items()):
        print(f"    {p}: {n}")
    print(f"  rows naming more than one country: {stats['multi_location_rows']}")
    print(f"  roles located in Africa: {stats['roles_located_in_africa']}")

    if args.check_only:
        sys.exit(1 if fail else 0)

    if fail and not args.force:
        print("\nRelease blocked. Fix the failures above, or pass --force if you "
              "have a documented reason.")
        sys.exit(1)

    # public posting file
    public_rows = build_public_rows(rows, args.text_mode)
    fields = list(PUBLIC_FIELDS)
    if args.text_mode == "full":
        fields.append("job_text")
    elif args.text_mode == "excerpt":
        fields.append("job_text_excerpt")
    write_csv(PUBLIC_DIR / "postings_public.csv", fields, public_rows)

    # country x platform, one posting counted once
    by_cp = Counter()
    for r in public_rows:
        if r["primary_country"]:
            by_cp[(r["primary_country"], r["company_name"])] += 1
    platforms = sorted({r["company_name"] for r in public_rows})
    country_rows = []
    for country in sorted({c for c, _ in by_cp}):
        row = {"country": country}
        total = 0
        for p in platforms:
            n = by_cp[(country, p)]
            row[p] = n
            total += n
        row["total"] = total
        country_rows.append(row)
    country_rows.sort(key=lambda r: -r["total"])
    write_csv(PUBLIC_DIR / "counts_country_by_platform.csv",
              ["country"] + platforms + ["total"], country_rows)

    # hub x platform
    hub_rows = []
    for p in platforms:
        counts = defaultdict(int)
        for r in public_rows:
            if r["company_name"] != p:
                continue
            hub = HUBS.get((r["primary_country"] or "").lower(), "Other")
            counts[hub] += 1
        hub_rows.append({
            "platform": p,
            "United States": counts["United States"],
            "Singapore": counts["Singapore"],
            "Ireland": counts["Ireland"],
            "Other": counts["Other"],
            "total": sum(counts.values()),
        })
    write_csv(PUBLIC_DIR / "counts_hub_by_platform.csv",
              ["platform", "United States", "Singapore", "Ireland", "Other", "total"],
              hub_rows)

    # manifest
    manifest = {
        "generated": date.today().isoformat(),
        "source_file": str(src.name),
        "text_mode": args.text_mode,
        "checks_passed": not fail,
        "forced": bool(fail and args.force),
        "failures": fail,
        "warnings": warn,
        "statistics": stats,
        "files": {},
    }
    for p in sorted(PUBLIC_DIR.glob("*.csv")):
        manifest["files"][p.name] = {
            "bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
        }
    (PUBLIC_DIR / "release_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\nRelease written to {PUBLIC_DIR}")
    for name in manifest["files"]:
        print(f"    {name}")
    print(f"\ntext-mode = {args.text_mode}. See ETHICS.md before changing it.")


if __name__ == "__main__":
    main()
