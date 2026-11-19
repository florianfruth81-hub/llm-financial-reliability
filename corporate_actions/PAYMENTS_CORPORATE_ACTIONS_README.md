# Payments and corporate actions: curated research add-on (Studies A–E)

This archive is intended to **merge into** the existing `financial-agent-reliability` GitHub repository. Extract it into the repository root: it creates `studies/A_payments/` through `studies/E_ca_citation_presentation/` and `PAYMENTS_CORPORATE_ACTIONS_README.md`. It **does not replace** the repository's root README or change the existing treasury package. Do not upload this ZIP itself as the repository content.

## Study-to-source map (source verified against recorded hashes)

| Paper label | Topic | Original folder/run | Publication path | Audit status |
|---|---|---|---|---|
| A | Payment evidence and assurance | `v3/payment_study_research/results_20261106_084236_009169` | `studies/A_payments` | Recorded source matches original protocol hash; later guard fix separate |
| B | Corporate-action brief notices | `v4/results_ca_20261106_141442_026775` | `studies/B_ca_brief_notices` | Corrected v2 source matches run plan |
| C | Corporate-action history / strict output | `v6/ca_live_v3/api_results` | `studies/C_ca_history_contract` | Live-development source matches manifest; mock excluded |
| D | Strict-contract focused diagnostic | `v7/public_ca_20261110T102229212370Z` (Haiku); `...102547202371Z` (Sonnet) | `studies/D_ca_strict_diagnostic` | Original source matches both manifests; retrospective inspection is not an executable pass |
| E | Action and evidence citation under presentation variants | `v8/ca_presentation_20261110T194131265536Z` (Haiku); `...200644578117Z` (Sonnet) | `studies/E_ca_citation_presentation` | Exact source matches both manifests |

## Primary reported results and limits

- **A:** Sonnet full policy: 0/144 evidence-policy violations; Sonnet minimal/none: 50/144 and 52/144. Haiku full-policy 48/144 evidence-policy violations; one response terminated at max tokens. Model settings and reference definitions must not be conflated with previous A versions.
- **B:** Sonnet 216/216 valid with 0 scored action mismatches. Haiku 202/216 valid; one mismatch (unnecessary clarification). Cases were synthetic and revised between v1 and v2.
- **C:** Sonnet 105/108 strictly valid; Haiku 25/108. Strict formatting and underlying semantic accuracy are different endpoints. The included source includes an offline diagnostic for extractable terms.
- **D:** Six responses per model. Strict formatting initially failed in all six Haiku responses and five of six Sonnet responses. Manually recovering desired values later does not make the submitted output executable.
- **E:** 108 responses; 105/105 *scorable* decisions matched the supplied references, while 77/105 had exact citation-set matches. Source reference labels are AI-assisted and not all independently reviewed.

Counts describe repeated responses on related synthetic fixtures, not independent cases or production error rates. Raw logs are kept to permit auditing. `api_results` refers to original model responses; this package excludes v6 mock harness outputs. Versions v1/v2, early v3, original v4 v1, and v5 are deliberately **not** represented as the frozen studies in this package; they remain historical development artifacts in the user's original Archive.zip.

## Reproducibility without API spending

The package contains the recorded source snapshots, case plans, output logs and metric summaries. Re-evaluating raw results offline may require running scripts' scoring-only functionality or writing a separate read-only verifier: do **not** execute their default run commands without inspecting `--help`, as these scripts can call the Anthropic API. The presence of source and logs does not imply that a single zero-API recomputation command has been validated for all five studies.

## Audit notes

**Study A source mismatch avoided:** the protocol records SHA256 of the original `run_payment_study.py.before_guard_fix`. The subsequent `run_payment_study.py` has a different hash and is included as `run_payment_study_later_guard_fix.py` for disclosure, not presented as the source that originally produced the logged answers. The audit has **not independently rerun** the original paid generation nor independently reviewed all synthetic labels.

**Public upload caution:** Automated scanning found no common API-key or private-key token patterns, but this is not a comprehensive sensitivity review. Raw API transcripts contain provider response metadata and may contain synthetic account/context fields. Review before publishing, preferably in a private GitHub repository.

**Names:** A–E are paper study identifiers; `v3`, `v4`, `v6`–`v8` are development folders. Original source locations, hashes and record timestamps are preserved in `provenance.json`. No original file was renamed or deleted.
