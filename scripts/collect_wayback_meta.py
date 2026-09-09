"""
collect_wayback_meta.py

Retrieves archived Meta job advertisements from the Internet Archive using the
CDX Server API, then fetches each snapshot and extracts posting-level fields.

This is the "reborn-digital" arm of the employment corpus: job pages that have
since been taken down off the live web but survive as timestamped snapshots.

Usage
-----
    python collect_wayback_meta.py
    python collect_wayback_meta.py --from 2023 --to 2026 --limit 500
    python collect_wayback_meta.py --discover-only     # just list snapshots, fetch nothing

Writes
------
    source_registry/meta_wayback_snapshots.csv   one row per snapshot found
    data_raw/meta_wayback/<timestamp>_<jobid>.html
    data_processed/meta_wayback_postings.csv     posting-level rows

Notes on the API
----------------
The CDX endpoint is http://web.archive.org/cdx/search/cdx and takes:
    url=<pattern>        with matchType=prefix for wildcard behaviour
    output=json
    fl=timestamp,original,statuscode,digest,mimetype
    collapse=digest      drops consecutive identical captures
    from=YYYY / to=YYYY  bounds the window
Snapshots are then fetched from
    https://web.archive.org/web/<timestamp>id_/<original>
The "id_" suffix asks for the original bytes without the Archive's toolbar,
which matters because the toolbar injects markup that breaks extraction.

Be patient with it. The Archive rate-limits, and this script backs off rather
than hammering. A few hundred snapshots takes a while; that is expected.
"""

from pathlib import Path
from urllib.parse import urlparse
import argparse
import csv
import json
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

CDX_ENDPOINT = "http://web.archive.org/cdx/search/cdx"
SNAPSHOT_TEMPLATE = "https://web.archive.org/web/{timestamp}id_/{original}"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; academic-research-scraper/1.0; "
        "trust-and-safety job posting study; contact endalk2006@gmail.com)"
    )
}

# URL patterns that have hosted Meta job advertisements over the period.
URL_PATTERNS = [
    "metacareers.com/profile/job_details/*",
    "metacareers.com/jobs/*",
    "www.facebook.com/careers/jobs/*",
    "www.facebook.com/careers/v2/jobs/*",
]

TIMEOUT = 45
FETCH_DELAY = 1.5          # seconds between snapshot fetches
MAX_RETRIES = 3
BACKOFF = 8                # seconds, doubled per retry


# ----------------------------
# CDX discovery
# ----------------------------
def cdx_query(pattern, date_from, date_to, limit=None):
    """Return a list of dicts describing archived captures for one URL pattern."""
    params = {
        "url": pattern,
        "matchType": "prefix" if pattern.endswith("*") else "exact",
        "output": "json",
        "fl": "timestamp,original,statuscode,digest,mimetype",
        "collapse": "digest",
        "filter": "statuscode:200",
        "from": str(date_from),
        "to": str(date_to),
    }
    if pattern.endswith("*"):
        params["url"] = pattern[:-1]
    if limit:
        params["limit"] = str(limit)

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(CDX_ENDPOINT, params=params, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                wait = BACKOFF * (2 ** attempt)
                print(f"    rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            text = r.text.strip()
            if not text:
                return []
            data = json.loads(text)
            if not data:
                return []
            header, rows = data[0], data[1:]
            return [dict(zip(header, row)) for row in rows]
        except json.JSONDecodeError:
            print("    CDX returned non-JSON; treating as empty")
            return []
        except Exception as e:
            wait = BACKOFF * (2 ** attempt)
            print(f"    CDX error ({e}); retry in {wait}s")
            time.sleep(wait)
    return []


def job_id_from_url(url):
    """Pull the platform job identifier out of a Meta careers URL."""
    m = re.search(r"/job_details/(\d+)", url)
    if m:
        return m.group(1)
    m = re.search(r"/(?:jobs|careers)/(?:v2/)?(?:jobs/)?(\d{6,})", url)
    if m:
        return m.group(1)
    return ""


# ----------------------------
# Snapshot extraction
# ----------------------------
def clean_text(t):
    return re.sub(r"\s+", " ", t or "").strip()


def extract_jsonld_jobposting(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []

    def walk(node):
        if isinstance(node, dict):
            types = node.get("@type")
            types = types if isinstance(types, list) else [types]
            if any(isinstance(t, str) and t.lower() == "jobposting" for t in types):
                out.append(node)
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw:
            continue
        try:
            walk(json.loads(raw))
        except json.JSONDecodeError:
            continue
    return out


def location_from_jsonld(posting):
    locs = posting.get("jobLocation")
    locs = locs if isinstance(locs, list) else [locs]
    names = []
    for loc in locs:
        if not isinstance(loc, dict):
            if isinstance(loc, str):
                names.append(loc)
            continue
        addr = loc.get("address")
        if isinstance(addr, dict):
            country = addr.get("addressCountry")
            if isinstance(country, dict):
                country = country.get("name", "")
            parts = [addr.get("addressLocality", ""), addr.get("addressRegion", ""), country or ""]
            names.append(", ".join(p for p in parts if p))
        elif isinstance(addr, str):
            names.append(addr)
    return "; ".join(n for n in names if n)


def extract_posting(html, url):
    """Best-effort extraction: JSON-LD first, then visible DOM."""
    postings = extract_jsonld_jobposting(html)
    if postings:
        p = postings[0]
        desc = BeautifulSoup(p.get("description", "") or "", "html.parser").get_text(" ")
        return {
            "job_title": clean_text(str(p.get("title", ""))),
            "location": clean_text(location_from_jsonld(p)),
            "date_posted": str(p.get("datePosted", "") or ""),
            "job_text": clean_text(desc),
            "extraction": "jsonld",
        }

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    h1 = soup.find(["h1", "h2"])
    title = clean_text(h1.get_text(" ")) if h1 else clean_text(soup.title.get_text() if soup.title else "")
    body = clean_text(soup.get_text(" "))
    return {
        "job_title": title,
        "location": "",
        "date_posted": "",
        "job_text": body,
        "extraction": "dom",
    }


def fetch_snapshot(timestamp, original):
    url = SNAPSHOT_TEMPLATE.format(timestamp=timestamp, original=original)
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                wait = BACKOFF * (2 ** attempt)
                print(f"    rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.text, ""
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return "", str(e)
            time.sleep(BACKOFF * (2 ** attempt))
    return "", "exhausted retries"


# ----------------------------
# Output schema (matches posting_level_corpus_filled.csv)
# ----------------------------
POSTING_FIELDS = [
    "record_id", "company_name", "job_id", "source_url", "capture_mode",
    "date_accessed", "job_title", "location", "team_function", "job_text",
    "africa_facing_signal", "africa_facing_text", "languages_named",
    "language_signal", "moderation_signal", "integrity_signal",
    "policy_enforcement_signal", "vendor_signal", "worker_risk_signal",
    "offshore_relative_to_market", "notes",
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="date_from", default="2023")
    ap.add_argument("--to", dest="date_to", default="2026")
    ap.add_argument("--limit", type=int, default=None,
                    help="cap snapshots per URL pattern")
    ap.add_argument("--discover-only", action="store_true",
                    help="write the snapshot registry and stop")
    args = ap.parse_args()

    registry_path = PROJECT_ROOT / "source_registry" / "meta_wayback_snapshots.csv"
    raw_dir = PROJECT_ROOT / "data_raw" / "meta_wayback"
    output_path = PROJECT_ROOT / "data_processed" / "meta_wayback_postings.csv"

    print(f"Window: {args.date_from} to {args.date_to}")

    # ---- discovery ----
    all_snaps = []
    seen_keys = set()
    for pattern in URL_PATTERNS:
        print(f"\nCDX query: {pattern}")
        rows = cdx_query(pattern, args.date_from, args.date_to, args.limit)
        print(f"  {len(rows)} captures")
        for row in rows:
            original = row.get("original", "")
            jid = job_id_from_url(original)
            key = (jid or original, row.get("timestamp", "")[:6])
            if key in seen_keys:
                continue
            seen_keys.add(key)
            row["job_id"] = jid
            row["pattern"] = pattern
            all_snaps.append(row)
        time.sleep(2)

    # deduplicate by job id, keeping the earliest capture of each posting
    by_job = {}
    for s in all_snaps:
        jid = s["job_id"] or s["original"]
        if jid not in by_job or s["timestamp"] < by_job[jid]["timestamp"]:
            by_job[jid] = s
    unique = sorted(by_job.values(), key=lambda s: s["timestamp"])

    registry_path.parent.mkdir(parents=True, exist_ok=True)
    with registry_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "original", "statuscode",
                                          "digest", "mimetype", "job_id", "pattern"])
        w.writeheader()
        for s in unique:
            w.writerow({k: s.get(k, "") for k in w.fieldnames})

    print(f"\n{len(all_snaps)} captures, {len(unique)} distinct postings")
    print("Snapshot registry:", registry_path)

    if args.discover_only:
        print("\n--discover-only set; stopping before fetch.")
        return

    # ---- fetch and extract ----
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows_out = []

    for i, snap in enumerate(unique, 1):
        ts, original, jid = snap["timestamp"], snap["original"], snap["job_id"]
        print(f"[{i}/{len(unique)}] {ts} {original[:80]}")

        html, err = fetch_snapshot(ts, original)
        if err:
            print(f"    ERROR {err}")
            continue

        fname = f"{ts}_{jid or 'nojobid'}.html"
        (raw_dir / fname).write_text(html, encoding="utf-8")

        fields = extract_posting(html, original)
        rows_out.append({
            "record_id": i,
            "company_name": "Meta",
            "job_id": jid,
            "source_url": original,
            "capture_mode": "wayback_snapshot",
            "date_accessed": f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}",
            "job_title": fields["job_title"],
            "location": fields["location"],
            "team_function": "",
            "job_text": fields["job_text"],
            "africa_facing_signal": "", "africa_facing_text": "",
            "languages_named": "", "language_signal": "",
            "moderation_signal": "", "integrity_signal": "",
            "policy_enforcement_signal": "", "vendor_signal": "",
            "worker_risk_signal": "", "offshore_relative_to_market": "",
            "notes": f"snapshot {ts}; extraction={fields['extraction']}; "
                     f"datePosted={fields['date_posted']}",
        })
        time.sleep(FETCH_DELAY)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=POSTING_FIELDS)
        w.writeheader()
        w.writerows(rows_out)

    print(f"\nDone. {len(rows_out)} postings written to {output_path}")
    print("Signal columns are blank by design; run code_postings.py to fill them.")


if __name__ == "__main__":
    main()
