# data/processed/

Working files. Not committed.

Collectors write here, `code_postings.py` adds the coded signals here, and
`prepare_release.py` reads from here to build `data/public/`.

Files at this stage may still contain full advertisement text, so `.gitignore`
excludes everything except this note. Publish through `prepare_release.py`
rather than by copying files across by hand: the release step is where the
integrity checks run.
