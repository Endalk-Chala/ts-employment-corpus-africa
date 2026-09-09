# Figures

Which file is which figure in the article, and the caption and alt text each
one carries. All plates are drawn at 300 dpi, the minimum the journal sets,
and a PDF vector copy sits beside every PNG. Nothing is titled inside the
image: the journal typesets captions from the manuscript, so a title baked
into the plate would appear twice in two different fonts.


## The four data plates in the article

| Article figure | File | Drawn by |
|---|---|---|
| Figure 1 | `alt_units_all_postings.png` / `.pdf` | `scripts/make_figures_alt.py --form units` |
| Figure 2 | `figure2_hub_concentration.png` / `.pdf` | `scripts/make_figures.py` |
| Figure 4 | `alt_languages_ranked.png` / `.pdf` | `scripts/make_figures_alt.py --form languages` |
| Figure 5 | `alt_african_language_siting.png` / `.pdf` | `scripts/make_figures_alt.py --form sited` |

Figure 3 of the article is the conceptual Meta, Sama and Majorel assemblage
diagram. It is drawn by hand rather than from the corpus, so it is not in this
repository.


### Figure 1: `alt_units_all_postings`

**Caption**

> A unit chart of every Trust and Safety posting in the corpus whose location is recoverable (n = 216 of 736 screened in), one square per advertisement, grouped by the three regulatory hubs (the United States, Ireland and Singapore), all other locations, and Africa. Source: archived career pages from Meta, Google/YouTube and TikTok, August 2023 to September 2026.

**Alt text**

> A grid of 216 small squares, one for each Trust and Safety job advertisement in the corpus whose location could be recovered. The squares are coloured by group and the legend reads 'Three hubs 158 (73%)', 'Elsewhere 57 (26%)' and 'Africa 1 (0.5%)'. Blue squares fill most of the grid, green squares follow, and a single red square sits at the end, annotated 'the one posting located in Africa: a recruiter, in Casablanca'.


### Figure 2: `figure2_hub_concentration`

**Caption**

> The share of located Trust and Safety postings falling in the three regulatory hubs, by platform. Percentages are of postings with a recoverable location rather than of all postings screened in; the denominator for each platform is given at the right.

**Alt text**

> Four horizontal stacked bars, one each for Meta, Google/YouTube, TikTok and all platforms combined, each running from 0 to 100 per cent. Every bar is divided into three segments, labelled in the legend as 'Three hubs' in blue, 'Elsewhere' in green and 'Africa' in red. Meta reads 82 per cent and 18 per cent, from 39 located postings. Google/YouTube reads 68 per cent and 32 per cent, from 117. TikTok reads 78 per cent and 20 per cent, with a red sliver, from 60. All platforms combined reads 73 per cent and 26 per cent, from 216, with a red sliver annotated 'Africa: 1 posting (0.5%)'. The horizontal axis is labelled 0, 25, 50, 75, 100 per cent.


### Figure 4: `alt_languages_ranked`

**Caption**

> Languages named in Trust and Safety job titles, ranked by the number of postings naming each (n = 79 postings across 31 languages), with African languages in red. Language is read from the job title, the only field recoverable for every posting in the corpus.

**Alt text**

> A horizontal bar chart of the 31 languages named in Trust and Safety job titles, ranked by the number of postings naming each. The horizontal axis is labelled 'postings naming the language' and runs from 0 to 12. Arabic leads with eleven postings, then Spanish with ten, then German with five, then Urdu, Japanese and English with four each. Most of the remaining languages are named in only one posting. Two African languages appear, drawn in red and labelled in the legend as 'African language' against 'Every other language': Hausa, with three postings, and Swahili, with two. Between them they account for five of the 79 postings that name a language at all.


### Figure 5: `alt_african_language_siting`

**Caption**

> All five postings in the corpus that name an African language, each showing the region where the language is principally spoken against the office where the role is sited. All five are TikTok postings; no Meta or Google/YouTube posting names an African language. A cross marks a posting that states no location, an absence of evidence rather than evidence of a location in Africa.

**Alt text**

> A chart with one row for each of the five postings in the corpus that name an African language, three for Hausa and two for Swahili. Each row has two marks joined by a line: a red mark for the region where the language is principally spoken, and on the right either a blue mark for the office where the role is sited or a cross where the posting states no location. Row one reads 'Hausa, spoken in West Africa' on the left and 'Dublin, role sited here' on the right. Rows two and three read 'Hausa, spoken in West Africa' and 'no location stated in the archived posting', their right-hand marks crosses rather than dots. Row four reads 'Swahili, spoken in East Africa' and 'Dublin, role sited here'. Row five reads 'Swahili, spoken in East Africa' and 'no location stated in the archived posting', its right-hand mark a cross. No row is sited in Africa.


## Two plates that are here but not in the article

`alt_dots_country_by_platform` and `alt_matrix_language_by_office` were drawn
during analysis and are kept because they are useful for checking the corpus,
not because the article uses them. The dots plate shows every located country
against every platform; the matrix crosses the language a posting names with
the office it is sited in. Neither carries an argument the four plates above do
not carry better, and both are omitted from the submission.

## One filename that is not what it looks like

`figure1_country_by_platform` is **not** Figure 1 of the article. It is an
earlier country by platform chart kept for continuity with `make_figures.py`,
which draws it alongside Figure 2. The article's Figure 1 is
`alt_units_all_postings`. The name is left alone so that the script and its
outputs stay in step; use the table above rather than the filenames.

## Changing how they look

Every plate reads its type, colour, size and output format from
`scripts/figure_style.py`. Change that file and rerun **both** figure scripts,
or Figure 2 will come out in a different typeface from the other three:

```
python scripts/make_figures.py
python scripts/make_figures_alt.py --form all
```

The captions and alt text above are generated from the same module, in
`manuscript_captions()` and `alt_texts()`, so the words and the pictures cannot
drift apart.

