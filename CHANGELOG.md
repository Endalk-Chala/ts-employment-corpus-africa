# Changelog

Record every change that alters what the numbers mean: dictionary edits,
coding-rule changes, recollection, and any change to the release text mode.

## Unreleased

- Repository scaffolded. Collection, coding and release code added.
- `prepare_release.py` blocks any release where country counts exceed platform
  totals. This defect produced a nine-role discrepancy between the country and
  platform figures in an earlier draft of the article.
- Release text mode defaults to `omit`, publishing a SHA-256 of each
  advertisement instead of its text.
