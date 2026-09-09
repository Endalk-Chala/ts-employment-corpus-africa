# Reproducing the analysis

## 0. Install

```bash
pip install -r requirements.txt
playwright install chromium      # only for the rendered collectors
```

## 1. Collect

Meta comes from the Internet Archive. Look before you fetch:

```bash
python scripts/collect_wayback_meta.py --discover-only
python scripts/collect_wayback_meta.py --from 2023 --to 2026
```

Google and TikTok render in JavaScript and need a browser:

```bash
python scripts/collect_rendered.py google discover
python scripts/collect_rendered.py google fetch
python scripts/collect_rendered.py tiktok discover
python scripts/collect_rendered.py tiktok fetch
```

The `discover` phase saves the JSON responses the sites' own pages request,
into `data/raw/<company>_xhr/`. If one of those payloads holds the whole result
set, parse it directly instead of rendering every job page.

## 2. Code

```bash
python scripts/code_postings.py \
    data/processed/meta_wayback_postings.csv \
    data/processed/google_postings.csv \
    data/processed/tiktok_postings.csv \
    --merge data/processed/postings_master.csv
```

Then review. Every proposed code carries the string that triggered it in
`notes`, so this is confirmation rather than re-reading. Correct the master file
in place.

## 3. Validate

```bash
python scripts/prepare_release.py data/processed/postings_master.csv --check-only
```

Fix what it reports. The check that matters most compares country counts against
platform totals: if a country sum exceeds a platform total, multi-location
postings are being counted more than once, which is what made an earlier version
of Figure 1 disagree with Figure 2 by nine roles.

## 4. Release

```bash
python scripts/prepare_release.py data/processed/postings_master.csv
```

Writes `data/public/` and a manifest with per-file checksums. `--text-mode`
controls how much advertisement text is published; read ETHICS.md before
changing it from the default.

## 5. Figures

```bash
python figures/make_figures.py
```

Regenerates Figures 1, 2 and 4 from the released counts, and refuses to draw
anything if the country and hub tables disagree.

## What you will not reproduce exactly

Re-running collection gives a current snapshot. Live advertisements expire, new
ones appear, and archived coverage changes as the Internet Archive crawls more.
Numbers will differ from the published article. That is a property of the
object of study, not a defect: the article measures a hiring geography at a
moment, and the moment moves.

Report your own collection date rather than presenting recollected figures as
the originals.
