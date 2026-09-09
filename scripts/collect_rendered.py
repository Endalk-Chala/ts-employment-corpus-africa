"""
collect_rendered.py

Collects job advertisements from career sites that render in JavaScript, which
plain `requests` cannot read. Covers Google/YouTube and TikTok.

Rather than guessing at a private API endpoint that may change without notice,
this script does something more durable: it opens the real careers site in a
headless browser and listens to the network traffic the page itself makes. Any
JSON response that looks like job data is captured and saved. That way the
site tells you its own API instead of you hardcoding a guess, and when the
endpoint changes the script keeps working.

Two phases:

    discover   render the search pages, capture JSON payloads and job links
    fetch      render each job page, extract JSON-LD or DOM fields

Usage
-----
    pip install playwright && playwright install chromium

    python collect_rendered.py google discover
    python collect_rendered.py google fetch
    python collect_rendered.py tiktok discover --query "trust and safety"
    python collect_rendered.py tiktok fetch

Writes
------
    data_raw/<company>_rendered/          rendered HTML per page
    data_raw/<company>_xhr/               captured JSON payloads
    data_processed/<company>_job_links.csv
    data_processed/<company>_postings.csv posting-level rows

Run this from your own terminal with normal internet access.
"""

from pathlib import Path
from urllib.parse import urljoin, urlparse
import argparse
import csv
import json
import re
import sys
import time

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed. Run:")
    print("    pip install playwright")
    print("    playwright install chromium")
    sys.exit(1)

from bs4 import BeautifulSoup

# ----------------------------
# Site configuration
# ----------------------------
SITES = {
    "google": {
        "label": "Google/YouTube",
        "search_urls": [
            "https://www.google.com/about/careers/applications/jobs/results/?q=%22trust%20and%20safety%22",
            "https://www.google.com/about/careers/applications/jobs/results/?q=%22content%20moderation%22",
            "https://www.google.com/about/careers/applications/jobs/results/?q=%22policy%20enforcement%22",
            "https://www.google.com/about/careers/applications/jobs/results/?q=integrity",
        ],
        "job_url_pattern": re.compile(r"/about/careers/applications/jobs/results/\d+"),
        "next_selectors": ["a[aria-label='Go to next page']", "a[jsname][aria-label*='next' i]"],
        "result_selector": "a[href*='/jobs/results/']",
    },
    "tiktok": {
        "label": "TikTok",
        "search_urls": [
            "https://lifeattiktok.com/search?keyword=trust%20and%20safety",
            "https://lifeattiktok.com/search?keyword=global%20operations",
            "https://lifeattiktok.com/search?keyword=content%20moderation",
            "https://lifeattiktok.com/search?keyword=integrity",
        ],
        "job_url_pattern": re.compile(r"/(?:position|search)/\d+"),
        "next_selectors": ["button[aria-label='next page']", "li.ant-pagination-next"],
        "result_selector": "a[href*='/position/']",
    },
}

JSON_HINT = re.compile(r"(job|position|search|posting|career)", re.I)
SCROLL_ROUNDS = 8
SCROLL_PAUSE = 1.2
PAGE_TIMEOUT = 45000


def clean_text(t):
    return re.sub(r"\s+", " ", t or "").strip()


# ----------------------------
# JSON-LD extraction (shared)
# ----------------------------
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


def location_from_jsonld(p):
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
                parts = [addr.get("addressLocality", ""), addr.get("addressRegion", ""), country or ""]
                names.append(", ".join(x for x in parts if x))
            elif isinstance(addr, str):
                names.append(addr)
        elif isinstance(loc, str):
            names.append(loc)
    return "; ".join(n for n in names if n)


# ----------------------------
# Browser plumbing
# ----------------------------
def make_capture(xhr_dir, captured):
    """Return a response handler that saves JSON payloads that look job-shaped."""
    xhr_dir.mkdir(parents=True, exist_ok=True)
    counter = {"n": 0}

    def on_response(response):
        try:
            ctype = (response.headers or {}).get("content-type", "")
            if "json" not in ctype.lower():
                return
            url = response.url
            if not JSON_HINT.search(url):
                return
            body = response.text()
            if len(body) < 200:
                return
            counter["n"] += 1
            name = f"{counter['n']:04d}_{re.sub(r'[^A-Za-z0-9]+', '_', urlparse(url).path)[:60]}.json"
            (xhr_dir / name).write_text(body, encoding="utf-8")
            captured.append({"url": url, "file": str(xhr_dir / name), "bytes": len(body)})
        except Exception:
            pass

    return on_response


def autoscroll(page):
    for _ in range(SCROLL_ROUNDS):
        page.mouse.wheel(0, 4000)
        time.sleep(SCROLL_PAUSE)


def discover(company, extra_query=None, headful=False):
    cfg = SITES[company]
    rendered_dir = PROJECT_ROOT / "data_raw" / f"{company}_rendered"
    xhr_dir = PROJECT_ROOT / "data_raw" / f"{company}_xhr"
    links_path = PROJECT_ROOT / "data_processed" / f"{company}_job_links.csv"
    rendered_dir.mkdir(parents=True, exist_ok=True)

    search_urls = list(cfg["search_urls"])
    if extra_query:
        from urllib.parse import quote
        base = search_urls[0].split("?")[0]
        key = "q" if company == "google" else "keyword"
        search_urls.insert(0, f"{base}?{key}={quote(extra_query)}")

    captured = []
    links = {}

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headful)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
            viewport={"width": 1400, "height": 1000},
        )
        page = ctx.new_page()
        page.on("response", make_capture(xhr_dir, captured))

        for i, url in enumerate(search_urls, 1):
            print(f"\n[{i}/{len(search_urls)}] {url}")
            try:
                page.goto(url, timeout=PAGE_TIMEOUT, wait_until="networkidle")
            except Exception as e:
                print(f"    navigation issue: {e}")
            time.sleep(2)
            autoscroll(page)

            html = page.content()
            (rendered_dir / f"search_{i:02d}.html").write_text(html, encoding="utf-8")

            found = 0
            for a in page.query_selector_all("a[href]"):
                href = a.get_attribute("href") or ""
                full = urljoin(url, href)
                if cfg["job_url_pattern"].search(full):
                    text = clean_text(a.inner_text())
                    if full not in links:
                        links[full] = {"job_url": full, "link_text": text, "found_on": url}
                        found += 1
            print(f"    {found} new job links (total {len(links)})")

        browser.close()

    links_path.parent.mkdir(parents=True, exist_ok=True)
    with links_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["job_url", "link_text", "found_on"])
        w.writeheader()
        w.writerows(links.values())

    print(f"\nJob links: {len(links)} -> {links_path}")
    print(f"Captured JSON payloads: {len(captured)} -> {xhr_dir}")
    if captured:
        print("\nThe site's own API responses were saved. Inspect the largest:")
        for c in sorted(captured, key=lambda x: -x["bytes"])[:5]:
            print(f"    {c['bytes']:>8} bytes  {c['url'][:110]}")
        print("If one of these holds the full result set, parse it directly rather")
        print("than rendering every job page. That is faster and kinder to the site.")


POSTING_FIELDS = [
    "record_id", "company_name", "job_id", "source_url", "capture_mode",
    "date_accessed", "job_title", "location", "team_function", "job_text",
    "africa_facing_signal", "africa_facing_text", "languages_named",
    "language_signal", "moderation_signal", "integrity_signal",
    "policy_enforcement_signal", "vendor_signal", "worker_risk_signal",
    "offshore_relative_to_market", "notes",
]


def fetch(company, headful=False, limit=None):
    cfg = SITES[company]
    links_path = PROJECT_ROOT / "data_processed" / f"{company}_job_links.csv"
    rendered_dir = PROJECT_ROOT / "data_raw" / f"{company}_rendered"
    out_path = PROJECT_ROOT / "data_processed" / f"{company}_postings.csv"

    if not links_path.exists():
        print(f"No link file at {links_path}. Run `discover` first.")
        sys.exit(1)

    with links_path.open(encoding="utf-8") as f:
        links = list(csv.DictReader(f))
    if limit:
        links = links[:limit]

    from datetime import date
    today = date.today().isoformat()
    rows = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not headful)
        ctx = browser.new_context(viewport={"width": 1400, "height": 1000})
        page = ctx.new_page()

        for i, link in enumerate(links, 1):
            url = link["job_url"]
            print(f"[{i}/{len(links)}] {url[:100]}")
            try:
                page.goto(url, timeout=PAGE_TIMEOUT, wait_until="networkidle")
                time.sleep(1.2)
                html = page.content()
            except Exception as e:
                print(f"    ERROR {e}")
                continue

            jid_m = re.search(r"/(\d{6,})", url)
            jid = jid_m.group(1) if jid_m else ""
            (rendered_dir / f"job_{jid or i}.html").write_text(html, encoding="utf-8")

            postings = extract_jsonld_jobposting(html)
            if postings:
                p = postings[0]
                desc = BeautifulSoup(p.get("description", "") or "", "html.parser").get_text(" ")
                title = clean_text(str(p.get("title", "")))
                loc = clean_text(location_from_jsonld(p))
                body = clean_text(desc)
                mode = "rendered_jsonld"
            else:
                soup = BeautifulSoup(html, "html.parser")
                for t in soup(["script", "style", "noscript", "header", "footer", "nav"]):
                    t.extract()
                h = soup.find(["h1", "h2"])
                title = clean_text(h.get_text(" ")) if h else ""
                loc = ""
                body = clean_text(soup.get_text(" "))
                mode = "rendered_dom"

            rows.append({
                "record_id": i,
                "company_name": cfg["label"],
                "job_id": jid,
                "source_url": url,
                "capture_mode": mode,
                "date_accessed": today,
                "job_title": title,
                "location": loc,
                "team_function": "",
                "job_text": body,
                "africa_facing_signal": "", "africa_facing_text": "",
                "languages_named": "", "language_signal": "",
                "moderation_signal": "", "integrity_signal": "",
                "policy_enforcement_signal": "", "vendor_signal": "",
                "worker_risk_signal": "", "offshore_relative_to_market": "",
                "notes": f"link text: {link.get('link_text','')}",
            })
            time.sleep(1.0)

        browser.close()

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=POSTING_FIELDS)
        w.writeheader()
        w.writerows(rows)

    print(f"\nDone. {len(rows)} postings -> {out_path}")
    print("Signal columns are blank by design; run code_postings.py to fill them.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("company", choices=sorted(SITES))
    ap.add_argument("phase", choices=["discover", "fetch"])
    ap.add_argument("--query", default=None, help="extra keyword search to add")
    ap.add_argument("--headful", action="store_true",
                    help="show the browser; useful when a site blocks headless")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    if args.phase == "discover":
        discover(args.company, args.query, args.headful)
    else:
        fetch(args.company, args.headful, args.limit)


if __name__ == "__main__":
    main()
