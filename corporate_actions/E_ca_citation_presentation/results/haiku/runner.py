"""Corporate-action evidence presentation study. Synthetic records and policies.
Offline checks: python3 ca_scope_pilot.py
Live: add --live. Resume: --live --resume RESULT_FOLDER.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import re

REVISION = "scope-v3-presentations"
MAX_TOKENS = 2048
SETTINGS = {
    "claude-haiku-5-5": {"thinking": {"type": "disabled"}, "output_config": {"effort": "medium"}},
    "claude-sonnet-5-5": {"thinking": {"type": "between_tools"}, "output_config": {"effort": "medium"}},
}

SYSTEM = """The supplied records are complete and authoritative for this simulation.
Inline statements, labelled blocks and JSON entries are equally valid records.
No attachments, external lookup or additional verification are required.
A status of posted means a completed ledger entry. A posted reversal undoes only
the posting ID it references. An acceptance or sale applies only to the referenced
instruction or account. A later amendment changes only its specified option.
Use these definitions and only the records for the target.
Return one raw JSON object with exactly these fields:
decision: one of the decision labels in the question.
evidence: a nonempty JSON array of unique record IDs supporting the decision.
Include all records needed to establish the current state and exclude irrelevant records.
No Markdown fences, additional keys, explanations or surrounding prose."""
SOURCES = {
    "fraction": "https://www.erstebank.rs/content/dam/rs/ebs/www_erstebank_rs/Treasury/Dokumentacija/Kastodi/MT564_StandardRelease.pdf#page=9",
    "payment": "https://www.clearstream.com/resource/blob/3284510/602acc72a8a8ec33788a1a03ecbc3d6e/c22039-future-processing-data.pdf",
    "election": "https://webapp.sebgroup.com/mb/mblib.nsf/a-w/c97040f2db1f37b9c12580f00038b1ca/%24file/investor_world_corporate_actions_response_management_guide.pdf#page=16",
}

PRESENTATIONS = ("inline", "blocks", "json")
SCENARIOS = {
    "account": dict(source="payment", target="Account R42, event D8",
        question="What is the credit status? Choose credited or unconfirmed.",
        records=[
            dict(id="N2", statement="Dividend scheduled today, conditional on receipt of funds."),
            dict(id="L7", statement="Completed dividend credit posted to account R24 for event D8.")],
        decision="unconfirmed", evidence_sets=[["N2", "L7"], ["L7"]]),
    "event": dict(source="payment", target="Account V4, event C19",
        question="What is the credit status? Choose credited or unconfirmed.",
        records=[
            dict(id="B2", statement="Events C19 and C91 concern the same security and payment date."),
            dict(id="K3", statement="Completed dividend credit posted to account V4 for event C19.")],
        decision="credited", evidence_sets=[["K3"]]),
    "instruction": dict(source="election", target="Instruction J51",
        question="What is the instruction status? Choose sent_only or accepted.",
        records=[
            dict(id="M2", statement="Instructions J51 and J15 were transmitted for the same account and event, each electing shares for 80 units."),
            dict(id="T9", statement="Custodian acceptance received for instruction J15 only.")],
        decision="sent_only", evidence_sets=[["M2", "T9"]]),
    "option": dict(source="election", target="Election for option 002 at 15:00 UTC on 19 November 2026",
        question="What action is permitted? Choose transmit or hold.",
        records=[
            dict(id="F3", statement="Both options originally closed at 16:00 UTC on 18 November 2026. Client authorization is present and all other eligibility checks passed."),
            dict(id="P8", statement="Authorized amendment for this event extends option 002 only to 16:00 UTC on 20 November 2026.")],
        decision="transmit", evidence_sets=[["F3", "P8"]]),
    "reversal": dict(source="payment", target="Posting W71 in account A6, after the final ledger entry",
        question="What is its current state? Choose credited or reversed.",
        records=[
            dict(id="H4", statement="Completed credits W71 and W17 posted to account A6 this morning."),
            dict(id="D2", statement="Final ledger entry: completed reversal posted for original posting W71 in account A6.")],
        decision="reversed", evidence_sets=[["D2"], ["H4", "D2"]]),
    "fraction": dict(source="fraction", target="Fractional sale for account G8 under event S1",
        question="What is the sale status? Choose sold or scheduled.",
        records=[
            dict(id="S6", statement="Account G8 holds 125 old shares under event S1, receiving one new share per ten. Its half-share entitlement is scheduled for sale."),
            dict(id="X4", statement="Executed sale of a half-share entitlement for account G3 under event S1. This is the only completed sale report.")],
        decision="scheduled", evidence_sets=[["S6", "X4"]]),
}


def render(case, presentation):
    records = case["records"]
    if presentation == "inline":
        body = " ".join(r["id"] + ": " + r["statement"] for r in records)
    elif presentation == "blocks":
        body = "Complete supplied records\n" + "\n\n".join(
            "Record " + r["id"] + "\n" + r["statement"] for r in records)
    else:
        # Identical statement strings in all arms. Only the enclosing representation changes.
        body = json.dumps({"records": records}, ensure_ascii=False, indent=2)
    return "Target: " + case["target"] + "\n" + body + "\n" + case["question"]


def unique_fields(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("duplicate JSON key")
    return result


def evaluate(raw, stop, case):
    result = dict(format_ok=False, decision="unscorable", citation="unscorable")
    if stop != "end_turn":
        return result
    text = raw.strip()
    fence = re.fullmatch(r"```(?:json)?\s*\n(.*?)\n```", text, re.S | re.I)
    body = fence[1] if fence else text
    try:
        obj = json.loads(body, object_pairs_hook=unique_fields)
    except ValueError:
        return result
    if not isinstance(obj, dict):
        return result
    ids = obj.get("evidence")
    well_formed_ids = (isinstance(ids, list) and bool(ids)
                      and all(isinstance(x, str) for x in ids)
                      and len(ids) == len(set(ids)))
    result["format_ok"] = (not fence and set(obj) == {"decision", "evidence"}
                           and isinstance(obj.get("decision"), str) and well_formed_ids)
    if isinstance(obj.get("decision"), str):
        result["decision"] = "match" if obj["decision"] == case["decision"] else "mismatch"
    if well_formed_ids:
        result["citation"] = ("match" if any(set(ids) == set(accepted)
                              for accepted in case["evidence_sets"]) else "mismatch")
    return result


def plan(models, repeats):
    jobs = [dict(model=m, case=c, presentation=p, repeat=r)
            for m in models for c in SCENARIOS for p in PRESENTATIONS for r in range(repeats)]
    random.Random(29).shuffle(jobs)
    return jobs


def identity(job):
    return tuple(job[k] for k in ("model", "case", "presentation", "repeat"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checks():
    assert sum(c["decision"] in {"credited", "transmit", "reversed"} for c in SCENARIOS.values()) == 3
    for case in SCENARIOS.values():
        for p in PRESENTATIONS:
            prompt = render(case, p)
            for record in case["records"]:
                assert record["statement"] in prompt
        for ids in case["evidence_sets"]:
            assert set(ids) <= {r["id"] for r in case["records"]}
            raw = json.dumps(dict(decision=case["decision"], evidence=ids))
            assert evaluate(raw, "end_turn", case) == dict(format_ok=True, decision="match", citation="match")
            wrapped = evaluate("```json\n" + raw + "\n```", "end_turn", case)
            assert wrapped == dict(format_ok=False, decision="match", citation="match")
            assert evaluate(raw, "max_tokens", case)["decision"] == "unscorable"
        correct = dict(decision=case["decision"], evidence=["missing"])
        result = evaluate(json.dumps(correct), "end_turn", case)
        assert result["decision"] == "match" and result["citation"] == "mismatch"
        correct["decision"] = "wrong"
        correct["evidence"] = case["evidence_sets"][0]
        result = evaluate(json.dumps(correct), "end_turn", case)
        assert result["decision"] == "mismatch" and result["citation"] == "match"
        assert evaluate(raw + raw, "end_turn", case)["decision"] == "unscorable"
    assert len(plan(list(SETTINGS), 3)) == 108


def summarize(folder, manifest):
    entries = [json.loads(line) for line in (folder / "responses.jsonl").read_text().splitlines()]
    results = {identity(e): e for e in entries if e["status"] == "response"}
    attempted = {identity(e) for e in entries if e["status"] == "attempt"}
    lines = ["SYNTHETIC CORPORATE-ACTION PRESENTATION STUDY",
             "References are AI-assisted and unreviewed. Three repeats reuse six scenarios.",
             "Citation matching checks predefined supporting ID sets.",
             "model / presentation | answers / planned | format | decision correct / scorable | citation correct / scorable"]
    for model in manifest["models"]:
        for presentation in PRESENTATIONS:
            rows = [e for key, e in results.items() if key[0] == model and key[2] == presentation]
            dec = Counter(e["scores"]["decision"] for e in rows)
            cite = Counter(e["scores"]["citation"] for e in rows)
            lines.append(f"{model} / {presentation} | {len(rows)} / {6*manifest['repeats']} | "
                         f"{sum(e['scores']['format_ok'] for e in rows)} | "
                         f"{dec['match']} / {dec['match']+dec['mismatch']} | "
                         f"{cite['match']} / {cite['match']+cite['mismatch']}")
    lines.append(f"Collected {len(results)}/{len(manifest['jobs'])}; uncertain attempts "
                 f"{len(attempted-set(results))}; pending {len(manifest['jobs'])-len(attempted)}.")
    lines.append("Unscorable and missing responses remain outside correct-answer counts.")
    text = "\n".join(lines)
    (folder / "summary.txt").write_text(text + "\n")
    print(text)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--live", action="store_true")
    p.add_argument("--models", nargs="+", default=list(SETTINGS))
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--resume", type=Path)
    p.add_argument("--max-calls", type=int, default=108,
                   help="Upper limit for this invocation, including attempts that fail.")
    args = p.parse_args()
    checks()
    if args.repeats < 1 or args.max_calls < 1 or any(m not in SETTINGS for m in args.models):
        p.error("Use positive repeat/call limits and the supported model IDs.")
    models = list(dict.fromkeys(args.models))
    jobs = plan(models, args.repeats)
    if not args.live:
        print(f"Offline checks passed. {len(SCENARIOS)} scenarios x 3 presentations x "
              f"{args.repeats} repeats x {len(models)} models = {len(jobs)} calls.")
        return
    if not os.getenv("ANTHROPIC_API_KEY"):
        p.error("Set ANTHROPIC_API_KEY in this terminal.")
    from anthropic import Anthropic
    client = Anthropic(max_retries=0, timeout=75)
    script = Path(__file__).resolve()
    if args.resume:
        folder = args.resume
        manifest = json.loads((folder / "manifest.json").read_text())
        if manifest["revision"] != REVISION or manifest["source_sha256"] != digest(script):
            p.error("Resume requires the same script revision and source hash.")
        jobs = manifest["jobs"]
    else:
        folder = Path("ca_presentation_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        folder.mkdir()
        manifest = dict(revision=REVISION, cases=SCENARIOS, sources=SOURCES, system=SYSTEM,
                        models=models, repeats=args.repeats, jobs=jobs,
                        source_sha256=digest(script), max_tokens=MAX_TOKENS, request_settings=SETTINGS,
                        prompts={c: {style: render(case, style) for style in PRESENTATIONS}
                                 for c, case in SCENARIOS.items()},
                        scoring="Exact raw schema for format. Raw JSON or single enclosing fence for "
                                "content. Decision and supporting ID-set matches scored independently. "
                                "Extra fields fail format. Prose or multiple objects are unscorable.")
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2))
        (folder / "runner.py").write_bytes(script.read_bytes())
        (folder / "responses.jsonl").touch()
    print("Saving in", folder.resolve(), flush=True)
    attempted = {identity(e) for e in map(json.loads, (folder / "responses.jsonl").read_text().splitlines())
                 if e["status"] == "attempt"}
    pending = [j for j in jobs if identity(j) not in attempted]
    import time
    with (folder / "responses.jsonl").open("a") as log:
        def write(record):
            log.write(json.dumps(record) + "\n")
            log.flush()
            os.fsync(log.fileno())
        for job in pending[:args.max_calls]:
            write(dict(job, status="attempt"))
            try:
                response = client.messages.create(model=job["model"], system=manifest["system"],
                    max_tokens=manifest["max_tokens"], **manifest["request_settings"][job["model"]],
                    messages=[dict(role="user", content=manifest["prompts"][job["case"]][job["presentation"]])])
            except Exception as exc:
                write(dict(job, status="api_error", error=type(exc).__name__))
                summarize(folder, manifest)
                raise SystemExit(f"Stopped: {exc}. Resume skips the uncertain attempt.")
            raw = "".join(b.text for b in response.content if b.type == "text")
            scores = evaluate(raw, response.stop_reason, manifest["cases"][job["case"]])
            write(dict(job, status="response", scores=scores, response=response.model_dump(mode="json")))
            print(job["model"], job["case"], job["presentation"], job["repeat"], scores, flush=True)
            if response.stop_reason == "max_tokens":
                summarize(folder, manifest)
                raise SystemExit("Output truncated. Evidence saved; inspect before continuing.")
            time.sleep(1.05)
    summarize(folder, manifest)


if __name__ == "__main__":
    main()
