# Reproducing the corpus

Every posting in this corpus comes from the Internet Archive. Nothing was
scraped from a live career page. That matters for reproduction: the pages the
article analyses no longer exist on the live web, and the only way back to them
is the archive.

## 0. Install

```bash
pip install -r requirements.txt
```

No browser automation is required. Earlier versions of this pipeline rendered
JavaScript career pages in a headless browser; that approach was abandoned
because it cannot reach postings that have already been taken down.

## 1. The three arms

Each platform is collected separately, because each one preserves a different
amount of a job advertisement.

**Meta.** Postings carry schema.org JSON-LD, so the full advertisement text
survives in the capture.

```bash
python scripts/collect_wayback_meta.py --discover-only   # list snapshots, fetch nothing
python scripts/collect_wayback_meta.py --from 2023 --to 2026
python scripts/reconstruct_meta_arm.py data_raw/meta_jobs_jsonld_large.csv
python scripts/clean_meta_jsonld.py meta_jobs_jsonld_large.csv
```

**Google/YouTube.** The rendered detail block survives, giving title and office
but no body text.

```bash
python scripts/collect_wayback_platform.py google --discover-only
python scripts/collect_wayback_platform.py google --from 2023 --to 2026
python scripts/screen_and_fetch_candidates.py google --report
python scripts/screen_and_fetch_candidates.py google --fetch
python scripts/reextract_google_pages.py
```

**TikTok.** The site renders client-side and suppresses structured data, so only
the server-rendered title survives. The fetch is resumable; `--retry-failed`
picks up captures that timed out.

```bash
python scripts/collect_tiktok_arm.py --discover-only
python scripts/collect_tiktok_arm.py --fetch
python scripts/collect_tiktok_arm.py --retry-failed
python scripts/collect_tiktok_arm.py --report
```

## 2. Merge

```bash
python scripts/build_unified_corpus.py
```

Writes `data_processed/unified_corpus.csv` and
`data_processed/unified_country_table.csv`. Every row carries an
`evidence_level` recording how much of the advertisement survived, and no
downstream claim should exceed what that field permits.

Add `--include-dropped` to see the postings screened out and why.

## 3. Figures

```bash
python scripts/make_figures.py
python scripts/make_figures_alt.py --form all
```

`figure_style.py` holds the shared type, colour and geometry settings, and both
scripts import it. Change the font or the palette there, not in the individual
scripts, and re-run both or the figures will diverge.

Titles and captions are switched off by default, because the journal typesets
them from the manuscript. `figure_style.manuscript_captions()` and
`figure_style.alt_texts()` return the caption and alt-text wording.

## 4. Release

```bash
python scripts/assemble_release.py --dry-run
python scripts/assemble_release.py
```

Copies the code, the public data, the registries and the figures into this
repository, strips any column on the forbidden list, writes `MANIFEST.md` with
SHA-256 checksums, and scans for anything that should never be published.

## What you will not reproduce exactly

Re-running discovery will not return the same set of captures. The Internet
Archive keeps crawling, so coverage grows; some captures also become
unavailable. Counts will differ from the article.

That is a property of the object of study rather than a defect. The article
measures a hiring geography as the archive preserved it in September 2026, and
the archive moves. Report your own retrieval date rather than presenting
recollected figures as the originals.

Two cautions carried over from the article's methods section, because they
govern what the data can be asked:

- **A capture is not an observation.** The distribution of captures over time
  reflects how often the Internet Archive crawled these pages, not how often the
  platforms were hiring. Of the 716 captures, 551 fall in 2025.
- **No posting found is not the same as no capacity exists.** Absence in this
  corpus means no publicly identifiable advertisement was preserved in the
  sources searched, and nothing stronger.
