"""
assemble_release.py

Copies the current working corpus into the release repository.

Run this from ts_jobs_corpus/. It populates ../ts-jobs-corpus-repo/ with the
scripts, the public data and the figures, and leaves everything the .gitignore
excludes exactly where it is.

What is released and what is not
--------------------------------
Released: the unified posting table, the country table, the complete screening
registries with every inclusion and exclusion decision and its triggering term,
the source registries with archived URLs and capture timestamps, all collection
and analysis code, and the figures.

Not released: archived HTML, full advertisement text, and anything touching the
interviews. The first two are excluded for size and copyright, the third
permanently, because the consent agreement does not cover publication.

Usage
-----
    python scripts/assemble_release.py
    python scripts/assemble_release.py --dry-run
"""

from pathlib import Path
import argparse
import csv
import hashlib
import shutil

SCRIPT_DIR = Path(__file__).resolve().parent
WORK = SCRIPT_DIR.parent                       # ts_jobs_corpus/
REPO = WORK.parent / "ts-jobs-corpus-repo"
csv.field_size_limit(10_000_000)

# Code that belongs in the release. Anything not listed stays behind.
SCRIPTS = [
    "collect_wayback_meta.py",
    "collect_wayback_platform.py",
    "screen_and_fetch_candidates.py",
    "reextract_google_pages.py",
    "collect_tiktok_arm.py",
    "reconstruct_meta_arm.py",
    "clean_meta_jsonld.py",
    "code_postings.py",
    "build_unified_corpus.py",
    "figure_style.py",
    "make_figures.py",
    "make_figures_alt.py",
    "assemble_release.py",
    "prepare_release.py",
]

# Derived data. Safe to publish: no advertisement body text in any of these.
PUBLIC_DATA = [
    ("data_processed/unified_corpus.csv", "data/public/unified_corpus.csv"),
    ("data_processed/unified_country_table.csv",
     "data/public/unified_country_table.csv"),
    ("data_processed/tiktok_title_registry.csv",
     "data/public/screening_tiktok.csv"),
    ("data_processed/google_ts_candidates.csv",
     "data/public/screening_google.csv"),
    ("data_processed/meta_arm_screened.csv",
     "data/public/screening_meta.csv"),
]

REGISTRIES = [
    ("source_registry/tiktok_wayback_snapshots.csv",
     "source_registry/tiktok_wayback_snapshots.csv"),
    ("source_registry/google_wayback_snapshots.csv",
     "source_registry/google_wayback_snapshots.csv"),
]

# Columns that must never reach data/public/, whatever file they appear in.
FORBIDDEN = {"job_text", "text_sample", "description", "raw_html_path",
             "saved_html", "participant", "transcript", "quote"}


def copy(src, dst, dry):
    src, dst = Path(src), Path(dst)
    if not src.exists():
        print(f"  skip (missing) {src.relative_to(WORK) if WORK in src.parents else src}")
        return False
    if dry:
        print(f"  would copy {src.name} -> {dst.relative_to(REPO)}")
        return True
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"  {dst.relative_to(REPO)}")
    return True


def strip_forbidden(path, dry):
    """Drop any column on the forbidden list, and report what was dropped."""
    if dry or not path.exists() or path.suffix != ".csv":
        return
    with path.open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        return
    cols = list(rows[0].keys())
    drop = [c for c in cols if c.lower() in FORBIDDEN]
    if not drop:
        return
    keep = [c for c in cols if c not in drop]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keep, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"      dropped from release: {', '.join(drop)}")


def checksums(dry):
    """A manifest, so anyone can confirm they have the same files."""
    if dry:
        return
    lines = ["# Release manifest", "",
             "SHA-256 of every released data file.", "", "```"]
    for p in sorted((REPO / "data" / "public").glob("*.csv")):
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{h}  data/public/{p.name}  ({p.stat().st_size:,} bytes)")
    for p in sorted((REPO / "source_registry").glob("*.csv")):
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        lines.append(f"{h}  source_registry/{p.name}  ({p.stat().st_size:,} bytes)")
    lines.append("```")
    (REPO / "MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("  MANIFEST.md")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    dry = args.dry_run

    if not REPO.exists():
        raise SystemExit(f"release repo not found at {REPO}")

    print(f"working folder : {WORK}")
    print(f"release folder : {REPO}\n")

    print("scripts")
    for name in SCRIPTS:
        copy(WORK / "scripts" / name, REPO / "scripts" / name, dry)

    print("\npublic data")
    for src, dst in PUBLIC_DATA:
        if copy(WORK / src, REPO / dst, dry):
            strip_forbidden(REPO / dst, dry)

    print("\nsource registries")
    for src, dst in REGISTRIES:
        copy(WORK / src, REPO / dst, dry)

    print("\nfigures")
    figs = sorted((WORK / "figures").glob("*")) if (WORK / "figures").exists() else []
    for p in figs:
        if p.suffix.lower() in (".png", ".pdf", ".svg"):
            copy(p, REPO / "figures" / p.name, dry)
    copy(WORK / "scripts" / "make_figures.py",
         REPO / "figures" / "make_figures.py", dry)

    print("\ndocumentation")
    for name in ("META_ARM_RECONSTRUCTION.md", "GOOGLE_ARM_RECONSTRUCTION.md",
                 "README_collection.md", "figure_reconciliation.md"):
        copy(WORK / name, REPO / "docs" / name, dry)

    print("\nmanifest")
    checksums(dry)

    # A last look for anything the .gitignore should have caught
    print("\nsafety check")
    bad = []
    for p in REPO.rglob("*"):
        if not p.is_file():
            continue
        low = p.name.lower()
        if p.suffix.lower() in (".html", ".warc", ".m4a", ".mp3", ".docx"):
            bad.append(p)
        if any(w in low for w in ("interview", "transcript", "consent",
                                  "participant")):
            bad.append(p)
    if bad:
        print("  DO NOT COMMIT, these should not be in the release:")
        for p in bad:
            print(f"    {p.relative_to(REPO)}")
    else:
        print("  clear: no archived HTML, no interview material")

    print("\nnext:")
    print("  cd ../ts-jobs-corpus-repo")
    print("  git status        # read this before the first commit")


if __name__ == "__main__":
    main()
