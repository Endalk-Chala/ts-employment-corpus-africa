# Reconciling Figure 1 and Figure 2 (historical)

> **Status: superseded, kept as a record.** Everything below concerns the
> earlier 279-posting corpus and the figures drawn from it. That corpus and
> those figures no longer exist. The corpus was rebuilt from the Internet
> Archive in September 2026 and now holds 736 screened-in postings, 216 of them
> with a recoverable location. None of the counts in this note are current, and
> none should be quoted. See `CHANGELOG.md` for the rebuild, `README.md` for
> the figures that stand, and `figures/README.md` for which plate is which.
>
> This note is kept because it documents how the discrepancy was found and what
> it turned out to be, which is part of the record of how the corpus was
> checked. It is not guidance.

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

## What happened

The corpus was rebuilt rather than patched, so the reconciliation resolved
itself. All three arms were recollected from the Internet Archive with a single
screening rule, deduplicated by platform job identifier, and given one primary
location each, the first site listed where a posting names more than one. The
country table and the platform totals are now built from the same rows, so they
cannot disagree.

Two things in the diagnosis above survived the rebuild and two did not.

**Survived.** The three-hub concentration is still the dominant pattern, and
Google/YouTube still has a genuine structural zero in Singapore, which is worth
a sentence in the article given that Singapore is one of TikTok's largest hubs.

**Did not survive.** The 82 per cent figure was a Meta-only count; across all
three arms the hub share is 73 per cent, 158 of 216 located postings. And Africa
is no longer zero: the corpus records one Africa-located posting, an
eleven-month Talent Acquisition Partner contract in Casablanca.

The figure that caused the trouble, a country by platform bar chart cut to the
top twelve, is no longer the article's Figure 1. Figure 1 is now a unit chart
that draws one square per located posting, so a reader can count the squares
and get the stated denominator. A cut that has to be explained in a caption was
replaced by a picture that does not need one.
