"""
make_figures.py

Draws Figures 1 and 2 from `unified_country_table.csv`.

Both figures come from the same file. That is the whole point of this script:
the previous Figure 1 was a hand-built chart definition with typed-in arrays,
and its Google column summed to 163 against the 154 stated in the text. Two
figures drawn from one table cannot disagree with each other.

Design notes
------------
Three platforms, so three categorical hues, assigned in fixed order and never
cycled. The palette was validated for colour-vision deficiency separation
across all pairs before anything was drawn: worst pair deltaE 9.2 under
deuteranopia, 24.0 under normal vision. One of the three sits below 3:1
contrast against the surface, so every bar carries a visible numeric label
rather than relying on the fill alone.

No dual axes, no pie charts, no gradient fills, no value printed on every
gridline. Grid and axis recede; the data is the only thing at full strength.

Usage
-----
    python scripts/make_figures.py
    python scripts/make_figures.py --theme dark
    python scripts/make_figures.py --top 12

Writes PNG at 300 dpi and PDF vector into figures/.
"""

from pathlib import Path
import argparse
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import figure_style as fs
fs.apply(matplotlib)
from matplotlib.ticker import MaxNLocator

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DP = ROOT / "data_processed"
FIG = ROOT / "figures"

PLATFORMS = [("meta", "Meta"),
             ("google_youtube", "Google/YouTube"),
             ("tiktok", "TikTok")]

THEMES = {"light": fs.theme("light"),
          "dark": fs.theme("dark")}


def load_country_table():
    path = DP / "unified_country_table.csv"
    if not path.exists():
        raise SystemExit("run build_unified_corpus.py first")
    with path.open(encoding="utf-8-sig") as fh:
        rows = [r for r in csv.DictReader(fh)]
    for r in rows:
        for k in ("meta", "google_youtube", "tiktok", "total"):
            r[k] = int(r[k] or 0)
    return rows


def style(ax, t):
    ax.set_facecolor(t["surface"])
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["grid"])
    ax.spines["bottom"].set_linewidth(0.8)
    ax.tick_params(colors=t["muted"], labelsize=9, length=0)
    ax.xaxis.label.set_color(t["muted"])
    ax.yaxis.label.set_color(t["muted"])


# --------------------------------------------------------------- Figure 1
def figure_one(rows, t, top, out_stem):
    """Where Trust and Safety roles are located, by platform."""
    rows = [r for r in rows if r["total"] > 0]
    rows.sort(key=lambda r: r["total"], reverse=True)
    shown = rows[:top]
    rest = rows[top:]
    # An African row must never be folded into "Other". The article's central
    # claim is about Africa; burying it in a residual category would hide the
    # one number a reader came to find.
    africa_rest = [r for r in rest if r["region"] == "Africa"]
    if africa_rest:
        shown += africa_rest
        rest = [r for r in rest if r["region"] != "Africa"]
    if rest:
        shown.append({
            "country": f"Other ({len(rest)} countries)", "region": "Other",
            "meta": sum(r["meta"] for r in rest),
            "google_youtube": sum(r["google_youtube"] for r in rest),
            "tiktok": sum(r["tiktok"] for r in rest),
            "total": sum(r["total"] for r in rest),
        })
    shown.reverse()

    n = len(shown)
    fig, ax = plt.subplots(figsize=(7.6, 0.34 * n + 1.4))
    fig.patch.set_facecolor(t["surface"])
    style(ax, t)

    h = 0.24
    ys = range(n)
    for i, (key, label) in enumerate(PLATFORMS):
        offset = (1 - i) * (h + 0.03)   # small surface gap between bars
        vals = [r[key] for r in shown]
        bars = ax.barh([y + offset for y in ys], vals, height=h,
                       color=t["series"][i], label=label,
                       edgecolor=t["surface"], linewidth=0.8)
        for bar, v in zip(bars, vals):
            if v:
                ax.text(bar.get_width() + max(vals) * 0.012,
                        bar.get_y() + bar.get_height() / 2, str(v),
                        va="center", ha="left", fontsize=7.5,
                        color=t["muted"])

    ax.set_yticks(list(ys))
    ax.set_yticklabels([r["country"] for r in shown], fontsize=9,
                       color=t["text"])
    # mark the African row so it is findable without relying on colour
    for i, r in enumerate(shown):
        if r["region"] == "Africa":
            ax.get_yticklabels()[i].set_color(t["africa"])
            ax.get_yticklabels()[i].set_fontweight("bold")

    ax.set_xlabel("Trust and Safety postings", fontsize=9)
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=6))
    ax.xaxis.grid(True, color=t["grid"], linewidth=0.7)
    ax.set_axisbelow(True)

    leg = ax.legend(loc="lower right", frameon=False, fontsize=9,
                    handlelength=0.9, handleheight=0.9, borderpad=0.4)
    for txt in leg.get_texts():
        txt.set_color(t["text"])

    fs.titles(ax, "Where Trust and Safety roles are located", None, t)
    fig.tight_layout()
    save(fig, out_stem)


# --------------------------------------------------------------- Figure 2
def figure_two(rows, t, out_stem):
    """Hub concentration by platform: three hubs, elsewhere, Africa."""
    groups = ["Three hubs", "Elsewhere", "Africa"]
    HUBS = {"United States", "Singapore", "Ireland"}
    data = {label: {g: 0 for g in groups} for _, label in PLATFORMS}
    data["All platforms"] = {g: 0 for g in groups}
    for r in rows:
        if r["region"] == "Africa":
            g = "Africa"
        elif r["country"] in HUBS:
            g = "Three hubs"
        else:
            g = "Elsewhere"
        for key, label in PLATFORMS:
            data[label][g] += r[key]
        data["All platforms"][g] += r["total"]

    labels = [label for _, label in PLATFORMS] + ["All platforms"]
    labels.reverse()
    colours = [t["series"][0], t["series"][2], t["africa"]]

    fig, ax = plt.subplots(figsize=(7.6, 0.5 * len(labels) + 1.8))
    fig.patch.set_facecolor(t["surface"])
    style(ax, t)

    for i, label in enumerate(labels):
        total = sum(data[label].values()) or 1
        left = 0.0
        for j, g in enumerate(groups):
            v = data[label][g]
            if not v:
                continue
            pct = 100 * v / total
            ax.barh(i, pct, left=left, height=0.5, color=colours[j],
                    edgecolor=t["surface"], linewidth=1.4)
            if pct >= 7:
                ax.text(left + pct / 2, i, f"{pct:.0f}%", va="center",
                        ha="center", fontsize=9, color="#ffffff",
                        fontweight="bold")
            left += pct
        ax.text(101, i, f"n = {total}", va="center", ha="left",
                fontsize=8, color=t["muted"])

    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=9.5, color=t["text"])
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100%"])
    ax.xaxis.grid(True, color=t["grid"], linewidth=0.7)
    ax.set_axisbelow(True)

    # Africa is half a per cent, so its segment is a sliver. The legend is
    # built from proxy handles rather than from whichever bar happened to be
    # drawn last, and the sliver carries a direct label, because a reader must
    # not have to find a one-pixel band to learn the paper's central number.
    from matplotlib.patches import Patch
    handles = [Patch(facecolor=colours[j], label=g) for j, g in enumerate(groups)]
    leg = ax.legend(handles=handles, loc="lower left",
                    bbox_to_anchor=(0, -0.30), ncol=3, frameon=False,
                    fontsize=9, handlelength=0.9, handleheight=0.9)
    for txt in leg.get_texts():
        txt.set_color(t["text"])

    all_i = labels.index("All platforms")
    a = data["All platforms"]["Africa"]
    a_tot = sum(data["All platforms"].values()) or 1
    if a:
        ax.annotate(f"Africa: {a} posting{'s' if a != 1 else ''} "
                    f"({100 * a / a_tot:.1f}%)",
                    xy=(100 - 100 * a / a_tot / 2, all_i),
                    xytext=(64, all_i + 0.50),
                    fontsize=8.5, color=t["africa"], fontweight="bold",
                    ha="left", va="center",
                    arrowprops=dict(arrowstyle="-", color=t["africa"],
                                    linewidth=1.0,
                                    connectionstyle="angle,angleA=0,angleB=90,rad=0"))

    fs.titles(ax, "Concentration in the three regulatory hubs",
          "United States, Ireland and Singapore", t)
    fig.tight_layout()
    save(fig, out_stem)


def save(fig, stem):
    FIG.mkdir(parents=True, exist_ok=True)
    for ext in fs.STYLE["formats"]:
        kw = {"dpi": fs.STYLE["dpi"]} if ext == "png" else {}
        p = FIG / f"{stem}.{ext}"
        fig.savefig(p, facecolor=fig.get_facecolor(), bbox_inches="tight", **kw)
        print("  wrote", p.relative_to(ROOT))
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", default="light", choices=sorted(THEMES))
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args()
    t = THEMES[args.theme]
    rows = load_country_table()

    suffix = "" if args.theme == "light" else f"_{args.theme}"
    print("drawing from unified_country_table.csv")
    figure_one(rows, t, args.top, f"figure1_country_by_platform{suffix}")
    figure_two(rows, t, f"figure2_hub_concentration{suffix}")

    total = sum(r["total"] for r in rows)
    hubs = sum(r["total"] for r in rows
               if r["country"] in {"United States", "Singapore", "Ireland"})
    africa = sum(r["total"] for r in rows if r["region"] == "Africa")
    print(f"\nlocated postings: {total}")
    print(f"  in the three hubs: {hubs}  ({100*hubs/total:.1f} per cent)")
    print(f"  in Africa        : {africa}  ({100*africa/total:.1f} per cent)")
    print("\nquote these figures, not the ones in the current manuscript.")


if __name__ == "__main__":
    main()
