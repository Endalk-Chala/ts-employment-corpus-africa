"""
collect_tiktok_arm.py

Reconstructs the TikTok arm of the employment corpus from the Internet Archive.

Why TikTok needs its own script
-------------------------------
Meta and Google could both be screened cheaply before downloading anything:
Meta's archived pages carry schema.org JobPosting JSON-LD, and Google puts the
job title in the URL slug. TikTok does neither.

A TikTok posting lives at:

    https://lifeattiktok.com/search/6704494100210518285

No title in the URL, no JSON-LD in the page (the site sends `robots: noindex`),
and the job body and location are fetched client-side from a signed API that
the Archive never captured. What the archived HTML *does* carry, server-rendered
in the document head, is the job title:

    <title>Content Moderator - Arabic</title>
    <meta property="og:title" content="Content Moderator - Arabic">

So the screen has to run on the title, and the title costs a page fetch. This
script therefore fetches every archived posting once, keeps the title, and saves
the full HTML only for postings that pass the screen.

What this arm can and cannot establish
--------------------------------------
CAN:  which Trust and Safety roles TikTok advertised, when, and in what
      language-specific varieties. Titles are explicit about language
      ("Content Moderator - Arabic"), which bears directly on the article's
      claim about language coverage.

CANNOT: give a location for every posting. TikTok's archived pages carry no
      location field at all. The country distribution in the published Figure 2
      came from live collection in March 2026 and cannot be re-derived in full
      from archived material. Say so in the methods rather than implying
      otherwise.

PARTLY: some titles name the office outright, as in "Quality Analyst-Dublin
      hub-Hausa" or "Content Moderator (Short Video) - VN". Where they do, the
      location is real and usable. Where they do not, the field is blank, and a
      blank must never be read as an absence of location, only as an absence of
      evidence. The two are reported in separate columns, `city_named` for an
      office and `market_named` for a market or region, precisely so that the
      distinction survives into the analysis.

The two legacy domains, careers.tiktok.com/position/<id>/detail and
jobs.bytedance.com/en/position/<id>/detail, were checked and are pure
JavaScript shells with the generic title "Join TikTok" / "Join ByteDance".
They are recorded for completeness but yield nothing.

Usage
-----
    python scripts/collect_tiktok_arm.py --discover-only
    python scripts/collect_tiktok_arm.py --fetch            # resumable
    python scripts/collect_tiktok_arm.py --report

Writes
------
    source_registry/tiktok_wayback_snapshots.csv    every archived posting URL
    data_processed/tiktok_title_registry.csv        one row per job id
    data_raw/tiktok_wayback/<ts>_<jobid>.html       screened-in postings only
"""

from pathlib import Path
from collections import Counter, defaultdict
import argparse
import csv
import html as htmllib
import re
import sys
import time

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
csv.field_size_limit(10_000_000)

CDX = "http://web.archive.org/cdx/search/cdx"
SNAPSHOT = "https://web.archive.org/web/{ts}id_/{url}"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (compatible; academic-research-scraper/1.0; "
                   "trust-and-safety job posting study; contact endalk2006@gmail.com)")
}
TIMEOUT = 45
FETCH_DELAY = 1.0
MAX_RETRIES = 4
BACKOFF = 6

# Ordered by preference: lifeattiktok is the only generation that server-renders
# a real title. The other two are kept so the registry is honest about what was
# archived, not because they yield anything.
PATTERNS = [
    ("lifeattiktok", "lifeattiktok.com/search/", re.compile(r"/search/(\d{6,})(?:[/?#]|$)")),
    ("careers_tiktok", "careers.tiktok.com/position/", re.compile(r"/position/(\d{6,})")),
    ("jobs_bytedance", "jobs.bytedance.com/en/position/", re.compile(r"/position/(\d{6,})")),
]

GENERIC_TITLES = {"join tiktok", "join bytedance", "tiktok", "lifeattiktok",
                  "life at tiktok", "404 page not found", "page not found"}

# ------------------------------------------------------------------ screening
# Same vocabulary family as the Google and Meta arms, expressed for titles.
# A trailing * means "stem": it matches the rest of the word, so
# "content moderat*" catches Moderator, Moderation and Moderators alike.
INCLUDE = [
    "trust and safety", "trust & safety", "t&s",
    "content moderat*", "content review*", "content quality", "content safety",
    "community operations", "community guidelines", "community standards",
    "policy manager", "policy specialist", "policy analyst", "policy program*",
    "policy enforcement", "policy operations", "public policy", "policy lead",
    "integrity", "misinformation", "disinformation", "inauthentic",
    "harmful content", "objectionable content", "violat*",
    "abuse", "escalation*", "online safety", "user safety", "child safety",
    "minor safety", "threat intelligence", "threat analyst", "crisis response",
    "risk operations", "risk analyst", "fraud", "spam",
    "safety operations", "safety policy", "safety program*", "governance",
    "civic integrity", "election integrity", "counter-speech", "counterspeech",
    "moderat*", "quality analyst", "annotat*", "safety review*",
    # "label" alone caught "Label Designer, Music" — a record-label job, not a
    # data-labelling one. Qualify it.
    "data label*", "content label*", "labeling specialist", "labelling specialist",
]

# The false-positive family found in the Meta arm: engineering senses of
# "integrity" and "safety" that have nothing to do with content governance.
EXCLUDE = [
    "signal integrity", "power integrity", "system integrity", "data integrity",
    "structural integrity", "device integrity", "hardware", "silicon",
    "fire safety", "life safety", "environmental health", "workplace safety",
    "food safety", "driver safety", "ai safety research", "agi safety",
    "data center", "datacenter", "site reliability", "functional safety",
]

# Language-specific moderation is where the article's argument bites, so
# languages are detected separately from the T&S screen. The African list is
# deliberately broad: the claim under test is an absence, and an absence is only
# credible if the search for a presence was generous.
AFRICAN_LANGUAGES = [
    "amharic", "afaan oromo", "afan oromo", "oromo", "oromiffa", "somali",
    "tigrinya", "tigrigna", "swahili", "kiswahili", "hausa", "yoruba", "igbo",
    "fulani", "fulfulde", "wolof", "zulu", "isizulu", "xhosa", "isixhosa",
    "afrikaans", "sesotho", "setswana", "shona", "ndebele", "chichewa",
    "kinyarwanda", "kirundi", "luganda", "lingala", "malagasy", "twi", "akan",
    "ewe", "ga", "tigre", "berber", "tamazight", "kabyle", "nuer", "dinka",
    "krio", "bambara", "mooré", "moore", "sango", "kanuri", "tsonga", "venda",
    "swati", "siswati", "sepedi", "northern sotho",
]

OTHER_LANGUAGES = [
    "arabic", "spanish", "portuguese", "brazilian portuguese", "french",
    "german", "italian", "dutch", "polish", "czech", "slovak", "hungarian",
    "romanian", "bulgarian", "greek", "turkish", "russian", "ukrainian",
    "kazakh", "uzbek", "azerbaijani", "hebrew", "persian", "farsi", "kurdish",
    "urdu", "hindi", "bengali", "punjabi", "gujarati", "marathi", "tamil",
    "telugu", "kannada", "malayalam", "nepali", "sinhala", "burmese",
    "thai", "lao", "khmer", "vietnamese", "indonesian", "bahasa", "malay",
    "tagalog", "filipino", "cebuano", "japanese", "korean", "mandarin",
    "cantonese", "chinese", "traditional chinese", "simplified chinese",
    "mongolian", "danish", "swedish", "norwegian", "finnish", "icelandic",
    "estonian", "latvian", "lithuanian", "croatian", "serbian", "bosnian",
    "albanian", "macedonian", "slovenian", "catalan", "basque", "galician",
    "welsh", "irish", "haitian creole", "quechua", "english",
]


# TikTok names the market in the title far more often than Meta or Google do:
# "Content Moderator (Short Video) - VN", "Content Moderator, Features - Korea",
# "Monetization Strategy - Middle East". This is not a location field and must
# not be reported as one, but it is a market signal, and the article's argument
# is about which markets get staffed.
MARKETS = {
    "Vietnam": ["vietnam", "vietnamese market"],
    "Korea": ["korea", "south korea"],
    "Japan": ["japan"],
    "Indonesia": ["indonesia"],
    "Thailand": ["thailand"],
    "Philippines": ["philippines"],
    "Malaysia": ["malaysia"],
    "Singapore": ["singapore"],
    "India": ["india"],
    "Pakistan": ["pakistan"],
    "Bangladesh": ["bangladesh"],
    "China": ["china", "mainland china"],
    "Taiwan": ["taiwan"],
    "Hong Kong": ["hong kong"],
    "Australia": ["australia", "anz"],
    "Brazil": ["brazil", "brasil"],
    "Mexico": ["mexico"],
    "LATAM": ["latam", "latin america"],
    "United States": ["united states", "usa", "u.s."],
    "Canada": ["canada"],
    "United Kingdom": ["united kingdom", "uk market"],
    "Ireland": ["ireland", "dublin"],
    "Germany": ["germany", "dach"],
    "France": ["france"],
    "Spain": ["spain", "iberia"],
    "Italy": ["italy"],
    "Netherlands": ["netherlands"],
    "Nordics": ["nordics", "nordic"],
    "Poland": ["poland"],
    "Turkey": ["turkey", "türkiye"],
    "Russia": ["russia", "cis"],
    "EMEA": ["emea"],
    "Europe": ["europe", "european"],
    "APAC": ["apac", "asia pacific", "sea market", "southeast asia", "south east asia"],
    "MENA": ["mena", "middle east", "gulf", "gcc", "saudi", "uae", "dubai", "qatar", "kuwait"],
    "Israel": ["israel"],
    "Africa": ["africa", "african", "sub-saharan", "subsaharan", "ssa", "nigeria",
               "kenya", "south africa", "egypt", "morocco", "ghana", "ethiopia",
               "tanzania", "uganda", "senegal", "ivory coast", "côte d'ivoire"],
}
MARKET_RE = {k: [re.compile(r"(?<![\w])" + re.escape(v).replace(r"\ ", r"[\s\-]+") + r"(?![\w])", re.I)
                 for v in vs] for k, vs in MARKETS.items()}

# Two-letter market codes are only trusted at the end of a title, after a
# separator, because "IN", "ID" and "IT" are ordinary English words elsewhere.
TRAILING_CODE = re.compile(r"[-–—,(\[]\s*([A-Z]{2})\s*[)\]]?\s*$")
CODE_TO_MARKET = {
    "VN": "Vietnam", "KR": "Korea", "JP": "Japan", "ID": "Indonesia",
    "TH": "Thailand", "PH": "Philippines", "MY": "Malaysia", "SG": "Singapore",
    "IN": "India", "PK": "Pakistan", "BD": "Bangladesh", "CN": "China",
    "TW": "Taiwan", "HK": "Hong Kong", "AU": "Australia", "BR": "Brazil",
    "MX": "Mexico", "US": "United States", "CA": "Canada", "UK": "United Kingdom",
    "GB": "United Kingdom", "IE": "Ireland", "DE": "Germany", "FR": "France",
    "ES": "Spain", "NL": "Netherlands", "PL": "Poland",
    "TR": "Turkey", "RU": "Russia", "IL": "Israel", "AE": "United Arab Emirates",
    "EG": "Egypt", "NG": "Nigeria", "KE": "Kenya", "ZA": "South Africa",
    "MA": "Morocco",
    # deliberately omitted: IT (information technology), SA (Saudi Arabia or
    # South Africa, and the ambiguity would fall on the Africa count).
}


# Titles sometimes name the office outright: "Quality Analyst-Dublin hub-Hausa",
# "Quality Analyst - Swahili speaker - Dublin". Where that happens the location
# is recoverable after all, for that subset only. Every African city the corpus
# could plausibly name is included, so that a null result is a real null.
CITIES = {
    "Dublin": "Ireland", "London": "United Kingdom", "Manchester": "United Kingdom",
    "Berlin": "Germany", "Amsterdam": "Netherlands", "Paris": "France",
    "Barcelona": "Spain", "Madrid": "Spain", "Lisbon": "Portugal",
    "Milan": "Italy", "Rome": "Italy", "Warsaw": "Poland", "Stockholm": "Sweden",
    "Copenhagen": "Denmark", "Oslo": "Norway", "Helsinki": "Finland",
    "Zurich": "Switzerland", "Zürich": "Switzerland", "Istanbul": "Turkey",
    "Tel Aviv": "Israel", "Dubai": "United Arab Emirates", "Riyadh": "Saudi Arabia",
    "Singapore": "Singapore", "Kuala Lumpur": "Malaysia", "Jakarta": "Indonesia",
    "Manila": "Philippines", "Taguig": "Philippines", "Bangkok": "Thailand",
    "Hanoi": "Vietnam", "Ho Chi Minh": "Vietnam", "Tokyo": "Japan",
    "Osaka": "Japan", "Seoul": "Korea", "Taipei": "Taiwan",
    "Shanghai": "China", "Beijing": "China", "Shenzhen": "China",
    "Guangzhou": "China", "Hangzhou": "China", "Hong Kong": "Hong Kong",
    "Sydney": "Australia", "Melbourne": "Australia",
    "Mumbai": "India", "Delhi": "India", "Gurgaon": "India",
    "Gurugram": "India", "Bangalore": "India", "Bengaluru": "India",
    "Hyderabad": "India", "Chennai": "India",
    "New York": "United States", "Los Angeles": "United States",
    "San Jose": "United States", "San Francisco": "United States",
    "Mountain View": "United States", "Seattle": "United States",
    "Austin": "United States", "Chicago": "United States",
    "Washington": "United States", "Culver City": "United States",
    "Toronto": "Canada", "Vancouver": "Canada",
    "Mexico City": "Mexico", "São Paulo": "Brazil", "Sao Paulo": "Brazil",
    "Buenos Aires": "Argentina", "Bogotá": "Colombia", "Bogota": "Colombia",
    "Lima": "Peru", "Santiago": "Chile",
    # African offices, listed generously because the claim is an absence
    "Nairobi": "Kenya", "Lagos": "Nigeria", "Abuja": "Nigeria",
    "Accra": "Ghana", "Johannesburg": "South Africa", "Cape Town": "South Africa",
    "Pretoria": "South Africa", "Durban": "South Africa", "Cairo": "Egypt",
    "Casablanca": "Morocco", "Rabat": "Morocco", "Tunis": "Tunisia",
    "Algiers": "Algeria", "Addis Ababa": "Ethiopia", "Kampala": "Uganda",
    "Kigali": "Rwanda", "Dar es Salaam": "Tanzania", "Dakar": "Senegal",
    "Abidjan": "Ivory Coast", "Luanda": "Angola", "Maputo": "Mozambique",
}
CITY_RE = {c: re.compile(r"(?<![\w])" + re.escape(c).replace(r"\ ", r"[\s\-]+") + r"(?![\w])", re.I)
           for c in CITIES}


AFRICAN_COUNTRIES = {"Kenya", "Nigeria", "Ghana", "South Africa", "Egypt",
                     "Morocco", "Tunisia", "Algeria", "Ethiopia", "Uganda",
                     "Rwanda", "Tanzania", "Senegal", "Ivory Coast", "Angola",
                     "Mozambique"}


def cities_in(title):
    return [c for c, rx in CITY_RE.items() if rx.search(title or "")]


def markets_in(title):
    found = []
    for name, rxs in MARKET_RE.items():
        if any(rx.search(title) for rx in rxs):
            found.append(name)
    m = TRAILING_CODE.search(title or "")
    if m and m.group(1) in CODE_TO_MARKET:
        name = CODE_TO_MARKET[m.group(1)]
        if name not in found:
            found.append(name)
    return found


def word_re(term):
    """Word-boundary anchored, so 'lao' never matches 'Laotian Airlines' and
    'twi' never matches 'Twitch'. The Google arm lost time to exactly this:
    an unanchored 'addis' matched 'Addison, TX' and produced a phantom
    Africa role in a paper whose headline finding is an absence.

    A trailing '*' relaxes only the right-hand boundary, so a stem such as
    'content moderat*' still cannot start inside another word."""
    stem = term.endswith("*")
    if stem:
        term = term[:-1]
    esc = re.escape(term).replace(r"\ ", r"[\s\-]+")
    tail = r"\w*" if stem else r"(?![\w])"
    return re.compile(r"(?<![\w])" + esc + tail, re.IGNORECASE)


INCLUDE_RE = [(t, word_re(t)) for t in INCLUDE]
EXCLUDE_RE = [(t, word_re(t)) for t in EXCLUDE]
AFRICAN_RE = [(t, word_re(t)) for t in AFRICAN_LANGUAGES]
OTHER_RE = [(t, word_re(t)) for t in OTHER_LANGUAGES]


def screen(title):
    """Return (decision, matched, excluded, african_langs, other_langs)."""
    t = title or ""
    matched = [term for term, rx in INCLUDE_RE if rx.search(t)]
    excluded = [term for term, rx in EXCLUDE_RE if rx.search(t)]
    afr = [term for term, rx in AFRICAN_RE if rx.search(t)]
    oth = [term for term, rx in OTHER_RE if rx.search(t)]
    if not t.strip():
        decision = "no_title"
    elif excluded:
        decision = "exclude"
    elif matched:
        decision = "include"
    else:
        decision = "drop"
    return decision, matched, excluded, afr, oth


# ------------------------------------------------------------------------ CDX
def cdx(pattern, date_from, date_to):
    params = {
        "url": pattern,
        "matchType": "prefix",
        "output": "text",
        "fl": "timestamp,original,statuscode,digest",
        "collapse": "urlkey",
        "filter": ["statuscode:200"],
        "from": str(date_from),
        "to": str(date_to),
        "limit": "300000",
    }
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(CDX, params=params, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                wait = BACKOFF * (2 ** attempt)
                print(f"    rate limited, waiting {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            rows = []
            for line in r.text.splitlines():
                parts = line.split(" ")
                if len(parts) >= 2:
                    rows.append((parts[0], parts[1]))
            return rows
        except Exception as e:
            wait = BACKOFF * (2 ** attempt)
            print(f"    CDX error ({e}); retry in {wait}s")
            time.sleep(wait)
    return []


REG_FIELDS = ["job_id", "generation", "timestamp", "original", "n_captures"]


def discover(date_from, date_to):
    """One row per job id, keeping the latest capture of the best generation."""
    best = {}
    counts = Counter()
    for gen, pattern, rx in PATTERNS:
        print(f"\nCDX: {pattern}")
        rows = cdx(pattern, date_from, date_to)
        print(f"  {len(rows)} archived urls")
        seen_ids = set()
        for ts, url in rows:
            m = rx.search(url)
            if not m:
                continue
            jid = m.group(1)
            seen_ids.add(jid)
            counts[jid] += 1
            prev = best.get(jid)
            # lifeattiktok wins outright; within a generation, latest capture wins
            if prev is None:
                best[jid] = (gen, ts, url)
            else:
                pgen, pts, _ = prev
                pgen_rank = [g for g, _, _ in PATTERNS].index(pgen)
                gen_rank = [g for g, _, _ in PATTERNS].index(gen)
                if gen_rank < pgen_rank or (gen_rank == pgen_rank and ts > pts):
                    best[jid] = (gen, ts, url)
        print(f"  {len(seen_ids)} distinct job ids")

    out = PROJECT_ROOT / "source_registry" / "tiktok_wayback_snapshots.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=REG_FIELDS)
        w.writeheader()
        for jid, (gen, ts, url) in sorted(best.items()):
            w.writerow({"job_id": jid, "generation": gen, "timestamp": ts,
                        "original": url, "n_captures": counts[jid]})

    print(f"\n{len(best)} distinct job ids written to {out}")
    print("generation chosen for each:")
    for g, n in Counter(v[0] for v in best.values()).most_common():
        print(f"   {n:6d}  {g}")
    print("earliest capture year of the chosen snapshot:")
    for y, n in sorted(Counter(v[1][:4] for v in best.values()).items()):
        print(f"   {y}: {n}")
    usable = sum(1 for v in best.values() if v[0] == "lifeattiktok")
    print(f"\npostings with a recoverable title: {usable}")
    print(f"estimated fetch time: {usable * (FETCH_DELAY + 0.6) / 60:.0f} minutes")


# ---------------------------------------------------------------------- fetch
TITLE_FIELDS = ["job_id", "generation", "timestamp", "source_url", "http_status",
                "page_status", "job_title", "screen_decision", "matched_terms",
                "excluded_terms", "african_language", "other_language",
                "market_named", "city_named", "country_of_city",
                "saved_html", "notes"]


def title_of(h):
    m = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]*)"', h)
    if not m:
        m = re.search(r"<title[^>]*>(.*?)</title>", h, flags=re.S | re.I)
    if not m:
        return ""
    t = htmllib.unescape(m.group(1))
    t = re.sub(r"\s*[|\-–—]\s*(TikTok|Life at TikTok|ByteDance)\s*$", "", t)
    return re.sub(r"\s+", " ", t).strip()


def page_state(h, title):
    """Classify a capture from the title, not from the body text.

    An earlier version tested for the literal "404 Page not found" and
    classified almost every healthy page as missing. The reason is worth
    recording: lifeattiktok.com ships the whole site's CMS payload, including
    the not-found route's copy, on every single page. The string is present
    once on a perfectly good job posting. Only the server-rendered title
    distinguishes a live capture from a dead one."""
    if len(h) < 12000:
        return "js_shell"
    if not title.strip():
        return "no_title"
    if title.strip().lower() in GENERIC_TITLES:
        return "not_found"
    return "detail"


def fetch(limit, only_gen, retry_failed=False):
    reg = PROJECT_ROOT / "source_registry" / "tiktok_wayback_snapshots.csv"
    if not reg.exists():
        sys.exit("run --discover-only first")
    out = PROJECT_ROOT / "data_processed" / "tiktok_title_registry.csv"
    raw = PROJECT_ROOT / "data_raw" / "tiktok_wayback"
    out.parent.mkdir(parents=True, exist_ok=True)
    raw.mkdir(parents=True, exist_ok=True)

    # A 3,966-page run will hit transient Archive errors. Rather than leaving
    # them in the file as permanent gaps, --retry-failed drops those rows so
    # the ordinary resume logic picks them up again.
    if retry_failed and out.exists():
        with out.open(encoding="utf-8-sig") as fh:
            rows = list(csv.DictReader(fh))
        keep = [r for r in rows if r["page_status"] != "fetch_failed"]
        dropped = len(rows) - len(keep)
        with out.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=TITLE_FIELDS)
            w.writeheader()
            w.writerows(keep)
        print(f"cleared {dropped} failed rows for retry")

    done = set()
    if out.exists():
        with out.open(encoding="utf-8-sig") as fh:
            done = {r["job_id"] for r in csv.DictReader(fh)}
        print(f"resuming: {len(done)} already fetched")

    todo = []
    with reg.open(encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            if r["job_id"] in done:
                continue
            if only_gen and r["generation"] != only_gen:
                continue
            todo.append(r)
    if limit:
        todo = todo[:limit]
    print(f"to fetch: {len(todo)}")

    new = not out.exists()
    fh_out = out.open("a", encoding="utf-8", newline="")
    w = csv.DictWriter(fh_out, fieldnames=TITLE_FIELDS)
    if new:
        w.writeheader()

    stats = Counter()
    try:
        for i, r in enumerate(todo, 1):
            url = SNAPSHOT.format(ts=r["timestamp"], url=r["original"])
            status, body, note = 0, "", ""
            for attempt in range(MAX_RETRIES):
                try:
                    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
                    status = resp.status_code
                    if status == 429:
                        time.sleep(BACKOFF * (2 ** attempt))
                        continue
                    body = resp.text
                    break
                except Exception as e:
                    note = str(e)[:120]
                    time.sleep(BACKOFF * (2 ** attempt))

            title = title_of(body) if body else ""
            pstate = page_state(body, title) if body else "fetch_failed"
            decision, matched, excluded, afr, oth = screen(title)
            mkts = markets_in(title)
            cits = cities_in(title)
            if pstate != "detail":
                decision = "unusable"

            saved = ""
            if decision == "include" and pstate == "detail":
                p = raw / f"{r['timestamp']}_{r['job_id']}.html"
                p.write_text(body, encoding="utf-8")
                saved = p.name

            stats[pstate] += 1
            stats[f"screen_{decision}"] += 1
            if afr:
                stats["african_language_title"] += 1

            w.writerow({
                "job_id": r["job_id"], "generation": r["generation"],
                "timestamp": r["timestamp"], "source_url": r["original"],
                "http_status": status, "page_status": pstate,
                "job_title": title, "screen_decision": decision,
                "matched_terms": "; ".join(matched),
                "excluded_terms": "; ".join(excluded),
                "african_language": "; ".join(afr),
                "other_language": "; ".join(oth),
                "market_named": "; ".join(mkts),
                "city_named": "; ".join(cits),
                "country_of_city": "; ".join(dict.fromkeys(CITIES[c] for c in cits)),
                "saved_html": saved, "notes": note,
            })
            fh_out.flush()

            if i % 25 == 0 or i == len(todo):
                print(f"  {i}/{len(todo)}  include={stats['screen_include']} "
                      f"detail={stats['detail']} shell={stats['js_shell']} "
                      f"notfound={stats['not_found']}")
            time.sleep(FETCH_DELAY)
    except KeyboardInterrupt:
        print("\ninterrupted; progress is saved, rerun --fetch to resume")
    finally:
        fh_out.close()

    print(f"\nwrote {out}")
    for k, n in stats.most_common():
        print(f"   {n:6d}  {k}")


# --------------------------------------------------------------------- report
def report():
    path = PROJECT_ROOT / "data_processed" / "tiktok_title_registry.csv"
    if not path.exists():
        sys.exit("run --fetch first")
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    print(f"rows: {len(rows)}")

    print("\npage state:")
    for k, n in Counter(r["page_status"] for r in rows).most_common():
        print(f"   {n:6d}  {k}")

    print("\nscreen decision:")
    for k, n in Counter(r["screen_decision"] for r in rows).most_common():
        print(f"   {n:6d}  {k}")

    inc = [r for r in rows if r["screen_decision"] == "include"]
    print(f"\nTrust and Safety postings: {len(inc)}")

    print("\nmost common matched terms:")
    c = Counter(t for r in inc for t in r["matched_terms"].split("; ") if t)
    for t, n in c.most_common(20):
        print(f"   {n:5d}  {t}")

    print("\ncapture year of screened-in postings:")
    for y, n in sorted(Counter(r["timestamp"][:4] for r in inc).items()):
        print(f"   {y}: {n}")

    print("\n--- language-specific moderation roles ---")
    afr = [r for r in rows if r["african_language"]]
    oth = [r for r in rows if r["other_language"] and not r["african_language"]]
    print(f"titles naming an AFRICAN language : {len(afr)}")
    for r in afr[:40]:
        print(f"   {r['african_language']:20s} | {r['job_title'][:70]}")
    print(f"\ntitles naming any other language  : {len(oth)}")
    c = Counter(t for r in oth for t in r["other_language"].split("; ") if t)
    for t, n in c.most_common(30):
        print(f"   {n:5d}  {t}")

    print("\n--- market named in the title (a market signal, NOT a location) ---")
    c = Counter(m for r in inc for m in r.get("market_named", "").split("; ") if m)
    for t, n in c.most_common(30):
        print(f"   {n:5d}  {t}")
    afr_mkt = [r for r in inc if "Africa" in r.get("market_named", "")]
    print(f"\nTrust and Safety titles naming an African market: {len(afr_mkt)}")
    for r in afr_mkt[:30]:
        print(f"   {r['job_title'][:80]}")

    print("\n--- office named in the title (a real location, where present) ---")
    with_city = [r for r in inc if r.get("city_named")]
    print(f"screened-in postings naming an office: {len(with_city)} of {len(inc)}")
    for t, n in Counter(r["city_named"] for r in with_city).most_common(25):
        print(f"   {n:5d}  {t}")
    print("\ncountry of the named office:")
    for t, n in Counter(r["country_of_city"] for r in with_city).most_common(25):
        print(f"   {n:5d}  {t}")

    print("\n--- the key cross-tabulation ---")
    print("language-specific roles, against the office named in the same title:")
    lang_rows = [r for r in inc if r["african_language"] or r["other_language"]]
    afr_lang = [r for r in lang_rows if r["african_language"]]
    print(f"\nAFRICAN-language roles: {len(afr_lang)}")
    for r in afr_lang:
        where = r.get("city_named") or r.get("market_named") or "(no place named)"
        print(f"   {r['african_language'][:18]:18s} -> {where[:28]:28s} | {r['job_title'][:60]}")
    in_africa = [r for r in afr_lang
                 if any(CITIES.get(c) in AFRICAN_COUNTRIES
                        for c in r.get("city_named", "").split("; ") if c)]
    print(f"\nAfrican-language roles based at an African office: {len(in_africa)}")
    for r in in_africa:
        print(f"   {r['city_named']} | {r['job_title'][:70]}")

    print("\nexcluded by the technical-integrity filter:")
    exc = [r for r in rows if r["screen_decision"] == "exclude"]
    for r in exc[:25]:
        print(f"   {r['excluded_terms']:24s} | {r['job_title'][:70]}")
    print(f"   ({len(exc)} total)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--discover-only", action="store_true")
    ap.add_argument("--fetch", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--retry-failed", dest="retry_failed", action="store_true",
                    help="drop rows that failed to fetch, so --fetch retries them")
    ap.add_argument("--from", dest="date_from", type=int, default=2019)
    ap.add_argument("--to", dest="date_to", type=int, default=2026)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--generation", default="lifeattiktok",
                    help="restrict fetching to one site generation; "
                         "'' means all three")
    args = ap.parse_args()

    if args.discover_only:
        discover(args.date_from, args.date_to)
    elif args.fetch:
        fetch(args.limit, args.generation, args.retry_failed)
    elif args.report:
        report()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
