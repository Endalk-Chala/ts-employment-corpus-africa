# Rebuilding the Trust and Safety employment corpus

Scripts for re-collecting the job-advertisement corpus behind *Governing at a
distance*. They target the three collection routes the paper describes, and
they all write into the same posting-level schema as
`data_processed/posting_level_corpus_filled.csv`.

Run these from your own terminal, not through a restricted shell: they need
ordinary internet access.

## The pipeline

```
                    collect_wayback_meta.py     (Meta, archived)
                    collect_rendered.py         (Google, TikTok, live)
                              |
                              v
                       code_postings.py         (fills the signal columns)
                              |
                              v
             data_processed/postings_master.csv
```

## 1. Meta, via the Internet Archive

```
pip install requests beautifulsoup4

python collect_wayback_meta.py --discover-only        # see what exists first
python collect_wayback_meta.py --from 2023 --to 2026
```

Queries the CDX Server API for four URL patterns Meta has used for job pages,
collapses duplicate captures, keeps the earliest snapshot of each job ID, then
fetches each snapshot with the `id_` flag so the Archive's toolbar markup does
not contaminate extraction. Backs off on rate limiting rather than hammering.

Start with `--discover-only`. It writes `source_registry/meta_wayback_snapshots.csv`
and stops, so you can see how many postings are actually recoverable before
committing to a long fetch.

## 2. Google and TikTok, via a headless browser

```
pip install playwright beautifulsoup4
playwright install chromium

python collect_rendered.py google discover
python collect_rendered.py google fetch

python collect_rendered.py tiktok discover
python collect_rendered.py tiktok fetch
```

Both career sites render in JavaScript, which is why the earlier `requests`
approach returned empty shells.

The `discover` phase does something worth understanding. Instead of hardcoding
a private API endpoint that will break the next time either company ships a
release, it opens the real site and **listens to the network calls the page
makes**, saving every JSON response that looks job-shaped into
`data_raw/<company>_xhr/`. The site tells you its own API. At the end of the
run the script prints the largest captured payloads. If one of them contains
the full result set, parse it directly instead of rendering hundreds of pages:
faster, and much lighter on the site.

`--headful` shows the browser, which sometimes gets you past headless
detection. `--query` adds an extra keyword search.

## 3. Coding

```
python code_postings.py data_processed/meta_wayback_postings.csv \
                       data_processed/google_postings.csv \
                       data_processed/tiktok_postings.csv \
                       --merge data_processed/postings_master.csv
```

Fills the ten signal columns and deduplicates by `(company_name, job_id)`,
which is the deduplication rule the paper states.

**This is a first pass, not coding.** Every flag it sets is written back into
`notes` with the exact string that triggered it, so a human can confirm or
overturn each decision quickly. That is the point: it makes reviewing 279
advertisements tractable, it does not replace the review.

A kappa computed between this script and you measures the script. Intercoder
reliability still requires a second human coding a sample independently.

### Validation

Run against the one surviving hand-coded record, with the human codes stripped
out, the script reproduced **9 of 10 fields exactly**: every yes/no signal,
the languages named, and the offshore judgement.

The tenth is a formatting convention rather than a disagreement. For
`africa_facing_text` the hand-coded row lists both `French Sub-Saharan Africa`
and `Sub-Saharan Africa`; the script keeps only the longest non-overlapping
phrase, so it returns `French Sub-Saharan Africa` alone. Same finding, less
redundancy. Change it in `africa_phrases()` if you would rather keep both.

## The schema

Twenty-one columns, unchanged from your original:

```
record_id, company_name, job_id, source_url, capture_mode, date_accessed,
job_title, location, team_function, job_text, africa_facing_signal,
africa_facing_text, languages_named, language_signal, moderation_signal,
integrity_signal, policy_enforcement_signal, vendor_signal,
worker_risk_signal, offshore_relative_to_market, notes
```

`offshore_relative_to_market` is set to `yes` when an advertisement is scoped
to an African market but the post itself sits in a governance hub elsewhere,
`no` when the post is located in Africa, and left blank when the advertisement
carries no Africa scope at all. That last case is a genuine non-applicable, not
a missing value, and should stay distinguishable from one.

## A caution about what this can and cannot restore

A fresh collection gives you a defensible corpus, but it is a **2026 snapshot,
not your March 2026 one**. Live postings expire. Numbers will differ from the
figures already in the manuscript.

If the original corpus is recovered, use it. If it is not, the honest move is
to report the new collection with its own date and let the numbers change,
rather than presenting recollected figures as though they were the originals.
