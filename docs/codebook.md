# Codebook

Coding scheme for the Trust and Safety employment corpus. Every variable is
coded from the text of the advertisement itself: title, body, team or function
label, and stated location. Nothing is inferred from the company's reputation,
from other postings, or from the coder's background knowledge of the role.

`scripts/code_postings.py` proposes each of these codes by dictionary matching
and records the exact matched string in `notes`. That is a first pass to make
review tractable, not a substitute for a human decision. See ETHICS.md.

---

## Identification and provenance

| Variable | Type | Definition |
|---|---|---|
| `record_id` | integer | Sequential within the release. Not stable across releases. |
| `company_name` | string | `Meta`, `TikTok`, or `Google/YouTube`. |
| `job_id` | string | The platform's own posting identifier, from the URL. The deduplication key. |
| `source_url` | string | Where the advertisement was retrieved. For Meta, the original URL rather than the Archive wrapper. |
| `capture_mode` | string | `wayback_snapshot`, `rendered_jsonld`, `rendered_dom`, or `manual_text_capture`. Records how the text was obtained, since extraction method affects completeness. |
| `date_accessed` | ISO date | For live captures, the collection date. For archived captures, the snapshot date. |
| `job_text_sha256` | hex | SHA-256 of the advertisement text as coded. Lets anyone verify they are looking at the same text without the text being redistributed. |

## Position

| Variable | Type | Definition |
|---|---|---|
| `job_title` | string | As advertised, unedited. |
| `location` | string | As advertised, unedited, including multi-office strings. |
| `primary_country` | string | The first country named in `location`. Used for country-level counts so each posting is counted once. |
| `all_countries` | string | Every country named, semicolon separated. |
| `location_count` | integer | How many countries `location` names. Greater than 1 means the posting spans offices. |
| `team_function` | string | The team or organisational unit named, where the advertisement states one. Blank where it does not; do not infer. |

## Coded signals

Each signal is `yes` or `no` on the presence of explicit textual evidence.
Absence of evidence is coded `no`, not blank. Blank means not yet coded.

### `africa_facing_signal`

`yes` when the advertisement names an African country, region, city, or market
scope, including MENA where the scope covers North Africa.

`africa_facing_text` records the phrase as it appears, not the dictionary stem.
"French Sub-Saharan Africa" is the evidence; "africa" is not.

A role is Africa-facing on the basis of its stated **market scope**, not its
location. A Dublin post covering Sub-Saharan Africa is Africa-facing. A Nairobi
post covering global operations is not.

### `language_signal` and `languages_named`

`yes` when the advertisement names one or more specific human languages as a
requirement or preference. `languages_named` lists them.

A generic phrase such as "additional languages an advantage" is `no`: it names
no language and so creates no verifiable capacity claim.

### `moderation_signal`

`yes` when the advertisement describes reviewing, moderating or enforcing
against user content: content moderation, content review, community standards
or guidelines enforcement, handling harmful or objectionable material.

### `integrity_signal`

`yes` for the platform-specific integrity vocabulary: integrity as an
organisational unit, inauthentic behaviour, misinformation or disinformation,
civic or election integrity, business integrity.

### `policy_enforcement_signal`

`yes` for the enforcement and escalation apparatus: policy enforcement,
escalations, appeals, trust and safety as a named function, abuse
investigations, risk or safety operations.

These three signals overlap by design. A single posting can be `yes` on all
three, and many are. They record different aspects of the same governance work,
not mutually exclusive categories.

### `vendor_signal`

`yes` when the advertisement refers to vendors, business process outsourcing,
outsourced or third-party partner operations, service providers, or vendor
management.

This is the marker of assemblage structure: it identifies posts whose holder
manages moderation labour rather than performing it.

### `worker_risk_signal`

`yes` when the advertisement itself discloses exposure to distressing material:
graphic or objectionable content, child exploitation, self-injury, animal abuse,
graphic violence, or an explicit wellbeing or resilience provision.

Coded from the employer's own disclosure. It measures what platforms admit
about the work, which is the analytically interesting thing.

### `offshore_relative_to_market`

Three-valued, and the distinction matters.

| Value | Condition |
|---|---|
| `yes` | The posting is scoped to an African market but located in a governance hub elsewhere. |
| `no` | The posting is scoped to an African market and located in Africa. |
| *(blank)* | The posting carries no African market scope. |

Blank here is **not applicable**, not missing. It must stay distinguishable
from a missing value in any analysis, because collapsing the two would treat
every non-Africa-facing role as evidence of onshoring.

This variable operationalises the article's spatial dimension of the
localisation gap directly.

## Reliability

Codes proposed by the script must be reviewed by a human. Because every
proposed code carries its trigger string in `notes`, review is a confirmation
task rather than a re-reading task.

For intercoder reliability, a second coder should code an independent sample
from the advertisement text without seeing the proposed codes. Agreement
between a human and the script measures the script's dictionaries and belongs
in a methods appendix as such, not as intercoder reliability.

## Change log for the scheme

Any change to a dictionary or a coding rule changes what the numbers mean.
Record it in `CHANGELOG.md` with the date and the reason, and note whether the
corpus was recoded.
