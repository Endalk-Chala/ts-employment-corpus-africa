# Google/YouTube arm: reconstructed from the Internet Archive

7 September 2026. Rebuilt from archived career pages covering 2023–2026, using
the method the article already describes for Meta.

## Collection funnel

| Stage | Count |
|---|---:|
| CDX captures across three Google careers domains | 41,656 |
| Distinct archived pages | 18,003 |
| Pages that are individual job postings | 15,092 |
| Screened in as Trust and Safety candidates | 296 |
| Successfully fetched | 292 |
| **Usable job-detail pages** | **117** |

Four fetches failed on transient Archive connection errors. Of the 292 retrieved,
139 were "Job not found" and 36 were JavaScript shells; see below.

## How screening worked

The job title is carried in the URL slug:

```
.../jobs/results/100350864866058950-policy-escalation-specialist-trust-and-safety-youtube
```

So screening ran on the snapshot registry before anything was downloaded. Thirty
inclusion terms covering the Trust and Safety vocabulary, plus exclusion terms
for the same false-positive family found in the Meta arm: `environmental-health`,
`fire-life-safety`, `device-integrity`, `agi-safety`, `data-center`.

**No candidate tripped an exclusion term.** Screening at the URL level caught the
technical-integrity problem before it entered the corpus, rather than after, which
is an improvement on the Meta arm where ten such postings had to be removed by
hand.

Every decision, kept or dropped, with its triggering terms, is recorded in
`data_processed/google_ts_candidates.csv`.

Most common matched terms: `trust-and-safety` (187), `abuse-analyst` (27),
`scaled-abuse` (24), `policy-specialist` (22), `threat-intelligence` (19),
`policy-enforcement` (17).

## Why only 117 of 292 are usable

This is the most important methodological finding of the exercise.

**139 captures say "Job not found. This job may have been taken down."** The
Archive crawled the URL after Google had removed the posting. A capture existing
does not mean the posting was live when it was taken. Any Wayback-based
employment corpus that counts captures rather than checking page state will
overcount, possibly badly.

**36 captures are JavaScript shells**, roughly 10 KB, almost all from 2023. The
careers site was client-rendered then and the Archive stored the empty frame.
Only the title survives, sometimes not even that.

The 117 remaining are fully rendered pages, mostly from 2025 onward, carrying
title, employer, location and description.

## How location was recovered

The archived pages contain no schema.org JSON-LD, and the Open Graph tags carry
title and description but no location. The location is in the job-detail block,
where Google uses material-icon names as field labels:

```
corporate_fare YouTube   place San Bruno, CA, USA   bar_chart Early
```

The extractor locates the detail heading (`h2.p1N2lc`), flattens that block, and
uses the icon words as delimiters.

**This matters for correctness, not just convenience.** The same page carries a
"similar jobs" rail listing other roles and their cities. Harvesting city names
from the page as a whole would attach the wrong location to the posting. That is
the same class of error that produced "Dublin, United Kingdom" and "Shanghai,
Taiwan" in the earlier Meta summaries.

## Results

Primary country, taken as the first office listed:

| Country | Reconstructed | Published |
|---|---:|---:|
| United States | 63 (53.8%) | 111 (72%) |
| India | 23 (19.7%) | within "Other" |
| **Ireland** | **9** | **9** |
| **Singapore** | **7** | **0** |
| United Arab Emirates | 4 | — |
| Switzerland | 4 | — |
| Spain | 3 | — |
| United Kingdom, Canada, Netherlands, Thailand | 1 each | — |
| **Africa** | **0** | **0** |

Employer split within the corpus: Google 79, YouTube 38.

Top offices: San Bruno 20, Hyderabad 18, Dublin 9, Singapore 7, Seattle 6,
Washington DC 5, Sunnyvale 5, Zürich 4, Mountain View 4, Dubai 3.

## Three findings

**1. Ireland reproduces exactly.** Nine, against a published nine. Combined with
the Meta arm, where Ireland came out at seven against a published seven, that is
two independent reconstructions hitting the same variable exactly. Ireland has
been stable under every filter at every stage of both. It is the most robust
number in the study.

**2. Africa is zero.** Confirmed from independently rebuilt data.

A caution attaches to this. An earlier version of the Africa detector matched
"Addison, TX" against the stem "addis" and reported a false Africa role. The
pattern is now word-boundary anchored. In a paper whose headline finding is an
absence, a substring false positive is the single most damaging error available,
and the screen should be checked with that in mind before publication.

**3. Google's Singapore figure needs correcting.** The published Figure 2 shows
Google with zero Singapore roles. The reconstruction finds seven Trust and Safety
roles located there. Singapore is one of the article's three hub jurisdictions,
so a platform's presence in it is not incidental detail.

## Caveats to state in the methods section

**Archive coverage is uneven and not a hiring signal.** Candidates by earliest
capture year: 2023: 64, 2024: 32, 2025: 180, 2026: 20. The 2025 peak reflects how
hard the Archive crawled the careers site that year, not Google's hiring.

**The reconstruction is a subset, not the population.** 117 usable postings
against a published 154. Nothing here establishes what the original 154 contained.

**Multi-location postings are 28 of 117**, roughly a quarter. Country counts must
be computed from a single primary location per posting, or the country chart will
again exceed the platform total.

**This is not the March 2026 corpus** and should not be presented as it. It is an
independent reconstruction from archived material covering the same window.

## Files

| File | Contents |
|---|---|
| `source_registry/google_wayback_snapshots.csv` | 18,003 archived pages |
| `data_processed/google_ts_candidates.csv` | every screening decision |
| `data_raw/google_wayback/*.html` | 292 saved captures |
| `data_processed/google_wayback_postings.csv` | 292 rows, 117 with location |
| `scripts/collect_wayback_platform.py` | CDX discovery |
| `scripts/screen_and_fetch_candidates.py` | screening and fetching |
| `scripts/reextract_google_pages.py` | offline re-extraction |

## Optional next step

The 175 unusable pages have no alternative capture in the registry, because
discovery kept one capture per job ID. The Archive holds 41,656 captures against
18,003 distinct pages, so most jobs were captured several times. Modifying
discovery to retain every timestamp, then retrying failed jobs against a later
capture, could raise the usable yield materially. Worth doing before the
reconstruction is treated as final.
