# Figures

Which file is which figure in the article, and the caption each one carries.
All plates are drawn at 300 dpi, the minimum the journal sets, and a PDF vector
copy sits beside every PNG. Nothing is titled inside the image: the journal
typesets captions from the manuscript, so a title baked into the plate would
appear twice in two different fonts.

The article carries **three** data plates. An earlier draft carried five, two of
which were cut during revision, and a conceptual assemblage diagram that was
also cut. The mapping below is the current one, verified by matching the image
bytes embedded in the submitted manuscript against the files in this directory.


## The three data plates in the article

| Article figure | File | Drawn by |
|---|---|---|
| Figure 1 | `alt_units_all_postings.png` / `.pdf` | `scripts/make_figures_alt.py --form units` |
| Figure 2 | `alt_dots_country_by_platform.png` / `.pdf` | `scripts/make_figures_alt.py --form dots` |
| Figure 3 | `alt_languages_ranked.png` / `.pdf` | `scripts/make_figures_alt.py --form languages` |


### Figure 1: `alt_units_all_postings`

**Caption as submitted**

> Figure 1. Geographic concentration of located Trust and Safety postings. Each square represents one of the 216 postings with a recoverable location. Source: author's employment corpus, reconstructed from archived Meta, Google/YouTube, and TikTok career pages, August 2023–September 2026.

**Alt text**

> A grid of 216 small squares, one for each Trust and Safety job advertisement in the corpus whose location could be recovered. The squares are coloured by group and the legend reads 'Three hubs 158 (73%)', 'Elsewhere 57 (26%)' and 'Africa 1 (0.5%)'. Blue squares fill most of the grid, green squares follow, and a single red square sits at the end, annotated 'the one posting located in Africa: a recruiter, in Casablanca'.


### Figure 2: `alt_dots_country_by_platform`

**Caption as submitted**

> Figure 2. Trust and Safety postings by country and platform. The figure shows the eleven most frequent locations among postings with recoverable locations, disaggregated by platform. Source: author's employment corpus.

**Alt text**

> A dot chart of the eleven most frequent locations among the 216 Trust and Safety postings with a recoverable location, with one row per country and separate marks for Meta, Google/YouTube and TikTok. The United States leads the chart with 116 postings across the three platforms, followed by India with 23, Ireland with 21 and Singapore with 21. Morocco appears at the foot of the chart with a single TikTok posting and is the only African location shown.


### Figure 3: `alt_languages_ranked`

**Caption as submitted**

> Figure 3. Languages named in Trust and Safety job postings. Seventy-nine of the 736 postings name at least one language. Source: author's employment corpus.

**Alt text**

> A horizontal bar chart of the 31 languages named in Trust and Safety job titles, ranked by the number of postings naming each. The horizontal axis is labelled 'postings naming the language' and runs from 0 to 12. Arabic leads with eleven postings, then Spanish with ten, then German with five, then Urdu, Japanese and English with four each. Most of the remaining languages are named in only one posting. Two African languages appear, drawn in red and labelled in the legend as 'African language' against 'Every other language': Hausa, with three postings, and Swahili, with two. Between them they account for five of the 79 postings that name a language at all.


## Plates that are here but not in the article

Four plates are kept because they are useful for checking the corpus, not
because the article uses them.

| File | What it shows | Why it is not in the article |
|---|---|---|
| `alt_african_language_siting` | Each of the five African-language postings, language region against office | Cut in revision; §4.1 states the same five postings in prose |
| `alt_matrix_language_by_office` | Language named crossed with office sited | Cut in revision |
| `figure1_country_by_platform` | An earlier country-by-platform chart | Superseded by `alt_dots_country_by_platform` |
| `figure2_hub_concentration` | Share of located postings in the three hubs, by platform | Superseded; the same 73 per cent figure is given in the text |

Note that `figure1_country_by_platform` and `figure2_hub_concentration` are
**not** Figures 1 and 2 of the article, despite the filenames. They are earlier
plates kept for continuity with `make_figures.py`, which draws them together.
Use the table at the top of this file rather than the filenames.


## Changing how they look

Every plate reads its type, colour, size and output format from
`scripts/figure_style.py`. Change that file and rerun both figure scripts:

```
python scripts/make_figures.py
python scripts/make_figures_alt.py --form all
```

The alt text above is generated from the same module, in `alt_texts()`. The
captions above are transcribed from the submitted manuscript, which is the
authority for them: if a caption is edited in the manuscript, update it here as
well, because the two are not generated from a single source.
