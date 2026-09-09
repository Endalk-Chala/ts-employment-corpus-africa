# data/public/

The released dataset. Everything here is written by
`scripts/assemble_release.py` and should not be edited by hand. Columns on the
forbidden list, including full advertisement text and any local file path, are
stripped on the way in.

| File | Rows | Contents |
|---|---:|---|
| `unified_corpus.csv` | 736 | One row per screened-in posting: platform, job id, archived URL, capture date, title, employer, raw and parsed location, region, multi-location flag, `evidence_level`, screening decision, matched terms, language and market signals |
| `unified_country_table.csv` | 16 | Country by platform, each posting counted once |
| `screening_meta.csv` | 613 | Every Meta posting considered, with role classification, signal strength and whether it entered the final subset |
| `screening_google.csv` | 15,092 | Every Google/YouTube capture considered, with matched and excluded terms |
| `screening_tiktok.csv` | 3,966 | Every TikTok job id considered, with page status, screening decision, matched and excluded terms, and language or market signals |

## The field that governs everything else

`evidence_level` records how much of the advertisement survived in the capture:

| Value | Meaning | Count |
|---|---|---:|
| `full_text` | Whole advertisement recovered, from schema.org JSON-LD | 39 |
| `detail_only` | Title and location, no body text | 117 |
| `title_only` | Job title alone | 580 |

Claims about what an advertisement *says* are limited to the 39 `full_text`
rows. Claims about *location* are limited to the 216 rows carrying a
recoverable `primary_country`. The remaining 520 postings support claims about
titles and nothing more.

## Checking what you have

`MANIFEST.md` in the repository root carries a SHA-256 for every file here and
in `source_registry/`. Verify against it before use.
