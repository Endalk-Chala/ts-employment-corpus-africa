"""
figure_style.py

One place to change how every figure looks. Both figure scripts import this,
so a change here applies to all of them and they cannot drift apart.

Edit the STYLE dictionary below. Nothing else needs touching.

Set for Internet Policy Review
------------------------------
The journal's style guide (v5.4) settles three things for us.

1. "Please provide figures in high resolution, with 300 dpi as the absolute
   minimum." So dpi is 300, and a PDF vector copy goes alongside.

2. "Captions precede tables and follow figures." The caption sits below the
   image and the journal typesets it from the manuscript. Nothing that belongs
   in a caption should be baked into the picture, or the reader sees it twice
   in two different fonts. So `title`, `subtitle` and `caption` all default to
   "off", and the words live in `manuscript_captions()` instead.

   Checked against a published article (Leveraging interdisciplinary methods
   for evidence collection in enforcement, policyreview.info): the journal
   renders figure captions BELOW the image and LEFT-ALIGNED, labelled with a
   colon, as "Figure 1: A diagram detailing the two bodies of knowledge...".
   The caption body is a descriptive noun phrase, not a full sentence opening
   with a verb. `manuscript_captions()` follows that house form. Centring a
   caption in the Word file will not survive typesetting, so `caption_align`
   below affects only a caption drawn inside the image.

3. Alt text is required: "Alt-text should contain a description of the image
   that allows a person unable to see the image to understand its content. If
   your image contains text, that text should be in the alt-text as well."
   `alt_texts()` holds one for each figure, written to that rule.

The guide also sets British spelling, -ise endings, sentence case for titles
and headings, "internet" lowercase, and numbers spelled out from one to nine
with numerals from 10 up. The caption and alt-text strings below follow all of
that, so they can be pasted straight into the manuscript.

On titles while you work
------------------------
Set `title` and `subtitle` to "in_figure" when a figure has to stand alone in
an email or a slide, then switch them back to "off" before you export the
submission versions.

On fonts
--------
`font_family` accepts any font installed on your machine. Matplotlib falls
back silently to its default if the name is not found, which is easy to miss,
so `check_font()` warns you when that happens. Common choices:

    "DejaVu Sans"        matplotlib's default, always present
    "Arial"              present on Windows
    "Times New Roman"    present on Windows, if you want serif
    "Source Sans 3"      free, good on screen and in print

Set `math_as_text` to True unless a figure contains real mathematics; it stops
matplotlib rendering stray dollar signs and underscores as equations.
"""

import warnings

STYLE = {
    # ---------------------------------------------------------------- type
    "font_family":   "DejaVu Sans",
    "size_title":    11.5,
    "size_subtitle": 9.5,
    "size_axis":     9,      # tick labels and axis titles
    "size_label":    9.5,    # category names down the side
    "size_value":    8,      # the number printed beside a bar
    "size_caption":  8,
    "size_legend":   9,

    # ------------------------------------------------------ what to include
    # "in_figure" draws it; "off" omits it and the journal sets it from the
    # manuscript. "off" is correct for submission.
    "title":         "off",
    "subtitle":      "off",
    "caption":       "off",          # "below" or "off"
    # Only applies when caption is drawn in the image. The journal itself
    # left-aligns, so "left" is what matches a published page.
    "caption_align": "left",         # "left" or "centre"
    "title_align":   "left",         # "left" or "centre"

    # ------------------------------------------------------------- geometry
    "width_in":      7.2,            # figure width in inches
    "row_in":        0.235,          # vertical space per category row
    "dpi":           300,            # the journal's stated minimum
    "formats":       ("png", "pdf"),

    # -------------------------------------------------------------- colour
    # Validated for colour-vision deficiency separation across all pairs
    # before use: worst pair dE 9.2 deuteranopia, 24.0 normal vision.
    # If you change these, re-validate rather than trusting your eye.
    "light": {
        "surface": "#fcfcfb", "text": "#0b0b0b", "muted": "#52514e",
        "grid": "#e4e3df", "faint": "#f0efec",
        "series": ["#2a78d6", "#eb6834", "#1baf7a"],
        "hub": "#2a78d6", "other": "#1baf7a", "africa": "#e34948",
    },
    "dark": {
        "surface": "#1a1a19", "text": "#ffffff", "muted": "#c3c2b7",
        "grid": "#33322f", "faint": "#262523",
        "series": ["#3987e5", "#d95926", "#199e70"],
        "hub": "#3987e5", "other": "#199e70", "africa": "#e66767",
    },

    "math_as_text":  True,
}


def apply(matplotlib):
    """Push the style onto matplotlib's defaults. Call once, before plotting."""
    rc = matplotlib.rcParams
    rc["font.family"] = STYLE["font_family"]
    rc["axes.unicode_minus"] = False
    if STYLE["math_as_text"]:
        rc["mathtext.default"] = "regular"
    rc["savefig.dpi"] = STYLE["dpi"]
    rc["figure.dpi"] = 110
    check_font(matplotlib)


def check_font(matplotlib):
    """Matplotlib falls back silently when a font is missing. Say so."""
    from matplotlib import font_manager
    want = STYLE["font_family"]
    have = {f.name for f in font_manager.fontManager.ttflist}
    if want not in have:
        warnings.warn(
            f"font '{want}' not found; matplotlib will substitute its default. "
            f"Some fonts on this machine: "
            f"{', '.join(sorted(list(have))[:8])} ...", stacklevel=2)


def theme(mode="light"):
    return STYLE[mode]


def _align(key):
    """Turn a STYLE alignment word into (matplotlib ha, x in axes coords)."""
    centred = str(STYLE.get(key, "left")).lower() in ("centre", "center")
    return ("center", 0.5) if centred else ("left", 0.0)


def titles(ax, title, subtitle, t):
    """Draw the title and subtitle, or not, according to STYLE."""
    ha, x = _align("title_align")
    if STYLE["title"] == "in_figure" and title:
        pad = 24 if (STYLE["subtitle"] == "in_figure" and subtitle) else 10
        ax.set_title(title, fontsize=STYLE["size_title"], color=t["text"],
                     loc="center" if ha == "center" else "left", pad=pad)
    if STYLE["subtitle"] == "in_figure" and subtitle:
        ax.text(x, 1.006, subtitle, transform=ax.transAxes,
                fontsize=STYLE["size_subtitle"], color=t["muted"],
                va="bottom", ha=ha)


def caption(fig, ax, text, t):
    """Draw a caption below the plot, or not, according to STYLE.

    Only used when you want a figure to stand alone outside the manuscript.
    For submission leave STYLE["caption"] at "off" and let the journal set it.
    """
    if STYLE["caption"] == "below" and text:
        ha, x = _align("caption_align")
        ax.text(x, -0.10, text, transform=ax.transAxes,
                fontsize=STYLE["size_caption"], color=t["muted"],
                va="top", ha=ha, wrap=True)


def manuscript_captions():
    """Caption text for each figure, for pasting into the manuscript.

    Kept here so the words and the pictures stay together even though the
    words are not drawn on the pictures. British spelling, sentence case,
    numbers spelled out below 10, per the journal's guide. Captions follow
    the figure.

    Numbering assumes the conceptual Meta-Sama-Majorel assemblage diagram
    keeps its place as Figure 3, so the two language plates are 4 and 5.

    House form, from a published article: "Figure 1: " with a colon, then a
    descriptive noun phrase rather than a sentence opening with a verb, then
    any qualifying sentences. Left-aligned, below the figure.
    """
    return {
        "units": (
            "Figure 1: A unit chart of every Trust and Safety posting in the "
            "corpus whose location is recoverable (n = 216 of 716 screened "
            "in), one square per advertisement, grouped by the three "
            "regulatory hubs (the United States, Ireland and Singapore), all "
            "other locations, and Africa. Source: archived career pages from "
            "Meta, Google/YouTube and TikTok, August 2023 to September 2026."),
        "hubs": (
            "Figure 2: The share of located Trust and Safety postings falling "
            "in the three regulatory hubs, by platform. Percentages are of "
            "postings with a recoverable location rather than of all postings "
            "screened in; the denominator for each platform is given at the "
            "right."),
        "languages": (
            "Figure 4: Languages named in Trust and Safety job titles, ranked "
            "by the number of postings naming each (n = 63 postings across 27 "
            "languages), with African languages in red. Language is read from "
            "the job title, the only field recoverable for every posting in "
            "the corpus."),
        "sited": (
            "Figure 5: The three postings in the corpus that name an African "
            "language, each showing the region where the language is "
            "principally spoken against the office where the role is sited. "
            "All three are TikTok postings; no Meta or Google/YouTube posting "
            "names an African language. A cross marks a posting that states "
            "no location, an absence of evidence rather than evidence of a "
            "location in Africa."),
    }


def alt_texts():
    """Alt text for each figure, as the journal requires.

    The rule is that someone who cannot see the image should be able to
    understand its content, and that any text inside the image appears in the
    alt text too. So each of these carries the axis labels, the category
    names and the numbers that are printed on the picture.
    """
    return {
        "units": (
            "A grid of 216 small squares, one for each Trust and Safety job "
            "advertisement in the corpus whose location could be recovered. "
            "The squares are coloured by group and the legend reads 'Three "
            "hubs 158 (73%)', 'Elsewhere 57 (26%)' and 'Africa 1 (0.5%)'. "
            "Blue squares fill most of the grid, green squares follow, and a "
            "single red square sits at the end, annotated 'the one posting "
            "located in Africa: a recruiter, in Casablanca'."),
        "hubs": (
            "Four horizontal stacked bars, one each for Meta, Google/YouTube, "
            "TikTok and all platforms combined, each running from 0 to 100 "
            "per cent. Every bar is divided into three segments, labelled in "
            "the legend as 'Three hubs' in blue, 'Elsewhere' in green and "
            "'Africa' in red. Meta reads 82 per cent and 18 per cent, from "
            "39 located postings. Google/YouTube reads 68 per cent and 32 per "
            "cent, from 117. TikTok reads 78 per cent and 20 per cent, with a "
            "red sliver, from 60. All platforms combined reads 73 per cent "
            "and 26 per cent, from 216, with a red sliver annotated 'Africa: "
            "1 posting (0.5%)'. The horizontal axis is labelled 0, 25, 50, "
            "75, 100 per cent."),
        "languages": (
            "A horizontal bar chart of the 27 languages named in Trust and "
            "Safety job titles, ranked by the number of postings naming each. "
            "The horizontal axis is labelled 'postings naming the language' "
            "and runs from 0 to 10. Spanish leads with nine postings, then "
            "Arabic with seven, then Japanese, German and English with four "
            "each. Most of the remaining languages are named in only one "
            "posting. Two African languages appear, drawn in red and labelled "
            "in the legend as 'African language' against 'Every other "
            "language': Hausa, with two postings, and Swahili, with one. "
            "Between them they account for three of the 63 postings that name "
            "a language at all."),
        "sited": (
            "A chart with one row for each of the three postings in the "
            "corpus that name an African language, two for Hausa and one for "
            "Swahili. Each row has two marks joined by a line: a red mark for "
            "the region where the language is principally spoken, a blue mark "
            "for the office where the role is sited. Row one reads 'Hausa, "
            "spoken in West Africa' on the left and 'Dublin, role sited here' "
            "on the right. Row two reads 'Hausa, spoken in West Africa' and "
            "'no location stated in the archived posting', its right-hand "
            "mark a cross rather than a dot. Row three reads 'Swahili, spoken "
            "in East Africa' and 'Dublin, role sited here'."),
    }
