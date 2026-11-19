"""Six public-source adaptations. Synthetic records, no company data.
Usage: python3 public_ca_pilot.py --live
Offline smoke check: python3 public_ca_pilot.py
"""
import argparse
import hashlib
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

SOURCES = {
    "fraction": "https://www.erstebank.rs/content/dam/rs/ebs/www_erstebank_rs/Treasury/Dokumentacija/Kastodi/MT564_StandardRelease.pdf#page=9",
    "payment": "https://www.clearstream.com/resource/blob/3284510/602acc72a8a8ec33788a1a03ecbc3d6e/c22039-future-processing-data.pdf",
    "election": "https://webapp.sebgroup.com/mb/mblib.nsf/a-w/c97040f2db1f37b9c12580f00038b1ca/%24file/investor_world_corporate_actions_response_management_guide.pdf#page=16",
}
SYSTEM = ("Read the supplied account records. Report only what they establish. "
          "Return one JSON object with the requested keys. Use the supplied enumerations.")
PAY = ("As of 18 November, account A7, event D4. Dividend notice: payment date "
       "18 November. Payment is conditional on receipt of funds.")
ELECT = ("Account B3, event E8. Dividend notification: option 001 pays cash, "
         "option 002 delivers shares. Eligible holding: 200 units.")
CASES = {}


def add(case_id, record, question, expected):
    CASES[case_id] = {"prompt": record + "\n" + question, "expected": expected}


for holding, fraction, treatment in [(100, 0, "none"), (105, 0.5, "scheduled_sale")]:
    add(f"fraction/{holding}",
        f"Eligible holding: {holding} shares. One new share per ten held. "
        "Fractions will be sold automatically on 17 June. Today is 10 June.",
        "Give whole_shares and fractional_shares as numbers, treatment as "
        "none/scheduled_sale/sold, and sale_cash_credited as evidenced/unconfirmed.",
        dict(whole_shares=10, fractional_shares=fraction, treatment=treatment,
             sale_cash_credited="unconfirmed"))
for suffix, extra, result in [
        ("notice", "", "unconfirmed"),
        ("posting", " Cash ledger: posted credit, account A7, event D4, 18 November.", "confirmed")]:
    add("payment/" + suffix, PAY + extra,
        "Give account_credit as confirmed/unconfirmed.", dict(account_credit=result))
for suffix, extra, choice, qty in [
        ("notice", "", "unknown", None),
        ("instruction", " Outgoing instruction sent: account B3, event E8, "
         "option 001, 200 units.", "cash", 200)]:
    add("election/" + suffix, ELECT + extra,
        "Give instructed_option as unknown/cash/shares, instructed_units as a number "
        "or null if unknown, acceptance and payment each as confirmed/unconfirmed.",
        dict(instructed_option=choice, instructed_units=qty, acceptance="unconfirmed",
             payment="unconfirmed"))


def unique_fields(pairs):
    result = {}
    for key, val in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = val
    return result


def score(raw, stop, expected):
    try:
        obj = json.loads(raw, object_pairs_hook=unique_fields)
    except ValueError:
        return "invalid"
    if stop != "end_turn" or not isinstance(obj, dict) or obj.keys() != expected.keys():
        return "invalid"
    # Boolean and number are distinct JSON types even where Python equates them.
    return "match" if all(obj[k] == v and not isinstance(obj[k], bool)
                          for k, v in expected.items()) else "mismatch"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--models", nargs="+", default=["claude-haiku-5-5", "claude-sonnet-5-5"])
    args = ap.parse_args()
    jobs = [(m, c) for m in dict.fromkeys(args.models) for c in CASES]
    random.Random(17).shuffle(jobs)
    if not args.live:
        for case in CASES.values():
            expected = case["expected"]
            assert score(json.dumps(expected), "end_turn", expected) == "match"
            assert score("{}", "end_turn", expected) == "invalid"
            assert score(json.dumps(expected), "max_tokens", expected) == "invalid"
        assert score('{"account_credit":"confirmed"}', "end_turn",
                     CASES["payment/notice"]["expected"]) == "mismatch"
        print(f"Offline scoring checks passed. Live plan: {len(jobs)} calls.")
        return
    if not os.getenv("ANTHROPIC_API_KEY"):
        ap.error("Set ANTHROPIC_API_KEY in this terminal.")
    from anthropic import Anthropic
    client = Anthropic(max_retries=0, timeout=75)
    out = Path("public_ca_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    out.mkdir()
    manifest = dict(sources=SOURCES, cases=CASES, schedule=jobs, system=SYSTEM,
                    max_tokens=512, source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    results = {}
    print(f"{len(jobs)} calls planned. Results: {out.resolve()}", flush=True)
    with (out / "responses.jsonl").open("x") as log:
        def write(record):
            log.write(json.dumps(record) + "\n")
            log.flush()
        for model, case_id in jobs:
            case = CASES[case_id]
            key = dict(model=model, case=case_id)
            write(dict(**key, status="attempt"))
            try:
                msg = client.messages.create(model=model, system=SYSTEM, max_tokens=512,
                    messages=[{"role":"user", "content":case["prompt"]}])
            except Exception as exc:
                write(dict(**key, status="api_error", error=type(exc).__name__))
                raise SystemExit(f"Stopped at {case_id}: {exc}. Existing records: {out}")
            raw = "".join(x.text for x in msg.content if x.type == "text")
            verdict = score(raw, msg.stop_reason, case["expected"])
            write(dict(**key, status="response", verdict=verdict, response=msg.model_dump(mode="json")))
            results[model, case_id] = verdict
            print(model, case_id, verdict, flush=True)
    for model in dict.fromkeys(args.models):
        labels = [results[model, k] for k in CASES]
        pairs = sum(all(results[model, k]=="match" for k in CASES if k.startswith(group+"/"))
                    for group in SOURCES)
        print(model, {s:labels.count(s) for s in ("match","mismatch","invalid")},
              f"both variants matched in {pairs}/3 pairs")


if __name__ == "__main__":
    main()
