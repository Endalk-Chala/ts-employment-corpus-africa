# Reconciling Figure 1 and Figure 2

*Governing at a distance* — diagnostic note. Updated 6 September 2026 after
pixel measurement of the figures and confirmation from the author that Figure 1
plots the top twelve countries only.

## The problem

The two figures encode different totals.

| Platform | Fig 1: hubs | Fig 1: other countries | Fig 1 total | Fig 2 total | Difference |
|---|---:|---:|---:|---:|---:|
| Meta | 36 | 0 | 36 | 40 | −4 |
| Google/YouTube | 120 | 43 | 163 | 154 | **+9** |
| TikTok | 72 | 3 | 75 | 85 | −10 |
| **All** | 228 | 46 | **274** | **279** | −5 |

The three hub cells agree exactly across both figures: United States 21 / 111 / 20,
Singapore 8 / 0 / 31, Ireland 7 / 9 / 21. Every disagreement sits in the residual.

## The readings are measured, not estimated

Each bar segment was classified by fill colour and converted to counts using the
United States bar as scale. Every value falls within 0.15 of an integer:

| Country | Meta | Google | TikTok | Total |
|---|---:|---:|---:|---:|
| United States | 20.89 | 110.86 | 20.04 | 152.00 |
| Singapore | 7.89 | 0 | 30.91 | 39.01 |
| Ireland | 7.04 | 8.95 | 20.89 | 36.88 |
| India | — | 13.86 | 0.85 | 14.92 |
| United Kingdom | — | 7.89 | 1.92 | 10.02 |
| Israel | — | 4.05 | — | 4.05 |
| Taiwan, Brazil, Malaysia, Indonesia, Thailand | — | 2.98 each | — | 2.98 |
| Germany | — | 1.92 | — | 1.92 |

Figure 2's segment widths were measured the same way and reproduce its printed
labels exactly for all three platforms. Figure 4 measures to TikTok 21, Google
8.94, Meta 6.98, summing to the 37 both other figures give for Ireland.

Two things follow that were previously uncertain:

- The unlabelled remainders in the India and United Kingdom bars **are TikTok**,
  at 0.85 and 1.92 units. No Meta blue appears in either.
- Google's Singapore is a **true structural zero**, not a segment too thin to
  render. Zero pixels of Singapore colour appear in Google's bar. Given that
  Singapore is TikTok's largest hub at 36% of its roles, this is a finding
  rather than an absence, and deserves a sentence in the article.

## Diagnosis: two causes, and they close exactly

**Confirmed by the author:** Figure 1 plots the top twelve countries only.

That explains Meta and TikTok. It cannot explain Google, and here is why.

If the cut is the only issue, the undisplayed countries hold Meta's missing 4
and TikTok's missing 10, which is 14 roles. But 279 − 274 = 5. The arithmetic
balances only if something is also nine roles too large, and Google is the only
candidate: 14 − 9 = 5.

So:

| Platform | Shown | Below the cut | Inflated by |
|---|---:|---:|---:|
| Meta | 36 | 4 | — |
| TikTok | 75 | 10 | — |
| Google/YouTube | 163 | ~0 | **9** |

**The mechanism for Google's +9: multi-location postings counted once per
location.** An advertisement naming "Dublin, Ireland; London, United Kingdom"
contributes one row to a platform-level count but one row per location to a
country-level count, unless the country table deduplicates by job identifier
first. Google career postings routinely list several offices; Meta's and
TikTok's more often name one. Google's non-hub total is 34 per Figure 2 while
its displayed country segments sum to 43, so nine of those 43 are the same
postings appearing twice.

Since Germany sits at 2, the cut line is 2 roles, and the undisplayed countries
hold one or two each: roughly seven to twelve small countries carrying Meta's 4
and TikTok's 10. An ordinary long tail.

## What to check when the corpus is recovered

1. Count rows whose location field names more than one country.
2. Rebuild the country table from data deduplicated by `job_id`, assigning each
   posting a single primary location, and confirm country counts then sum to
   40 / 154 / 85.
3. Confirm Google has no roles in countries below the cut, which is what this
   reconciliation implies.

`scripts/prepare_release.py` in the replication repository now blocks any
release where country counts exceed platform totals, so this cannot recur
silently.

## What this does and does not affect

**Unaffected.** The paper's central claim. The three-hub concentration,
152 + 39 + 37 = 228, or 82% of 279, is identical in both figures. Africa is zero
in both. Every hub cell agrees. Sections 4.1 through 4.4 and the whole argument
stand.

**Affected.** Figure 1's country detail, and its caption. As drawn, Figure 1
implies a Google total of 163, contradicting the 154 stated in the text a few
paragraphs later.

## Recommendation

Treat **Figure 2 as authoritative** and regenerate Figure 1 from the same table,
deduplicated by job identifier.

Then fix the caption. The current one does not say the chart is a top-twelve
cut, so a reader who sums the bars gets 274 and cannot reconcile it with the
stated 279. It needs a line to the effect of: *Top twelve countries shown; a
further N countries with one or two roles each (14 roles) are omitted.*

Reviewer 1 asked for stronger methodological transparency. Fixing this before
resubmission converts a vulnerability into a demonstration of care.
