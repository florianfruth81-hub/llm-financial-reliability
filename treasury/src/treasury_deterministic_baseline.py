#!/usr/bin/env python3
"""Deterministic treasury baseline policy (v14 integration candidate).

NO network/API calls. Standard-library only.

Two modes:
  schedule: inspect frozen tape and write an earliest-eligible payment schedule.
            This DOES NOT execute payments or report success/returns.
  decide:   read JSON observations (one per line) from an authoritative simulator
            and emit JSON action proposals (one per line). Simulator remains
            responsible for validation, time progression, interest, accounting,
            and execution. No balance is updated optimistically.

To obtain comparable baseline metrics, call decide(...) at the same checkpoints
as model policy in treasury_sustained_study.py and feed actions into THE SAME
validator/executor. DO NOT compare schedule output to model execution metrics.

Observation contract (amounts in USD *cents*, times absolute hours):
{
 "t": 8, "core_cents": 12000000000, "floor_cents": 2500000000,
 "payments": [{"id":"S0-DOM-0","amount":5209140,
               "earliest_send":8,"due":9,"routes":["domestic"]}],
 "available_funding_cents": 0,  // optional; confirmed borrowable headroom
 "allowed_ops": ["pay","borrow"], // optional; defaults to pay only
 "confirmed_routes": ["domestic","correspondent"] // optional
}

Output: {"t": 8, "actions": [...], "unfunded": [...], "notes": [...]}

IMPORTANT: Funding action schema is a *candidate* adapter and might not match
v14; do not enable borrowing until checked against the original source.
"""
import argparse
import json
import sys
from pathlib import Path

DEFAULT_ROUTE_ORDER = ("domestic", "correspondent", "tokenized_deposit", "stablecoin")


def integer(value, label):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be an integer (cents or absolute hours)")
    return value


def validate_payment(p):
    for k in ("id", "amount", "earliest_send", "due", "routes"):
        if k not in p:
            raise ValueError(f"payment missing {k}: {p}")
    integer(p["amount"], "payment.amount")
    integer(p["earliest_send"], "payment.earliest_send")
    integer(p["due"], "payment.due")
    if p["amount"] <= 0 or not p["routes"]:
        raise ValueError(f"invalid payment {p['id']}")
    return p


def decide(obs, enable_borrow=False, route_order=DEFAULT_ROUTE_ORDER):
    """Pure policy function: same observation yields identical action proposals.

    Payment-first, deadline-order, floor-preserving. Borrowing is OFF by
    default because funding constraints and action schema must be validated
    against the original v14 engine before use.
    """
    t = integer(obs["t"], "t")
    cash = integer(obs["core_cents"], "core_cents")
    floor = integer(obs["floor_cents"], "floor_cents")
    if cash < 0 or floor < 0:
        raise ValueError("cash and floor must be nonnegative")
    ops = set(obs.get("allowed_ops", ["pay"]))
    confirmed = set(obs.get("confirmed_routes", ["domestic", "correspondent"]))
    payments = [validate_payment(p) for p in obs.get("payments", [])]
    seen = set()
    for p in payments:
        if p["id"] in seen:
            raise ValueError(f"duplicate payment ID: {p['id']}")
        seen.add(p["id"])
    eligible = sorted((p for p in payments if p["earliest_send"] <= t <= p["due"]),
                      key=lambda p:(p["due"], p["earliest_send"], p["id"]))
    expired = sorted(p["id"] for p in payments if p["due"] < t)
    actions, unfunded, notes = [], [], []
    if expired:
        notes.append(f"{len(expired)} payment(s) already past due on observation")
    funding_headroom = integer(obs.get("available_funding_cents", 0), "available_funding_cents")
    if funding_headroom < 0:
        raise ValueError("available_funding_cents must be nonnegative")
    # Actions are constructed against *conservative reserved cash*; the real
    # engine must independently validate every proposal.
    reserved_cash = cash
    for p in eligible:
        route = next((r for r in route_order if r in p["routes"] and r in confirmed), None)
        if route is None:
            unfunded.append({"payment":p["id"],"reason":"no_confirmed_route"})
            continue
        if "pay" not in ops:
            unfunded.append({"payment":p["id"],"reason":"pay_not_allowed"})
            continue
        amount = p["amount"]
        if reserved_cash - amount < floor:
            deficit = floor + amount - reserved_cash
            if enable_borrow and "borrow" in ops and funding_headroom >= deficit:
                # Candidate schema ONLY. Map to actual v14 borrow syntax first.
                actions.append({"id":f"rules-{t}-borrow-{p['id']}","op":"borrow",
                                "ccy":"USD","amount":deficit})
                reserved_cash += deficit
                funding_headroom -= deficit
            else:
                unfunded.append({"payment":p["id"],"reason":"insufficient_confirmed_cash",
                                 "shortfall_cents":deficit})
                continue
        actions.append({"id":f"rules-{t}-pay-{p['id']}","op":"pay",
                        "payment":p["id"],"route":route})
        reserved_cash -= amount
    return {"t":t,"actions":actions,"unfunded":unfunded,
            "expired":expired,"notes":notes,
            "projected_core_cents_if_all_accepted":reserved_cash,
            "policy":"rules_payment_first_v1"}


def schedule(tape):
    """Diagnostic only; never uses or leaks future tape data into decisions.
    Builds a schedule from every day's payment disclosure in isolation.
    """
    result=[]
    ids=set()
    for day in tape:
        day_idx = integer(day["day"], "day")
        for p in day["payments"]:
            validate_payment(p)
            if p["id"] in ids:
                raise ValueError("duplicate ID across tape: "+p["id"])
            ids.add(p["id"])
            send = p["earliest_send"]
            if send//24 < day_idx:
                raise ValueError(f"payment {p['id']} earliest send precedes disclosure day")
            route = next((r for r in DEFAULT_ROUTE_ORDER if r in p["routes"]),None)
            result.append({"payment":p["id"],"disclosed_day":day_idx,
                           "earliest_send":send,"due":p["due"],
                           "amount_cents":p["amount"],"route_candidate":route,
                           "status":"NOT_EXECUTED"})
    return sorted(result,key=lambda r:(r["earliest_send"],r["due"],r["payment"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="mode", required=True)
    s=sp.add_parser("schedule",help="Validate tape and write non-executable schedule")
    s.add_argument("--tape",required=True)
    s.add_argument("--out",required=True)
    d=sp.add_parser("decide",help="JSONL observations in; action proposals out")
    d.add_argument("--input",default="-",help="observation JSONL, or - for stdin")
    d.add_argument("--out",default="-",help="action proposal JSONL, or - for stdout")
    d.add_argument("--enable-borrow",action="store_true",
                   help="EXPERIMENTAL: requires confirming borrow action contract")
    args=ap.parse_args()
    if args.mode=="schedule":
        tape=json.loads(Path(args.tape).read_text(encoding="utf-8"))
        rows=schedule(tape)
        out=Path(args.out)
        with out.open("w",encoding="utf-8") as f:
            for row in rows:f.write(json.dumps(row,sort_keys=True)+"\n")
        print(f"Schedule audit: {len(rows)} payment instructions; no payments executed. Saved {out}")
        return
    inp=sys.stdin if args.input=="-" else open(args.input,encoding="utf-8")
    out=sys.stdout if args.out=="-" else open(args.out,"w",encoding="utf-8")
    try:
        for lineno,line in enumerate(inp,1):
            if not line.strip():continue
            try:
                proposal=decide(json.loads(line),enable_borrow=args.enable_borrow)
            except (ValueError,KeyError,TypeError) as e:
                print(f"Invalid observation line {lineno}: {e}",file=sys.stderr)
                raise SystemExit(2)
            out.write(json.dumps(proposal,sort_keys=True)+"\n")
            out.flush()
    finally:
        if inp is not sys.stdin:inp.close()
        if out is not sys.stdout:out.close()

if __name__=="__main__": main()
