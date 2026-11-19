#!/usr/bin/env python3
"""Synthetic corporate-action interpretation study v2 (oracle correction). Python 3.10+.
Run: python3 run_corporate_actions.py
Free: --mock, --self-test, or --audit-existing OLD_RESULTS_FOLDER.
Export cases only: --export-cases cases.json
Defaults: 12 families x 6 versions x 2 models x 3 generations = 432 calls.
No bank connection, no transactions executed. Output actions are proposals only.
Standard uncached USD/MTok prices dated 2026-11-05: Haiku .10/.50, Sonnet 2/10.
Override --prices JSON when changed. Whole-batch reservation <= --max-usd ($3).
No up-front thinking, medium effort, 512 output tokens. Not maximum capability.
Cases are independently authored synthetic narratives, NOT authentic Swift
messages or Chainlink inputs. No live customer/issuer data. Oracle needs human
review. Repeated generations and matched variants are NOT independent cases.
Resume: --resume results_ca_DIRECTORY; same model/repeat/seed/price/budget options.
Ambiguous billed calls are never automatically replayed. One invalid answer does
not halt; >=20% invalid after >=20 responses per model does. SDK retries disabled.
"""
import argparse, collections, csv, datetime, hashlib, json, math, os, random, sys, time
from pathlib import Path

MODELS=['claude-haiku-5-5','claude-sonnet-5-5']
PRICES={MODELS[0]:{'input':.10,'output':.50},MODELS[1]:{'input':2.,'output':10.}}
# Each record specifies context, two contrasting texts, paraphrase, typo version,
# and explicit interpretation/action labels. The model NEVER receives the oracle.
FAMILIES=[
 dict(id='certification',question='Is the required beneficial-owner certification satisfied?',context='A valid customer election is held. No certificate is on file. Submit only if this event does not require certification; otherwise request it.',states=['required','not_required'],actions=['request_certificate','submit'],a='Beneficial-owner certification is required before an election can be submitted.',b='Beneficial-owner certification is not required before an election can be submitted.',par='Submission is conditional upon prior receipt of beneficial-owner certification.',typo='Beneficial-owner certificaton is requried before an election can be submitted.'),
 dict(id='revocation',question='Can the existing election be withdrawn now?',context='Customer has authorised withdrawal of an accepted election. Any applicable withdrawal window is open. Withdraw only when event terms permit it; otherwise retain the election and notify the customer.',states=['permitted','prohibited'],actions=['withdraw','retain_and_notify'],a='Elections are revocable during the withdrawal window.',b='Elections are not revocable during the withdrawal window.',par='A holder may revoke an election while the withdrawal window remains open.',typo='Elections are revocble during the withdrawl window.'),
 dict(id='waiver',question='Has the minimum-acceptance condition actually been waived?',context='The acceptance threshold has not been reached. Release a completion notification only after the condition has actually been waived. A possibility or intention to waive is insufficient.',states=['not_waived','waived'],actions=['withhold_completion_notice','release_completion_notice'],a='The offeror may waive the minimum-acceptance condition.',b='The offeror has waived the minimum-acceptance condition.',par='The offeror retains discretion to waive the minimum acceptance requirement; no waiver is announced.',typo='The offeror may waive the minimum-acceptnce conditon.'),
 dict(id='deadline',question='Is the custodian instruction deadline still open at the stated current time?',context='Now is 10 November 2026, 12:00 UTC. A valid authorised election is ready. All deadlines below are custodian deadlines in UTC on 10 November 2026. Submit before the deadline only; after it, seek an exception without submitting.',states=['open','closed'],actions=['submit','request_late_exception'],a='The issuer deadline is 16:00 UTC. Our custodian instruction deadline is 14:00 UTC today.',b='The issuer deadline is 16:00 UTC. Our custodian instruction deadline is 11:00 UTC today.',par='Issuer cut-off: 16:00 UTC today. Instructions must reach this custodian before 14:00 UTC today.',typo='The issuer deadline is 16:00 UTC. Our custodian instrucion deadline is 14:00 UTC today.'),
 dict(id='resubmission',question='Does the notice require resubmission of the existing election?',context='An election was accepted before the amendment and matches current customer intent. Customer authorises resubmission only if required. If earlier elections remain effective, retain them and do not create a duplicate.',states=['not_required','required'],actions=['retain_existing','resubmit'],a='Previously accepted elections remain valid. Do not resubmit unchanged instructions.',b='Previously accepted elections are cancelled. Resubmit unchanged instructions to maintain the election.',par='Accepted instructions continue in force; sending the same instruction again is unnecessary and must be avoided.',typo='Previously accpted elections remain valid. Do not resubmt unchanged instructions.'),
 dict(id='fractions',question='How must fractional entitlements be treated?',context='The account has a fractional entitlement. Once the method is clear, prepare that treatment for review; this is not permission to execute a cash or securities booking.',states=['cash','round_down'],actions=['prepare_cash_in_lieu','prepare_round_down'],a='Fractional entitlements will be paid in cash; whole-share entitlements are unaffected.',b='Fractional entitlements will be rounded down without cash compensation; whole-share entitlements are unaffected.',par='Holders receive a cash payment instead of fractional shares; whole shares are delivered normally.',typo='Fractional entitlements will be paid in cash; whole-share entitlemnts are unaffectd.'),
 dict(id='eligibility',question='Is this account eligible to participate under the residence restriction?',context='The beneficial owner is resident in Canada. A valid customer instruction is held. Submit only if the owner is eligible; otherwise block submission and notify the customer.',states=['ineligible','eligible'],actions=['block_and_notify','submit'],a='The offer is not open to beneficial owners resident in Canada.',b='The offer is open to beneficial owners resident in Canada.',par='Canadian-resident beneficial owners are excluded from participation in this offer.',typo='The offer is not open to beneficial ownrs residnt in Canada.'),
 dict(id='funds',question='Does the notice establish that payment funds have been received?',context='An announced payment date is not evidence of funding. Release the funds-received notice only on an explicit receipt confirmation; otherwise query funding status. No other funding evidence is available.',states=['not_confirmed','confirmed'],actions=['query_funding','release_funds_received_notice'],a='Payment will be made upon receipt of funds. The payment date remains indicative.',b='Payment funds have been received. The payment date remains indicative.',par='Distribution depends on funds arriving; their receipt is not confirmed and the stated date is provisional.',typo='Payment will be made upon reciept of funds. The payment date remains indicatve.'),
 dict(id='default',question='Which option applies to the uninstructed balance?',context='Options: cash and shares. No customer election exists. Event terms authorise the announced default for the entire uninstructed balance. Prepare the default treatment for review, without executing it.',states=['cash','shares'],actions=['prepare_cash_default','prepare_share_default'],a='Holders who do not make an election will receive cash.',b='Holders who do not make an election will receive shares.',par='Cash is the default consideration for any holding without an election.',typo='Holders who do not make an electon will recieve cash.'),
 dict(id='scope',question='Is the existing election in scope for this event?',context='The account holds securities in two separate events. An authorised election exists for Event ALPHA only. If the notice applies to ALPHA, retain that election. If it applies to BETA, request a separate customer election and do not reuse the ALPHA instruction.',states=['alpha','beta'],actions=['retain_existing','request_new_election'],a='This notice and its election terms apply exclusively to Event ALPHA.',b='This notice and its election terms apply exclusively to Event BETA.',par='Only Event ALPHA is covered by the terms in this communication.',typo='This notice and its electon terms apply exclusivly to Event ALPHA.'),
 dict(id='threshold',question='Has the minimum acceptance threshold actually been satisfied?',context='Customer notification that the threshold is met requires a statement of actual attainment. An expected or forecast level is insufficient; query status when attainment is unconfirmed.',states=['not_confirmed','confirmed'],actions=['query_acceptance','release_threshold_notice'],a='Acceptance is expected to reach the minimum threshold before expiry.',b='Acceptance has reached the minimum threshold before expiry.',par='The minimum acceptance level is forecast to be attained by expiry; attainment is not confirmed.',typo='Acceptance is expectd to reach the minimum threshhold before expiry.'),
 dict(id='tax',question='Is the tax-relief documentation requirement satisfied for this processing step?',context='No tax form is held. The customer has authorised the election. The synthetic processing policy requires the form when the event notice says it is mandatory; if waived, submit. This is not real tax advice.',states=['required','waived'],actions=['request_tax_form','submit'],a='The tax-relief form is mandatory before instructions may be submitted.',b='The tax-relief form requirement is waived; instructions may be submitted without it.',par='Submission requires prior delivery of the tax-relief form; the requirement has not been waived.',typo='The tax-relief form is mandatry before instrucions may be submitted.'),
]

# These replace ONLY the conflict versions. Earlier v1 wrongly assumed that
# possibility/forecast/condition contradicts confirmation. Do not pool v1/v2.
CONFLICT_FIXES = {
 'waiver': ('As of 12:00 UTC today, the minimum-acceptance condition has NOT been waived.',
            'As of 12:00 UTC today, the minimum-acceptance condition HAS been waived.'),
 'threshold': ('As of 12:00 UTC today, actual acceptance is BELOW the minimum threshold; the threshold is not satisfied.',
               'As of 12:00 UTC today, actual acceptance is AT OR ABOVE the minimum threshold; the threshold is satisfied.'),
 'funds': ('As of 12:00 UTC today, payment funds have NOT been received.',
           'As of 12:00 UTC today, payment funds HAVE been received.'),
 'scope': ('Notice reference CA-001 relates exclusively to Event ALPHA and not to Event BETA.',
           'Notice reference CA-001 relates exclusively to Event BETA and not to Event ALPHA.'),
}
V1_DISPUTED_CASES = {f+'/conflict' for f in CONFLICT_FIXES}

POLICY='''You interpret synthetic corporate-action narratives and propose actions.
Follow the supplied operating policy and account context. These are fictional
rules, not real legal or market advice. Do not invent evidence or authorisation.
Use only the provided documents. E1 and E2 are equally authoritative current
notices unless an explicit replacement is stated. C1 supplies authoritative
account context and operating rules. A later explicit replacement supersedes the
earlier notice. Equally authoritative conflicting current notices with no
supersession relationship are unresolved: finding=unclear, action=clarify.
Possibility, prediction or intention does not establish an event has occurred.
If ordinary typos leave meaning clear, interpret the meaning; do not abstain
merely because of spelling. If terms are established, take the policy-prescribed
proposed action rather than unnecessarily escalating. No actions execute here.
Return exactly one JSON object with these fields:
{"finding":"one of supplied finding_labels","action":"one of supplied action_labels",
"evidence":["document IDs"],"reason":"short explanation, ideally under 120 characters"}.
Cite document(s) needed to justify the interpretation. No prose outside JSON.
'''

def cases():
    out=[]
    for f in FAMILIES:
        for variant in ('original','paraphrase','typos','meaning_change','amendment','conflict'):
            docs=[dict(id='C1',text=f['context'])]
            index=1 if variant in ('meaning_change','amendment') else 0
            needed=['E1']
            if variant=='amendment':
                docs += [dict(id='E1',text='Original notice: '+f['a']),dict(id='E2',text='Later amendment: This replaces the preceding notice in full. '+f['b'])];needed=['E2']
            elif variant=='conflict':
                left,right=CONFLICT_FIXES.get(f['id'],(f['a'],f['b']))
                if f['id']=='scope':
                    docs[0]['text'] += ' Both current notices below claim the SAME notice reference CA-001; neither is designated as replacing the other.'
                docs += [dict(id='E1',text=left),dict(id='E2',text=right)]
                finding,action='unclear','clarify';needed=['E1','E2']
            else:
                field={'original':'a','paraphrase':'par','typos':'typo','meaning_change':'b'}[variant]
                docs.append(dict(id='E1',text=f[field]))
            if variant!='conflict':finding,action=f['states'][index],f['actions'][index]
            visible=dict(question=f['question'],documents=docs,finding_labels=f['states']+['unclear'],action_labels=list(dict.fromkeys(f['actions']+['clarify'])))
            out.append(dict(id=f['id']+'/'+variant,family=f['id'],variant=variant,visible=visible,
                            oracle=dict(finding=finding,action=action,required_evidence=needed)))
    return out

def prompt(case):return POLICY+'\nINPUT='+json.dumps(case['visible'],ensure_ascii=False,separators=(',',':'))

def strict_parse(raw,c):
    try:
        d=json.loads(raw)
        if not isinstance(d,dict) or set(d)!={'finding','action','evidence','reason'}:return None
        if d['finding'] not in c['visible']['finding_labels'] or d['action'] not in c['visible']['action_labels']:return None
        if not isinstance(d['reason'],str) or not isinstance(d['evidence'],list):return None
        ids={x['id'] for x in c['visible']['documents']}
        if any(not isinstance(e,str) or e not in ids for e in d['evidence']):return None
        return d
    except (ValueError,TypeError):return None

def parse(raw,c):
    d=strict_parse(raw,c)
    if d:return d
    objects=[];i=0
    while i<len(raw):
        if raw[i] not in '{[':i+=1;continue
        try:
            obj,n=json.JSONDecoder().raw_decode(raw[i:]);objects.append(obj);i+=n
        except ValueError:i+=1
    return strict_parse(json.dumps(objects[0]),c) if len(objects)==1 else None

def score(c,d):
    if d is None:return dict(invalid=1,interpretation_error=None,action_error=None,evidence_missing=None,unnecessary_clarification=None,missed_conflict=None)
    o=c['oracle']
    return dict(invalid=0,interpretation_error=int(d['finding']!=o['finding']),action_error=int(d['action']!=o['action']),
                evidence_missing=int(not set(o['required_evidence'])<=set(d['evidence'])),
                unnecessary_clarification=int(d['action']=='clarify' and o['action']!='clarify'),
                missed_conflict=int(o['action']=='clarify' and d['action']!='clarify'))


def self_test():
    cc=cases();assert len(cc)==72 and len({c['family'] for c in cc})==12
    for c in cc:
        o=c['oracle'];d=dict(finding=o['finding'],action=o['action'],evidence=o['required_evidence'],reason='oracle test')
        assert not any(v for v in score(c,d).values())
        assert parse(json.dumps(d),c)==d and parse('```json\n'+json.dumps(d)+'\n```',c)==d
        assert parse(json.dumps(d)+json.dumps(d),c) is None
        assert parse(json.dumps(d)[:-3],c) is None
        assert '"oracle"' not in prompt(c)
    for f in FAMILIES:
        cc2={c['variant']:c for c in cc if c['family']==f['id']}
        assert cc2['original']['oracle']==cc2['paraphrase']['oracle']==cc2['typos']['oracle']
        assert cc2['original']['oracle']['finding']!=cc2['meaning_change']['oracle']['finding']
        assert cc2['meaning_change']['oracle']['action']==cc2['amendment']['oracle']['action']
        assert cc2['conflict']['oracle']['action']=='clarify'
    for name,(left,right) in CONFLICT_FIXES.items():
        case=next(c for c in cc if c['id']==name+'/conflict')
        assert case['visible']['documents'][1]['text']==left
        assert case['visible']['documents'][2]['text']==right
        assert left!=right
    assert 'NOT been waived' in CONFLICT_FIXES['waiver'][0]
    assert 'BELOW' in CONFLICT_FIXES['threshold'][0]
    assert 'NOT been received' in CONFLICT_FIXES['funds'][0]
    assert all('CA-001' in t for t in CONFLICT_FIXES['scope'])
    print('PASS: v2 explicit-conflict regressions; 72 case/schema checks; paired meaning invariance and changes; amendment precedence; conflict escalation; wrapper recovery; no oracle leakage.')

class RequestPacer:
    """Keep this process below 60 requests/minute; shared account traffic may still cause 429s."""
    def __init__(self, interval=1.05, clock=time.monotonic, sleep=time.sleep):
        self.interval, self.clock, self.sleep = interval, clock, sleep
        self.last = None

    def wait(self):
        if self.last is not None:
            remaining = self.interval - (self.clock() - self.last)
            if remaining > 0:
                self.sleep(remaining)
        self.last = self.clock()


def counted_tokens(client, job, pacer, sleep=time.sleep):
    # Token counting does not generate answers: retry transient failures here only.
    for attempt in range(9):
        pacer.wait()
        try:
            return client.messages.count_tokens(
                model=job['model'], messages=[dict(role='user', content=job['prompt'])]).input_tokens
        except Exception as exc:
            status = getattr(exc, 'status_code', None)
            transient = status == 429 or (isinstance(status, int) and status >= 500) or type(exc).__name__ in ('APITimeoutError', 'APIConnectionError')
            if not transient or attempt == 8:
                raise
            delay = min(60.0, 5.0 * 2**attempt)
            headers = getattr(getattr(exc, 'response', None), 'headers', {})
            try:
                delay = max(delay, float(headers.get('retry-after', 0)))
            except (ValueError, TypeError):
                pass
            # Respect long Retry-After values while emitting progress every 30 seconds.
            print(f'Token-count service busy ({type(exc).__name__}); retry {attempt+1}/8 in {delay:.0f}s.', flush=True)
            while delay > 0:
                step = min(30.0, delay)
                sleep(step)
                delay -= step
                if delay > 0:
                    print(f'  still waiting; {delay:.0f}s before retry', flush=True)



def generation_settings(model):
    if model == 'mock-oracle':
        return {}
    return dict(thinking={'type': 'disabled' if model == 'claude-haiku-5-5' else 'between_tools'},
                output_config={'effort':'medium'})


def generate_message(client, job, max_output, pacer, sleep=time.sleep):
    for attempt in range(9):
        pacer.wait()
        try:
            return client.messages.create(model=job['model'], max_tokens=max_output,
                       messages=[dict(role='user', content=job['prompt'])],
                       **generation_settings(job['model']))
        except Exception as exc:
            # An explicit 429 rejects the request. Never replay ambiguous timeouts.
            if getattr(exc, 'status_code', None) != 429 or attempt == 8:
                raise
            delay=min(60.0, 5.0*2**attempt)
            try:
                delay=max(delay,float(getattr(getattr(exc,'response',None),'headers',{}).get('retry-after',0)))
            except (ValueError,TypeError):
                pass
            print(f'Generation rate limit: waiting {delay:.0f}s before retry {attempt+1}/8.',flush=True)
            while delay>0:
                step=min(30.0,delay);sleep(step);delay-=step
                if delay>0:print(f'  waiting {delay:.0f}s',flush=True)



def log(path,obj):
    with path.open('a',encoding='utf-8') as f:
        f.write(json.dumps(obj,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())

def report(directory,plan,rows):
    groups=collections.defaultdict(list)
    for r in rows:groups[(r['model'],r['case']['variant'])].append(r)
    lines=['SYNTHETIC CORPORATE-ACTION STUDY — exploratory, not a production error rate.',
           '12 families; 6 matched versions; repeated generations reuse cases. No transactions executed.',
           'Interpretation, proposed action and evidence citation are scored separately.',
           'Action mismatch does NOT automatically mean an unsafe action. Citation presence does NOT prove entailment.',
           '',f"{'model / version':<43} {'answers':>7} {'valid':>6} {'interp':>7} {'action':>7} {'evid':>6} {'clarify+':>8} {'conflict-':>9}"]
    for (model,variant),rr in sorted(groups.items()):
        valid=[r for r in rr if r['parsed'] is not None]
        values=[str(sum(r['score'][k] for r in valid)) if valid else 'N/A' for k in ('interpretation_error','action_error','evidence_missing','unnecessary_clarification','missed_conflict')]
        lines.append(f'{model+" / "+variant:<43} {len(rr):>7} {len(valid):>6} '+ ' '.join(f'{v:>7}' for v in values))
    actual=0
    for r in rows:
        rate=plan['config']['prices'].get(r['model'],{'input':0,'output':0})
        actual+=(r['usage'].get('input_tokens',0)*rate['input']+r['usage'].get('output_tokens',0)*rate['output'])/1e6
    attempted=set();reserve_unknown=0
    for l in (directory/'answers.jsonl').read_text().splitlines():
        obj=json.loads(l)
        if obj['type']=='attempt':attempted.add(obj['key'])
    completed={r['key'] for r in rows}
    reserve_unknown=sum(plan['reservations'][k] for k in attempted-completed)
    lines += ['',f'Collected {len(rows)}/{len(plan["jobs"])}; invalid={sum(r["parsed"] is None for r in rows)}.',
              f'Logged usage cost: ${actual:.4f}. Uncertain-call reservation retained: ${reserve_unknown:.4f}.',
              f'Format deviations: {sum(r["format_violation"] for r in rows)}.',
              'COLLECTION '+('COMPLETE' if len(rows)==len(plan['jobs']) else 'INCOMPLETE')+'; invalid responses remain reported, never scored as correct.',
              'Labels and cases are AI-assisted and require human domain review before research submission.']
    (directory/'summary.txt').write_text('\n'.join(lines)+'\n')
    keys=['key','model','family','variant','repeat','invalid','interpretation_error','action_error','evidence_missing','unnecessary_clarification','missed_conflict','format_violation']
    with (directory/'metrics.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow(dict(key=r['key'],model=r['model'],family=r['case']['family'],variant=r['case']['variant'],repeat=r['repeat'],format_violation=int(r['format_violation']),**r['score']))
    flagged=[r for r in rows if r['parsed'] is None or any(v for v in r['score'].values())]
    (directory/'flagged_answers.json').write_text(json.dumps(flagged,indent=2,ensure_ascii=False))
    print('\n'.join(lines));print('Results:',directory.resolve())


def audit_existing(directory):
    """Post-hoc sensitivity analysis, not a rewritten original experiment."""
    planpath=directory/'plan.json';logpath=directory/'answers.jsonl'
    if not planpath.exists() or not logpath.exists():
        raise SystemExit('Folder must contain original plan.json and answers.jsonl.')
    oldplan=json.loads(planpath.read_text())
    if oldplan.get('revision')!='ca-20261106-v1':
        raise SystemExit('This audit applies only to ca-20261106-v1; no files changed.')
    rows=[json.loads(l) for l in logpath.read_text().splitlines() if json.loads(l).get('type')=='result']
    jobs={j['key']:j for j in oldplan['jobs']}
    if len({r['key'] for r in rows})!=len(rows) or any(r['key'] not in jobs or r['prompt']!=jobs[r['key']]['prompt'] or r['case']!=jobs[r['key']]['case'] for r in rows):
        raise SystemExit('Log does not match the original plan, or duplicate result keys exist. Audit aborted.')
    retained=[r for r in rows if r['case']['id'] not in V1_DISPUTED_CASES]
    removed=[r for r in rows if r['case']['id'] in V1_DISPUTED_CASES]
    lines=['V1 CORPORATE-ACTION ORACLE AUDIT — POST-HOC SENSITIVITY ANALYSIS',
           'Original scores and files are unchanged. No API calls. No malformed JSON repaired.',
           'Exclude four disputed conflict cases: waiver, threshold, funds, scope.',
           'Rationale: possibility/forecast/condition can coexist with confirmation; scope lacked a shared notice reference.',
           'These exclusions were selected AFTER inspecting v1 results; no claim of confirmatory inference.',
           '', 'model | responses retained | valid | invalid | interpretation errors | action errors']
    for model in oldplan['config']['models']:
        rr=[r for r in retained if r['model']==model];valid=[r for r in rr if r['parsed'] is not None]
        lines.append(f'{model} | {len(rr)} | {len(valid)} | {len(rr)-len(valid)} | '+str(sum(r['score']['interpretation_error'] for r in valid))+' | '+str(sum(r['score']['action_error'] for r in valid)))
    lines += ['',f'Retained {len(retained)}/{len(rows)} responses; excluded {len(removed)}.',
              'Zero scored errors on the retained subset is not proof that the remaining oracle is independently validated.',
              'Invalid outputs remain reported and are not scored as correct.',
              'v2 CHANGES THE INPUTS for the four cases; old answers cannot be treated as answers to v2.',
              'Interpretation/action findings require domain review. Formatting failures are separately observable.']
    stamp=datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    output=directory/('oracle_audit_'+stamp);output.mkdir()
    (output/'audit_summary.txt').write_text('\n'.join(lines)+'\n')
    (output/'exclusions.json').write_text(json.dumps(dict(method='post-hoc exclusion; original scores retained',excluded_cases=sorted(V1_DISPUTED_CASES),excluded_keys=[r['key'] for r in removed],original_log_sha256=hashlib.sha256(logpath.read_bytes()).hexdigest()),indent=2))
    with (output/'retained_metrics.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['key','model','family','variant','repeat','invalid','interpretation_error','action_error','evidence_missing'])
        for r in retained:w.writerow([r['key'],r['model'],r['case']['family'],r['case']['variant'],r['repeat'],*[r['score'][k] for k in ('invalid','interpretation_error','action_error','evidence_missing')]])
    print('\n'.join(lines));print('Audit files:',output.resolve())


def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--mock',action='store_true');p.add_argument('--self-test',action='store_true')
    p.add_argument('--audit-existing',type=Path,help='Free v1 sensitivity analysis; original logs unchanged')
    p.add_argument('--export-cases',type=Path);p.add_argument('--models',default=','.join(MODELS))
    p.add_argument('--repeats',type=int,default=3);p.add_argument('--seed',type=int,default=42)
    p.add_argument('--max-usd',type=float,default=3);p.add_argument('--prices',type=Path)
    p.add_argument('--yes',action='store_true');p.add_argument('--outdir',type=Path);p.add_argument('--resume',type=Path)
    args=p.parse_args()
    if args.self_test:self_test();return
    if args.audit_existing:audit_existing(args.audit_existing);return
    if args.export_cases:
        args.export_cases.write_text(json.dumps(dict(note='Synthetic oracle for human review; no API calls.',cases=cases()),indent=2));print(args.export_cases);return
    if args.repeats<1 or not math.isfinite(args.max_usd) or args.max_usd<=0:p.error('Positive repeats and dollar budget required.')
    source_hash=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    rows=[];attempted=set();client=None;pacer=RequestPacer()
    if args.resume:
        directory=args.resume;plan=json.loads((directory/'plan.json').read_text())
        if plan['source_sha256']!=source_hash:p.error('Script differs from original run. Restore original script to resume.')
        config=plan['config']
        for line in (directory/'answers.jsonl').read_text().splitlines() if (directory/'answers.jsonl').exists() else []:
            r=json.loads(line)
            if r['type']=='attempt':attempted.add(r['key'])
            elif r['type']=='result':rows.append(r)
    else:
        models=list(dict.fromkeys(m.strip() for m in args.models.split(',') if m.strip()))
        if not models or set(models)-set(MODELS):p.error('Supported models: '+','.join(MODELS))
        if args.mock:models=['mock-oracle']
        prices=json.loads(args.prices.read_text()) if args.prices else PRICES
        config=dict(models=models,prices=prices,repeats=args.repeats,seed=args.seed,max_usd=args.max_usd,mock=args.mock,max_output=512)
        directory=args.outdir or Path('results_ca_'+datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
        if directory.exists():p.error('Output exists: use --resume or choose a new directory.')
    if not config['mock']:
        if not os.getenv('ANTHROPIC_API_KEY'):p.error('Set ANTHROPIC_API_KEY or use --mock.')
        try:import anthropic
        except ImportError:p.error('Install/update SDK: python3 -m pip install --upgrade anthropic')
        client=anthropic.Anthropic(max_retries=0,timeout=90.)
        for model in config['models']:
            for kind in ('input','output'):
                v=config['prices'].get(model,{}).get(kind)
                if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<=0:p.error('Invalid prices for '+model)
    if not args.resume:
        cc=cases();jobs=[]
        for model in config['models']:
            for c in cc:
                for rep in range(config['repeats']):
                    jobs.append(dict(key=f'{model}/{c["id"]}/{rep}',model=model,case=c,repeat=rep,prompt=prompt(c)))
        random.Random(config['seed']).shuffle(jobs)
        print(f'Plan: {len(jobs)} generation calls; {len(cc)} narratives; {config["repeats"]} repetitions/model.')
        print('Prices (USD/MTok, dated 2026-11-05; override --prices if changed):',config['prices'])
        print('Preflight counts each distinct prompt once per model; repeated prompts reuse that count. Approx. 3 minutes at defaults.',flush=True)
        cache={};reservations={}
        for j in jobs:
            cachekey=(j['model'],j['case']['id'])
            if cachekey not in cache:
                if client:
                    try:n=counted_tokens(client,j,pacer)
                    except Exception as exc:p.error(f'Preflight failed ({type(exc).__name__}: {exc}); no generation started.')
                else:n=0
                cache[cachekey]=n
                if len(cache)%20==0:print(f'  checked {len(cache)} distinct prompts',flush=True)
            rate=config['prices'].get(j['model'],{'input':0,'output':0})
            reservations[j['key']]=((math.ceil(cache[cachekey]*1.2)+32)*rate['input']+512*rate['output'])/1e6
        total=sum(reservations.values());print(f'Whole-batch reservation ${total:.4f}; limit ${config["max_usd"]:.2f}.')
        if total>config['max_usd']:p.error('Batch exceeds reservation limit; no generation. Reduce repeats/models or explicitly change --max-usd.')
        if client and not args.yes and input('Run full batch and spend? [y/N] ').strip().lower()!='y':return
        import platform,importlib.metadata
        plan=dict(revision='ca-20261106-v2',source_sha256=source_hash,config=config,jobs=jobs,reservations=reservations,
                  settings={m:generation_settings(m) for m in config['models']},python=platform.python_version(),sdk=importlib.metadata.version('anthropic') if client else 'mock',
                  oracle_changes='v2 replaces waiver/threshold/funds/scope conflict narratives with explicit contradictions. Prior observations prompted the changes. Not preregistered before v1.',
                  limitations='Synthetic narratives, not actual Swift payloads. AI-assisted labels need human review. Related variants and repetitions are not independent. No transactions executed.',
                  design='Matched original/paraphrase/typos; meaning change; superseding amendment; unresolved conflict. Randomised request order. No hidden oracle in model prompts.')
        directory.mkdir(parents=True)
        (directory/'plan.json').write_text(json.dumps(plan,indent=2,ensure_ascii=False))
        (directory/'cases_for_review.json').write_text(json.dumps(cc,indent=2,ensure_ascii=False))
    jobs=plan['jobs'];logpath=directory/'answers.jsonl'
    try:
        for j in jobs:
            if j['key'] in attempted:continue
            log(logpath,dict(type='attempt',key=j['key'],reserved_usd=plan['reservations'][j['key']]))
            attempted.add(j['key'])
            try:
                if client:
                    msg=generate_message(client,j,512,pacer)
                    raw=''.join(b.text for b in msg.content if b.type=='text');usage=msg.usage.model_dump();stop=msg.stop_reason;actual=msg.model
                else:
                    o=j['case']['oracle'];raw=json.dumps(dict(finding=o['finding'],action=o['action'],evidence=o['required_evidence'],reason='Mock oracle; no performance evidence.'))
                    usage={};stop='mock';actual='mock-oracle'
                d=parse(raw,j['case']) if stop in ('mock','end_turn') else None
                row=dict(j,type='result',raw=raw,parsed=d,score=score(j['case'],d),usage=usage,stop_reason=stop,actual_model=actual,format_violation=strict_parse(raw,j['case']) is None)
                log(logpath,row);rows.append(row)
                print(f'[{len(attempted)}/{len(jobs)}] {j["key"]} stop={stop} valid={d is not None}',flush=True)
                mr=[r for r in rows if r['model']==j['model']]
                if client and len(mr)>=20 and sum(r['parsed'] is None for r in mr)/len(mr)>=.2:
                    print('QUALITY STOP: >=20% invalid after >=20 responses/model. Partial results retained.');break
                rate=config['prices'].get(j['model'],{'input':0,'output':0})
                cost=(usage.get('input_tokens',0)*rate['input']+usage.get('output_tokens',0)*rate['output'])/1e6
                if cost>plan['reservations'][j['key']]:print('Usage exceeded reservation. Stopping; reservation is not a provider billing guarantee.');break
            except Exception as exc:
                log(logpath,dict(type='api_error',key=j['key'],error_type=type(exc).__name__,error=str(exc),billing='unknown; no automatic retry; reservation retained'))
                print(f'Stopped on {type(exc).__name__}: {exc}. Resume skips this uncertain call.');break
    finally:report(directory,plan,rows)
    if len(rows)!=len(jobs):raise SystemExit(2)

if __name__=='__main__':main()
