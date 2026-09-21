# Codebook

Every field in every released file, what it means, how it was assigned, and
what it can and cannot support.

The corpus is reconstructed from Internet Archive captures of three career
sites. Nothing here is inferred from a company's reputation, from other
postings by the same employer, or from background knowledge of what a role
probably involves. Where a value could not be recovered from the captured page,
the field is blank, and blank is never silently read as a negative. The
distinction between "the advertisement says no" and "the capture does not say"
is the single most important thing in this document.

Contents:

- [The evidence ladder governs everything](#the-evidence-ladder-governs-everything)
- [`data/public/unified_corpus.csv`](#datapublicunified_corpuscsv)
- [`data/public/unified_country_table.csv`](#datapublicunified_country_tablecsv)
- [`data/public/screening_tiktok.csv`](#datapublicscreening_tiktokcsv)
- [`data/public/screening_google.csv`](#datapublicscreening_googlecsv)
- [`data/public/screening_meta.csv`](#datapublicscreening_metacsv)
- [`source_registry/`](#source_registry)
- [Coding rules in full](#coding-rules-in-full)
- [Reliability](#reliability)
- [What this corpus cannot answer](#what-this-corpus-cannot-answer)

---

## The evidence ladder governs everything

The three arms did not survive equally in the Archive, and the corpus does not
pretend otherwise. `evidence_level` records how much of each advertisement was
recoverable, and it sets the ceiling on what any claim about that row can rest
on.

| `evidence_level` | Postings | What the capture yielded | What a row can support |
|---|---:|---|---|
| `full_text` | 39 | schema.org JSON-LD, including the body | claims about what the advertisement says |
| `detail_only` | 117 | rendered detail block: title, office, no body | claims about title and location |
| `title_only` | 580 | job title alone; 60 of these also state a location | claims about titles, and about location for those 60 |

A fourth value, `detail_no_location`, exists in the scheme for rendered pages
carrying no location field. No posting in this corpus takes it.

Three consequences follow, and they are load-bearing:

1. A statement of the form "no advertisement requires X" is a statement about
   **39 postings at full depth**, not 736. Say which.
2. Every geographic percentage has **216** as its denominator, the postings
   with a recoverable location, not 736.
3. The language finding is a claim about **job titles**, and is stronger for
   being stated that way. A language named in a title is a more deliberate
   signal than one buried in a requirements list.

This asymmetry also explains why the Meta screening file carries coded fields
the other two do not. Those codes need body text. Where body text did not
survive, the codes are not estimated, they are absent.

---

## `data/public/unified_corpus.csv`

736 rows, one per screened-in posting. Deduplicated by `job_id` within
platform. This is the analysis file.

### Identification and provenance

| Field | Type | Values / definition |
|---|---|---|
| `platform` | string | `TikTok` (580), `Google/YouTube` (117), `Meta` (39). The collection arm. |
| `job_id` | string | The platform's own posting identifier, taken from the URL. The deduplication key. Unique across the file. |
| `source_url` | string | The advertisement's own URL, not the Archive wrapper. Paste it into the Wayback Machine with `capture_date` to retrieve the same page. |
| `capture_date` | ISO date | The date of the Archive snapshot the row was built from. Range 2023-08-01 to 2026-09-04. **This is not the date the job was advertised.** |
| `employer` | string | `TikTok` (580), `Google` (79), `Meta` (39), `YouTube` (38). Distinguishes Google from YouTube inside the Google/YouTube arm; `platform` keeps them together for analysis. |

`capture_date` deserves emphasis. Captures are heavily concentrated in 2025
(565 of 736) because that is when the Archive crawled these pages most, not
because that is when the platforms hired most. A capture is not an observation.
Only Meta postings carry a true advertisement date, and it is not in this file;
it is `date_posted` in `screening_meta.csv`.

### Position

| Field | Type | Values / definition |
|---|---|---|
| `job_title` | string | As advertised, unedited. 696 distinct across 736 rows. |
| `location_raw` | string | The location string as advertised, unedited, including multi-office strings. Blank for 520 rows where no location survived. |
| `primary_city` | string | The first site component of `location_raw`, verbatim. Not normalised: Meta rows give a bare city (`Dublin`), Google/YouTube rows give the site as advertised (`Mountain View, CA, USA`). Use `primary_country` for any grouping. |
| `primary_country` | string | The first country named in `location_raw`. 16 countries occur: Brazil, Canada, China, Germany, India, Ireland, Mexico, Morocco, Netherlands, Singapore, Spain, Switzerland, Thailand, United Arab Emirates, United Kingdom, United States. |
| `region_group` | string | `Hub` (158), `Other` (57), `Africa` (1). Blank where no location. See the rule below. |
| `multi_location` | `yes` / `no` | `yes` (31 rows) means `location_raw` names more than one site. Never blank. |

**The location rule.** Where a posting names more than one site, the first is
taken as its location, and `multi_location` is set to `yes` so the choice stays
visible and every such row can be pulled out and rechecked. This affects 31 of
the 216 located postings. Most additional sites lie in the same country as the
first, so the rule changes few country assignments, and none that bears on the
findings. No posting in the corpus advertises a remote or hybrid arrangement.

Two shapes of multi-site row exist, and they differ by arm. For Google/YouTube
and TikTok, `location_raw` carries the whole advertised string, semicolon
separated, sometimes ending in Google's own `+N more`. For Meta, `location_raw`
carries the primary site only and the flag is set from Meta's structured
`country_count`; the full list for those rows is `all_countries` in
`screening_meta.csv`. Three rows are therefore flagged `yes` while showing a
single site here. That is the Meta shape, not an error.

**The `region_group` rule.** `Hub` is the United States, Ireland or Singapore,
the three jurisdictions the article treats as regulatory hubs. `Africa` is any
African country. `Other` is everything else. The grouping is applied to
`primary_country` only, so it inherits the first-site rule above.

### Screening and evidence

| Field | Type | Values / definition |
|---|---|---|
| `evidence_level` | string | `title_only` (580), `detail_only` (117), `full_text` (39). See the ladder above. |
| `screen_decision` | string | `include` for every row. Present so the file has the same shape as the screening registries, where the excluded rows live. |
| `matched_terms` | string | The inclusion term or terms that admitted the posting, semicolon separated, as matched. 97 distinct combinations. Most common: `trust & safety` (121), `trust and safety` (81), `governance` (75), `trust-and-safety` (68), `integrity` (56). A trailing `*` marks a stem, so `content moderat*` matched both "Content Moderator" and "Content Moderation". |

`matched_terms` is what makes a screening decision contestable. A reader who
thinks `governance` is too broad can filter those 75 rows out and recompute
every number in the article.

### Coded signals

These three are coded from the job title, the only field available for every
row. All are blank where the title names nothing, and **blank means the title
does not name one**, not that the role does not involve one.

| Field | Type | Values / definition |
|---|---|---|
| `african_language` | string | A sub-Saharan African language named in the title. 5 rows: `hausa` (3), `swahili` (2). Lowercase. |
| `other_language` | string | Any other human language named in the title. 74 rows, 29 distinct languages. Lowercase. Semicolon separated where a title names more than one. |
| `market_named` | string | A country, region or market scope named in the title. 97 rows, 24 distinct values, including `Africa`, `MENA`, `EMEA`, `APAC`, `LATAM` and individual countries. Capitalised as the title writes it. |

**Counting note, because two conventions give two answers.** 79 postings name at
least one language: 5 African, 74 other. Counting each posting by its **first
named** language gives **31** distinct languages, and that is how the ranked
language figure is drawn, so a reader who counts its bars gets 31. Counting
**every** language named gives **33**, because two postings name more than one.
Neither is wrong. Any number quoted from this field should say which it uses.

A generic phrase such as "additional languages an advantage" is not a language
signal. It names no language and so creates no verifiable capacity claim.

`market_named` records **stated market scope**, which is not location. A Dublin
post covering sub-Saharan Africa is Africa-scoped and Dublin-located, and the
gap between those two columns is the article's argument.

### Notes

| Field | Type | Values / definition |
|---|---|---|
| `notes` | string | Semicolon-separated `key=value` pairs. Never blank. |

Three keys occur:

| Key | Rows | Values |
|---|---:|---|
| `page_status` | 697 | `detail` |
| `role_class` | 39 | `core_integrity` (36), `policy_enforcement` (3) |
| `signal` | 39 | `high` |

`role_class` and `signal` appear only on the 39 Meta rows, because they are
coded from body text. See `screening_meta.csv` for their definitions and for
the other codes in that family.

---

## `data/public/unified_country_table.csv`

16 rows, one per country with at least one located posting. A convenience
table, derivable from `unified_corpus.csv`, published so that the country
figures in the article can be checked without rerunning anything.

| Field | Type | Definition |
|---|---|---|
| `country` | string | As in `primary_country`. |
| `region` | string | `Hub` (3), `Other` (12), `Africa` (1). |
| `meta` | integer | Located Meta postings in that country. |
| `google_youtube` | integer | Located Google/YouTube postings. |
| `tiktok` | integer | Located TikTok postings. |
| `total` | integer | Sum of the three. |

Each posting is counted once, under its `primary_country`. The three platform
columns sum to `total`, and the `total` column sums to 216. If any of that
fails to hold, the release is broken; `assemble_release.py` checks it.

---

## `data/public/screening_tiktok.csv`

3,966 rows, one per TikTok job identifier considered. The full screening record
for the arm that contributes 580 of the corpus.

| Field | Type | Values / definition |
|---|---|---|
| `job_id` | string | TikTok's posting identifier. Unique. |
| `generation` | string | `lifeattiktok` for all rows in this file. TikTok has run three career sites; this file covers the current one. The other two appear in the source registry. |
| `timestamp` | string | Archive capture timestamp, `YYYYMMDDhhmmss`. |
| `source_url` | string | The posting URL as captured. |
| `http_status` | integer | The Archive's status for the fetch: `200` (3,942), `404` (16), `0` (8, meaning the fetch itself failed). |
| `page_status` | string | What the fetched page actually was: `detail` (3,663), `js_shell` (295), `fetch_failed` (8). |
| `job_title` | string | From the server-rendered `<title>`. Blank for 287 rows where no title survived. |
| `screen_decision` | string | `drop` (3,028), `include` (580), `unusable` (303), `exclude` (55). |
| `matched_terms` | string | Inclusion terms that fired, semicolon separated. |
| `excluded_terms` | string | Exclusion terms that fired: `site reliability` (46), `data center` (4), `food safety` (2), `hardware` (1), `datacenter` (1), `fire safety` (1). |
| `african_language`, `other_language`, `market_named` | string | As in the unified corpus, coded from the title. |
| `city_named` | string | A city named in the title. 363 rows, 36 distinct. |
| `country_of_city` | string | The country that city sits in. Assigned from a fixed city-to-country lookup, not inferred per posting. |
| `notes` | string | Free text. Mostly fetch errors for the rows that failed. |

**The four screening decisions are not interchangeable.**

| Decision | Meaning |
|---|---|
| `include` | An inclusion term matched and no exclusion term did. Enters the corpus. |
| `exclude` | An exclusion term matched. A deliberate rejection of a role the term list would otherwise have caught. |
| `drop` | No inclusion term matched. Not a Trust and Safety posting as this study defines one. |
| `unusable` | The capture yielded no usable title: a JavaScript shell, a 404, or a failed fetch. **Not a judgement about the role**, and it must not be counted as evidence that the role was not Trust and Safety. |

`page_status` carries a finding of its own. `lifeattiktok.com` ships its entire
content-management payload on every route, including the copy for the
not-found page, so a body-text test for "page not found" matches on a perfectly
healthy posting. Only the server-rendered `<title>` distinguishes a live capture
from a dead one. Any employment corpus built from this site with a body-text
test will be wrong in a way that is invisible.

---

## `data/public/screening_google.csv`

15,092 rows, one per Google/YouTube capture considered.

| Field | Type | Values / definition |
|---|---|---|
| `job_id` | string | Google's posting identifier from the URL. Unique. |
| `title` | string | Job title where recoverable. Blank for 3,497 rows. |
| `timestamp` | string | Archive capture timestamp, `YYYYMMDDhhmmss`. |
| `original` | string | The posting URL as captured. |
| `is_candidate` | `yes` / `no` | `yes` (296) means an inclusion term matched and no exclusion term did. These were then fetched and re-extracted; 117 survived into the corpus. |
| `matched_terms` | string | Inclusion terms that fired, hyphenated, semicolon separated. 58 distinct combinations. |
| `exclusion_terms` | string | Exclusion terms that fired. 700 rows. |

The gap between 296 candidates and 117 corpus rows is not attrition through
judgement. It is the "Job not found" problem: of 292 archived Google career
pages retrieved, 139 returned Google's own removal notice, because the Archive
crawled the URL after the posting came down, and a further 36 were JavaScript
shells from the era when the site was client-rendered.

**The exclusion list, and why it exists.** "Integrity" and "safety" have
engineering senses with nothing to do with content governance. The exclusions
are dominated by `data-center`, which fires on 633 of the 700 excluded rows,
461 of them on its own, followed
by `electrical`, `mechanical`, `construction`, `structural`,
`environmental-health`, `health-and-safety`, `fire-life-safety`,
`signal-integrity`, `power-integrity`, `device-integrity` and
`hardware-integrity`. Three AI-safety terms, `frontier-safety`,
`agi-safety` and `safety-alignment`, are also excluded: model alignment
research is a different object from platform content governance, and folding it
in would inflate the counts with work that has no bearing on the argument.

Every exclusion is by rule and is logged. Nothing is dropped silently.

---

## `data/public/screening_meta.csv`

613 rows, one per Meta posting considered. This file carries a coding layer the
other two arms do not, because Meta's postings carried structured JSON-LD and
so their body text survived. Nothing here is estimated for the other arms.

### Provenance

| Field | Type | Values / definition |
|---|---|---|
| `job_id` | string | Meta's posting identifier. Unique. |
| `job_title` | string | As advertised. |
| `city`, `country` | string | As advertised. 51 cities, 24 countries. |
| `region` | string | `North America` (454), `Western Europe` (42), `Unknown` (36), `East Asia` (26), `Southeast Asia` (24), `South Asia` (19), `Middle East & North Africa` (7), `Latin America` (2), and smaller. |
| `all_countries` | string | Every country the posting names, semicolon separated. |
| `country_count` | integer | How many: `1` (599), `2` (13), `3` (1). |
| `date_posted` | ISO datetime | **The advertisement's own date**, from JSON-LD. The only true posting date anywhere in the corpus. Range May 2023 to February 2026. |
| `capture_date` | string | Archive capture date, `YYYYMMDD`. |
| `capture_year` | integer | `2025` (433), `2026` (180). |
| `employment_type` | string | `Full-time` (556), `Internship` (57). |
| `original_url` | string | The posting's own URL. |

### Screening and coding

| Field | Type | Values / definition |
|---|---|---|
| `ts_term_count` | integer | How many distinct Trust and Safety terms occur in the text. `0` for 563 rows. |
| `ts_term_hits` | string | Which ones. Blank where none. |
| `role_class` | string | `non_integrity` (527), `core_integrity` (46), `possible_integrity` (37), `policy_enforcement` (3). |
| `signal_strength` | string | `none` (527), `high` (49), `low` (37). Derived from `ts_term_count` and where the terms fall. |
| `security_relevant` | `yes` / `no` | `yes` (86) where the role bears on platform security governance as the article defines it. |
| `harm_exposure_flag` | `yes` / `no` | `yes` (12) where **the advertisement itself** discloses exposure to distressing material: graphic or objectionable content, child exploitation, self-injury, animal abuse, or an explicit wellbeing or resilience provision. Coded from the employer's own disclosure, so it measures what platforms admit about the work rather than what the work involves. |
| `market_specific_flag` | `yes` / `no` | `yes` (114) where the posting names a specific market or region. |
| `technical_integrity_false_positive` | `yes` / `no` | `yes` (10) where a term matched in its engineering sense and the posting was rejected on that basis. Published so the exclusions can be inspected rather than trusted. |
| `in_final_subset` | `yes` / `no` | `yes` (39). These are the Meta rows in `unified_corpus.csv`. |

`role_class` values:

| Value | Definition |
|---|---|
| `core_integrity` | Integrity, trust and safety, or content governance is the role's stated function. |
| `policy_enforcement` | The enforcement and escalation apparatus: policy enforcement, escalations, appeals, abuse investigations, risk or safety operations. |
| `possible_integrity` | Trust and Safety vocabulary occurs but is not the role's stated function. **Not included** in the corpus. Published so the boundary can be argued with. |
| `non_integrity` | No Trust and Safety function. |

The 37 `possible_integrity` rows are the honest edge of the corpus. A reader who
thinks the boundary is drawn too tightly can add them back and see what moves.

---

## `source_registry/`

Every archived page discovered, before any screening. This is the discovery
record: it says what the Archive held, independently of what this study did
with it.

**`google_wayback_snapshots.csv`**, 18,003 rows, from the CDX Server API.

| Field | Definition |
|---|---|
| `timestamp` | Capture timestamp, `YYYYMMDDhhmmss`. |
| `original` | The URL as captured. |
| `statuscode` | `200` for all rows; the query filtered on it. |
| `digest` | The Archive's content digest. Identical digests mean identical captures. |
| `mimetype` | `text/html` for all rows. |
| `job_id` | Parsed from the URL. Blank for 2,911 rows that are listing pages rather than postings. |

18,003 captures reduce to 15,092 distinct job identifiers, which is what
`screening_google.csv` screens.

**`tiktok_wayback_snapshots.csv`**, 7,307 rows, one per distinct job identifier
across all three TikTok career-site generations.

| Field | Definition |
|---|---|
| `job_id` | TikTok's posting identifier. |
| `generation` | `lifeattiktok` (3,966), `jobs_bytedance` (1,894), `careers_tiktok` (1,447). |
| `timestamp` | The capture used, `YYYYMMDDhhmmss`. |
| `original` | The URL as captured. |
| `n_captures` | How many captures the Archive holds for this posting. Ranges 1 to 26; 5,104 postings have exactly one. |

Only the `lifeattiktok` generation was screened and fetched. The other two are
recorded here because a reader should be able to see what was left on the table
and judge whether it matters.

---

## Coding rules in full

### Screening terms are matched with word boundaries

An earlier unanchored version matched "Addison, TX" against the stem `addis` and
produced a phantom Africa role. In a study whose central finding is an absence,
a substring false positive is the most damaging error available, so matching is
anchored at word boundaries and a stem is marked explicitly with `*`. Spaces in
a term match spaces or hyphens, so `trust and safety`, `trust-and-safety` and
`Trust & Safety` are all reachable, each recorded as it matched.

The term list was widened once, on 9 September 2026, after an audit of the
dropped TikTok titles. See `CHANGELOG.md` for exactly what was added, what was
considered and rejected, and what moved as a result.

### Blank is not a negative

Every field in this corpus is either populated from the capture or blank.
Blank means the capture did not yield it. It never means the advertisement said
no.

This matters most for the three title-coded signals. 520 rows have no location,
not because the roles are unlocated but because a title-only capture does not
carry one. Treating those as "not in Africa" would be a category error, and it
would run the wrong way for the article's argument.

The same discipline applies to the study's central claim, and is worth stating
in the terms the source-tracking work first put it: **do not code "no posting
found" as "no capacity exists."** Code it as "no publicly identifiable
Africa-facing Trust and Safety role found in the sources searched", and nothing
stronger.

### Language is read from the title

Not from a requirements list, because for 580 of 736 postings there is no
requirements list to read. This is a limitation that turns out to be a
strength: a language named in a job title is a more deliberate signal than one
buried in a body, so the language finding rests on the platforms' own framing of
what the role is for.

---

## Reliability

Codes proposed by script must be reviewed by a human. Because every proposed
code carries its trigger string, in `matched_terms` or in `notes`, review is a
confirmation task rather than a re-reading task.

Two cautions about what any reliability statistic here would measure:

- **Do not measure agreement on the screening itself.** It is a deterministic
  word-boundary rule. A human agreeing with a regular expression tells a reader
  nothing about the construct.
- **Measure the places where judgement enters.** Those are the screen-in
  decision on ambiguous titles, the Africa-scope coding, and the language
  coding. A second coder should work from the titles and text without seeing
  the proposed codes; otherwise the statistic measures the dictionaries rather
  than the construct, and belongs in a methods appendix labelled as such.

---

## What this corpus cannot answer

Stated plainly, because a codebook that only describes what a dataset holds
invites misuse of what it does not.

- **Headcount.** Job advertisements record hiring intent, not staffing. A
  posting may be filled, refilled, cancelled, or reposted, and none of that is
  visible here.
- **Vendor and contractor labour.** Outsourced moderation does not appear in a
  platform's own career pages at all. The corpus sees declared, direct
  employment and nothing else, which is precisely why the article treats
  contractor arrangements through litigation and documentary evidence instead.
- **Automation.** No advertisement discloses how much enforcement is automated.
  The gap between enforcement volume and declared human capacity is an
  inference, and the article marks it as one.
- **Hiring over time.** Captures cluster in 2025 because of Archive crawl
  intensity. The corpus is evidence of where roles were located across the
  window, not a time series.
- **What an advertisement says, for 697 of 736 rows.** Only the 39 `full_text`
  rows support that.

---

## Changing the scheme

Any change to a term list or a coding rule changes what the numbers mean.
Record it in `CHANGELOG.md` with the date, the reason, and whether the corpus
was rebuilt. The 9 September 2026 entry is the model to follow.
