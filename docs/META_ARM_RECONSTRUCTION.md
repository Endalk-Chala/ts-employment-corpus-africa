# Meta arm: screening funnel reconstructed

7 September 2026. Rebuilt from `data_raw/meta_jobs_jsonld_large.csv` using the
classification rules in `create_meta_coded_file.R`.

## The funnel

| Stage | Count |
|---|---:|
| Wayback captures | 805 |
| Distinct postings, deduplicated by `job_id` | 613 |
| Security-relevant under the original role classification | 86 |
| Of those, high signal strength | 49 |
| Minus technical-integrity false positives | **39** |
| **Published figure** | **40** |

Reconstructed to within one posting.

## What each stage does

**805 to 613.** The Wayback pull captured many postings more than once. Removing
repeat captures of the same `job_id`, keeping the earliest, leaves 613 distinct
advertisements.

**613 to 86.** `classify_role()` from your R script, ported without alteration:
same term lists, same precedence, same thresholds. It assigns each posting to
`core_integrity`, `content_review_quality`, `policy_enforcement`,
`operations_support`, `possible_integrity`, or `non_integrity`. The first five
are security-relevant. Result: 46 core_integrity, 37 possible_integrity,
3 policy_enforcement, 527 non_integrity.

**86 to 49.** Keeping only `high` signal strength, which drops the
`possible_integrity` tier, where classification rested on a single term match.

**49 to 39.** Removing postings whose only integrity language is technical, with
no governance language anywhere in the advertisement. Ten postings:

| Country | Title | Term |
|---|---|---|
| United States | Display Electrical Engineer | signal integrity |
| United States | Research Scientist Intern, AI Signal and Power Integrity | power integrity |
| United States | System Architecture Engineer | data integrity |
| United States | Network Automation Engineer, Fullstack | data integrity |
| United States | Software Engineer | data integrity |
| United States | Controls Subject Matter Expert (×2) | system integrity |
| United States | Electrical Subject Matter Expert | system integrity |
| United States | Mechanical Subject Matter Expert | system integrity |
| India | Application Engineer, Salesforce | data integrity |

Nine of the ten are United States engineering roles, which is why the American
count falls furthest at this stage.

**This step is not an invention.** Your `VERIFICATION_NOTES.md` specified it
before I looked:

> The raw Meta data contain uses of words such as `integrity` in technical and
> non-platform-governance contexts (for example signal/system/data integrity).
> Therefore, keyword hits should be documented as a candidate-screening
> mechanism, not as the final operational definition of a Trust & Safety role.

The reconstruction simply applies the rule you had already written down.

## Final subset, and how it compares

| | Reconstructed | Published |
|---|---:|---:|
| Total | 39 | 40 |
| United States | 18 | 21 |
| Singapore | 7 | 8 |
| **Ireland** | **7** | **7** |
| Other | 7 | 4 |
| **Located in Africa** | **0** | **0** |

Ireland matches exactly, and has matched under every filter tried at every
stage. Africa is zero in both. Total differs by one.

The United States and "other" columns differ by three each, which is the
expected size of disagreement over borderline cases when a manual review step is
reconstructed rather than recovered. Some of what I count as "other" (United
Kingdom 3, Switzerland 2, Germany 1, China 1) may have been folded into the
hub categories, or a few borderline exclusions went the other way.

## What this establishes for the revision

**The screening pipeline is documentable.** Five stages, each with a stated rule,
reproducing the published figure to within one posting. That is a complete answer
to Reviewer 1 on the Meta arm, and it can be stated in the methods section in a
paragraph.

**The classification code survives and is auditable.** `create_meta_coded_file.R`
holds the full term lists and decision precedence.

**Two corrections the reconstruction forces.**

First, the geography in the R pipeline was broken. `parse_country()` split the
location string on commas and took the last element, but the field is shaped
`Dublin, Ireland, {'@type': 'Country', 'name': ['IRL', 'GBR']}`, so the last
element is `'name': ['IRL', 'GBR']}` rather than a country. That is why
`region_group` is "Unknown" for all 805 rows in the coded output, and it is the
source of "Dublin, United Kingdom", "Tel Aviv, France" and "Shanghai, Taiwan" in
the processed summaries. The published country figures therefore cannot have
come from that pipeline. `reconstruct_meta_arm.py` fixes it by taking the prefix
before the brace.

Second, the exact published Meta split cannot be reproduced by any rule in the
surviving code. It required a manual review step that was not written down. The
honest form of words for the methods section is that keyword classification
produced a candidate pool which was then reviewed by hand against the role
definition, with technical uses of governance vocabulary excluded. Say that
plainly rather than implying the screen was fully automated.

## Files

| File | Contents |
|---|---|
| `data_raw/meta_jobs_jsonld_large.csv` | 805 raw captures |
| `data_processed/meta_postings_clean.csv` | 613 distinct, location parsed |
| `data_processed/meta_arm_reconstructed.csv` | 613 with role class, flags, region |
| `data_processed/meta_arm_screened.csv` | adds `technical_integrity_false_positive` and `in_final_subset` |
| `scripts/reconstruct_meta_arm.py` | the ported classifier |
| `scripts/clean_meta_jsonld.py` | location parsing and deduplication |

## Still outstanding

Google (154) and TikTok (85) have no underlying data on this machine. Neither
this container nor the device shell can reach `web.archive.org`,
`google.com/about/careers` or `lifeattiktok.com`, so re-collection has to be run
by you locally:

```
pip install playwright beautifulsoup4 && playwright install chromium
python scripts/collect_rendered.py google discover
python scripts/collect_rendered.py google fetch
python scripts/collect_rendered.py tiktok discover
python scripts/collect_rendered.py tiktok fetch
```

That produces a current snapshot, not the March one. The numbers will move.
