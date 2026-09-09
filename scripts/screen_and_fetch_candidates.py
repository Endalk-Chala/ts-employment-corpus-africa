"""
screen_and_fetch_candidates.py

Screens a Wayback snapshot registry down to Trust and Safety candidates, then
fetches only those pages.

Why this exists
---------------
Discovery on Google returned 15,092 individual job postings, which is the whole
careers site. Fetching all of them would take hours and most are irrelevant.
But the job title is already in the URL slug:

    .../jobs/results/100350864866058950-policy-escalation-specialist-trust-and-safety-youtube

So screening can happen on the registry, before any page is downloaded. Only
candidates get fetched, which is both faster and lighter on the Archive.

Run --report first. It downloads nothing and prints how many candidates the
screen produces, with a sample, so the rule can be inspected before it is used.

Usage
-----
    python scripts/screen_and_fetch_candidates.py google --report
    python scripts/screen_and_fetch_candidates.py google --fetch
    python scripts/screen_and_fetch_candidates.py google --fetch --strict

Reads   source_registry/<platform>_wayback_snapshots.csv
Writes  data_processed/<platform>_ts_candidates.csv    (screening decisions)
        data_raw/<platform>_wayback/<ts>_<jobid>.html
        data_processed/<platform>_wayback_postings.csv (21-column schema)
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
csv.field_size_limit(10_000_000)

SNAPSHOT = "https://web.archive.org/web/{ts}id_/{url}"
HEADERS = {"User-Agent": ("Mozilla/5.0 (compatible; academic-research-scraper/1.0; "
                          "trust-and-safety job posting study; contact endalk2006@gmail.com)")}
TIMEOUT, DELAY, RETRIES, BACKOFF = 45, 1.2, 3, 8

LABEL = {"google": "Google/YouTube", "tiktok": "TikTok", "meta": "Meta"}

# Slug terms that mark a candidate. Deliberately broad: screening out happens
# afterwards, as a documented step, exactly as in the Meta arm.
INCLUDE = [
    "trust-and-safety", "trust-safety", "trust_and_safety",
    "content-moderation", "content-moderator", "content-specialist",
    "content-review", "policy-enforcement", "policy-escalation",
    "policy-specialist", "policy-lead", "policy-development",
    "scaled-abuse", "abuse-analyst", "abuse-manager", "abuse-specialist",
    "market-responsibility", "election-integrity", "misinformation",
    "child-safety", "egregious-harms", "adversarial-red-team",
    "crisis-response", "rapid-response", "enforcement-detection",
    "investigations-analyst", "threat-intelligence", "community-moderation",
    "responsible-ai", "safe-browsing", "legal-removals", "copyright-operations",
]

# Slug terms that mark an obvious non-governance use of the same vocabulary.
# These are excluded only when no INCLUDE term is also present.
EXCLUDE = [
    "environmental-health", "health-and-safety", "health-safety",
    "fire-life-safety", "data-center", "construction",
    "device-integrity", "signal-integrity", "power-integrity",
    "hardware-integrity", "structural", "mechanical", "electrical",
    "safety-alignment", "agi-safety", "frontier-safety",
]

# Under --strict, only the unambiguous core terms qualify.
STRICT = ["trust-and-safety", "trust-safety", "content-moderation",
          "content-moderator", "policy-enforcement", "scaled-abuse"]


def slug_parts(url):
    """Return (job_id, title) parsed from the URL slug."""
    path = url.split("?")[0].rstrip("/")
    m = re.search(r"/(?:results|position)/(\d+)-([a-z0-9\-,%\.]+)$", path, re.I)
    if m:
        jid, slug = m.group(1), m.group(2)
    else:
        m2 = re.search(r"/(?:results|position)/(\d+)", path)
        if not m2:
            return "", ""
        jid, slug = m2.group(1), ""
    title = re.sub(r"[-_]+", " ", slug).strip()
    title = re.sub(r"\s+", " ", title)
    return jid, title.title()


def screen(slug_lower, strict=False):
    terms = STRICT if strict else INCLUDE
    inc = [t for t in terms if t in slug_lower]
    exc = [t for t in EXCLUDE if t in slug_lower]
    if inc:
        return True, inc, exc
    return False, inc, exc


def load_registry(platform):
    p = PROJECT_ROOT / "source_registry" / f"{platform}_wayback_snapshots.csv"
    if not p.exists():
        print(f"Missing {p}. Run collect_wayback_platform.py --discover-only first.")
        sys.exit(1)
    with p.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def build(platform, strict):
    rows = load_registry(platform)
    best = {}
    for r in rows:
        url = r.get("original", "")
        jid, title = slug_parts(url)
        if not jid:
            continue
        ts = r.get("timestamp", "")
        # keep the earliest capture, and prefer a URL that carries a title slug
        cur = best.get(jid)
        if cur is None or (title and not cur["title"]) or \
           (bool(title) == bool(cur["title"]) and ts < cur["timestamp"]):
            best[jid] = {"job_id": jid, "title": title, "timestamp": ts,
                         "original": url}
    out = []
    for rec in best.values():
        slug = rec["original"].lower()
        keep, inc, exc = screen(slug, strict)
        rec["is_candidate"] = "yes" if keep else "no"
        rec["matched_terms"] = "; ".join(inc)
        rec["exclusion_terms"] = "; ".join(exc)
        out.append(rec)
    return out


# ------------------------------------------------------------ extraction
def _walk(node, acc):
    if isinstance(node, dict):
        t = node.get("@type")
        t = t if isinstance(t, list) else [t]
        if any(isinstance(x, str) and x.lower() == "jobposting" for x in t):
            acc.append(node)
        for v in node.values():
            _walk(v, acc)
    elif isinstance(node, list):
        for v in node:
            _walk(v, acc)


def jsonld_loc(p):
    locs = p.get("jobLocation")
    locs = locs if isinstance(locs, list) else [locs]
    names = []
    for loc in locs:
        if isinstance(loc, dict):
            a = loc.get("address")
            if isinstance(a, dict):
                c = a.get("addressCountry")
                if isinstance(c, dict):
                    c = c.get("name", "")
                parts = [a.get("addressLocality", ""), a.get("addressRegion", ""), c or ""]
                names.append(", ".join(x for x in parts if x))
            elif isinstance(a, str):
                names.append(a)
        elif isinstance(loc, str):
            names.append(loc)
    return "; ".join(n for n in names if n)


def extract(html):
    soup = BeautifulSoup(html, "html.parser")
    acc = []
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (tag.string or tag.get_text() or "").strip()
        if raw:
            try:
                _walk(json.loads(raw), acc)
            except json.JSONDecodeError:
                pass
    if acc:
        p = acc[0]
        desc = BeautifulSoup(p.get("description", "") or "", "html.parser").get_text(" ")
        return {"title": re.sub(r"\s+", " ", str(p.get("title", ""))).strip(),
                "location": jsonld_loc(p), "date_posted": str(p.get("datePosted", "") or ""),
                "text": re.sub(r"\s+", " ", desc).strip(), "method": "jsonld"}

    def mp(*names):
        for n in names:
            t = soup.find("meta", attrs={"property": n}) or soup.find("meta", attrs={"name": n})
            if t and t.get("content"):
                return re.sub(r"\s+", " ", t["content"]).strip()
        return ""

    ot, od = mp("og:title", "twitter:title"), mp("og:description", "description")
    if ot or od:
        loc = ""
        m = re.search(r"[—–-]\s*([A-Z][^—–|]{2,60})$", ot)
        if m:
            loc = m.group(1).strip()
        return {"title": ot, "location": loc, "date_posted": "", "text": od,
                "method": "opengraph"}

    for t in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        t.extract()
    h = soup.find(["h1", "h2"])
    body = re.sub(r"\s+", " ", soup.get_text(" ")).strip()
    # Google archived pages often carry "Location" adjacent to the office name
    loc = ""
    lm = re.search(r"(?:Location|Office)s?[:\s]+([A-Z][A-Za-z .'-]+,\s*[A-Z][A-Za-z .'-]+)", body)
    if lm:
        loc = lm.group(1).strip()
    return {"title": h.get_text(" ").strip() if h else "", "location": loc,
            "date_posted": "", "text": body, "method": "dom"}


def fetch(ts, url):
    for a in range(RETRIES):
        try:
            r = requests.get(SNAPSHOT.format(ts=ts, url=url), headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                time.sleep(BACKOFF * (2 ** a))
                continue
            r.raise_for_status()
            return r.text, ""
        except Exception as e:
            if a == RETRIES - 1:
                return "", str(e)
            time.sleep(BACKOFF * (2 ** a))
    return "", "retries exhausted"


FIELDS = ["record_id", "company_name", "job_id", "source_url", "capture_mode",
          "date_accessed", "job_title", "location", "team_function", "job_text",
          "africa_facing_signal", "africa_facing_text", "languages_named",
          "language_signal", "moderation_signal", "integrity_signal",
          "policy_enforcement_signal", "vendor_signal", "worker_risk_signal",
          "offshore_relative_to_market", "notes"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("platform", choices=sorted(LABEL))
    ap.add_argument("--report", action="store_true", help="screen only, download nothing")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--strict", action="store_true", help="core terms only")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    recs = build(args.platform, args.strict)
    cands = [r for r in recs if r["is_candidate"] == "yes"]

    cand_path = PROJECT_ROOT / "data_processed" / f"{args.platform}_ts_candidates.csv"
    cand_path.parent.mkdir(parents=True, exist_ok=True)
    with cand_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["job_id", "title", "timestamp", "original",
                                          "is_candidate", "matched_terms", "exclusion_terms"])
        w.writeheader()
        w.writerows(recs)

    print(f"distinct job ids in registry : {len(recs)}")
    print(f"screened in as candidates    : {len(cands)}"
          f"{'   (--strict)' if args.strict else ''}")
    print(f"screening decisions written  : {cand_path}")

    yrs = Counter(r["timestamp"][:4] for r in cands)
    print("\ncandidates by earliest capture year:")
    for y in sorted(yrs):
        print(f"   {y}: {yrs[y]}")

    print("\nmost common matched terms:")
    tc = Counter(t for r in cands for t in r["matched_terms"].split("; ") if t)
    for t, n in tc.most_common(12):
        print(f"   {n:5d}  {t}")

    flagged = [r for r in cands if r["exclusion_terms"]]
    if flagged:
        print(f"\ncandidates ALSO carrying an exclusion term ({len(flagged)}), "
              f"review these by hand:")
        for r in flagged[:12]:
            print(f"   {r['title'][:70]}  [{r['exclusion_terms']}]")

    print("\nsample of 15 candidates:")
    for r in cands[:15]:
        print(f"   {r['job_id']}  {r['title'][:72]}")

    if args.report or not args.fetch:
        mins = len(cands) * (DELAY + 0.8) / 60
        print(f"\nReport only. Fetching these would take roughly {mins:.0f} minutes.")
        print("Run with --fetch when the screen looks right.")
        return

    raw = PROJECT_ROOT / "data_raw" / f"{args.platform}_wayback"
    raw.mkdir(parents=True, exist_ok=True)
    out = PROJECT_ROOT / "data_processed" / f"{args.platform}_wayback_postings.csv"

    todo = cands[:args.limit] if args.limit else cands
    rows, n = [], 0
    for i, c in enumerate(todo, 1):
        print(f"[{i}/{len(todo)}] {c['timestamp']} {c['title'][:60]}")
        html, err = fetch(c["timestamp"], c["original"])
        if err:
            print(f"    ERROR {err}")
            continue
        (raw / f"{c['timestamp']}_{c['job_id']}.html").write_text(html, encoding="utf-8")
        f = extract(html)
        n += 1
        rows.append({
            "record_id": n, "company_name": LABEL[args.platform], "job_id": c["job_id"],
            "source_url": c["original"], "capture_mode": "wayback_snapshot",
            "date_accessed": f"{c['timestamp'][0:4]}-{c['timestamp'][4:6]}-{c['timestamp'][6:8]}",
            "job_title": f["title"] or c["title"], "location": f["location"],
            "team_function": "", "job_text": f["text"],
            "africa_facing_signal": "", "africa_facing_text": "", "languages_named": "",
            "language_signal": "", "moderation_signal": "", "integrity_signal": "",
            "policy_enforcement_signal": "", "vendor_signal": "", "worker_risk_signal": "",
            "offshore_relative_to_market": "",
            "notes": f"snapshot {c['timestamp']}; extraction={f['method']}; "
                     f"slug_title={c['title']}; matched={c['matched_terms']}; "
                     f"datePosted={f['date_posted']}",
        })
        time.sleep(DELAY)

    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} postings written to {out}")
    print("extraction methods:",
          dict(Counter(r["notes"].split("extraction=")[1].split(";")[0] for r in rows)))
    print(f"with a location: {sum(1 for r in rows if r['location'])}")
    print("Run code_postings.py next to fill the signal columns.")


if __name__ == "__main__":
    main()
