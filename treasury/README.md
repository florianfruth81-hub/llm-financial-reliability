# Reliable AI Decisions in Financial Operations

**Exploratory synthetic research** on evidence-grounded decisions, executable instructions, and settlement outcomes in financial workflows. This repository contains a selected reproducibility package, not every development run.

## Research question

Can an AI agent deliver incremental value beyond deterministic controls while respecting payment deadlines, liquidity constraints, and executable-output requirements?

## Verified sustained treasury experiment (Study G)

Both runs used the same v14 simulator source and frozen 28-day synthetic tape (seed 42, start 2026-11-23). The model run terminated at simulated hour 570, while the deterministic `cash_reserve` run completed the full horizon.

| Evaluation horizon | Deterministic `cash_reserve` | Claude model |
|---|---:|---:|
| Through simulation hour 570: payments on time | 1,136 / 1,136 | 917 / 1,136 |
| Through simulation hour 570: missed payments | 0 | 219 |
| Through simulation hour 570: liquidity floor breach hours | 0 | 0 |
| Full 28-day run complete | Yes | No |
| Full run: on-time payments | 1,295 / 1,295 | Not reached |

**Interpretation:** one synthetic tape and one agent trajectory; not independent samples. The deterministic controller prioritizes payment reliability rather than optimizing income. Reported net interest excludes economic penalties for missed payments, so it **does not establish relative economic superiority**. The model run ended after an ambiguous response and was fail-closed. These results do **not** establish general superiority of rules over AI.

## Repository map

- `paper/`: six-page research synthesis (Studies A–G, selected related work).
- `src/treasury_sustained_study.py`: simulator v14 (standard library); SHA-256 `d77017cff1f4f198f09ed611ededb1041b1561933de07427527cf86870518cb7`.
- `data/`: frozen synthetic 28-day tape; digest recorded in model manifest (`5b80d93b3e47ae607d0f90d973888224935067ebd6ce980ba2b36ae7faf65ab8`).
- `results/`: selected summaries, original model manifest and daily reporting; **not raw model transcripts**.
- `src/treasury_deterministic_baseline.py`: separate exploratory controller; **not** the simulator's `cash_reserve` policy. Its unit tests do not constitute a head-to-head run.

## Reproduce the zero-API-cost baseline

Requires Python 3.12+ (standard library only). From repository root:

```bash
python3 src/treasury_sustained_study.py --self-test
PYTHONPATH=src python3 -m unittest discover -s tests -v
python3 src/treasury_sustained_study.py --policy cash_reserve --scenario sustained_20bd --days 28 --start 2026-11-23 --seed 42
```

The simulator itself generates its deterministic tape from the declared seed. The copy in `data/` is included for inspection; no real transactions are involved. Do **not** use `--live` or `--policy model` to reproduce the zero-cost run.

## Study labels

- **A:** payment assurance
- **B–E:** corporate-actions investigations
- **F:** short treasury pilot
- **G:** sustained treasury experiment, including the `cash_reserve` comparator

Only **Study G's executable files and summaries** are currently packaged here. The paper discusses earlier investigations; their raw run artifacts are not yet curated for public reproduction.

## Limits and disclosure

This is self-directed exploratory work, with AI-assisted scenario/code/reference-label creation. Case labels have not all been independently domain-verified. The simulation is synthetic and not production banking software. No employer data, customer records, or production credentials should be uploaded. Model transcript publishing requires a separate privacy and content review.
