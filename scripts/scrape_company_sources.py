"""
scrape_company_sources.py

Source-page scraper for the trust-and-safety job-ads corpus.

This mirrors scrape_meta_sources.py but works for any company listed in
COMPANIES below, so TikTok and Google do not each need their own copy of
the same 250 lines. The Meta script is left untouched.

Usage
-----
    python scrape_company_sources.py tiktok
    python scrape_company_sources.py google
    python scrape_company_sources.py meta      # re-runs Meta through this path

Reads
-----
    source_registry/<company>_source_registry.csv
        columns: company_name, source_type, source_url, notes

Writes
------
    data_processed/<company>_records.csv
    data_raw/<company>_html/*.html

What this adds over the original Meta script
--------------------------------------------
1. robots.txt is fetched and honoured per host. A disallowed URL is recorded
   as record_type="skipped_by_robots" rather than fetched.
2. A fixed delay between requests, so the crawl stays polite.
3. schema.org JobPosting JSON-LD extraction. Career sites that render their
   listings in JavaScript often still embed structured job data in a
   <script type="application/ld+json"> block, which is the only reliable way
   to get title, date and location out of them. This is the same shape of
   data behind meta_jobs_jsonld_large.csv.
4. A js_shell_flag column. Both lifeattiktok.com and Google's careers app are
   client-rendered, so a plain GET usually returns an near-empty shell. When
   the extracted text is very short the row is flagged, which tells you the
   page needs manual_text_capture instead (the mode already used in
   source_registry.csv) or a headless browser.

The original 17 columns are preserved in their original order so that
clean_meta_records.py and the other downstream scripts keep working. New
columns are appended at the end.
"""

from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import csv
import json
import re
import sys
import time
import uuid
from datetime import date

import requests
from bs4 import BeautifulSoup

# ----------------------------
# Project paths
# ----------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# ----------------------------
# Config
# ----------------------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; academic-research-scraper/1.0; "
        "trust-and-safety job posting study; contact endalk2006@gmail.com)"
    )
}
TIMEOUT = 20
REQUEST_DELAY = 2.0          # seconds between requests
RESPECT_ROBOTS = True
JS_SHELL_TEXT_THRESHOLD = 400  # chars; below this the page is probably a JS shell

# ----------------------------
# Keyword dictionaries
# ----------------------------
TS_KEYWORDS = [
    "trust and safety",
    "content moderation",
    "content moderator",
    "integrity",
    "safety",
    "security",
    "policy enforcement",
    "community guidelines",
    "community standards",
    "investigations",
    "misinformation",
    "risk",
    "abuse",
    "election",
    "inauthentic behavior",
    "escalation",
    "harmful content",
]

AFRICA_KEYWORDS = [
    "africa",
    "sub-saharan africa",
    "french sub-saharan africa",
    "east africa",
    "west africa",
    "kenya",
    "ethiopia",
    "ghana",
    "nigeria",
    "south africa",
    "nairobi",
    "lagos",
    "johannesburg",
    "accra",
    "addis ababa",
]

LANGUAGE_KEYWORDS = [
    "amharic",
    "hausa",
    "swahili",
    "kiswahili",
    "somali",
    "oromo",
    "afaan oromo",
    "tigrinya",
    "arabic",
    "french",
    "portuguese",
    "yoruba",
    "igbo",
    "zulu",
]

# ----------------------------
# Per-company configuration
# ----------------------------
COMPANIES = {
    "meta": {
        "label": "Meta",
        "job_link_patterns": [
            "job_details", "/jobsearch/", "careers", "job", "jobs",
            "position", "opening",
        ],
    },
    "tiktok": {
        "label": "TikTok",
        # lifeattiktok.com uses /search and /position/<id>/detail
        # jobs.bytedance.com uses /en/position/<id>/detail
        "job_link_patterns": [
            "/position/", "/detail", "/search", "careers", "job", "jobs",
            "opening", "opportunity",
        ],
    },
    "google": {
        "label": "Google",
        # careers app uses /about/careers/applications/jobs/results/<id>
        "job_link_patterns": [
            "/jobs/results/", "careers/applications", "careers", "job", "jobs",
            "position", "opening",
        ],
    },
}


# ----------------------------
# Helpers
# ----------------------------
def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def keyword_hits(text: str, keywords: list) -> str:
    text_lower = text.lower()
    hits = [kw for kw in keywords if kw.lower() in text_lower]
    return "; ".join(sorted(set(hits)))


def yes_no(hit_string: str) -> str:
    return "yes" if hit_string else "no"


def save_html(raw_html_dir: Path, source_type: str, html: str) -> str:
    raw_html_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{source_type}_{uuid.uuid4().hex[:8]}.html"
    path = raw_html_dir / filename
    path.write_text(html, encoding="utf-8")
    return str(path)


def extract_text_and_title(html: str):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.extract()
    title = soup.title.get_text(strip=True) if soup.title else ""
    text = clean_text(soup.get_text(" ", strip=True))
    return title, text


def collect_links(base_url: str, html: str):
    soup = BeautifulSoup(html, "html.parser")
    results = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = clean_text(a.get_text(" ", strip=True))
        full_url = urljoin(base_url, href)

        if not full_url.startswith("http"):
            continue

        key = (full_url, text)
        if key in seen:
            continue
        seen.add(key)
        results.append((full_url, text))

    return results


def is_likely_job_link(url: str, text: str, patterns: list) -> str:
    combined = f"{url} {text}".lower()
    return "yes" if any(p.lower() in combined for p in patterns) else "no"


# ----------------------------
# robots.txt
# ----------------------------
_ROBOTS_CACHE = {}


def robots_allows(url: str) -> bool:
    """Return True if robots.txt permits fetching this URL. Fails open on error."""
    if not RESPECT_ROBOTS:
        return True

    parsed = urlparse(url)
    root = f"{parsed.scheme}://{parsed.netloc}"

    if root not in _ROBOTS_CACHE:
        parser = RobotFileParser()
        parser.set_url(urljoin(root, "/robots.txt"))
        try:
            parser.read()
        except Exception:
            parser = None          # unreachable robots.txt: do not block the crawl
        _ROBOTS_CACHE[root] = parser

    parser = _ROBOTS_CACHE[root]
    if parser is None:
        return True

    try:
        return parser.can_fetch(HEADERS["User-Agent"], url)
    except Exception:
        return True


# ----------------------------
# schema.org JobPosting JSON-LD
# ----------------------------
def _as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _flatten_jsonld(node, found):
    """Walk a JSON-LD structure and collect every JobPosting object."""
    if isinstance(node, dict):
        node_type = node.get("@type")
        types = [t.lower() for t in _as_list(node_type) if isinstance(t, str)]
        if "jobposting" in types:
            found.append(node)
        for value in node.values():
            _flatten_jsonld(value, found)
    elif isinstance(node, list):
        for item in node:
            _flatten_jsonld(item, found)


def extract_job_postings(html: str):
    """Return every schema.org JobPosting embedded in the page as JSON-LD."""
    soup = BeautifulSoup(html, "html.parser")
    found = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        _flatten_jsonld(data, found)

    return found


def _org_name(value):
    if isinstance(value, dict):
        return value.get("name", "")
    if isinstance(value, str):
        return value
    return ""


def _location_names(value):
    names = []
    for loc in _as_list(value):
        if isinstance(loc, dict):
            addr = loc.get("address")
            if isinstance(addr, dict):
                parts = [
                    addr.get("addressLocality", ""),
                    addr.get("addressRegion", ""),
                    addr.get("addressCountry", ""),
                ]
                if isinstance(parts[2], dict):
                    parts[2] = parts[2].get("name", "")
                names.append(", ".join(p for p in parts if p))
            elif isinstance(addr, str):
                names.append(addr)
            elif loc.get("name"):
                names.append(loc["name"])
        elif isinstance(loc, str):
            names.append(loc)
    return "; ".join(n for n in names if n)


def summarize_postings(postings: list):
    """Collapse the JobPosting objects on one page into flat CSV fields."""
    if not postings:
        return {
            "jsonld_found": "0",
            "jsonld_title": "",
            "jsonld_date_posted": "",
            "jsonld_employment_type": "",
            "jsonld_hiring_org": "",
            "jsonld_locations": "",
        }

    titles, dates, emp_types, orgs, locs = [], [], [], [], []
    for p in postings:
        if p.get("title"):
            titles.append(clean_text(str(p["title"])))
        if p.get("datePosted"):
            dates.append(str(p["datePosted"]))
        for et in _as_list(p.get("employmentType")):
            if isinstance(et, str):
                emp_types.append(et)
        org = _org_name(p.get("hiringOrganization"))
        if org:
            orgs.append(org)
        loc = _location_names(p.get("jobLocation"))
        if loc:
            locs.append(loc)

    def joined(seq):
        return "; ".join(dict.fromkeys(seq))

    return {
        "jsonld_found": str(len(postings)),
        "jsonld_title": joined(titles),
        "jsonld_date_posted": joined(dates),
        "jsonld_employment_type": joined(emp_types),
        "jsonld_hiring_org": joined(orgs),
        "jsonld_locations": joined(locs),
    }


# ----------------------------
# Output schema
# ----------------------------
BASE_FIELDS = [
    "record_type",
    "company_name",
    "source_type",
    "source_url",
    "page_title",
    "raw_html_path",
    "meta_hits",
    "meta_flag",
    "africa_hits",
    "africa_flag",
    "language_hits",
    "language_flag",
    "discovered_link",
    "link_text",
    "likely_job_link",
    "notes",
    "text_sample",
]

EXTRA_FIELDS = [
    "jsonld_found",
    "jsonld_title",
    "jsonld_date_posted",
    "jsonld_employment_type",
    "jsonld_hiring_org",
    "jsonld_locations",
    "js_shell_flag",
    "http_status",
    "date_accessed",
]

FIELDNAMES = BASE_FIELDS + EXTRA_FIELDS


def blank_row(**overrides):
    row = {field: "" for field in FIELDNAMES}
    row.update(overrides)
    return row


# ----------------------------
# Main
# ----------------------------
def main():
    if len(sys.argv) < 2 or sys.argv[1].lower() not in COMPANIES:
        print("Usage: python scrape_company_sources.py <company>")
        print("Available:", ", ".join(sorted(COMPANIES)))
        sys.exit(1)

    company_key = sys.argv[1].lower()
    config = COMPANIES[company_key]
    job_patterns = config["job_link_patterns"]

    registry_path = PROJECT_ROOT / "source_registry" / f"{company_key}_source_registry.csv"
    output_path = PROJECT_ROOT / "data_processed" / f"{company_key}_records.csv"
    raw_html_dir = PROJECT_ROOT / "data_raw" / f"{company_key}_html"

    print("Company:      ", config["label"])
    print("Project root: ", PROJECT_ROOT)
    print("Registry path:", registry_path)
    print("Output path:  ", output_path)

    if not registry_path.exists():
        raise FileNotFoundError(f"Missing file: {registry_path}")

    with registry_path.open("r", encoding="utf-8", newline="") as f:
        sources = list(csv.DictReader(f))

    today = date.today().isoformat()
    rows_out = []

    for i, row in enumerate(sources):
        company_name = row["company_name"].strip()
        source_type = row["source_type"].strip()
        source_url = row["source_url"].strip()
        notes = row.get("notes", "").strip()

        if not robots_allows(source_url):
            rows_out.append(blank_row(
                record_type="skipped_by_robots",
                company_name=company_name,
                source_type=source_type,
                source_url=source_url,
                notes=f"{notes} | disallowed by robots.txt",
                date_accessed=today,
            ))
            print(f"[ROBOTS] {source_type}: {source_url}")
            continue

        if i > 0:
            time.sleep(REQUEST_DELAY)

        try:
            r = requests.get(source_url, headers=HEADERS, timeout=TIMEOUT)
            status = str(r.status_code)
            r.raise_for_status()
            html = r.text

            raw_html_path = save_html(raw_html_dir, source_type, html)
            page_title, full_text = extract_text_and_title(html)

            postings = extract_job_postings(html)
            jsonld = summarize_postings(postings)

            ts_hits = keyword_hits(full_text, TS_KEYWORDS)
            africa_hits = keyword_hits(full_text, AFRICA_KEYWORDS)
            language_hits = keyword_hits(full_text, LANGUAGE_KEYWORDS)

            js_shell = "yes" if len(full_text) < JS_SHELL_TEXT_THRESHOLD else "no"

            rows_out.append(blank_row(
                record_type="source_page",
                company_name=company_name,
                source_type=source_type,
                source_url=source_url,
                page_title=page_title,
                raw_html_path=raw_html_path,
                meta_hits=ts_hits,
                meta_flag=yes_no(ts_hits),
                africa_hits=africa_hits,
                africa_flag=yes_no(africa_hits),
                language_hits=language_hits,
                language_flag=yes_no(language_hits),
                notes=notes,
                text_sample=full_text[:1200],
                js_shell_flag=js_shell,
                http_status=status,
                date_accessed=today,
                **jsonld,
            ))

            for full_url, link_text in collect_links(source_url, html):
                rows_out.append(blank_row(
                    record_type="discovered_link",
                    company_name=company_name,
                    source_type=source_type,
                    source_url=source_url,
                    page_title=page_title,
                    raw_html_path=raw_html_path,
                    discovered_link=full_url,
                    link_text=link_text,
                    likely_job_link=is_likely_job_link(full_url, link_text, job_patterns),
                    notes=notes,
                    http_status=status,
                    date_accessed=today,
                ))

            flag = " [JS SHELL]" if js_shell == "yes" else ""
            print(f"[OK] {source_type}: {source_url} "
                  f"(text {len(full_text)} chars, {jsonld['jsonld_found']} JSON-LD postings){flag}")

        except Exception as e:
            rows_out.append(blank_row(
                record_type="error",
                company_name=company_name,
                source_type=source_type,
                source_url=source_url,
                notes=f"{notes} | ERROR: {e}",
                date_accessed=today,
            ))
            print(f"[ERROR] {source_type}: {source_url} -> {e}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows_out)

    shells = sum(1 for r in rows_out if r["js_shell_flag"] == "yes")
    postings_total = sum(
        int(r["jsonld_found"]) for r in rows_out if r["jsonld_found"].isdigit()
    )

    print("\nDone.")
    print("Saved to:", output_path)
    print(f"Rows: {len(rows_out)} | JSON-LD job postings found: {postings_total}")
    if shells:
        print(f"Warning: {shells} page(s) returned what looks like a JavaScript shell.")
        print("Those need manual_text_capture or a headless browser, not requests.")


if __name__ == "__main__":
    main()
