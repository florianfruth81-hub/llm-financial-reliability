# Study G — Sustained treasury v14

This folder contains the original simulator, deterministic-policy tests, frozen seed-42 tape, and selected evidence for the model trajectory and deterministic `cash_reserve` policy. v14 is **software version**, not the study identifier.

At simulated hour 570, both policies faced 1,136 due payments: cash reserve 1,136 on time and the incomplete Claude model trajectory 917 on time (219 missed). Floor-breach hours: 0 in both. The deterministic controller completed the full 28-day horizon (1,295/1,295); the model did not. One tape, one model trajectory, no demonstrated economic superiority.

The independent `treasury_deterministic_baseline.py` is an exploratory controller: its passing tests are **not** the integrated `cash_reserve` comparison.

## Offline reproduction

From repository root:

```bash
python3 studies/G_treasury_sustained/src/treasury_sustained_study.py --self-test
PYTHONPATH=studies/G_treasury_sustained/src python3 -m unittest discover -s studies/G_treasury_sustained/tests -v
python3 studies/G_treasury_sustained/src/treasury_sustained_study.py --policy cash_reserve --scenario sustained_20bd --days 28 --start 2026-11-23 --seed 42
```

Do **not** use `--live` or `--policy model` for the free baseline. `results/` contains a curated subset, not the full original model journal. The simulator's net-interest metric lacks a missed-payment penalty.

See `provenance.json` for original run identifiers and source checks.
