# Changelog

Record every change that alters what the numbers mean: dictionary edits,
coding-rule changes, recollection, and any change to the release text mode.

## Unreleased

### 9 September 2026: screening term list widened, corpus rebuilt

An audit of the 3,048 TikTok titles the screen had dropped found safety-qualified
roles the term list did not reach. Four terms were added to the TikTok include
list: `safety model*`, `safety label*`, `law enforcement`, and `trust&safety`
(the no-space spelling, which neither `trust & safety` nor `t&s` matched). The
bare term `quality assurance` was considered and rejected: of the 64 dropped
titles carrying it, most are software, advertising, commerce or search roles, so
it would have admitted far more noise than signal. `screen()` was re-applied to
the saved titles without refetching, via a new `--rescreen` entry point.

The Google and Meta arms were audited the same way and had no misses.

What changed:

| | Before | After |
|---|---:|---:|
| Screened in | 716 | 736 |
| With a recoverable location | 216 | 216 |
| In the three hubs | 158 (73.1%) | 158 (73.1%) |
| `title_only` | 560 | 580 |
| Captures in 2025 | 551 | 565 |
| Postings naming an African language | 3 | 5 |
| Postings naming any language | 63 | 79 |

The location findings are unchanged. The two new African-language postings are
`Safety Model Operations Quality Assurance - Hausa` and `- Swahili`, neither
stating a location. Figure captions and alt text in `scripts/figure_style.py`
were updated to match, and the language count in the Figure 4 caption was set to
31, the number of bars the plate actually draws, since two postings name more
than one language and the plate ranks the first named.

- Repository scaffolded. Collection, coding and release code added.
- `prepare_release.py` blocks any release where country counts exceed platform
  totals. This defect produced a nine-role discrepancy between the country and
  platform figures in an earlier draft of the article.
- Release text mode defaults to `omit`, publishing a SHA-256 of each
  advertisement instead of its text.
