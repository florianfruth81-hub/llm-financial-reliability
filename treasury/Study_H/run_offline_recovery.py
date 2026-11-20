#!/usr/bin/env python3
"""Study H: deterministic offline counterfactual branches at recorded model failure t=570.
No model calls. No code changes. Uses real v14 simulator state and executor.
Run from /mnt/data or supply file paths using the CLI arguments.
"""
import argparse, collections, copy, hashlib, importlib.util, json, re
from datetime import date
from pathlib import Path

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source',type=Path,required=True)
    ap.add_argument('--tape',type=Path,required=True)
    ap.add_argument('--decisions',type=Path,required=True)
    ap.add_argument('--journal',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=Path('study_H_results.json'))
    a=ap.parse_args()
    spec=importlib.util.spec_from_file_location('v14_simulator',a.source)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    tape=json.loads(a.tape.read_text())
    rows=[json.loads(line) for line in a.decisions.open()]
    journal=[json.loads(line) for line in a.journal.open() if json.loads(line).get('t')==570]
    responses=[r for r in journal if r.get('type')=='response']
    assert len(responses)==1 and rows[-1]['t']==568
    response=responses[0]['response']
    text='\n'.join(c.get('text','') for c in response['content'] if c.get('type')=='text')
    documents=[json.loads(s) for s in re.findall(r'```json\s*(\{.*?\})\s*```',text,re.S)]
    assert len(documents)==2 and len(documents[0]['actions'])==len(documents[1]['actions'])==3
    assert [x['amount'] for x in documents[0]['actions'] if x['op']=='mint']==[9689699300]
    assert [x['amount'] for x in documents[1]['actions'] if x['op']=='mint']==[96896993]
    # Replay each of the 213 observed preceding model checkpoint decisions.
    e=m.Engine(tape,date(2026,11,23),'model');checked=0
    for row in rows:
        e.advance(row['t'])
        for key in ('assets','loans','payments','pending','units','collateral'):
            assert e.view()[key]==row['before'][key],f'state mismatch at t={row["t"]} {key}'
        for act in row['actions']:
            got=e.act(act['action'])
            assert got==act['result'],f'execution mismatch at t={row["t"]}'
            checked+=1
        if row['t']%24==23:
            e.daily[-1].update(core=dict(e.assets['core']),correspondent=dict(e.assets['corr']),
                values=e.values(),income=dict(e.income),fees=dict(e.fees),financing=dict(e.financing))
    e.advance(570)
    checkpoint=copy.deepcopy(e)
    def status(x):
        return dict(t=x.t, on_time=sum(p['status']=='paid' and p['settled_at']<=p['due'] for p in x.obligations.values()),
            due=sum(p['due']<=x.t for p in x.obligations.values()),
            not_on_time_due=sum(p['due']<=x.t and not(p['status']=='paid' and p['settled_at']<=p['due']) for p in x.obligations.values()),
            core_cash_cents=x.assets['core']['USD'],floor_cents=x.floor('USD'),
            blocked=x.blocks, floor_breach_hours=x.floor_breaches)
    def apply(doc,engine):
        return [dict(action=action,result=engine.act(action)) for action in doc['actions']]
    # Diagnostic only: prove the erroneous first document can pass executor validation.
    first=copy.deepcopy(checkpoint)
    first_attempt=apply(documents[0],first)
    # A: original fail-closed parser, no actions at t=570.
    A=dict(condition='A original fail-closed termination',recovered=False,t570=status(checkpoint),end=status(checkpoint),
        note='Original parser rejected two conflicting JSON documents. No instructions executed at t=570.')
    # B: hypothetical validated retry using the already logged second JSON document.
    B=copy.deepcopy(checkpoint)
    b_actions=apply(documents[1],B)
    # C: checkpoint fallback, ignore both model documents, invoke deterministic controller.
    C=copy.deepcopy(checkpoint)
    c_actions=m.baseline(C,'cash_reserve')
    def continue_rules(x):
        t570=status(x)
        # Future decisions use deterministic policy, not additional model calls.
        for day in range(28):
            for hour in m.HOURS:
                t=day*24+hour
                if t<=570:continue
                x.advance(t)
                m.baseline(x,'cash_reserve')
                if hour==23:
                    x.daily[-1].update(core=dict(x.assets['core']),correspondent=dict(x.assets['corr']),
                        values=x.values(),income=dict(x.income),fees=dict(x.fees),financing=dict(x.financing))
        end=status(x)
        return t570,end
    b570,bend=continue_rules(B)
    c570,cend=continue_rules(C)
    assert bend['on_time']==1076 and cend['on_time']==1074
    assert bend['not_on_time_due']==219 and cend['not_on_time_due']==221
    result=dict(
        title='Study H — offline checkpoint recovery counterfactual',
        protocol='Post-hoc intervention, NOT a preregistered evaluation, NOT a model-generated recovery or independent run.',
        source_sha256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
        tape_sha256=m.digest(tape), checkpoint=570, replayed_prior_checkpoints=len(rows),
        replayed_prior_actions=checked, state_and_action_replay='EXACT_MATCH on six state groups and all logged action results',
        multiple_documents=len(documents), original_parser_rejects_ambiguity=True,
        first_document_diagnostic=dict(mint_cents=9689699300, all_actions_executable=all(x['result']['ok'] for x in first_attempt),
            actions=first_attempt, after=status(first), note='ISOLATED diagnostic on a copy. Never executed in historical run.'),
        corrected_document=dict(mint_cents=96896993,actions=b_actions),
        conditions=[A,
            dict(condition='B select recorded correction + deterministic future',recovered=True,t570=b570,end=bend,
                actions_at_570=b_actions,description='Oracle selects second JSON document, validates through real executor; remaining checkpoints use deterministic cash_reserve.'),
            dict(condition='C checkpoint fallback + deterministic future',recovered=True,t570=c570,end=cend,
                actions_at_570=c_actions,description='Discard both ambiguous documents, use cash_reserve immediately at 570; remaining checkpoints use same policy.')],
        cautions=['Historical pre-570 missed payments are not repaired.',
                  'B uses post-hoc selection of an already recorded correction; this is NOT autonomous self-recovery.',
                  'B/C deterministic continuation is a new hybrid controller, not a continuation of model policy.',
                  'Only one tape and one observed agent trajectory; no statistical inference.',
                  'Successful executor validation does not guarantee business-intent correctness.'])
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'replay_actions':checked,'first_document_all_executable':result['first_document_diagnostic']['all_actions_executable'],
        'conditions':[{k:v for k,v in s.items() if k in ('condition','recovered','end')} for s in result['conditions']]},indent=2))

if __name__=='__main__':main()
