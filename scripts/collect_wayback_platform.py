"""
collect_wayback_platform.py

Reconstructs a platform's Trust and Safety job corpus from the Internet Archive,
covering the period the article actually claims rather than today's live pages.

This generalises collect_wayback_meta.py to Google/YouTube and TikTok. The method
is the one the article already describes for Meta: query the CDX Server API for
archived career pages, deduplicate, fetch each snapshot, extract the posting.

Why archived pages work where live scraping struggles
-----------------------------------------------------
Google's and TikTok's live career sites render in JavaScript, so a plain HTTP
request returns an empty shell. Archived captures are often better behaved:
career sites emit schema.org JobPosting JSON-LD for search indexing, and that
markup is in the saved HTML even when the visible listing is not. Where JSON-LD
is missing this script falls back to Open Graph tags, then to the DOM.

What it cannot do
-----------------
Guarantee coverage. The Archive crawls these sites less densely than
metacareers.com, so expect to recover a fraction of any original count. Run
`--discover-only` first and look at the year distribution before committing.

Usage
-----
    python collect_wayback_platform.py google --discover-only
    python collect_wayback_platform.py google --from 2023 --to 2026
    python collect_wayback_platform.py tiktok --discover-only
    python collect_wayback_platform.py tiktok --from 2023 --to 2026 --limit 800

Writes
------
    source_registry/<platform>_wayback_snapshots.csv
    data_raw/<platform>_wayback/<timestamp>_<jobid>.html
    data_processed/<platform>_wayback_postings.csv   (21-column posting schema)
"""

from pathlib import Path
from collections import Counter
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

CDX = "http://web.archive.org/cdx/search/cdx"
SNAPSHOT = "https://web.archive.org/web/{ts}id_/{url}"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (compatible; academic-research-scraper/1.0; "
                   "trust-and-safety job posting study; contact endalk2006@gmail.com)")
}
TIMEOUT = 45
FETCH_DELAY = 1.5
MAX_RETRIES = 3
BACKOFF = 8

PLATFORMS = {
    "google": {
        "label": "Google/YouTube",
        # Google has moved its careers site three times; all three are archived.
        "patterns": [
            "careers.google.com/jobs/results/*",
            "careers.google.com/jobs/*",
            "www.google.com/about/careers/applications/jobs/results/*",
            "google.com/about/careers/jobs/results/*",
        ],
        "id_regex": re.compile(r"/jobs/results/(\d+)"),
    },
    "tiktok": {
        "label": "TikTok",
        "patterns": [
            "lifeattiktok.com/search/*",
            "lifeattiktok.com/position/*",
            "careers.tiktok.com/position/*",
            "careers.tiktok.com/*",
            "jobs.bytedance.com/en/position/*",
        ],
        "id_regex": re.compile(r"/(?:position|results)/(\d{6,})"),
    },
    "meta": {
        "label": "Meta",
        "patterns": [
            "metacareers.com/profile/job_details/*",
            "metacareers.com/jobs/*",
            "www.facebook.com/careers/jobs/*",
        ],
        "id_regex": re.compile(r"/job_details/(\d+)|/jobs/(\d{6,})"),
    },
}

TS_TERMS = [
    "trust and safety", "trust & safety", "content moderation", "content review",
    "community standards", "community guidelines", "policy enforcement",
    "integrity", "misinformation", "inauthentic", "harmful content",
    "objectionable content", "abuse", "escalation", "online safety",
    "threat intelligence", "crisis response",
]


def clean(t):
    return re.sub(r"\s+", " ", t or "").strip()


# ------------------------------------------------------------------ CDX
def cdx_query(pattern, date_from, date_to, limit=None):
    params = {
        "url": pattern[:-1] if pattern.endswith("*") else pattern,
        "matchType": "prefix" if pattern.endswith("*") else "exact",
        "output": "json",
        "fl": "timestamp,original,statuscode,digest,mimetype",
        "collapse": "digest",
        "filter": ["statuscode:200", "mimetype:text/html"],
        "from": str(date_from),
        "to": str(date_to),
    }
    if limit:
        params["limit"] = str(limit)

    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(CDX, params=params, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                wait = BACKOFF * (2 ** attempt)
                print(f"    rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            txt = r.text.strip()
            if not txt:
                return []
            data = json.loads(txt)
            if not data:
                return []
            head, rows = data[0], data[1:]
            return [dict(zip(head, row)) for row in rows]
        except json.JSONDecodeError:
            return []
        except Exception as e:
            wait = BACKOFF * (2 ** attempt)
            print(f"    CDX error ({e}); retry in {wait}s")
            time.sleep(wait)
    return []


def job_id(url, rx):
    m = rx.search(url)
    if not m:
        return ""
    return next((g for g in m.groups() if g), "")


# ----------------------------------------------------------- extraction
def _walk_jsonld(node, out):
    if isinstance(node, dict):
        types = node.get("@type")
        types = types if isinstance(types, list) else [types]
        if any(isinstance(t, str) and t.lower() == "jobposting" for t in types):
            out.append(node)
        for v in node.values():
            _walk_jsonld(v, out)
    elif isinstance(node, list):
        for v in node:
            _walk_jsonld(v, out)


def jsonld_postings(soup):
    out = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (tag.string or tag.get_text() or "").strip()
        if not raw:
            continue
        try:
            _walk_jsonld(json.loads(raw), out)
        except json.JSONDecodeError:
            continue
    return out


def jsonld_location(p):
    locs = p.get("jobLocation")
    locs = locs if isinstance(locs, list) else [locs]
    names = []
    for loc in locs:
        if isinstance(loc, dict):
            addr = loc.get("address")
            if isinstance(addr, dict):
                country = addr.get("addressCountry")
                if isinstance(country, dict):
                    country = country.get("name", "")
                parts = [addr.get("addressLocality", ""),
                         addr.get("addressRegion", ""), country or ""]
                names.append(", ".join(x for x in parts if x))
            elif isinstance(addr, str):
                names.append(addr)
            elif loc.get("name"):
                names.append(loc["name"])
        elif isinstance(loc, str):
            names.append(loc)
    return "; ".join(n for n in names if n)


def extract(html):
    """JSON-LD, then Open Graph, then DOM. Returns a dict plus the method used."""
    soup = BeautifulSoup(html, "html.parser")

    posts = jsonld_postings(soup)
    if posts:
        p = posts[0]
        desc = BeautifulSoup(p.get("description", "") or "", "html.parser").get_text(" ")
        return {
            "job_title": clean(str(p.get("title", ""))),
            "location": clean(jsonld_location(p)),
            "date_posted": str(p.get("datePosted", "") or ""),
            "job_text": clean(desc),
            "method": "jsonld",
        }

    def meta_prop(*names):
        for n in names:
            tag = soup.find("meta", attrs={"property": n}) or \
                  soup.find("meta", attrs={"name": n})
            if tag and tag.get("content"):
                return clean(tag["content"])
        return ""

    og_title = meta_prop("og:title", "twitter:title", "title")
    og_desc = meta_prop("og:description", "twitter:description", "description")
    if og_title or og_desc:
        # Google page titles look like "Trust & Safety Analyst — Dublin, Ireland"
        loc = ""
        m = re.search(r"[—–-]\s*([A-Z][^—–|]{2,60})$", og_title)
        if m:
            loc = clean(m.group(1))
        return {"job_title": og_title, "location": loc, "date_posted": "",
                "job_text": og_desc, "method": "opengraph"}

    for t in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        t.extract()
    h = soup.find(["h1", "h2"])
    title = clean(h.get_text(" ")) if h else clean(soup.title.get_text() if soup.title else "")
    return {"job_title": title, "location": "", "date_posted": "",
            "job_text": clean(soup.get_text(" ")), "method": "dom"}


def fetch(ts, url):
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(SNAPSHOT.format(ts=ts, url=url), headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                time.sleep(BACKOFF * (2 ** attempt))
                continue
            r.raise_for_status()
            return r.text, ""
        except Exception as e:
            if attempt == MAX_RETRIES - 1:
                return "", str(e)
            time.sleep(BACKOFF * (2 ** attempt))
    return "", "retries exhausted"


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
    ap.add_argument("platform", choices=sorted(PLATFORMS))
    ap.add_argument("--from", dest="date_from", default="2023")
    ap.add_argument("--to", dest="date_to", default="2026")
    ap.add_argument("--limit", type=int, default=None, help="cap snapshots per pattern")
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--ts-only", action="store_true",
                    help="keep only postings whose text carries a T&S term")
    args = ap.parse_args()

    cfg = PLATFORMS[args.platform]
    rx = cfg["id_regex"]
    reg = PROJECT_ROOT / "source_registry" / f"{args.platform}_wayback_snapshots.csv"
    raw_dir = PROJECT_ROOT / "data_raw" / f"{args.platform}_wayback"
    out = PROJECT_ROOT / "data_processed" / f"{args.platform}_wayback_postings.csv"

    print(f"{cfg['label']}   window {args.date_from}-{args.date_to}")

    snaps, seen = [], set()
    for pat in cfg["patterns"]:
        print(f"\nCDX: {pat}")
        rows = cdx_query(pat, args.date_from, args.date_to, args.limit)
        print(f"  {len(rows)} captures")
        for r in rows:
            jid = job_id(r.get("original", ""), rx)
            key = jid or r.get("original", "")
            if key in seen:
                continue
            seen.add(key)
            r["job_id"] = jid
            snaps.append(r)
        time.sleep(2)

    snaps.sort(key=lambda s: s["timestamp"])
    reg.parent.mkdir(parents=True, exist_ok=True)
    with reg.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["timestamp", "original", "statuscode",
                                          "digest", "mimetype", "job_id"])
        w.writeheader()
        for s in snaps:
            w.writerow({k: s.get(k, "") for k in w.fieldnames})

    print(f"\n{len(snaps)} distinct pages")
    print("captures by year:")
    for y, n in sorted(Counter(s["timestamp"][:4] for s in snaps).items()):
        print(f"   {y}: {n}")
    with_id = sum(1 for s in snaps if s["job_id"])
    print(f"pages that look like individual job postings: {with_id}")
    print(f"registry: {reg}")

    if args.discover_only:
        print("\n--discover-only set. Look at the year spread before running the fetch.")
        return

    raw_dir.mkdir(parents=True, exist_ok=True)
    rows_out, kept = [], 0
    for i, s in enumerate(snaps, 1):
        ts, url, jid = s["timestamp"], s["original"], s["job_id"]
        print(f"[{i}/{len(snaps)}] {ts} {url[:82]}")
        html, err = fetch(ts, url)
        if err:
            print(f"    ERROR {err}")
            continue
        (raw_dir / f"{ts}_{jid or 'nojobid'}.html").write_text(html, encoding="utf-8")
        f = extract(html)

        hay = f"{f['job_title']} {f['job_text']}".lower()
        hits = [t for t in TS_TERMS if t in hay]
        if args.ts_only and not hits:
            time.sleep(FETCH_DELAY)
            continue

        kept += 1
        rows_out.append({
            "record_id": kept, "company_name": cfg["label"], "job_id": jid,
            "source_url": url, "capture_mode": "wayback_snapshot",
            "date_accessed": f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}",
            "job_title": f["job_title"], "location": f["location"],
            "team_function": "", "job_text": f["job_text"],
            "africa_facing_signal": "", "africa_facing_text": "",
            "languages_named": "", "language_signal": "",
            "moderation_signal": "", "integrity_signal": "",
            "policy_enforcement_signal": "", "vendor_signal": "",
            "worker_risk_signal": "", "offshore_relative_to_market": "",
            "notes": f"snapshot {ts}; extraction={f['method']}; "
                     f"datePosted={f['date_posted']}; ts_terms={'; '.join(hits)}",
        })
        time.sleep(FETCH_DELAY)

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=POSTING_FIELDS)
        w.writeheader()
        w.writerows(rows_out)

    print(f"\n{len(rows_out)} postings written to {out}")
    meths = Counter(r["notes"].split("extraction=")[1].split(";")[0] for r in rows_out)
    print("extraction method:", dict(meths))
    print("Signal columns are blank by design; run code_postings.py next.")


if __name__ == "__main__":
    main()
