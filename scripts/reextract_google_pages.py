"""
reextract_google_pages.py

Re-parses the archived Google career pages already saved in data_raw/, without
touching the Internet Archive again.

Why a second pass was needed
----------------------------
The first extraction found a location for only 36 of 292 postings. Inspecting
the saved HTML showed why: these pages carry no schema.org JSON-LD at all, and
the Open Graph tags hold the title and description but no location.

The location is present, though, in the job-detail block. Google renders it with
material-icon names acting as labels:

    corporate_fare YouTube   place San Bruno, CA, USA   bar_chart Early

So the focal block is located by its detail heading (`h2.p1N2lc`), the text is
flattened, and the icon words delimit the fields. This is more reliable than
scraping city names out of the page, because the same page also contains a
"similar jobs" rail full of other roles' locations. Reading those would attach
the wrong city to the posting, which is precisely the class of error that put
"Dublin, United Kingdom" into the earlier Meta summaries.

Two capture populations
-----------------------
Snapshots from 2023 are roughly 10 KB: JavaScript shells with only generic
Open Graph tags. Nothing but the title is recoverable, and often not even that.
Snapshots from 2025 onward are roughly 1.2 MB and fully rendered. The script
reports the split rather than hiding it, because it bears on what the
reconstructed corpus can support.

Usage
-----
    python scripts/reextract_google_pages.py
    python scripts/reextract_google_pages.py --platform tiktok
"""

from pathlib import Path
from collections import Counter
import argparse
import csv
import html as htmllib
import re

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
csv.field_size_limit(10_000_000)

LABEL = {"google": "Google/YouTube", "tiktok": "TikTok", "meta": "Meta"}

FIELDS = ["record_id", "company_name", "job_id", "source_url", "capture_mode",
          "date_accessed", "job_title", "location", "team_function", "job_text",
          "africa_facing_signal", "africa_facing_text", "languages_named",
          "language_signal", "moderation_signal", "integrity_signal",
          "policy_enforcement_signal", "vendor_signal", "worker_risk_signal",
          "offshore_relative_to_market", "notes"]


def strip_tags(s):
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    return re.sub(r"\s+", " ", htmllib.unescape(s)).strip()


def meta_content(h, *names):
    for n in names:
        m = re.search(r'<meta[^>]+(?:property|name)="%s"[^>]+content="([^"]*)"' % re.escape(n), h)
        if not m:
            m = re.search(r'<meta[^>]+content="([^"]*)"[^>]+(?:property|name)="%s"' % re.escape(n), h)
        if m:
            return htmllib.unescape(m.group(1)).strip()
    return ""


ICON_WORDS = ["corporate_fare", "place", "bar_chart", "Apply", "share"]


def parse_detail_block(h):
    """Return (title, company, location, level) from the focal job-detail block."""
    m = re.search(r'<h2 class="p1N2lc">(.*?)</h2>', h, flags=re.S)
    if not m:
        return "", "", "", ""
    title = strip_tags(m.group(1))
    window = h[m.start(): m.start() + 9000]
    text = strip_tags(window)

    def between(a, b):
        ia = text.find(a)
        if ia < 0:
            return ""
        ia += len(a)
        ib = len(text)
        for stop in b:
            j = text.find(stop, ia)
            if j >= 0:
                ib = min(ib, j)
        return text[ia:ib].strip(" ;,")

    company = between("corporate_fare", ["place", "bar_chart", "Apply"])
    location = between("place", ["bar_chart", "Apply", "share"])
    level = between("bar_chart", ["Apply", "share", "Experience"])

    # multi-location roles list several, sometimes with a "+N more" marker
    spans = re.findall(r'<span[^>]*class="r0wTof[^"]*"[^>]*>([^<]{2,80})</span>', window)
    if spans:
        seen, ordered = set(), []
        for s in spans:
            s = htmllib.unescape(s).strip(" ;")
            if s and s not in seen:
                seen.add(s)
                ordered.append(s)
        location = "; ".join(ordered)

    more = re.search(r'<span[^>]*class="BVHzed"[^>]*>([^<]*)</span>', window)
    if more and "more" in more.group(1):
        location += " " + more.group(1).strip()

    for w in ICON_WORDS:
        company = company.replace(w, "").strip()
        level = level.replace(w, "").strip()
    return title, company, location, level


def description(h):
    d = meta_content(h, "og:description", "description", "twitter:description")
    if d and len(d) > 120:
        return d
    m = re.search(r'<h2 class="p1N2lc">', h)
    if m:
        return strip_tags(h[m.start(): m.start() + 20000])[:8000]
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", default="google", choices=sorted(LABEL))
    args = ap.parse_args()
    plat = args.platform

    raw_dir = PROJECT_ROOT / "data_raw" / f"{plat}_wayback"
    cand_path = PROJECT_ROOT / "data_processed" / f"{plat}_ts_candidates.csv"
    out = PROJECT_ROOT / "data_processed" / f"{plat}_wayback_postings.csv"

    cands = {}
    if cand_path.exists():
        for r in csv.DictReader(open(cand_path, encoding="utf-8-sig")):
            cands[r["job_id"]] = r

    files = sorted(raw_dir.glob("*.html"))
    print(f"saved pages: {len(files)}")

    rows, stats = [], Counter()
    for i, f in enumerate(files, 1):
        stamp, _, jid = f.stem.partition("_")
        h = f.read_text(encoding="utf-8", errors="replace")
        stats["shell" if len(h) < 50000 else "rendered"] += 1

        title, company, location, level = parse_detail_block(h)
        og_title = meta_content(h, "og:title", "twitter:title")
        og_title = re.sub(r"\s*[—-]\s*Google Careers\s*$", "", og_title).strip()
        if og_title.lower().startswith("build for everyone"):
            og_title = ""

        # A capture can exist while the posting was already gone: Google serves
        # "Job not found. This job may have been taken down." Those pages carry
        # no location and must not be counted as observations.
        if len(h) < 50000:
            page_status = "js_shell"
        elif "Job not found" in h:
            page_status = "job_not_found"
        else:
            page_status = "detail"
        stats[page_status] += 1

        c = cands.get(jid, {})
        final_title = title or og_title or c.get("title", "")
        if location:
            stats["with_location"] += 1
        if title:
            stats["detail_block"] += 1
        elif og_title:
            stats["og_only"] += 1
        else:
            stats["title_from_slug"] += 1

        rows.append({
            "record_id": i,
            "company_name": company if company in ("Google", "YouTube") else LABEL[plat],
            "job_id": jid,
            "source_url": c.get("original", ""),
            "capture_mode": "wayback_snapshot",
            "date_accessed": f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}",
            "job_title": final_title,
            "location": location,
            "team_function": company,
            "job_text": description(h),
            "africa_facing_signal": "", "africa_facing_text": "",
            "languages_named": "", "language_signal": "",
            "moderation_signal": "", "integrity_signal": "",
            "policy_enforcement_signal": "", "vendor_signal": "",
            "worker_risk_signal": "", "offshore_relative_to_market": "",
            "notes": (f"snapshot {stamp}; page_status={page_status}; "
                      f"level={level}; slug_title={c.get('title','')}; "
                      f"matched={c.get('matched_terms','')}"),
        })

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"\nwrote {len(rows)} rows to {out}")
    print(f"  usable job-detail pages      : {stats['detail']}")
    print(f"  'Job not found' at capture   : {stats['job_not_found']}")
    print(f"  javascript shells (2023-ish) : {stats['js_shell']}")
    print(f"  WITH A LOCATION              : {stats['with_location']}")
    print(f"  title from detail block      : {stats['detail_block']}")
    print(f"  title from Open Graph only   : {stats['og_only']}")
    print(f"  title from URL slug only     : {stats['title_from_slug']}")

    loc = [r for r in rows if r["location"]]
    print("\ntop locations:")
    for c, n in Counter(r["location"] for r in loc).most_common(15):
        print(f"   {n:4d}  {c}")
    print("\ncompany split:")
    for c, n in Counter(r["team_function"] for r in rows if r["team_function"]).most_common():
        print(f"   {n:4d}  {c}")
    AFRICA = re.compile(
        r"\b(africa|kenya|nairobi|nigeria|lagos|abuja|ghana|accra|ethiopia|"
        r"addis ababa|johannesburg|cape town|pretoria|egypt|cairo|morocco|"
        r"casablanca|senegal|dakar|tanzania|uganda|kampala|rwanda|kigali)\b", re.I)
    africa = [r for r in loc if AFRICA.search(r["location"])]
    print(f"\npostings located in Africa: {len(africa)}")
    for r in africa[:10]:
        print(f"   {r['job_title'][:60]}  |  {r['location']}")


if __name__ == "__main__":
    main()
