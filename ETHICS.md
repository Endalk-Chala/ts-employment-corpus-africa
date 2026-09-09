# Ethics and data handling

This document states what is released, what is withheld, and why. It is part
of the research record, not boilerplate.

## The four evidence streams and how each is treated

| Stream | Released here | Reason |
|---|---|---|
| Employment corpus (279 job advertisements) | Coded variables, aggregate counts, source URLs, capture timestamps | Public organisational data. See the text question below. |
| Practitioner interviews (n = 30) | **Nothing** | Consent covers analysis, not publication. |
| Documentary and litigation records | Citations only | Already public; no redistribution needed. |
| Tigray case vignette | **Nothing beyond what is in the article** | Single identifiable practitioner in a conflict setting. |

## Interviews are not in this repository and will not be

Thirty practitioners were interviewed, twelve of them vendor-side content
moderation workers with language expertise covering Swahili, Oromo, Amharic and
other African languages. That is a small, specialised professional population.
A moderator who worked on Ethiopian escalation during the Tigray conflict is
identifiable to an employer from role, market and period alone, even with a
name removed. Several described conditions their employers would prefer were
not described.

Deidentification does not solve this. When a population is small enough,
combinations of ordinary attributes re-identify people, and the consequences
here are not embarrassment but employment and, plausibly, safety.

So no transcripts, no audio, no field notes, no per-participant quotation
files, and no participant-level table of roles and locations. `.gitignore`
blocks these by pattern so an accidental `git add .` cannot publish them.
Anyone who needs to verify the interview claims should approach the author and,
where appropriate, an ethics committee, not this repository.

## The job advertisement text question

Job advertisements are published by companies for public consumption, and their
URLs and capture dates are recorded here so anyone can retrieve the same pages.
Whether to redistribute the **full text** of each advertisement is a separate
decision with two defensible answers.

**Withholding the text** avoids republishing several hundred pieces of
corporate copy that the platforms own and that their terms of service restrict.
It costs some verifiability: a reader cannot re-derive the codes from scratch.

**Releasing the text** makes the coding fully auditable, which is the stronger
scientific position, and fair-dealing or fair-use arguments for research are
reasonable. It carries a real, if small, legal risk and may breach terms of
service.

`scripts/prepare_release.py` supports both through `--text-mode`:

- `omit` (default) drops `job_text` and publishes a SHA-256 hash of it instead,
  so anyone who retrieves the page can verify they have the same text I coded.
- `excerpt` publishes the first 300 characters, enough to identify the posting.
- `full` publishes everything.

The default is `omit` because the hash preserves the verification property that
matters most while carrying the least risk. Change it deliberately, and record
the choice in `CHANGELOG.md` if you do.

## Collection conduct

Collection followed the constraints the article describes. Requests were rate
limited with a fixed delay. `robots.txt` was fetched and honoured per host, and
disallowed URLs were recorded as skipped rather than fetched. Archived Meta
pages came from the Internet Archive's public CDX API rather than from
circumventing any access control. No authentication was used and no login-only
material was collected.

None of this required an application for review, since no human subjects were
involved in the corpus arm. The interview arm did, and is not published here.

## Auto-coding is disclosed, not hidden

`scripts/code_postings.py` proposes codes by dictionary matching and writes the
exact matched string into the `notes` column of every row. This is a first pass
that makes human review of several hundred advertisements tractable. It is not
a coder.

Two consequences follow, and both belong in any methods section that uses this
pipeline. Intercoder reliability must be computed between two humans coding
independently; agreement between a human and this script measures the script.
And because every proposed code carries its trigger string, a reader can audit
the coding decisions rather than trusting them.

## Known limitations, restated

Carried over from the article so that anyone using this data meets them here
too. The corpus captures publicly declared governance capacity only, so vendor
moderation roles are largely invisible. It is biased towards English-language
postings. Advertisements record hiring intention, not confirmed headcount, and
a posting is not a person.

## Contact

Endalkachew H. Chala — endalk2006@gmail.com — ORCID 0000-0001-6210-6706
