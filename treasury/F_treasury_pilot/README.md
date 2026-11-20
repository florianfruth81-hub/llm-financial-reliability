# Study F — Two-day treasury autonomy pilot (v9)

The paper's Study F examines three autonomy levels: `route_only`, `route_and_funding`, and `full_workflow`, each using one synthetic two-day trajectory. This folder preserves the archived v9 **run-specific source snapshots** and summaries for an offline reference, unguided model, and guided model.

| Autonomy scope | Unguided model on time | Guided model on time |
|---|---:|---:|
| Route-only | 9/9 | 9/9 |
| Route + funding | 8/9 | 7/9 |
| Full workflow | 8/9 | 9/9 |

The guidance comparison is **confounded**, not causal evidence about autonomy. All numbers describe related decisions on a tiny synthetic tape. The v9 pilot uses a DIFFERENT simulator and experimental protocol from sustained Study G; outcomes must not be pooled.

The original `source.py` snapshots and `manifest.json` files are kept together under `results/` to preserve their source/run relationship. Do not use `--live` for offline inspection. `decisions.jsonl` is included only as stored decisions, not as a proof of independently reproduced scores. API journals are excluded pending review.

See `provenance.json` for exact original folder names, run settings, source hashes and arm metrics.
