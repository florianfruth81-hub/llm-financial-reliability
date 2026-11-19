PAYMENT ASSURANCE STUDY — RESEARCH REVISION 2026-11-06

1. Put run_payment_study.py and test_payment_study.py in your v3 folder.
2. In Terminal:
   cd /Users/tutlhino_1/Dev/Anthropic/v3
   python3 -m pip install --upgrade anthropic
   python3 test_payment_study.py
   python3 run_payment_study.py
3. After preflight, enter y to authorize the full batch.
   Your existing ANTHROPIC_API_KEY environment setting is reused.
4. Keep your Mac awake and connected. Preflight is approximately 15 minutes;
   generation adds time. Do not launch another copy simultaneously.
5. Upload answers.jsonl, summary.txt, protocol.json and family_metrics.csv from
   the NEW results folder. Keep plan.json and decision_metrics.csv too.

The batch contains 864 calls: 2 models x 3 policy ablations x 36 fixture variants
x 4 conditions. It includes the automated tests in the paid batch; there is no
manual case-by-case API workflow. Budget reservation limit is USD 3, applied to
all planned calls before generation. It stops before generation if the full
reservation exceeds the limit. Dollar reservation is not a provider billing cap.
Configured prices were verified on 2026-11-05; use --prices to override them.
No-up-front-thinking and medium effort are explicit for both models. Results
measure this configuration, not maximum capability. No truncated answer is
repaired; no ambiguous generation failure is automatically replayed.

WHAT CHANGED (freeze this revision before collecting results)
- Full policy explicitly defines fresh current full-payment credit assurance,
  negative ages, and the lowest milestone reached by ALL batch children.
- Exactly one complete schema-valid JSON decision can be recovered from prose
  or Markdown; the original format violation remains a separate metric.
- Primary errors are violations of VISIBLE evidence under the synthetic policy.
  Hidden-outcome mismatch is secondary and never substitutes for evidence.
- Full-policy adherence is primary. Minimal/none are rule-disclosure ablations;
  their disagreement is NOT automatically general model incompetence.
- All calls are shuffled deterministically across model/policy/condition to
  reduce time/order confounding; seeds and source SHA256 are saved.
- Per-response and per-family CSVs accompany the immutable raw answer log.

ABSTRACT BOUNDARIES
This is an exploratory synthetic benchmark, not a production safety validation.
12 stress families are represented by 3 amount/reference variants each. N=864
is the number of calls, NOT the number of independent scenarios. Do not attach
binomial confidence intervals treating calls as independent. One generation
per cell does not establish repeatability. The oracle and fixtures are AI-
authored and need domain review; offline assertions verify internal consistency,
not independent correctness. For submission, have a domain reviewer verify all
12 family labels and manually review all false-final flags and disputed errors.
Document that review. Do not claim independent validation unless it happened.

This revision follows inspection of earlier runs: label it exploratory and
versioned; do not describe it as prospectively preregistered before those runs.
Do not pool old and new results. Report formatting failures separately and
state how many calls/decisions support every denominator. Retain invalid
responses in all-attempt coverage reporting; never infer correctness from them.
A clean run means collection and decision extraction succeeded, not that the
model made no mistakes. Human review still determines abstract readiness.
