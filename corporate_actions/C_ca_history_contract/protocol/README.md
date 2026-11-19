# Corporate-action history study

This is a new DEVELOPMENT study, not a rerun or silent fix of previous results.
The uploaded simulator remains separate. No real transactions execute.

## Free commands
python3 run_ca_study.py --self-test
python3 run_ca_study.py --prepare ca_study
python3 run_ca_study.py --mock ca_study

Preparing creates 36 cases, REVIEW.md, review.json, config.json, a frozen manifest,
PROTOCOL.md with the accepted action sets, and a source snapshot. The mock command
exercises 216 scheduled jobs for free.
Run the same command again to resume; completed or uncertain jobs are not replayed.
Use --limit 4 for a free interrupted-run test. Mock results are not model results.
An incomplete/limited/budget-stopped run exits with code 2 and saves its reports;
a fully collected run exits 0. Resume with the same command and no --limit.

## Before a paid run
Cases derive from previously seen scenarios, so no independent held-out
confirmation is claimed. If you cannot verify their labels, leave review.json
unchanged. Use --allow-unreviewed for explicitly UNREVIEWED DEVELOPMENT; the
status persists in the frozen execution record, metrics and summary. The results
are then reference-policy disagreements, not validated operational model errors.
Only record approved=true and a reviewer name after actual review; set
independently_reviewed truthfully. No claim of review is needed to do development.

Edit config.json to enter available model IDs and current standard uncached API
input/output prices. The example IDs come from your old logs and are UNVERIFIED.
No prices are guessed. --prepare-live NEW_FOLDER fills verified first-party
uncached rates (2026-11-10) offline. It makes no provider calls or access checks.
Default supported modes are Haiku disabled and Sonnet between_tools, with medium
effort in both: no upfront thinking in this no-tool-call task. API modes remain
different and are logged; this is not a maximum-capability comparison.
Per-model settings explicitly override shared settings before requests are frozen.
A failure halts rather than silently changing settings.
Prices: https://platform.claude.com/docs/en/about-claude/pricing
Request docs: https://platform.claude.com/docs/en/api/messages/create

Set ANTHROPIC_API_KEY only in your local environment. Install the SDK locally:
python3 -m pip install anthropic
python3 run_ca_study.py --run ca_study

For labels that have NOT been reviewed:
python3 run_ca_study.py --run ca_study --allow-unreviewed

--run is the only paid mode and asks before spending. Default reservation limit
is $2; you choose the cap in config.json before the first live call. This package
has NOT made paid calls or verified provider/model compatibility. Token-count
requests are paced/cached, generation SDK retries are disabled. Rate-limit
retries apply to token counting only. Generation errors retain an uncertain
reservation and halt. Resume never resends uncertain or invalid responses.
The local budget is based on entered standard uncached rates and logged usage,
not a provider billing guarantee. Do not enable caching/extra services without
extending the accounting. Other account traffic is outside this budget.

## Integrity and output
cases/policy/code are frozen at prepare; execution config/review lock on first
run separately in mock_results and api_results. Change code/cases/config for a
NEW run, not to relabel existing observations. A schedule seed makes the order
repeatable; it does NOT make model generations deterministic.
execution.json: exact scheduled jobs and configuration. events.jsonl: fsynced,
hash-chained attempts/results, exact requests, usage and provider model IDs.
scores.json/metrics.json/summary.txt: derived, regenerable reports.
Do not edit the journal. A damaged/truncated journal tail fails closed. A stale
writer.lock may be removed ONLY after confirming no writer is active.

## What is and is not scored
Strict JSON/schema validity; all extracted reference terms; proposed action;
quantity; explicitly prohibited proposal; unnecessary escalation; exact quotation
and decisive document IDs. Citation checks do NOT establish semantic entailment.
Request IDs, accepted action sets, simulated accepted-quantity targets, new write
counts, same-ID replays and payload conflicts are also recorded. Withdrawal
prohibition uses retain_and_notify, not an undefined escalation action.
The offline verifier-on-extracted-terms diagnostic is NOT an independent treatment
arm or proof of benefit; it can help locate errors. No three-way agent experiment
is represented as completed. Families/history levels/repeats are related.
History length is 0/5/15 irrelevant messages; decisive evidence position is fixed
per template and balanced over templates, not fully crossed within each template.
The references still require domain validation. A scripted oracle pass only tests
the harness. Code/source hashes detect changes, not scientific correctness.
To incorporate reviewed corrections without editing an existing run, copy its
cases.json, edit the copy, and prepare a NEW folder:
python3 run_ca_study.py --prepare ca_reviewed --cases-file reviewed_cases.json
Internal checks do not prove the corrected prose entails its reference labels.

## Original simulator audit (free)
Place its source.py, plan.json and episodes.json alone in original_results/.
python3 run_ca_study.py --audit-original original_results
It reproduces stored scores then writes a separate post-hoc rescore. It does NOT
overwrite originals or claim independent validation. No API calls occur.
