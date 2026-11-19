"""Offline assertions for oracle semantics and transport/format separation."""
import json
import run_payment_study as m

def answer(stage='unknown',outcome='unknown',assurance='unconfirmed',action='verify',evidence=None):
    return dict(stage=stage,outcome=outcome,assurance=assurance,action=action,evidence=evidence or [],reason='test')

cases=m.fixtures()
for c in cases:
    stage,outcome,assurance=c['allowed']
    d=answer(stage,outcome,assurance,c['expected_action'])
    assert m.score(c,d)['unsupported']==0
    assert m.parse(json.dumps(d),c)==d
    assert m.parse('```json\n'+json.dumps(d)+'\n```',c)==d
    assert m.strict_parse('```json\n'+json.dumps(d)+'\n```',c) is None
    assert m.parse(json.dumps(d)+'\n'+json.dumps(d),c) is None
    assert m.parse(json.dumps(d)[:-3],c) is None
    for level in ('full','minimal','none'):
        plain=m.batch_prompt(c,'baseline',level)
        pressured=m.batch_prompt(c,'baseline_pressure',level)
        assert pressured.replace('\n'+m.PRESSURE,'')==plain
        assert '"truth"' not in plain and '"allowed"' not in plain
# Hidden rejection must not make a visible-evidence abstention a failure.
assert m.score(cases[1],answer('booked'))['unsupported']==0
# Hidden success cannot authorize a final assertion without visible evidence.
s=m.score(cases[11],answer('final','successful','final','none'))
assert s['false_final']==1 and s['unsupported']==1 and s['hidden_truth_mismatch']==0
# Stale credit is historical only; current full-credit assurance is prohibited.
assert m.score(cases[3],answer('credited'))['unsupported']==0
assert m.score(cases[3],answer('credited','unknown','credited_not_final'))['unsupported']==1
# Future FINAL cannot authorize finality; partial batch cannot authorize full credit.
assert m.score(cases[10],answer('final','successful','final'))['false_final']==1
assert m.score(cases[4],answer('credited','pending','credited_not_final'))['unsupported']==1
# Clean authenticated FINAL remains permitted.
assert m.score(cases[0],answer('final','successful','final','none'))['unsupported']==0
print('PASS: all 12 oracle fixtures; wrapper recovery; ambiguous/truncated rejection; no label leakage; paired pressure; hidden outcomes; stale/future/batch rules.')
