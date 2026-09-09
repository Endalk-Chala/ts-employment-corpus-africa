# Trust and Safety employment corpus

Replication materials for *Governing at a distance: Offshored trust and safety,
security assemblages, and the African localisation gap* (Chala, forthcoming,
*Internet Policy Review*).

This repository contains the corpus, the collection code, the screening record
and the figure scripts. It does not contain interview material, and it does not
contain the archived pages themselves. Both exclusions are explained below and
enforced by `.gitignore`.

---

Canonical location: <https://github.com/Endalk-Chala/ts-employment-corpus-africa>

## What the corpus is

736 Trust and Safety and governance-adjacent job advertisements from Meta,
Google/YouTube and TikTok, reconstructed from Internet Archive captures.

| Platform | Postings | What survived in the capture |
|---|---:|---|
| TikTok | 580 | Job title only |
| Google/YouTube | 117 | Rendered detail block, including office |
| Meta | 39 | Full schema.org posting data and body text |
| **Total** | **736** | |

The three arms do not observe the same thing, and the corpus does not pretend
otherwise. Every row carries an `evidence_level` field:

| Level | What survived | Postings |
|---|---|---:|
| `full_text` | Structured posting data and description | 39 |
| `detail_only` | Rendered detail block with a location | 117 |
| `title_only` | Job title alone | 580 |

A fourth level, `detail_no_location`, exists in the coding scheme for rendered
pages carrying no location field. No posting in this corpus took that value.

**Any claim about geography must state which evidence levels it draws on.**
216 of the 736 postings have a recoverable location. That is the denominator for
every geographic figure in the article, and it is not 736.

## Observation window

Captures run from **1 August 2023 to 4 September 2026**. Meta's postings carry
their own advertisement dates, from 24 May 2023 to 26 February 2026.

Discovery searched archived captures back to 2019. Nothing before August 2023
yielded a usable posting page: earlier snapshots are JavaScript shells or record
postings already removed. Captures are unevenly distributed, with 2025 heavily
overrepresented. **That reflects Internet Archive crawl intensity, not platform
hiring activity**, and should not be read as a hiring trend.

## Headline results

Computed over the 216 located postings:

| | Postings | Share |
|---|---:|---:|
| Three hubs (United States, Ireland, Singapore) | 158 | 73% |
| United States | 116 | 54% |
| India | 23 | 11% |
| Ireland | 21 | 10% |
| Singapore | 21 | 10% |
| Africa | 1 | 0.5% |

The single Africa-located posting is a Talent Acquisition Partner for Trust and
Safety in Casablanca: a role hired to recruit Trust and Safety staff rather than
to perform Trust and Safety work.

Five postings in 736 name an African language, three Hausa and two Swahili. Two
of the five are located in Dublin; the other three state no location. None is
located in Africa.

---

## A capture is not an observation

The most consequential methodological finding here, and the one most likely to
matter to other researchers building employment corpora from archived pages.

Of 292 archived Google career pages retrieved, **139 returned "Job not found.
This job may have been taken down."** The Archive had crawled the URL after
Google removed the posting. A further 36 were JavaScript shells from the era
when the careers site was client-rendered.

An employment corpus that counts captures rather than checking page state will
overcount, potentially by a wide margin. The screening scripts here record a
`page_status` for every capture so the distinction survives into the data.

The same problem takes a different form on TikTok. `lifeattiktok.com` ships its
entire content-management payload on every route, including the copy for the
not-found page. A body-text test for "page not found" therefore matches on a
perfectly healthy job posting. Only the server-rendered `<title>` distinguishes
a live capture from a dead one.

---

## Layout

```
data/
  public/            the released corpus and derived tables
  processed/         intermediate stage, not released
  raw/               archived HTML, never committed
docs/
  codebook.md        every field, every coding rule
  reproduction.md    how to rebuild the corpus from scratch
figures/             figure scripts and output (see figures/README.md for
                     which plate is which article figure)
scripts/             collection, screening, coding, assembly
source_registry/     every archived page discovered, with timestamps
```

## Reproducing the corpus

```bash
pip install -r requirements.txt

# discovery and collection, one arm at a time
python scripts/collect_wayback_meta.py
python scripts/collect_wayback_platform.py google --discover-only
python scripts/screen_and_fetch_candidates.py google --fetch
python scripts/reextract_google_pages.py
python scripts/collect_tiktok_arm.py --discover-only
python scripts/collect_tiktok_arm.py --fetch

# merge the three arms and draw the figures
python scripts/build_unified_corpus.py
python scripts/make_figures.py
python scripts/make_figures_alt.py --form all
```

Full collection takes several hours, most of it the TikTok arm, which fetches
roughly 4,000 pages at one per second to stay within the Archive's tolerance.
`docs/reproduction.md` has the detail.

## Screening

Inclusion and exclusion are recorded per posting, with the term that triggered
each decision, in the screening registries under `data/public/`. Nothing is
dropped silently.

The exclusion list exists because "integrity" and "safety" have engineering
senses unrelated to content governance. Signal integrity, power integrity,
structural integrity, fire and life safety, data centre roles and site
reliability engineering are excluded by rule, not by judgement, and every
exclusion is logged.

Screening terms are matched with word boundaries. An earlier unanchored version
matched "Addison, TX" against the stem "addis" and produced a phantom Africa
role. In a study whose central finding is an absence, a substring false positive
is the most damaging error available.

---

## What is not here, and why

**Interview material.** Thirty practitioner interviews inform the article. They
were given under a consent agreement that does not cover publication.
Transcripts, audio, notes and anything derived from them that could identify a
participant are permanently excluded. See `ETHICS.md`.

**Archived HTML.** Roughly 260 MB of saved captures. Excluded for size, and
because redistributing whole career pages raises copyright and terms-of-service
questions that the derived, coded data does not. Every row carries its
`source_url` and capture timestamp, so anyone can retrieve the same pages from
the Internet Archive.

**Full advertisement text.** Held in `data/processed/`, which is not released.
The public data carries titles, locations, coded fields and screening decisions.

---

## Licences

Code is MIT (`LICENSE`). Data is CC BY 4.0 (`LICENSE-DATA`). Job advertisement
text remains the property of the platforms that published it and is not
relicensed here.

## Citation

See `CITATION.cff`.
