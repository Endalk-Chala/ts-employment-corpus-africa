"""
make_figures_alt.py

Three alternative treatments of the same data, for choosing between.

    --form dots    ranked dot plot, one row per country, three platform dots
    --form units   unit chart, one mark per posting, coloured by region
    --form matrix  language against office location
    --form languages  every language named, ranked, African marked
    --form sited      the African-language postings: spoken where, sited where

Why these three
---------------
A grouped bar chart answers "how many in each country per platform". That is a
real question, but it is not the article's question. The article's question is
"where is capacity, and what is absent", and an absence is exactly what a bar
chart renders worst: one posting out of 216 is a bar too short to see.

`dots` is the conservative replacement. Same information as the grouped bars,
a third of the ink, and within-country comparison becomes a glance along a row
rather than a comparison of bar lengths across a gap.

`units` draws one mark per posting. The denominator becomes visible, and the
single African posting is a single mark that can be pointed at. For a finding
that is fundamentally about proportion and absence, this is the honest form:
nothing is aggregated away, and the reader counts what they are being told.

`matrix` is the figure the article does not yet have. It crosses the language a
role names against the office it sits in, which is the paper's argument stated
as a table: African languages appear, and they appear in European hubs.

Usage
-----
    python scripts/make_figures_alt.py --form dots
    python scripts/make_figures_alt.py --form units
    python scripts/make_figures_alt.py --form matrix
    python scripts/make_figures_alt.py --form all --theme dark
"""

from pathlib import Path
from collections import Counter, defaultdict
import argparse
import csv
import math

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import figure_style as fs
fs.apply(matplotlib)
from matplotlib.patches import Patch

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DP = ROOT / "data_processed"
FIG = ROOT / "figures"

PLATFORMS = [("meta", "Meta"),
             ("google_youtube", "Google/YouTube"),
             ("tiktok", "TikTok")]
HUBS = {"United States", "Singapore", "Ireland"}

THEMES = {"light": fs.theme("light"),
          "dark": fs.theme("dark")}


def load_countries():
    p = DP / "unified_country_table.csv"
    if not p.exists():
        raise SystemExit("run build_unified_corpus.py first")
    rows = list(csv.DictReader(p.open(encoding="utf-8-sig")))
    for r in rows:
        for k in ("meta", "google_youtube", "tiktok", "total"):
            r[k] = int(r[k] or 0)
    return [r for r in rows if r["total"]]


def load_corpus():
    p = DP / "unified_corpus.csv"
    if not p.exists():
        raise SystemExit("run build_unified_corpus.py first")
    return list(csv.DictReader(p.open(encoding="utf-8-sig")))


def base(ax, t):
    ax.set_facecolor(t["surface"])
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=t["muted"], labelsize=9, length=0)


def save(fig, stem):
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in fs.STYLE["formats"]:
        kw = {"dpi": fs.STYLE["dpi"]} if ext == "png" else {}
        p = FIG / f"{stem}.{ext}"
        fig.savefig(p, facecolor=fig.get_facecolor(), bbox_inches="tight", **kw)
        print("  wrote", p.name)
    plt.close(fig)


# ------------------------------------------------------------------- dots
def form_dots(t, top, suffix):
    rows = sorted(load_countries(), key=lambda r: r["total"], reverse=True)
    shown = rows[:top]
    africa_rest = [r for r in rows[top:] if r["region"] == "Africa"]
    shown += africa_rest
    shown.reverse()
    n = len(shown)

    fig, ax = plt.subplots(figsize=(7.4, 0.36 * n + 1.5))
    fig.patch.set_facecolor(t["surface"])
    base(ax, t)

    xmax = max(r["total"] for r in shown)
    for i, r in enumerate(shown):
        # connector: the row's own range, so the eye reads along it
        vals = [r[k] for k, _ in PLATFORMS if r[k]]
        if vals:
            ax.plot([min(vals), max(vals)], [i, i], color=t["grid"],
                    linewidth=1.4, zorder=1, solid_capstyle="round")
        for j, (k, label) in enumerate(PLATFORMS):
            if r[k]:
                ax.scatter(r[k], i, s=64, color=t["series"][j], zorder=3,
                           edgecolors=t["surface"], linewidths=1.2)
        ax.text(-xmax * 0.015, i, str(r["total"]), ha="right", va="center",
                fontsize=8.5, color=t["muted"])

    ax.set_yticks(range(n))
    labs = [r["country"] for r in shown]
    ax.set_yticklabels(labs, fontsize=9.5, color=t["text"])
    for i, r in enumerate(shown):
        if r["region"] == "Africa":
            lab = ax.get_yticklabels()[i]
            lab.set_color(t["africa"]); lab.set_fontweight("bold")

    ax.set_xlim(-xmax * 0.10, xmax * 1.06)
    ax.set_ylim(-0.8, n - 0.2)
    ax.xaxis.grid(True, color=t["faint"], linewidth=1.0)
    ax.set_axisbelow(True)
    ax.set_xlabel("postings", fontsize=9, color=t["muted"])

    handles = [Patch(facecolor=t["series"][j], label=l)
               for j, (_, l) in enumerate(PLATFORMS)]
    leg = ax.legend(handles=handles, loc="lower right", frameon=False,
                    fontsize=9, handlelength=0.9, handleheight=0.9)
    for x in leg.get_texts():
        x.set_color(t["text"])
    fs.titles(ax, "Trust and Safety postings by country and platform", None, t)
    fig.tight_layout()
    save(fig, f"alt_dots_country_by_platform{suffix}")


# ------------------------------------------------------------------ units
def form_units(t, suffix):
    """One mark per located posting. The denominator is the picture."""
    rows = load_countries()
    marks = []
    for r in sorted(rows, key=lambda r: (r["region"] != "Africa", -r["total"])):
        if r["region"] == "Africa":
            grp, col = "Africa", t["africa"]
        elif r["country"] in HUBS:
            grp, col = "Three hubs", t["hub"]
        else:
            grp, col = "Elsewhere", t["other"]
        marks += [(grp, col, r["country"])] * r["total"]
    # hubs first, then elsewhere, then Africa last so it ends the sequence
    order = {"Three hubs": 0, "Elsewhere": 1, "Africa": 2}
    marks.sort(key=lambda m: order[m[0]])

    per_row = 30
    n = len(marks)
    nrows = math.ceil(n / per_row)

    fig, ax = plt.subplots(figsize=(7.4, 0.245 * nrows + 1.9))
    fig.patch.set_facecolor(t["surface"])
    base(ax, t)
    ax.set_xticks([]); ax.set_yticks([])

    for idx, (grp, col, country) in enumerate(marks):
        x = idx % per_row
        y = -(idx // per_row)
        ax.scatter(x, y, s=52, color=col, marker="s",
                   edgecolors=t["surface"], linewidths=1.1)
        if grp == "Africa":
            ax.annotate("the one posting located in Africa:\n"
                        "a recruiter, in Casablanca",
                        xy=(x, y), xytext=(x + 2.2, y - 1.9),
                        fontsize=9, fontweight="bold", color=t["africa"],
                        ha="left", va="center",
                        arrowprops=dict(arrowstyle="-", color=t["africa"],
                                        linewidth=1.2))

    counts = Counter(m[0] for m in marks)
    handles = [Patch(facecolor=c, label=f"{g}  {counts[g]}  "
                                       f"({100*counts[g]/n:.0f}%)"
               if counts[g] / n >= 0.01 else
                                       f"{g}  {counts[g]}  (0.5%)")
               for g, c in (("Three hubs", t["hub"]),
                            ("Elsewhere", t["other"]),
                            ("Africa", t["africa"]))]
    leg = ax.legend(handles=handles, loc="upper left",
                    bbox_to_anchor=(0, -0.06), ncol=3, frameon=False,
                    fontsize=9, handlelength=0.9, handleheight=0.9)
    for x in leg.get_texts():
        x.set_color(t["text"])

    ax.set_xlim(-1.0, per_row + 0.5)
    ax.set_ylim(-nrows - 1.6, 0.9)
    fs.titles(ax, f"Every Trust and Safety posting whose location is known (n = {n})",
              "One square is one advertisement", t)
    fig.tight_layout()
    save(fig, f"alt_units_all_postings{suffix}")


# ----------------------------------------------------------------- matrix
def form_matrix(t, suffix):
    """Language named in the posting, against the office it sits in."""
    rows = load_corpus()
    AFR = set()
    cells = defaultdict(int)
    langs, places = set(), set()
    for r in rows:
        a = (r.get("african_language") or "").split(";")[0].strip()
        o = (r.get("other_language") or "").split(";")[0].strip()
        lang = a or o
        if not lang:
            continue
        if a:
            AFR.add(a.title())
        place = (r.get("primary_city") or "").split(";")[0].strip() \
            or (r.get("market_named") or "").split(";")[0].strip() \
            or "not stated"
        cells[(lang.title(), place)] += 1
        langs.add(lang.title()); places.add(place)

    if not cells:
        print("  no language-tagged postings found; skipping matrix")
        return

    lang_tot = Counter()
    place_tot = Counter()
    for (l, p), v in cells.items():
        lang_tot[l] += v
        place_tot[p] += v
    # African languages first, then the rest by frequency
    langs = ([l for l, _ in lang_tot.most_common() if l in AFR] +
             [l for l, _ in lang_tot.most_common() if l not in AFR])
    places = [p for p, _ in place_tot.most_common()]

    fig, ax = plt.subplots(figsize=(0.52 * len(places) + 3.4,
                                    0.38 * len(langs) + 2.0))
    fig.patch.set_facecolor(t["surface"])
    base(ax, t)

    vmax = max(cells.values())
    for yi, l in enumerate(reversed(langs)):
        for xi, p in enumerate(places):
            v = cells.get((l, p), 0)
            if not v:
                continue
            col = t["africa"] if l in AFR else t["hub"]
            ax.scatter(xi, yi, s=90 + 320 * (v / vmax), color=col,
                       edgecolors=t["surface"], linewidths=1.2, zorder=3)
            ax.text(xi, yi, str(v), ha="center", va="center", fontsize=7.5,
                    color="#ffffff", fontweight="bold", zorder=4)

    ax.set_xticks(range(len(places)))
    ax.set_xticklabels(places, rotation=40, ha="right", fontsize=9,
                       color=t["text"])
    ax.set_yticks(range(len(langs)))
    ax.set_yticklabels(list(reversed(langs)), fontsize=9, color=t["text"])
    for yi, l in enumerate(reversed(langs)):
        if l in AFR:
            lab = ax.get_yticklabels()[yi]
            lab.set_color(t["africa"]); lab.set_fontweight("bold")

    ax.set_xlim(-0.7, len(places) - 0.3)
    ax.set_ylim(-0.7, len(langs) - 0.3)
    ax.grid(True, color=t["faint"], linewidth=1.0)
    ax.set_axisbelow(True)
    fs.titles(ax, "Language named in the posting, against the office it sits in",
          "African languages in red", t)
    fig.tight_layout()
    save(fig, f"alt_matrix_language_by_office{suffix}")



# -------------------------------------------------------------- languages
def form_languages(t, suffix):
    """Every language named in a posting, ranked, African languages marked.

    The comparison this figure exists to make is African against everything
    else, so that is what colour encodes: one highlighted category, the rest
    recessive. Ranking alone will not carry it, because the African languages
    sit low in the order and a reader scanning a single-hue ranking has no
    reason to stop there.
    """
    rows = load_corpus()
    counts, african = Counter(), set()
    places = defaultdict(list)          # language -> offices it is sited in
    for r in rows:
        a = (r.get("african_language") or "").split(";")[0].strip()
        o = (r.get("other_language") or "").split(";")[0].strip()
        lang = (a or o).strip()
        if not lang:
            continue
        name = lang.title()
        counts[name] += 1
        if a:
            african.add(name)
        where = (r.get("primary_city") or "").split(";")[0].strip() \
            or (r.get("market_named") or "").split(";")[0].strip()
        places[name].append(where or "location not stated")
    if not counts:
        print("  no language-tagged postings found; skipping languages")
        return

    def where_label(name):
        """Offices for one language, most common first, as a short phrase.
        Only drawn on the African rows: the point of the annotation is that
        these roles are sited away from the languages they serve, and putting
        it on all 27 rows would bury that under noise."""
        c = Counter(places[name])
        parts = [p if n == 1 else f"{p} x{n}" for p, n in c.most_common()]
        return "; ".join(parts)

    ordered = sorted(counts.items(), key=lambda kv: (kv[1], kv[0].lower()))
    names = [k for k, _ in ordered]
    vals = [v for _, v in ordered]
    n_post = sum(vals)
    n_afr_post = sum(v for k, v in ordered if k in african)

    fig, ax = plt.subplots(figsize=(7.2, 0.235 * len(names) + 2.1))
    fig.patch.set_facecolor(t["surface"])
    base(ax, t)

    colours = [t["africa"] if k in african else t["hub"] for k in names]
    bars = ax.barh(range(len(names)), vals, height=0.66, color=colours,
                   edgecolor=t["surface"], linewidth=0.8)
    # The office is deliberately not annotated here. Where these roles are
    # sited is its own figure (--form sited); repeating it on the bars would
    # make two figures say the same thing and crowd this one.
    for b, v in zip(bars, vals):
        ax.text(b.get_width() + max(vals) * 0.015,
                b.get_y() + b.get_height() / 2, str(v),
                va="center", ha="left", fontsize=8, color=t["muted"])

    ax.set_yticks(range(len(names)))
    ax.set_yticklabels(names, fontsize=9, color=t["text"])
    for i, k in enumerate(names):
        if k in african:
            lab = ax.get_yticklabels()[i]
            lab.set_color(t["africa"])
            lab.set_fontweight("bold")

    ax.set_xlim(0, max(vals) * 1.12)
    ax.set_ylim(-0.8, len(names) - 0.2)
    ax.xaxis.grid(True, color=t["faint"], linewidth=1.0)
    ax.set_axisbelow(True)
    ax.set_xlabel("postings naming the language", fontsize=9,
                  color=t["muted"])

    handles = [Patch(facecolor=t["africa"], label="African language"),
               Patch(facecolor=t["hub"], label="Every other language")]
    leg = ax.legend(handles=handles, loc="lower right", frameon=False,
                    fontsize=9, handlelength=0.9, handleheight=0.9)
    for x in leg.get_texts():
        x.set_color(t["text"])

    fs.titles(ax, "Languages named in Trust and Safety postings",
          f"{len(african)} of {len(names)} languages are African, "
          f"accounting for {n_afr_post} of {n_post} postings", t)
    fig.tight_layout()
    save(fig, f"alt_languages_ranked{suffix}")



# ----------------------------------------------------------------- sited
# Where the language is spoken, against where the role sits. Three postings
# is too few for a distribution, and a bar chart of three bars of height one
# invites a fractional y-axis and reads as padding. Three postings is exactly
# right for showing three specific relationships, which is what this does.
LANGUAGE_REGION = {
    "Hausa": "West Africa", "Swahili": "East Africa", "Amharic": "Ethiopia",
    "Oromo": "Ethiopia", "Afaan Oromo": "Ethiopia", "Somali": "Horn of Africa",
    "Yoruba": "West Africa", "Igbo": "West Africa", "Zulu": "Southern Africa",
    "Xhosa": "Southern Africa", "Afrikaans": "Southern Africa",
    "Tigrinya": "Horn of Africa", "Wolof": "West Africa",
    "Kinyarwanda": "East Africa", "Luganda": "East Africa",
    "Shona": "Southern Africa", "Twi": "West Africa", "Akan": "West Africa",
}


def form_sited(t, suffix):
    rows = load_corpus()
    items = []
    for r in rows:
        a = (r.get("african_language") or "").split(";")[0].strip()
        if not a:
            continue
        lang = a.title()
        office = (r.get("primary_city") or "").split(";")[0].strip() \
            or (r.get("market_named") or "").split(";")[0].strip()
        items.append((lang, LANGUAGE_REGION.get(lang, "Africa"),
                      office or None, (r.get("platform") or "").strip()))
    if not items:
        print("  no African-language postings found; skipping sited")
        return
    items.sort(key=lambda x: (x[0], x[2] or "zzz"))

    n = len(items)
    fig, ax = plt.subplots(figsize=(6.6, 0.62 * n + 2.0))
    fig.patch.set_facecolor(t["surface"])
    base(ax, t)
    ax.set_xticks([]); ax.set_yticks([])

    LX, RX = 0.0, 1.0
    for i, (lang, region, office, _plat) in enumerate(items):
        y = n - 1 - i
        known = office is not None
        right_col = t["hub"] if known else t["muted"]

        ax.plot([LX, RX], [y, y], color=t["grid"], linewidth=1.6, zorder=1,
                solid_capstyle="round")
        ax.scatter([LX], [y], s=150, color=t["africa"], zorder=3,
                   edgecolors=t["surface"], linewidths=1.6)
        ax.scatter([RX], [y], s=150, color=right_col, zorder=3,
                   edgecolors=t["surface"], linewidths=1.6,
                   marker="o" if known else "X")

        ax.text(LX - 0.035, y + 0.14, lang, ha="right", va="bottom",
                fontsize=10, fontweight="bold", color=t["africa"])
        ax.text(LX - 0.035, y - 0.16, f"spoken in {region}", ha="right",
                va="top", fontsize=8.5, color=t["muted"])
        ax.text(RX + 0.035, y + 0.14,
                office if known else "no location stated",
                ha="left", va="bottom", fontsize=10, fontweight="bold",
                color=right_col)
        ax.text(RX + 0.035, y - 0.16,
                "role sited here" if known else "in the archived posting",
                ha="left", va="top", fontsize=8.5, color=t["muted"])

    ax.set_xlim(-0.72, 1.72)
    ax.set_ylim(-0.9, n - 0.1)
    # Say which platforms these actually come from rather than assuming all
    # three. In the present corpus every African-language posting is TikTok's,
    # and that is itself part of the finding.
    plats = sorted({p for *_, p in items if p})
    who = plats[0] if len(plats) == 1 else \
        (" and ".join(plats) if len(plats) == 2 else "all three platforms")
    WORDS = {1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five",
             6: "Six", 7: "Seven", 8: "Eight", 9: "Nine"}
    count = WORDS.get(n, str(n))
    fs.titles(ax, "Every posting in the corpus that names an African language",
              f"{count} posting{'' if n == 1 else 's'}, all {who}. "
              f"None is sited in Africa.", t)
    fig.tight_layout()
    save(fig, f"alt_african_language_siting{suffix}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--form", default="all",
                    choices=["dots", "units", "matrix", "languages", "sited", "all"])
    ap.add_argument("--theme", default="light", choices=sorted(THEMES))
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()
    t = THEMES[args.theme]
    suffix = "" if args.theme == "light" else f"_{args.theme}"

    if args.form in ("dots", "all"):
        form_dots(t, args.top, suffix)
    if args.form in ("units", "all"):
        form_units(t, suffix)
    if args.form in ("matrix", "all"):
        form_matrix(t, suffix)
    if args.form in ("languages", "all"):
        form_languages(t, suffix)
    if args.form in ("sited", "all"):
        form_sited(t, suffix)


if __name__ == "__main__":
    main()
