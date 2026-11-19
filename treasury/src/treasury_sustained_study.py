#!/usr/bin/env python3
"""Four-week synthetic USD treasury study. Standard library, Python 3.12+.
Default: 28 calendar days from Monday 2026-11-23, including20 weekdays and8 weekend days.
Run --self-test, then --days 2 for a free prefix check, then --days 28 for free references.
Paid generation requires --policy model --live --model ID and explicit price/budget flags.
See the accompanying README for the frozen protocol, commands, limits and submission notes.
No real transactions. Single-currency managed sleeve, not a complete bank ALM simulation.
"""
import argparse
import calendar
import copy
import csv
import hashlib
import json
import io
import os
from pathlib import Path
import random
import re
import sys
import time
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import unittest
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

VERSION = 'treasury-sustained-14.0'
INTERFACE_CONDITION = 'explicit_yield_and_transaction_fees'
YIELD_TERMS = '''INSTRUMENT YIELD AND FEES
yield_adjustment_bps is an annual yield adjustment, not a transaction charge.
rate_bps is the final annual yield, already including that adjustment; do not add it again.
subscription_fee_cents and redemption_fee_cents are flat charges per operation.
fee_cents is the same legacy flat fee, not an additional charge.
transaction_spread_bps=0: this simulation charges no percentage transaction spread
on instrument subscriptions or redemptions. Instrument price changes, if any, are
separate from fees. FX conversion charges remain as specified in fx_spread_bps.
'''

def explicit_instrument_terms(instruments):
    result=copy.deepcopy(instruments)
    for instrument in result.values():
        instrument['yield_adjustment_bps']=instrument.pop('spread_bps')
        instrument['subscription_fee_cents']=instrument['fee_cents']
        instrument['redemption_fee_cents']=instrument['fee_cents']
        instrument['transaction_spread_bps']=0
    return result
AFTER_HOURS = ('after_hours','after_hours_control')
CYCLE_CASES = ('required_redemption','optional_investment')
ISOLATED = AFTER_HOURS + CYCLE_CASES
CCY = ('USD', 'GBP', 'EUR', 'CHF')
HOURS = (6, 8, 10, 12, 14, 16, 18, 22, 23)
MICRO = 1_000_000
D = Decimal

def money(x):
    return int((D(str(x))*100).quantize(D('1'), rounding=ROUND_HALF_UP))

def rounded(x):
    return int(D(x).quantize(D('1'), rounding=ROUND_HALF_UP))

def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, sort_keys=True)+'\n')

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()

def append(path, obj):
    with open(path, 'a') as f:
        f.write(json.dumps(obj, sort_keys=True)+'\n'); f.flush(); os.fsync(f.fileno())

GUIDE = r'''TREASURY BANK LAB v11 -- SYNTHETIC, UNREVIEWED DEVELOPMENT

BANK / SCOPE
Opening CHF40bn balance sheet (static calibration, not a full bank ALM ledger): mortgages29bn, other loans3bn, reserves/operating cash3.5bn,
correspondent0.5bn, treasury investments3bn, other assets1bn. Funding: customer
deposits25bn, wholesale10bn, other liabilities2bn, equity3bn. Client securities
in custody10bn, including discretionary AUM4bn, are NOT treasury assets.
This scale is informed by public Swiss bank balance sheets (reference exported
in bank_profile.json); flows/rates/buffers are synthetic assumptions, not actual
bank transactions, product terms, regulatory compliance or an optimal policy.

The agent manages ONLY CHF2bn equivalent: operating cash500m, correspondent500m,
inherited conventional MMFs1bn. Protected reserves3bn and protected securities2bn
are outside its authority. Operating cash allocation CHF300m, USD100m equivalent,
EUR75m equivalent, GBP25m equivalent. Correspondent allocation USD250m equivalent,
EUR150m equivalent, GBP100m equivalent. Initial funds use CHF60%, USD20%, EUR15%,
GBP5%. Foreign currency amounts are converted at opening FX.
Cash floors in CHF equivalent at opening FX: CHF75m, USD25m, EUR20m, GBP10m;
month-end multiplies by1.5. Correspondent hard floors: USD50m, EUR30m, GBP20m.
No limit breach is permitted on payment or recall. FX cumulative principal
changes are capped at CHF25m equivalent in each currency. No speculative FX
mandate. Currency funding liabilities/hedges are not dynamically modelled;
translation P&L is for the managed treasury portfolio, NOT whole-bank profit.

CALENDAR / FLOWS
Default 30 calendar days from 2026-11-23, with weekends and month-end. Two-day run
is the exact prefix. Fixed CET UTC+1, no holidays or DST. Nine checkpoints/day:
06,08,10,12,14,16,18,22,23. Ledger progresses hourly between decisions.
Daily 240 customer payments, plus business-day mortgage batch10-40m CHF.
Customer-payment total200-400m CHF equivalent, multiplied1.7 month-end and0.30
weekends. Independent daily incoming220-420m equivalent, multiplied1.7 month-end
and0.35 weekends; 30% settles12:00,70%18:00. These are independent synthetic
samples, NOT matched replenishment. Exceptional CHF250m withdrawals on day index1
and15, due15:00, are stress scenarios. Daily rates vary +/-3bps, with a -25bps
step at day index7 and +15bps at20; FX varies around opening levels. Not forecasts.
Only current-day obligations, rates and known receipts are exposed at06:00.
No future random values. Events and payments are saved as the frozen tape.

ASSETS / SETTLEMENT / CONTROLS
All product terms invented. No claim of access to an actual central bank facility.
Catalogue includes local deposits, an eligible synthetic GBP central-bank deposit,
conventional MMFs, tokenized MMFs, short bills. Deposits and funds NAV100; bills
have a simple rate-sensitive mark. Confirmed holdings earn hourly ACT/365 income.
Local/central windows08-17 weekdays, settle1h in next business window. MMF subscribe
08-16/redeem08-10 weekdays; settle after6h, rolled to next business window08-18.
Bills08-16, settle next business morning. Tokenized MMF subscriptions24/7,
redemption00-22, settle2h into tokenized deposits. Mint/burn settle1h, fee100 cents.
Pending cash/units cannot be reused. A digital token is not instant fiat liquidity.

Domestic route: core cash,1h,50 cents. Correspondent: correspondent cash,2h,
2000 cents, weekdays08-17 only. Tokenized deposit:td,1h,1800 cents.
Stablecoin:stable,1h,3000 cents. Recipient eligible routes are explicit per payment.
Recall correspondent to core:2h,2000 cents,weekday desk08-17.
Replenish core to correspondent:2h,2000 cents,weekday desk08-17;
stablecoin to correspondent:2h,3000 cents,24/7 synthetic prearranged access.
FX core-to-core1h,5bps spread, weekdays08-17. All transaction fees debit core.
Collateral is explicitly confirmed at22:00, total100-300m CHF equivalent/day.
It is a stock update, not a cumulative gift. Borrowing haircut20%,month-end30%,
settlement1h. Borrowing rate600bps plus change from opening currency rate.
Borrowing creates a liability; repayment settles1h before collateral releases.
Protected securities include the pledged collateral; do not add it again as cash.

BASELINES
All policies start with identical holdings and disclosures. Conventional and
cash-only cannot use digital payment rails. Cash-only liquidates inherited funds
when open and does not reinvest. Conventional/hybrid redeem to cover known
obligations, reserve cash for a next-day uncertainty allowance, and may invest
surplus in accessible local/central deposits once daily. Hybrid may release excess
correspondent balances and use tokenized-deposit payments. These are feasible-rule
heuristics, not optimisation benchmarks. No hidden helper acts for the model.
They replenish correspondent cash at16:00 when free cash permits, and do not
automatically borrow against pending redemptions. Compare economic
results cautiously, including inherited-fund income, end holdings and liabilities.

REDEMPTION DRILL
--scenario redemption_drill is a separate diagnostic, NOT the bank-wide scenario.
Only CHF40m cash plus CHF150m conventional MMF; cash floor25m; a CHF100m payment
due15:00 day0. Only redeem/pay operations permitted; no receipts or borrowing.
A request by08:00 redeems by14:00, allowing payment settlement15:00. This deliberately
isolates redemption timing; avoiding redemption should fail the payment.

ACTION CONTRACT
Return {"actions":[...]} with at most80 top-level operations. Unique id and op within this checkpoint. The controller namespaces IDs by checkpoint;
reusing a local ID at a later checkpoint does not collide. Within one checkpoint,
same ID + identical payload is an idempotent replay; a changed payload is rejected.
The next view includes recent_execution for the last checkpoint with actions.
Inspect failures and pending settlements before deciding. Accepted does not mean settled.
DEADLINE POLICY: this experiment forbids settlement after a payment deadline.
Overdue payments remain visible for audit, marked overdue; do not retry them or
mint assets for them. They remain missed. This is a synthetic on-time-only policy,
not a claim that banks should never settle an obligation late.
Positive INTEGER cents for amount; units are integer micro-units (1 unit=1e6).
mint/burn: ccy,asset='td'|'stable',amount. subscribe:instrument,amount.
redeem:instrument,units. borrow/repay/recall:ccy,amount.
replenish:ccy,asset='core'|'stable',amount. fx:ccy,dest,amount.
pay:payment,route. pay_batch:payments=[payment IDs],route (up to300 IDs).
Each batch child is independently checked; valid children execute even if others
fail. Child action IDs are batch-id:payment-id. Use batches to avoid long outputs.
Actions run in order; pending proceeds cannot finance later actions in the batch.
Identical accepted IDs are no-ops; conflicting IDs are blocked.
A single fenced JSON document with surrounding prose is accepted and counted as
a format deviation; raw content is retained. Conflicting structured blocks rejected.

AUDIT / COST
No external financial transactions. Frozen profile/tape/source hashes saved.
Run --self-test, then --days2 and --days30 OFFLINE before paying for model calls.
--policy model --live needs explicit prices and budget. 2days18 calls;30days270.
Default max-output16384. Provider-default thinking/effort; settings documented.
--resume reuses verified saved responses. --retry-uncertain explicitly replaces a
terminal unanswered generation, retains its possible cost and counts the attempt.
No automatic retries; unknown cost is not treated as zero. Keep original folders.

Economics: interest, fees, financing, FX trades/translation and pending assets are
separate. Protected-book income and bank funding transfer price are excluded.
A positive treasury return is NOT whole-bank profit or proof of optimal allocation.
Redeemed units are attributed to inherited or newly subscribed holdings using
synthetic FIFO. This is not proof of a complete redemption-to-fiat roundtrip.
No automatic horizon liquidation: ending held/pending assets remain disclosed.
'''

def catalogue():
    result={}
    for c in CCY:
        for kind, offset, fee, settlement in [('local',-40,0,'core'),('mmf',15,200,'core'),
                                             ('tmmf',10,150,'td'),('bill',30,500,'core')]:
            k=f'{c}_{kind}'
            result[k]=dict(ccy=c,kind=kind,spread_bps=offset,fee_cents=fee,
                           settlement_asset=settlement,eligible=True)
    result['GBP_central']=dict(ccy='GBP',kind='central',spread_bps=-15,
                              fee_cents=0,settlement_asset='core',eligible=True)
    return result


class SettlementEngine:
    def __init__(self,tape,start,policy):
        self.tape=tape;self.start=start;self.policy=policy;self.t=0;self.day=0
        self.cat=catalogue();self.market=tape[0]
        self.assets={a:{c:0 for c in CCY} for a in ('core','td','stable','corr')}
        # Opening portfolio is supplied by the bank scenario subclass.
        self.units={k:0 for k in self.cat};self.pending=[];self.obligations={};self.receipts=[]
        self.loan={c:0 for c in CCY};self.encumbered={c:0 for c in CCY};self.collateral={c:0 for c in CCY}
        self.accepted={};self.log=[];self.blocks=0;self.nextid=0;self.daily=[]
        self.income={c:0 for c in CCY};self.fees={c:0 for c in CCY};self.financing={c:0 for c in CCY}
        self.external={c:0 for c in CCY};self.fxtrade={c:0 for c in CCY}
        self.opening=self.values();self.flow_chf=0;self.fx_open=sum(self.opening[c]*D(str(self.market['fx'][c])) for c in CCY)
        self.floor_breaches=0;self.initialised=False

    def business(self,t):return (self.start+timedelta(days=t//24)).weekday()<5
    def floor(self,c):return money(150_000_000 if self.market['month_end'] else 100_000_000)
    def rate(self,k):return max(0,self.market['rates'][self.cat[k]['ccy']]+self.cat[k]['spread_bps'])
    def price(self,k):
        i=self.cat[k]
        return 10000 if i['kind']!='bill' else 10000-rounded(D(self.market['rates'][i['ccy']]-self.tape[0]['rates'][i['ccy']])*D('.20'))
    def holding(self,k,u=None):return (self.units[k] if u is None else u)*self.price(k)//MICRO
    def values(self):
        v={c:sum(a[c] for a in self.assets.values())-self.loan[c] for c in CCY}
        for k in self.units:v[self.cat[k]['ccy']]+=self.holding(k)
        for x in self.pending:
            if x['kind']=='units':v[x['ccy']]+=self.holding(x['instrument'],x['units'])
            elif x['kind']!='borrow':v[x['ccy']]+=x['amount']
        return v
    def event(self,kind,**data):self.log.append(dict(t=self.t,kind=kind,**data))
    def business_settle(self,earliest):
        while not self.business(earliest) or not 8<=earliest%24<=18:earliest+=1
        return earliest
    def window(self,k,redeem=False):
        kind=self.cat[k]['kind'];h=self.t%24
        if kind=='tmmf':return not redeem or h<=22
        return self.business(self.t) and 8<=h<=(10 if kind=='mmf' and redeem else 16 if kind in ('mmf','bill') else 17)
    def settle_time(self,k):
        kind=self.cat[k]['kind']
        if kind=='tmmf':return self.t+2
        if kind=='bill':return self.business_settle((self.t//24+1)*24+8)
        return self.business_settle(self.t+(6 if kind=='mmf' else 1))
    def queue(self,kind,delay=1,**data):self.pending.append(dict(kind=kind,due=self.t+delay,**data))
    def fee(self,c,n):
        if self.assets['core'][c]-n<self.floor(c):raise ValueError('fee would breach cash floor')
        self.assets['core'][c]-=n;self.fees[c]+=n
    def debit(self,a,c,n):
        if n>self.assets[a][c]:raise ValueError('insufficient settled '+a)
        if a=='core' and self.assets[a][c]-n<self.floor(c):raise ValueError('cash floor')
        self.assets[a][c]-=n
    def advance(self,t):
        for hour in range(self.t if not self.initialised else self.t+1,t+1):
            self.t=hour;self.day=hour//24
            if hour>0:
                for k,u in self.units.items():
                    c=self.cat[k]['ccy'];n=rounded(D(self.holding(k))*self.rate(k)/10000/365/24)
                    self.assets[self.cat[k]['settlement_asset']][c]+=n;self.income[c]+=n
                for c in CCY:
                    n=rounded(D(self.loan[c])*(600+self.market['rates'][c]-self.tape[0]['rates'][c])/10000/365/24)
                    self.loan[c]+=n;self.financing[c]+=n
            # Today's data is revealed only at 06:00, not at midnight.
            if hour%24==6 and self.day<len(self.tape):
                self.market=self.tape[self.day]
                for p in self.market['payments']:self.obligations[p['id']]=dict(p,status='open')
                self.receipts.extend(copy.deepcopy(self.market['receipts']))
                self.event('daily_disclosure',date=self.market['date'],rates=self.market['rates'],month_end=self.market['month_end'])
            if hour%24==22 and self.day<len(self.tape):
                self.collateral=dict(self.tape[self.day]['collateral_release'])
                self.event('collateral_confirmed_available',amounts=self.collateral)
            for r in list(self.receipts):
                if r['t']<=hour:
                    c=r['ccy'];n=r['amount'];self.assets['core'][c]+=n;self.external[c]+=n
                    self.flow_chf+=D(n)*D(str(self.market['fx'][c]));self.receipts.remove(r)
                    self.event('receipt_confirmed',ccy=c,amount=n)
            for x in list(self.pending):
                if x['due']>hour:continue
                c=x['ccy'];kind=x['kind'];n=x.get('amount',0)
                if kind=='units':self.units[x['instrument']]+=x['units']
                elif kind=='pay':
                    p=self.obligations[x['payment']];p['status']='paid';p['settled_at']=hour
                    self.external[c]-=n;self.flow_chf-=D(n)*D(str(self.market['fx'][c]))
                elif kind=='repay':
                    self.loan[c]-=n;self.encumbered[c]=max(0,self.encumbered[c]-x['collateral'])
                elif kind=='borrow':self.assets['core'][c]+=n;self.loan[c]+=n
                else:self.assets[x['asset']][c]+=n
                self.pending.remove(x);self.event('settled',transfer=x)
            if any(self.assets['core'][c]<self.floor(c) for c in CCY):self.floor_breaches+=1
            if hour%24==23:
                self.daily.append(dict(day=self.day,date=(self.start+timedelta(days=self.day)).isoformat(),
                    core=dict(self.assets['core']),correspondent=dict(self.assets['corr']),
                    values=self.values(),income=dict(self.income),fees=dict(self.fees),financing=dict(self.financing)))
        self.initialised=True
    def _action(self,a):
        op=a['op'];c=a.get('ccy','USD');n=a.get('amount',0)
        if c not in CCY:raise ValueError('currency')
        if op not in ('pay','redeem') and (type(n)!=int or n<=0):raise ValueError('positive integer cents required')
        if op in ('mint','burn'):
            asset=a['asset']
            if asset not in ('td','stable'):raise ValueError('asset')
            self.fee(c,100);self.debit('core' if op=='mint' else asset,c,n)
            self.queue('cash',ccy=c,amount=n,asset=asset if op=='mint' else 'core')
        elif op in ('subscribe','redeem'):
            k=a['instrument'];i=self.cat[k];c=i['ccy']
            if not i['eligible'] or not self.window(k,op=='redeem'):raise ValueError('eligibility or order window')
            self.fee(c,i['fee_cents'])
            if op=='subscribe':
                u=n*MICRO//self.price(k)
                if not u:raise ValueError('below one micro-unit')
                spent=(u*self.price(k)+MICRO-1)//MICRO
                self.debit(i['settlement_asset'],c,spent)
                self.queue('units',self.settle_time(k)-self.t,ccy=c,instrument=k,units=u,amount=spent)
            else:
                u=a['units']
                if type(u)!=int or not 0<u<=self.units[k]:raise ValueError('units')
                self.units[k]-=u;n=u*self.price(k)//MICRO
                self.queue('cash',self.settle_time(k)-self.t,ccy=c,asset=i['settlement_asset'],amount=n)
        elif op=='recall':
            if c!='USD':raise ValueError('USD correspondent only')
            self.fee(c,2000);self.debit('corr',c,n)
            self.queue('cash',2,ccy=c,asset='core',amount=n)
        elif op=='replenish':
            asset=a.get('asset','core')
            if c!='USD' or asset not in ('core','stable'):raise ValueError('replenishment path')
            if asset=='core' and (not self.business(self.t) or not 8<=self.t%24<=17):raise ValueError('desk closed')
            self.fee(c,2000 if asset=='core' else 3000);self.debit(asset,c,n)
            self.queue('cash',2,ccy=c,asset='corr',amount=n)
        elif op=='borrow':
            haircut=D('.30') if self.market['month_end'] else D('.20')
            collateral=rounded(D(n)/(1-haircut))
            if collateral>self.collateral[c]-self.encumbered[c]:raise ValueError('collateral unavailable')
            self.encumbered[c]+=collateral
            self.queue('borrow',ccy=c,amount=n,collateral=collateral)
        elif op=='repay':
            reserved=sum(x['amount'] for x in self.pending if x['kind']=='repay' and x['ccy']==c)
            if n>self.loan[c]-reserved:raise ValueError('repayment exceeds unreserved debt')
            self.debit('core',c,n)
            collateral=self.encumbered[c] if n==self.loan[c] else self.encumbered[c]*n//self.loan[c]
            self.queue('repay',ccy=c,amount=n,collateral=collateral)
        elif op=='fx':
            dest=a['dest']
            if dest not in CCY or dest==c:raise ValueError('FX currency')
            if not self.business(self.t) or not 8<=self.t%24<=17:raise ValueError('FX desk closed')
            self.debit('core',c,n)
            result=int(D(n)*D(str(self.market['fx'][c]))/D(str(self.market['fx'][dest]))*D('.9995'))
            self.fxtrade[c]-=n;self.fxtrade[dest]+=result
            self.queue('cash',ccy=dest,asset='core',amount=result)
        elif op=='pay':
            p=self.obligations[a['payment']];c=p['ccy'];n=p['amount'];r=a['route']
            if p['status']!='open' or r not in p['routes']:raise ValueError('payment status or recipient eligibility')
            asset,delay,fee={'domestic':('core',1,50),'correspondent':('corr',2,2000),
                             'stablecoin':('stable',1,3000),'tokenized_deposit':('td',1,1800)}[r]
            if self.t+delay>p['due']:raise ValueError('would miss deadline')
            if r=='correspondent' and (not self.business(self.t) or not 8<=self.t%24<=17):raise ValueError('correspondent window')
            self.fee(c,fee);self.debit(asset,c,n);p['status']='pending'
            self.queue('pay',delay,ccy=c,amount=n,payment=p['id'],asset=asset)
        else:raise ValueError('unknown operation')
    def act(self,a):
        ident=a.get('id') if isinstance(a,dict) else None
        if not isinstance(ident,str) or not ident:
            self.blocks+=1;return dict(ok=False,error='missing action id')
        if ident in self.accepted:
            if self.accepted[ident]==a:return dict(ok=True,duplicate=True)
            self.blocks+=1;return dict(ok=False,error='conflicting action id')
        # Transactional validation: rejected operations never charge fees or alter balances.
        fields=('assets','units','pending','encumbered','fees','fxtrade')
        before={k:copy.deepcopy(getattr(self,k)) for k in fields}
        try:self._action(a)
        except (KeyError,ValueError,TypeError) as exc:
            self.__dict__.update(before);self.blocks+=1;self.event('blocked',action=a,error=str(exc))
            return dict(ok=False,error=str(exc))
        self.accepted[ident]=copy.deepcopy(a);self.event('accepted',action=a)
        return dict(ok=True)
    def view(self):
        return dict(t=self.t,date=(self.start+timedelta(days=self.t//24)).isoformat(),hour_CET=self.t%24,
            assets=self.assets,units=self.units,unit_scale=MICRO,pending=self.pending,loans=self.loan,
            collateral=self.collateral,encumbered=self.encumbered,
            floors={c:self.floor(c) for c in CCY},market={k:self.market[k] for k in ('rates','fx','month_end')},
            instruments={k:dict(v,rate_bps=self.rate(k),price_cents=self.price(k),
                        can_subscribe=self.window(k),can_redeem=self.window(k,True),
                        settlement_time=self.settle_time(k)) for k,v in self.cat.items()},
            payments=list(self.obligations.values()),known_receipts=self.receipts,
            quotes=dict(domestic=dict(asset='core',delay_hours=1,fee_cents=50),
                correspondent=dict(asset='corr',delay_hours=2,fee_cents=2000),
                stablecoin=dict(asset='stable',delay_hours=1,fee_cents=3000),
                tokenized_deposit=dict(asset='td',delay_hours=1,fee_cents=1800),
                mint_burn_fee_cents=100,recall_fee_cents=2000,
                replenish_fee_cents=dict(core=2000,stable=3000),fx_spread_bps=5,
                borrowing_rate_bps={c:600+self.market['rates'][c]-self.tape[0]['rates'][c] for c in CCY}))


def portfolio_metrics(e,complete):
    payments=list(e.obligations.values());paid=[p for p in payments if p['status']=='paid']
    due=[p for p in payments if p['due']<=e.t]
    misses=[p for p in due if p['status']!='paid' or p['settled_at']>p['due']]
    values=e.values()
    pnl={c:values[c]-e.opening[c]-e.external[c]-e.fxtrade[c] for c in CCY}
    explicit={c:e.income[c]-e.fees[c]-e.financing[c] for c in CCY}
    final_chf=sum(D(values[c])*D(str(e.market['fx'][c])) for c in CCY)
    return dict(policy=e.policy,run_complete=complete,t=e.t,payments_revealed=len(payments),payments_due=len(due),
        on_time=sum(p['status']=='paid' and p['settled_at']<=p['due'] for p in due),
        paid_early_not_yet_due=sum(p['due']>e.t for p in paid),
        paid_total=len(paid),late=sum(p['settled_at']>p['due'] for p in paid),
        missed=len(misses),missed_ids=[p['id'] for p in misses],pending_payments=sum(p['status']=='pending' for p in payments),
        blocked_actions=e.blocks,floor_breach_hours=e.floor_breaches,assets_cents=e.assets,units_micro=e.units,
        loans_cents=e.loan,encumbered_collateral_cents=e.encumbered,pending=e.pending,
        gross_income_cents=e.income,fees_cents=e.fees,financing_cents=e.financing,
        net_interest_less_costs_cents=explicit,local_pnl_excluding_fx_trades_cents=pnl,
        mark_and_rounding_residual_cents={c:pnl[c]-explicit[c] for c in CCY},
        net_assets_cents=values,external_net_receipts_cents=e.external,fx_trade_net_cents=e.fxtrade,
        CHF_net_asset_change_less_external_flows_cents=rounded(final_chf-e.fx_open-e.flow_chf),
        note='CHF bridge includes FX translation and investment P&L; not pure realised profit. Pending investment assets are not usable cash.')

def parse_response(reply):
    if reply.get('stop_reason')!='end_turn':
        raise ValueError('non-end_turn response retained: '+str(reply.get('stop_reason')))
    raw=''.join(x.get('text','') for x in reply.get('content',[]) if x.get('type')=='text').strip()
    # Permit exactly one fenced action document plus prose. Never repair JSON.
    # Reject competing code blocks or JSON-like structures outside that block.
    fences=list(re.finditer(r'```(?:json)?[ \t]*\r?\n(.*?)\r?\n```',raw,re.DOTALL|re.IGNORECASE))
    wrapped=bool(fences)
    if wrapped:
        if len(fences)!=1 or raw.count('```')!=2:
            raise ValueError('ambiguous multiple or malformed code fences')
        fenced=fences[0];outside=raw[:fenced.start()]+raw[fenced.end():]
        # A repeated inline JSON document may explain the fenced answer.
        # Accept only complete, identical documents; never merge action lists.
        document=json.loads(fenced.group(1))
        canonical=json.dumps(document,sort_keys=True,separators=(',',':'))
        def remove_identical_inline(match):
            inline=match.group(1)
            if not any(c in inline for c in '{}[]'):return match.group(0)
            try:other=json.loads(inline)
            except ValueError:raise ValueError('malformed structured content outside action block')
            if json.dumps(other,sort_keys=True,separators=(',',':'))!=canonical:
                raise ValueError('conflicting structured content outside action block')
            return ''
        outside=re.sub(r'(?<!`)`([^`\r\n]+)`(?!`)',remove_identical_inline,outside)
        if any(c in outside for c in '{}[]'):
            raise ValueError('possible competing structured content outside action block')
        raw=fenced.group(1).strip()
    if wrapped:
        obj=json.loads(raw)
    else:
        # Accept an unambiguous document after a separately delimited text prefix.
        # Outside text (including tool-like markup) is inert, NEVER executed.
        # Do not skip an earlier JSON-like structure to find a preferred answer.
        if not raw.startswith('{'):
            start=raw.find('{')
            prefix=raw[:start] if start>=0 else raw
            if start<0 or not prefix.endswith(('\n\n','\r\n\r\n')) or any(c in prefix for c in '{}[]') or '```' in prefix:
                raise ValueError('missing or ambiguous action document')
            raw=raw[start:]
            wrapped=True
        obj,end=json.JSONDecoder().raw_decode(raw)
        suffix=raw[end:]
        if suffix.strip():
            if not suffix.startswith(('\n\n','\r\n\r\n')) or any(c in suffix for c in '{}[]') or '```' in suffix:
                raise ValueError('ambiguous trailing content after action document')
            wrapped=True
    if not isinstance(obj,dict) or set(obj)!= {'actions'} or not isinstance(obj['actions'],list) or len(obj['actions'])>80:
        raise ValueError('invalid action contract')
    return obj['actions'],wrapped

def load_recovery(path,args,tape,start):
    old=json.loads((path/'manifest.json').read_text())
    if old.get('version')!=VERSION:
        raise ValueError('interface version changed; start a fresh run, preserve the old results')
    for key in ('days','start','seed','model','max_output'):
        if old.get(key)!=getattr(args,key):raise ValueError('resume configuration mismatch: '+key)
    if old.get('policy')!='model' or old.get('tape_sha256')!=digest(tape):
        raise ValueError('resume policy or event tape mismatch')
    if old.get('prices')!=dict(input=args.input_price,output=args.output_price):
        raise ValueError('resume price mismatch')
    attempts={};responses={};uncertain=[]
    for line in (path/'api_journal.jsonl').read_text().splitlines():
        row=json.loads(line);t=row.get('t')
        if row.get('type')=='uncertain_attempt':uncertain.append(row)
        elif row.get('type')=='attempt':
            if t in attempts:raise ValueError('multiple attempts at checkpoint; manual audit required')
            attempts[t]=row
        elif row.get('type')=='response':
            if t in responses:raise ValueError('multiple responses at checkpoint')
            responses[t]=row['response']
    schedule=[d*24+h for d in range(args.days) for h in HOURS]
    missing=set(attempts)-set(responses)
    if set(responses)-set(attempts):raise ValueError('response without corresponding attempt')
    if missing:
        if not getattr(args,'retry_uncertain',False):
            raise ValueError('uncertain API attempt: use --retry-uncertain to explicitly request a replacement generation, retaining its cost reservation')
        if len(missing)!=1 or len(responses)>=len(schedule) or missing!={schedule[len(responses)]}:
            raise ValueError('only a terminal unanswered attempt can be replaced')
        t=next(iter(missing));uncertain.append(dict(attempts.pop(t),type='uncertain_attempt',source=str(path.resolve())))
    for row in uncertain:
        if not isinstance(row.get('reservation_usd'),(int,float)) or row['reservation_usd']<0:
            raise ValueError('missing uncertain cost reservation')
    if sorted(responses)!=schedule[:len(responses)]:raise ValueError('saved responses are not a contiguous prefix')
    # Reconstruct and check every original input BEFORE approving any new calls.
    engine=Engine(tape,start,'model');replay={}
    for t in sorted(responses):
        engine.advance(t);payload=attempts[t]['payload']
        if json.loads(payload['messages'][0]['content'])!=engine.view():
            raise ValueError('reconstructed state differs from saved prompt at '+str(t))
        actions,wrapped=parse_response(responses[t])
        for action in actions:engine.act(action)
        replay[t]=dict(attempt=attempts[t],response=responses[t])
    if missing:
        t=next(iter(missing));engine.advance(t)
        if json.loads(uncertain[-1]['payload']['messages'][0]['content'])!=engine.view():
            raise ValueError('uncertain checkpoint state mismatch')
    args.uncertain_attempts=uncertain
    return replay

def request_model(view,args,folder,usage):
    system=protocol_for(view.get('scenario','bank'))+'\nAct as treasury decision layer. Preserve floors and meet obligations; seek net return only with feasible funding. Use only current disclosed information. Return the ACTION CONTRACT JSON.'
    if args.replay:system=args.replay[min(args.replay)]['attempt']['payload']['system']
    payload=dict(model=args.model,max_tokens=args.max_output,system=system,messages=[dict(role='user',content=json.dumps(view))])
    if view['t'] in args.replay:
        saved=args.replay[view['t']];reply=saved['response']
        if json.loads(saved['attempt']['payload']['messages'][0]['content'])!=view:
            raise ValueError('recovery state mismatch')
        append(folder/'api_journal.jsonl',dict(saved['attempt'],recovered_from=str(args.resume.resolve())))
        append(folder/'api_journal.jsonl',dict(type='response',t=view['t'],response=reply,recovered=True))
        usage['reused_responses']+=1
        actions,wrapped=parse_response(reply)
        usage['format_wrappers']+=int(wrapped)
        usage['tool_like_text_responses']=usage.get('tool_like_text_responses',0)+int(any('<invoke' in b.get('text','').lower() for b in reply.get('content',[]) if b.get('type')=='text'))
        print(f"Checkpoint {view['t']}: reused saved response; no API call",flush=True)
        return actions
    # UTF-8 byte-count reservation is conservative for ordinary text, not a billing guarantee.
    reserve=(len(json.dumps(payload).encode())*args.input_price+args.max_output*args.output_price)/1e6
    if usage['calls']>=args.max_calls or usage['usd']+usage['uncertain_usd']+reserve>args.max_usd:raise RuntimeError('call/budget reservation stop; no request sent')
    append(folder/'api_journal.jsonl',dict(type='attempt',t=view['t'],reservation_usd=reserve,payload=payload))
    usage['calls']+=1;usage['uncertain_usd']+=reserve
    req=urllib.request.Request('https://api.anthropic.com/v1/messages',data=json.dumps(payload).encode(),
        headers={'x-api-key':os.environ['ANTHROPIC_API_KEY'],'anthropic-version':'2023-06-01','content-type':'application/json'})
    with urllib.request.urlopen(req,timeout=120) as response:reply=json.load(response)
    append(folder/'api_journal.jsonl',dict(type='response',t=view['t'],response=reply))
    u=reply.get('usage',{});usage['usd']+=(u.get('input_tokens',0)*args.input_price+u.get('output_tokens',0)*args.output_price)/1e6
    usage['uncertain_usd']=max(0,usage['uncertain_usd']-reserve)
    actions,wrapped=parse_response(reply)
    usage['format_wrappers']+=int(wrapped)
    usage['tool_like_text_responses']=usage.get('tool_like_text_responses',0)+int(any('<invoke' in b.get('text','').lower() for b in reply.get('content',[]) if b.get('type')=='text'))
    return actions

class ResponseTests(unittest.TestCase):
    def test_fenced_response_and_rejection(self):
        action=dict(id='one',op='pay',payment='D0-USD-1',route='tokenized_deposit')
        body=json.dumps(dict(actions=[action]))
        def reply(text,stop='end_turn'):return dict(stop_reason=stop,content=[dict(type='thinking',thinking='ignored'),dict(type='text',text=text)])
        self.assertEqual(parse_response(reply(body)),([action],False))
        self.assertEqual(parse_response(reply('```json\n'+body+'\n```')),([action],True))
        for text in ('Here is the JSON: '+body,'```json\n'+body,body+' trailing text','[]'):
            with self.assertRaises(ValueError):parse_response(reply(text))
        with self.assertRaises(ValueError):parse_response(reply(body,'max_tokens'))

    def test_fenced_actions_with_commentary(self):
        actions=[dict(id='t16-sub-USD-tmmf',op='subscribe',instrument='USD_tmmf',amount=30000000000),
                 dict(id='t16-recall-USD-corr',op='recall',ccy='USD',amount=15000000000)]
        block='```json\n'+json.dumps(dict(actions=actions))+'\n```'
        def reply(text):return dict(stop_reason='end_turn',content=[dict(type='text',text=text)])
        prose='\n\nI kept the plan small.\n- **Payments:** All 24 day-0 payments are paid.\n- The recall settles later.'
        self.assertEqual(parse_response(reply(block+prose)),(actions,True))
        self.assertEqual(parse_response(reply(json.dumps(dict(actions=actions))+prose)),(actions,True))
        self.assertEqual(parse_response(reply('{"actions":[]}\n\nNo action at 18:00.')),([],True))
        self.assertEqual(parse_response(reply('Proposed actions:\n'+block+prose)),(actions,True))
        for text in (block+'\n'+block,block+'\n{"actions":[]}',block+'\n```python\npass\n```',
                     '{"actions":[]}\n\n{"actions":[]}', '{"actions":[]}\n\n```json\n{}\n```'):
            with self.assertRaises(ValueError):parse_response(reply(text))

    def test_uncertain_cost_counts_against_budget(self):
        args=SimpleNamespace(model='test',max_output=100,input_price=2,output_price=10,
                             replay={},max_calls=17,max_usd=.21)
        usage=dict(calls=14,usd=.01,uncertain_usd=.2,format_wrappers=0)
        reply=dict(stop_reason='end_turn',content=[dict(type='text',text='{"actions":[]}')],usage=dict(input_tokens=10,output_tokens=20))
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,ANTHROPIC_API_KEY='offline-test'):
            with patch('urllib.request.urlopen',side_effect=AssertionError('budget should prevent request')):
                with self.assertRaisesRegex(RuntimeError,'budget'):request_model(dict(t=42),args,Path(tmp),usage)
            self.assertEqual(usage['calls'],14)
            args.max_usd=5
            with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(reply).encode())):
                self.assertEqual(request_model(dict(t=42),args,Path(tmp),usage),[])
            self.assertEqual(usage['calls'],15)
            self.assertAlmostEqual(usage['uncertain_usd'],.2)


# Bank calibration and reference policies use the settlement engine above.
PROFILE={
 'name':'Synthetic Swiss bank; not a reconstruction of any named institution',
 'assets_chf':{'mortgages':29_000_000_000,'other_loans':3_000_000_000,
   'reserves_and_operating_cash':3_500_000_000,'correspondent':500_000_000,
   'treasury_investments':3_000_000_000,'other_assets':1_000_000_000},
 'funding_chf':{'customer_deposits':25_000_000_000,'wholesale':10_000_000_000,
   'other_liabilities':2_000_000_000,'equity':3_000_000_000},
 'client_custody_chf':10_000_000_000,'discretionary_aum_subset_chf':4_000_000_000,
 'protected_reserves_chf':3_000_000_000,'protected_securities_chf':2_000_000_000,
 'managed_treasury_chf':2_000_000_000,
 'calibration_reference':'https://www.valiant.ch/en/investor-relations/profile',
 'reference_scope':'2025 balance-sheet scale only. All flows, buffers, rates and access rules are synthetic assumptions, not observed Valiant operations.'}
WEIGHTS={'CHF':.60,'USD':.20,'EUR':.15,'GBP':.05}
CORE_CHF={'CHF':300_000_000,'USD':100_000_000,'EUR':75_000_000,'GBP':25_000_000}
CORR_CHF={'CHF':0,'USD':250_000_000,'EUR':150_000_000,'GBP':100_000_000}
FLOOR_CHF={'CHF':75_000_000,'USD':25_000_000,'EUR':20_000_000,'GBP':10_000_000}
CORR_FLOOR_CHF={'CHF':0,'USD':50_000_000,'EUR':30_000_000,'GBP':20_000_000}

def make_tape(days,start,seed,scenario='bank'):
    if scenario in ISOLATED and (days!=2 or start.weekday()!=4):
        raise ValueError('after-hours matched scenarios require --days 2 and a Friday --start (e.g. 2026-11-27)')
    rng=random.Random(seed);tape=[]
    for d in range(days):
        dt=start+timedelta(days=d);business=dt.weekday()<5
        me=dt.day==calendar.monthrange(dt.year,dt.month)[1]
        fx={c:round(v*(1+rng.uniform(-.002,.002)),6) for c,v in zip(CCY,[.88,1.12,.94,1])};fx['CHF']=1
        rates={c:b+rng.randint(-3,3)+(-25 if d>=7 else 0)+(15 if d>=20 else 0) for c,b in zip(CCY,[420,390,240,90])}
        volume=rng.randint(200,400)*1_000_000*(1.7 if me else 1)*(1 if business else .30)
        incoming=rng.randint(220,420)*1_000_000*(1.7 if me else 1)*(1 if business else .35)
        payments=[];receipts=[]
        for c in CCY:
            amounts=[rng.uniform(.2,1.8) for _ in range(60)];den=sum(amounts)
            for j,v in enumerate(amounts):
                routes=['domestic'] if c=='CHF' or j%4 else ['correspondent','stablecoin','tokenized_deposit']
                n=money(volume*WEIGHTS[c]/fx[c]*v/den)
                payments.append(dict(id=f'D{d}-{c}-{j}',ccy=c,amount=n,due=d*24+([11,15,19,23][(j//4)%4] if 'correspondent' in routes else [9,11,13,15,19,23][j%6]),routes=routes,category='customer_payment'))
            # Independent daily receipts; not matched to outgoing payments.
            receipts.extend([dict(ccy=c,amount=money(incoming*WEIGHTS[c]/fx[c]*share),t=d*24+h)
                             for h,share in [(12,.30),(18,.70)]])
        if business:
            payments.append(dict(id=f'D{d}-mortgage-batch',ccy='CHF',amount=money(rng.randint(10,40)*1_000_000),
                                 due=d*24+11,routes=['domestic'],category='mortgage_disbursement'))
        if d in (1,15):
            payments.append(dict(id=f'D{d}-withdrawal-stress',ccy='CHF',amount=money(250_000_000),
                                 due=d*24+15,routes=['domestic'],category='exceptional_withdrawal'))
        events=[dict(hour=h,kind=k) for h,k in zip(HOURS,['disclose_day','desk_open','redemption_review',
            'first_receipts','settlement_review','preclose_review','desk_close_and_receipts','collateral_release','overnight_review'])]
        collateral=rng.randint(100,300)*1_000_000
        row=dict(day=d,date=dt.isoformat(),month_end=me,rates=rates,fx=fx,payments=payments,receipts=receipts,
                 events=events,scenario=scenario,collateral_release={c:money(collateral*WEIGHTS[c]/fx[c]) for c in CCY})
        if scenario=='redemption_drill':
            # Isolated, transparent component test, not representative bank volumes.
            row['payments']=([dict(id='REDEEM-CHF-100M',ccy='CHF',amount=money(100_000_000),due=15,
                                  routes=['domestic'],category='diagnostic_withdrawal')] if d==0 else [])
            row['receipts']=[];row['collateral_release']={c:0 for c in CCY}
        if scenario in ISOLATED:
            # Announced on Friday; release times prevent prepaying to evade the weekend.
            row['payments']=([dict(id='AH-20M',ccy='USD',amount=money(20_000_000),
                due=31,earliest_send=30,routes=(['domestic','correspondent','stablecoin','tokenized_deposit']
                if scenario=='after_hours_control' else ['correspondent','stablecoin','tokenized_deposit']),
                category='weekend_external_payment'),
                dict(id='AH-70M',ccy='USD',amount=money(70_000_000),due=33,earliest_send=32,
                routes=['domestic'],category='weekend_fiat_obligation')] if d==0 else [])
            row['receipts']=[];row['collateral_release']={c:0 for c in CCY}
        if scenario in CYCLE_CASES and d==0:
            row['payments'][1]['amount']=money(74_900_000)
        tape.append(row)
    return tape

class Engine(SettlementEngine):
    def __init__(self,tape,start,policy):
        super().__init__(tape,start,policy)
        self.scenario=tape[0].get('scenario','bank')
        self.assets={a:{c:0 for c in CCY} for a in ('core','td','stable','corr')}
        for c in CCY:
            self.assets['core'][c]=self.local(CORE_CHF[c],c)
            self.assets['corr'][c]=self.local(CORR_CHF[c],c)
            self.units[f'{c}_mmf']=self.local(1_000_000_000*WEIGHTS[c],c)*MICRO//10000
        if self.scenario=='redemption_drill':
            self.assets={a:{c:0 for c in CCY} for a in ('core','td','stable','corr')}
            self.assets['core']['CHF']=money(40_000_000)
            self.units={k:0 for k in self.cat};self.units['CHF_mmf']=money(150_000_000)*MICRO//10000
        if self.scenario in ISOLATED:
            self.assets={a:{c:0 for c in CCY} for a in ('core','td','stable','corr')}
            self.assets['core']['USD']=money(120_000_000)
            self.units={k:0 for k in self.cat}
            for instrument in self.cat.values():instrument['eligible']=instrument['ccy']=='USD'
        if self.scenario=='required_redemption':
            self.assets['core']['USD']=money(30_000_000)
            self.units['USD_tmmf']=money(90_000_000)*MICRO//self.price('USD_tmmf')
        self.opening=self.values();self.fx_open=sum(D(self.opening[c])*D(str(self.market['fx'][c])) for c in CCY)
        self.opening_units=dict(self.units)
        self.batch_requests={}
        self.request_records={}
        self.feedback_t=None
        self.feedback=[]
    def local(self,chf,c):return rounded(D(str(chf))*100/D(str(self.tape[0]['fx'][c])))
    def floor(self,c):
        if getattr(self,'scenario','bank') in ISOLATED:return money(25_000_000) if c=='USD' else 0
        if getattr(self,'scenario','bank')=='redemption_drill':return money(25_000_000) if c=='CHF' else 0
        return self.local(FLOOR_CHF[c]*(1.5 if self.market['month_end'] else 1),c)
    def corr_floor(self,c):return 0 if self.scenario in ISOLATED else self.local(CORR_FLOOR_CHF[c],c)
    def act(self,a):
        # Transport IDs belong to the controller, not model financial reasoning.
        if self.feedback_t!=self.t:
            self.feedback_t=self.t;self.feedback=[]
        local=a.get('id') if isinstance(a,dict) else None
        key=json.dumps(['checkpoint',self.t,local],separators=(',',':')) if isinstance(local,str) and local else None
        if key and key in self.request_records:
            previous,result=self.request_records[key]
            if previous==a:
                return dict(copy.deepcopy(result),duplicate=True)
            self.blocks+=1
            result=dict(ok=False,error='conflicting action id within checkpoint')
            self.event('blocked',action=a,error=result['error'])
        else:
            effective=copy.deepcopy(a)
            if key:effective['id']=key
            result=self._execute(effective)
            if key:self.request_records[key]=(copy.deepcopy(a),copy.deepcopy(result))
        item=dict(id=local,op=a.get('op') if isinstance(a,dict) else None,
                  ok=result['ok'],error=result.get('error'))
        if isinstance(a,dict) and a.get('op')=='pay_batch' and 'children' in result:
            item['accepted_count']=sum(x['ok'] for x in result['children'])
            item['failed_payments']=[dict(payment=p,error=r.get('error'))
                for p,r in zip(a['payments'],result['children']) if not r['ok']]
        self.feedback.append(item)
        return result
    def _execute(self,a):
        # Batches are convenience only: every child is independently checked/logged.
        if isinstance(a,dict) and a.get('op')=='pay_batch':
            ids=a.get('payments')
            if not isinstance(a.get('id'),str) or not a['id'] or not isinstance(ids,list) or len(ids)>300 or any(not isinstance(p,str) for p in ids):
                self.blocks+=1;return dict(ok=False,error='invalid payment batch')
            if a['id'] in self.batch_requests:
                previous,result=self.batch_requests[a['id']]
                if previous==a:return dict(result,duplicate=True)
                self.blocks+=1;self.event('blocked',action=a,error='conflicting batch id')
                return dict(ok=False,error='conflicting batch id')
            result=[self._execute(dict(id=json.dumps(['child',a['id'],p],separators=(',',':')),op='pay',payment=p,route=a.get('route'))) for p in ids]
            response=dict(ok=all(x['ok'] for x in result),children=result)
            self.batch_requests[a['id']]=(copy.deepcopy(a),copy.deepcopy(response))
            return response
        return super().act(a)
    def _action(self,a):
        op=a['op'];c=a.get('ccy','USD')
        if self.scenario in ISOLATED:
            if op in ('fx','borrow','repay'):raise ValueError('isolated USD sleeve has no FX or borrowing facility')
            if op=='pay' and self.t<self.obligations[a['payment']].get('earliest_send',0):
                raise ValueError('payment release time not reached')
        if self.scenario=='redemption_drill' and op not in ('redeem','pay'):
            raise ValueError('isolated redemption drill permits only redeem and pay')
        if op in ('recall','replenish'):
            n=a.get('amount');asset='corr' if op=='recall' else a.get('asset','core')
            if c not in CCY or type(n)!=int or n<=0:raise ValueError('currency or amount')
            if asset not in ('core','stable','corr'):raise ValueError('asset')
            if asset!='stable' and (not self.business(self.t) or not 8<=self.t%24<=17):raise ValueError('funding desk closed')
            if op=='recall' and self.assets['corr'][c]-n<self.corr_floor(c):raise ValueError('correspondent reserve')
            self.fee(c,2000 if asset!='stable' else 3000);self.debit(asset,c,n)
            self.queue('cash',2,ccy=c,amount=n,asset='core' if op=='recall' else 'corr');return
        if op=='pay' and a.get('route')=='correspondent':
            p=self.obligations[a['payment']]
            if self.assets['corr'][p['ccy']]-p['amount']<self.corr_floor(p['ccy']):raise ValueError('correspondent reserve')
        if op=='fx':
            n=a.get('amount',0)
            if type(n)!=int or n<=0:raise ValueError('amount')
            limit=self.local(25_000_000,c)
            if abs(self.fxtrade[c]-n)>limit:raise ValueError('cumulative FX principal limit')
            dest=a['dest'];out=int(D(n)*D(str(self.market['fx'][c]))/D(str(self.market['fx'][dest]))*D('.9995'))
            if abs(self.fxtrade[dest]+out)>self.local(25_000_000,dest):raise ValueError('destination FX principal limit')
        super()._action(a)
    def view(self):
        v=super().view()
        v['instruments']=explicit_instrument_terms(v['instruments'])
        v['payments']=[dict(p,overdue=p['due']<=self.t) for p in v['payments'] if p['status']!='paid']
        v['recent_execution']=dict(t=self.feedback_t,results=copy.deepcopy(self.feedback))
        v['deadline_policy']='on_time_only; overdue payments cannot execute; remain missed'
        v['action_id_scope']='checkpoint; identical retries in same checkpoint are idempotent'
        v.update(bank_profile=PROFILE,scenario=self.scenario,
                 correspondent_floors={c:self.corr_floor(c) for c in CCY},
                 cumulative_fx_principal=self.fxtrade,fx_principal_limits={c:self.local(25_000_000,c) for c in CCY})
        if self.scenario in ISOLATED:
            v['bank_profile']=after_hours_profile(self.scenario)
            v['scenario_rules']=scenario_rules(self.scenario)
        return v

def after_hours_profile(scenario="after_hours"):
    return dict(name='Isolated synthetic USD treasury sleeve',opening_core_usd=30_000_000 if scenario=='required_redemption' else 120_000_000,
                core_floor_usd=25_000_000,inherited_investments_usd=90_000_000 if scenario=='required_redemption' else 0,
                bank_wide_aum_or_deposits='not modelled in this diagnostic')

AFTER_HOURS_RULES = """ISOLATED AFTER-HOURS TREASURY DIAGNOSTIC
USD120m opening core cash; USD25m hard core floor; no inherited funds, incoming receipts,
FX or credit facility. USD instruments only. All terms are synthetic, not product claims.
Two obligations are disclosed Friday 06:00. Send only when earliest_send is reached.
AH-20M: Saturday 06:00 release, 07:00 settlement deadline. Recipient accepts only its
listed routes. AH-70M: Saturday 08:00 release, 09:00 deadline, domestic fiat only.
Domestic route is 24/7 here. Correspondent execution requires a weekday desk window.
Mint/burn settle in 1h; tokenized MMF subscriptions and redemptions settle in 2h;
redemption orders accepted 00:00 through 22:00. Local deposits and conventional MMFs
have their displayed weekday windows. Pending assets cannot fund other actions.
Payment feasibility is primary; net interest less fees is secondary. You may hold cash,
use conventional instruments, stablecoins or tokenized deposits, or decline investment.
No bonus is awarded for using a digital asset. Choose the instruments and sequence yourself.
This is a transparent component experiment, not a representative bank-wide sample."""

def scenario_rules(scenario):
    if scenario not in CYCLE_CASES:return AFTER_HOURS_RULES
    opening=('USD30m opening core cash and USD90m inherited USD_tmmf holdings'
             if scenario=='required_redemption' else 'USD120m opening core cash and no inherited fund holdings')
    return (AFTER_HOURS_RULES.replace(
        'USD120m opening core cash; USD25m hard core floor; no inherited funds, incoming receipts,',
        opening+'; USD25m hard core floor; no incoming receipts,')
        .replace('AH-70M: Saturday 08:00 release, 09:00 deadline, domestic fiat only.',
                 'AH-70M (identifier retained): USD74.9m, Saturday 08:00 release, 09:00 deadline, domestic fiat only.')
        +'\nThe payment list gives authoritative amounts. Investment is optional; payment and floor constraints take priority. '
        'The horizon ends Saturday 23:00. Unsold holdings remain valued assets; report their value separately from income. '
        'No terminal liquidation is required and holding cash is permitted.')

def cycle_baseline(e,policy):
    actions=[]
    def do(op,**kw):
        a=dict(id=f'{policy}-{e.t}-{len(actions)}',op=op,**kw)
        actions.append(dict(action=a,result=e.act(a)))
    if policy=='reference':
        if e.scenario=='optional_investment':
            if e.t==6:do('mint',ccy='USD',asset='td',amount=money(90_000_000))
            if e.t==8:do('subscribe',instrument='USD_tmmf',amount=money(90_000_000))
        if e.t==22:do('redeem',instrument='USD_tmmf',units=e.units['USD_tmmf'])
        if e.t==30:
            do('burn',ccy='USD',asset='td',amount=money(70_000_000))
            do('pay',payment='AH-20M',route='tokenized_deposit')
        if e.t==32:do('pay',payment='AH-70M',route='domestic')
    elif policy=='hold_cash' and e.scenario=='optional_investment':
        if e.t==22:do('mint',ccy='USD',asset='td',amount=money(20_000_000))
        if e.t==30:do('pay',payment='AH-20M',route='tokenized_deposit')
        if e.t==32:do('pay',payment='AH-70M',route='domestic')
    # Required-redemption hold_cash deliberately leaves inherited holdings untouched:
    # a negative control, not a competitive investment strategy.
    return actions

def protocol_for(scenario):
    if scenario not in ISOLATED:return GUIDE+'\n'+YIELD_TERMS
    mechanics=GUIDE.split('ASSETS / SETTLEMENT / CONTROLS\n',1)[1].split('Collateral is explicitly',1)[0]
    contract=GUIDE.split('ACTION CONTRACT\n',1)[1]
    return (scenario_rules(scenario)+'\nFixed CET UTC+1, no holidays/DST. Decision hours each day: '
            '06,08,10,12,14,16,18,22,23. Settlement progresses hourly between decisions. '
            'Current-day rates only; no future random data.\n'+mechanics+'\nACTION CONTRACT\n'+contract+'\n'+YIELD_TERMS)

def after_hours_baseline(e,policy):
    # Frozen illustrative schedules, NOT optimal policies. All respect the same windows.
    actions=[]
    def do(op,**kw):
        a=dict(id=f'{policy}-{e.t}-{len(actions)}',op=op,**kw)
        actions.append(dict(action=a,result=e.act(a)))
    if policy=='direct_tokens':
        if e.t==22:do('mint',ccy='USD',asset='td',amount=money(20_000_000))
        if e.t==30:do('pay',payment='AH-20M',route='tokenized_deposit')
        if e.t==32:do('pay',payment='AH-70M',route='domestic')
    elif policy=='hybrid':
        if e.t==6:do('mint',ccy='USD',asset='td',amount=money(90_000_000))
        if e.t==8:do('subscribe',instrument='USD_tmmf',amount=money(90_000_000))
        if e.t==22:do('redeem',instrument='USD_tmmf',units=e.units['USD_tmmf'])
        if e.t==30:
            do('burn',ccy='USD',asset='td',amount=money(70_000_000))
            do('pay',payment='AH-20M',route='tokenized_deposit')
        if e.t==32:
            do('pay',payment='AH-70M',route='domestic')
    else:
        if policy=='conventional':
            if e.t==8:do('subscribe',instrument='USD_local',amount=money(90_000_000))
            if e.t==16:do('redeem',instrument='USD_local',units=e.units['USD_local'])
        if e.t==30 and e.scenario=='after_hours_control':do('pay',payment='AH-20M',route='domestic')
        if e.t==32:do('pay',payment='AH-70M',route='domestic')
    return actions

def baseline(e,policy):
    if e.scenario in CYCLE_CASES:return cycle_baseline(e,policy)
    if e.scenario in ISOLATED:return after_hours_baseline(e,policy)
    actions=[]
    def do(op,**kw):
        e.nextid+=1;a=dict(id=f'{policy}-{e.t}-{e.nextid}',op=op,**kw)
        res=e.act(a);actions.append(dict(action=a,result=res));return res
    for c in CCY:
        openp=[p for p in e.obligations.values() if p['ccy']==c and p['status']=='open' and p['due']>e.t]
        need=sum(p['amount'] for p in openp)
        next_day_allowance=e.local(400_000_000*WEIGHTS[c]+(40_000_000 if c=='CHF' else 0),c) if e.scenario=='bank' else 0
        reserve=e.floor(c)+need+next_day_allowance+e.local(5_000_000,c)
        pendingcore=sum(x.get('amount',0) for x in e.pending if x['ccy']==c and x['kind']=='cash' and x['asset']=='core')
        gap=max(0,reserve-e.assets['core'][c]-pendingcore)
        # Cash-only liquidates inherited funds, then abstains from new investment.
        if gap or policy=='cash_only':
            for k,i in e.cat.items():
                if i['ccy']==c and e.units[k] and e.window(k,True):
                    # Funds redeem only enough to meet current commitments + buffer.
                    value=e.holding(k);n=value if policy=='cash_only' else min(value,gap+e.local(1_000_000,c))
                    if n<=0:continue
                    u=min(e.units[k],(n*MICRO+e.price(k)-1)//e.price(k))
                    if do('redeem',instrument=k,units=u)['ok']:gap=max(0,gap-n)
            for asset in ('td','stable'):
                digital_commitment=sum(p['amount'] for p in openp if 'tokenized_deposit' in p['routes']) if asset=='td' and policy=='hybrid' else 0
                n=min(max(0,e.assets[asset][c]-digital_commitment),max(0,reserve-e.assets['core'][c]-pendingcore))
                if n and e.scenario!='redemption_drill':do('burn',ccy=c,asset=asset,amount=n)
        if e.scenario!='redemption_drill' and policy=='hybrid' and e.t%24==8 and e.business(e.t):
            n=max(0,e.assets['corr'][c]-e.corr_floor(c)-e.local(30_000_000,c))
            if n:do('recall',ccy=c,amount=n)
    if policy=='hybrid' and e.scenario=='bank':
        for c in CCY:
            total=sum(p['amount'] for p in e.obligations.values() if p['ccy']==c and p['status']=='open'
                      and 'tokenized_deposit' in p['routes'] and p['due']>=e.t+2)
            pending=sum(x.get('amount',0) for x in e.pending if x['ccy']==c and x['kind']=='cash' and x['asset']=='td')
            n=max(0,total-e.assets['td'][c]-pending)
            domestic_need=sum(p['amount'] for p in e.obligations.values() if p['ccy']==c and p['status']=='open' and 'domestic' in p['routes'])
            if n and e.assets['core'][c]-n-100>=e.floor(c)+domestic_need:do('mint',ccy=c,asset='td',amount=n)
    # No speculative borrowing: upcoming cash is checked against settlement times.
    for p in e.obligations.values():
        if p['status']!='open' or p['due']<=e.t:continue
        c=p['ccy'];n=p['amount']
        for route in ('domestic','tokenized_deposit','correspondent','stablecoin'):
            if route not in p['routes'] or (policy!='hybrid' and route in ('tokenized_deposit','stablecoin')):continue
            asset={'domestic':'core','correspondent':'corr','tokenized_deposit':'td','stablecoin':'stable'}[route]
            if route=='correspondent' and (not e.business(e.t) or not 8<=e.t%24<=17):continue
            delay=2 if asset=='corr' else 1
            floor=e.floor(c) if asset=='core' else e.corr_floor(c) if asset=='corr' else 0
            if e.t+delay<=p['due'] and e.assets[asset][c]-n>=floor+5000:
                do('pay',payment=p['id'],route=route);break
        else:
            if policy=='hybrid' and 'tokenized_deposit' in p['routes']:
                pending=sum(x.get('amount',0) for x in e.pending if x['ccy']==c and x['kind']=='cash' and x['asset']=='td')
                n=max(0,n-e.assets['td'][c]-pending)
                domestic_need=sum(q['amount'] for q in e.obligations.values() if q['ccy']==c and q['status']=='open' and 'domestic' in q['routes'])
                if n and e.assets['core'][c]-n-100>e.floor(c)+domestic_need:do('mint',ccy=c,asset='td',amount=n)
    # One daily allocation, no churn. Preserve next-day cash against a declared bound.
    if e.scenario=='bank' and e.t%24==16 and e.business(e.t):
        for c in CCY:
            target=e.local(CORR_CHF[c],c) if policy!='hybrid' else e.corr_floor(c)+e.local(30_000_000,c)
            n=max(0,target-e.assets['corr'][c])
            domestic_need=sum(p['amount'] for p in e.obligations.values() if p['ccy']==c and p['status']=='open' and 'domestic' in p['routes'])
            if n and e.assets['core'][c]-n-2000>=e.floor(c)+domestic_need:
                do('replenish',ccy=c,asset='core',amount=n)
    if policy!='cash_only' and e.scenario!='redemption_drill' and e.t%24==16:
        for c in CCY:
            need=sum(p['amount'] for p in e.obligations.values() if p['ccy']==c and p['status']=='open')
            reserve=e.floor(c)+need+e.local(400_000_000*WEIGHTS[c]+(40_000_000 if c=='CHF' else 0),c)
            n=max(0,e.assets['core'][c]-reserve-e.local(1_000_000,c))
            eligible=[k for k,i in e.cat.items() if i['ccy']==c and i['kind'] in ('local','central') and e.window(k)]
            if n>e.local(5_000_000,c) and eligible:
                k=max(eligible,key=e.rate)
                if D(n)*e.rate(k)/10000/365>2*e.cat[k]['fee_cents']:do('subscribe',instrument=k,amount=n)
    return actions

def metrics(e,complete):
    m=portfolio_metrics(e,complete)
    accepted=[r['action'] for r in e.log if r['kind']=='accepted']
    counts={op:sum(a['op']==op for a in accepted) for op in ('redeem','burn','borrow','repay','subscribe','fx')}
    inherited=dict(e.opening_units);redeemed_initial={k:0 for k in e.cat};redeemed_new={k:0 for k in e.cat}
    for a in accepted:
        if a['op']=='redeem':
            k=a['instrument'];u=a['units'];old=min(inherited[k],u)
            inherited[k]-=old;redeemed_initial[k]+=old;redeemed_new[k]+=u-old
    m.update(scenario=e.scenario,bank_profile=PROFILE,workflow_counts=counts,
             redeemed_inherited_micro_units=redeemed_initial,redeemed_subscribed_micro_units=redeemed_new,
             lot_attribution='Synthetic FIFO: inherited units redeemed first; not a full economic roundtrip score',
             restricted_assets_excluded_from_agent_chf=5_000_000_000 if e.scenario=='bank' else None,
             scope='Managed treasury portfolio P&L only. Excludes bank funding transfer price, loan income, protected reserves, bank-wide FX hedges and taxes; not whole-bank profit.')
    if e.scenario in ISOLATED:
        m['bank_profile']=after_hours_profile(e.scenario)
        m['scope']='Isolated USD sleeve; synthetic rates/windows; no whole-bank profitability claim'
        m['workflow_counts']={op:sum(a['op']==op for a in accepted) for op in
                              ('mint','subscribe','redeem','burn','pay','recall','replenish','borrow','fx')}
        m['net_interest_less_costs_usd']=m['net_interest_less_costs_cents']['USD']/100
        m['coverage']={
            'new_tokenized_fund_units_redeemed':redeemed_new['USD_tmmf'],
            'mint_usd':sum(a['amount'] for a in accepted if a['op']=='mint' and a['asset']=='td')/100,
            'burn_usd':sum(a['amount'] for a in accepted if a['op']=='burn' and a['asset']=='td')/100,
            'tokenized_payment_count':sum(a['op']=='pay' and a.get('route')=='tokenized_deposit' for a in accepted),
            'stablecoin_payment_count':sum(a['op']=='pay' and a.get('route')=='stablecoin' for a in accepted),
            'note':'Operation counts and newly redeemed units; inspect settlement order to establish a complete cycle.'}
        m['interpretation']='After-hours case excludes domestic route for AH-20M; conventional-only failure is a designed access restriction, not model superiority.'
    if e.scenario in CYCLE_CASES:
        m['interpretation']='Paired opening-allocation diagnostic; same USD94.9m obligations. Reference is feasible, not proven optimal. hold_cash is a negative control in required_redemption.'
        m['ending_tokenized_fund_value_usd']=e.holding('USD_tmmf')/100
        m['inherited_tokenized_units_redeemed']=redeemed_initial['USD_tmmf']
    return m

class Tests(unittest.TestCase):
    def test_identical_inline_document_is_executed_once(self):
        action=dict(id='once',op='mint',ccy='USD',asset='td',amount=money(1_000_000))
        obj=dict(actions=[action]);body=json.dumps(obj)
        reply=dict(stop_reason='end_turn',content=[dict(type='text',text=
            'Plan: `'+json.dumps(obj,sort_keys=True)+'`.\n\n```json\n'+body+'\n```')])
        actions,wrapped=parse_response(reply)
        self.assertEqual(actions,[action]);self.assertTrue(wrapped)
        e=self.cycle_engine('optional_investment');e.advance(6)
        for a in actions:self.assertTrue(e.act(a)['ok'])
        self.assertEqual(len(e.pending),1)
        self.assertEqual(sum(r['kind']=='accepted' for r in e.log),1)

    def test_identical_noop_inline_and_conflicts(self):
        def reply(text):return dict(stop_reason='end_turn',content=[dict(type='text',text=text)])
        block='\n\n```json\n{"actions":[]}\n```'
        self.assertEqual(parse_response(reply('No actions: `{"actions":[]}`.'+block)),([],True))
        for outside in ('`{"actions":[{"op":"pay"}]}`','`{"actions": [}`',
                        '`{"actions":[],"extra":true}`','{"actions":[]}',
                        '`{"actions":[]}` and {"actions":[1]}'):
            with self.assertRaises(ValueError):parse_response(reply(outside+block))
        with self.assertRaises(ValueError):parse_response(reply(block+block))

    def cycle_engine(self,scenario):
        dt=datetime(2026,11,27).date()
        return Engine(make_tape(2,dt,42,scenario),dt,'test')

    def test_cycle_matched_obligations_and_opening_assets(self):
        a=self.cycle_engine('required_redemption');b=self.cycle_engine('optional_investment')
        left=copy.deepcopy(a.tape);right=copy.deepcopy(b.tape)
        for row in left+right:row.pop('scenario')
        self.assertEqual(left,right)
        self.assertEqual(a.values()['USD'],money(120_000_000))
        self.assertEqual(a.values(),b.values())
        for e in (a,b):
            e.advance(6)
            self.assertEqual(sum(p['amount'] for p in e.view()['payments']),money(94_900_000))
            self.assertEqual(e.floor('USD'),money(25_000_000))
            self.assertIn('USD74.9m',protocol_for(e.scenario))
            self.assertNotIn('USD120m opening core cash',protocol_for('required_redemption'))

    def test_cycle_reference_and_cash_controls(self):
        for scenario in CYCLE_CASES:
            for policy in ('reference','hold_cash'):
                e=self.cycle_engine(scenario)
                for d in range(2):
                    for h in HOURS:e.advance(24*d+h);baseline(e,policy)
                r=metrics(e,True)
                self.assertEqual(r['on_time'],0 if scenario=='required_redemption' and policy=='hold_cash' else 2)
                self.assertEqual(r['blocked_actions'],0)
                self.assertEqual(r['floor_breach_hours'],0)
                self.assertTrue(all(v==0 for v in r['mark_and_rounding_residual_cents'].values()))
                if policy=='reference':
                    self.assertEqual(e.units['USD_tmmf'],0)
                    self.assertFalse(e.pending)
                    self.assertEqual(e.obligations['AH-20M']['settled_at'],31)
                    self.assertEqual(e.obligations['AH-70M']['settled_at'],33)
                    self.assertEqual(r['coverage']['burn_usd'],70_000_000)
                    if scenario=='optional_investment':
                        self.assertGreater(r['coverage']['new_tokenized_fund_units_redeemed'],0)
                        kinds=[x['transfer']['kind'] for x in e.log if x['kind']=='settled']
                        self.assertEqual(kinds,['cash','units','cash','cash','pay','pay'])
                    else:self.assertGreater(r['inherited_tokenized_units_redeemed'],0)

    def test_cycle_late_redemption_cannot_fund_deadline(self):
        e=self.cycle_engine('required_redemption');e.advance(30)
        self.assertTrue(e.act(dict(id='redeem',op='redeem',instrument='USD_tmmf',units=e.units['USD_tmmf']))['ok'])
        r=e.act(dict(id='pay',op='pay',payment='AH-20M',route='tokenized_deposit'))
        self.assertFalse(r['ok']);self.assertIn('insufficient settled',r['error'])
        e.advance(32)
        self.assertFalse(e.act(dict(id='late-pay',op='pay',payment='AH-20M',route='tokenized_deposit'))['ok'])
        e.advance(47);self.assertGreaterEqual(metrics(e,True)['missed'],1)

    def test_cycle_no_pre_release_payment_or_closed_redemption(self):
        e=self.cycle_engine('required_redemption');e.advance(22)
        self.assertFalse(e.act(dict(id='early',op='pay',payment='AH-20M',route='tokenized_deposit'))['ok'])
        e.advance(23)
        self.assertFalse(e.act(dict(id='closed',op='redeem',instrument='USD_tmmf',units=e.units['USD_tmmf']))['ok'])

    def test_yield_terms_are_explicit_and_non_mutating(self):
        e=self.after_engine();e.advance(8)
        original=copy.deepcopy(e.cat)
        v=e.view()['instruments']['USD_tmmf']
        self.assertNotIn('spread_bps',v)
        self.assertEqual(v['yield_adjustment_bps'],10)
        self.assertEqual(v['rate_bps'],e.market['rates']['USD']+10)
        self.assertEqual(v['subscription_fee_cents'],150)
        self.assertEqual(v['redemption_fee_cents'],150)
        self.assertEqual(v['transaction_spread_bps'],0)
        self.assertEqual(e.cat,original)
        self.assertIn(YIELD_TERMS,protocol_for('after_hours'))

    def test_instrument_fee_is_flat_not_a_yield_spread(self):
        e=self.after_engine();e.advance(6)
        self.assertTrue(e.act(dict(id='mint',op='mint',ccy='USD',asset='td',amount=money(5_000_000)))['ok'])
        e.advance(8);fees=e.fees['USD']
        self.assertTrue(e.act(dict(id='sub',op='subscribe',instrument='USD_tmmf',amount=money(5_000_000)))['ok'])
        self.assertEqual(e.fees['USD']-fees,150)
        e.advance(10);fees=e.fees['USD']
        self.assertTrue(e.act(dict(id='redeem',op='redeem',instrument='USD_tmmf',units=e.units['USD_tmmf']))['ok'])
        self.assertEqual(e.fees['USD']-fees,150)

    def after_engine(self,scenario='after_hours'):
        dt=datetime(2026,11,27).date()
        return Engine(make_tape(2,dt,42,scenario),dt,'test')

    def test_after_hours_matched_control_and_visibility(self):
        e=self.after_engine();c=self.after_engine('after_hours_control')
        left=copy.deepcopy(e.tape);right=copy.deepcopy(c.tape)
        for row in left+right:row.pop('scenario')
        right[0]['payments'][0]['routes'].remove('domestic')
        self.assertEqual(left,right)
        e.advance(6)
        self.assertEqual(len(e.view()['payments']),2)
        self.assertEqual(e.view()['bank_profile']['opening_core_usd'],120_000_000)
        self.assertEqual(e.view()['instruments']['EUR_mmf']['eligible'],False)
        with self.assertRaisesRegex(ValueError,'Friday'):
            make_tape(2,datetime(2026,11,23).date(),42,'after_hours')

    def test_after_hours_reference_policies_and_roundtrip(self):
        for scenario in AFTER_HOURS:
            for policy in ('conventional','hybrid','cash_only','direct_tokens'):
                e=self.after_engine(scenario)
                for d in range(2):
                    for h in HOURS:e.advance(24*d+h);after_hours_baseline(e,policy)
                r=metrics(e,True)
                self.assertEqual(r['on_time'],2 if policy in ('hybrid','direct_tokens') or scenario=='after_hours_control' else 1)
                self.assertEqual(r['blocked_actions'],0)
                self.assertEqual(r['floor_breach_hours'],0)
                self.assertTrue(all(v==0 for v in r['mark_and_rounding_residual_cents'].values()))
                if policy=='hybrid':
                    self.assertGreater(r['coverage']['new_tokenized_fund_units_redeemed'],0)
                    self.assertEqual(r['coverage']['burn_usd'],70_000_000)
                    self.assertEqual(e.obligations['AH-20M']['settled_at'],31)
                    self.assertEqual(e.obligations['AH-70M']['settled_at'],33)

    def test_after_hours_release_pending_and_windows(self):
        e=self.after_engine();e.advance(6)
        before=copy.deepcopy((e.assets,e.pending,e.fees))
        self.assertFalse(e.act(dict(id='early',op='pay',payment='AH-70M',route='domestic'))['ok'])
        self.assertEqual(before,(e.assets,e.pending,e.fees))
        self.assertTrue(e.act(dict(id='mint',op='mint',ccy='USD',asset='td',amount=money(90_000_000)))['ok'])
        self.assertFalse(e.act(dict(id='premature-sub',op='subscribe',instrument='USD_tmmf',amount=money(90_000_000)))['ok'])
        e.advance(8)
        self.assertTrue(e.act(dict(id='sub',op='subscribe',instrument='USD_tmmf',amount=money(90_000_000)))['ok'])
        e.advance(23)
        self.assertFalse(e.act(dict(id='late-redemption',op='redeem',instrument='USD_tmmf',units=e.units['USD_tmmf']))['ok'])
        e.advance(30)
        self.assertTrue(e.act(dict(id='sat-redemption',op='redeem',instrument='USD_tmmf',units=e.units['USD_tmmf']))['ok'])
        self.assertFalse(e.act(dict(id='premature-burn',op='burn',ccy='USD',asset='td',amount=money(70_000_000)))['ok'])
        e.advance(32)
        self.assertTrue(e.act(dict(id='burn',op='burn',ccy='USD',asset='td',amount=money(70_000_000)))['ok'])
        self.assertFalse(e.act(dict(id='fiat-too-soon',op='pay',payment='AH-70M',route='domestic'))['ok'])
        e.advance(34)
        self.assertFalse(e.act(dict(id='fiat-too-late',op='pay',payment='AH-70M',route='domestic'))['ok'])

    def test_after_hours_cash_and_direct_tokens_are_valid(self):
        # Safety does not require investment: mint only the cross-border amount.
        e=self.after_engine();e.advance(22)
        self.assertTrue(e.act(dict(id='mint',op='mint',ccy='USD',asset='td',amount=money(20_000_000)))['ok'])
        e.advance(30)
        self.assertTrue(e.act(dict(id='external',op='pay',payment='AH-20M',route='tokenized_deposit'))['ok'])
        e.advance(32)
        self.assertTrue(e.act(dict(id='domestic',op='pay',payment='AH-70M',route='domestic'))['ok'])
        e.advance(47)
        r=metrics(e,True)
        self.assertEqual(r['on_time'],2)
        self.assertEqual(r['coverage']['new_tokenized_fund_units_redeemed'],0)

    def test_saved_tool_like_prefix_is_inert(self):
        raw='<invoke name="bash">\n<parameter name="command">echo "no tool needed"</parameter>\n</invoke>\n\n{"actions":[\n{"id":"c-usd","op":"pay_batch","route":"correspondent","payments":["D0-USD-0","D0-USD-4","D0-USD-8","D0-USD-12","D0-USD-16","D0-USD-20","D0-USD-24","D0-USD-28","D0-USD-32","D0-USD-36","D0-USD-40","D0-USD-44","D0-USD-48","D0-USD-52","D0-USD-56"]},\n{"id":"c-gbp","op":"pay_batch","route":"correspondent","payments":["D0-GBP-0","D0-GBP-4","D0-GBP-8","D0-GBP-12","D0-GBP-16","D0-GBP-20","D0-GBP-24","D0-GBP-28","D0-GBP-32","D0-GBP-36","D0-GBP-40","D0-GBP-44","D0-GBP-48","D0-GBP-52","D0-GBP-56"]},\n{"id":"c-eur","op":"pay_batch","route":"correspondent","payments":["D0-EUR-0","D0-EUR-4","D0-EUR-8","D0-EUR-12","D0-EUR-16","D0-EUR-20","D0-EUR-24","D0-EUR-28","D0-EUR-32","D0-EUR-36","D0-EUR-40","D0-EUR-44","D0-EUR-48","D0-EUR-52","D0-EUR-56"]},\n{"id":"d-usd","op":"pay_batch","route":"domestic","payments":["D0-USD-2","D0-USD-3","D0-USD-5","D0-USD-9","D0-USD-10","D0-USD-11","D0-USD-14","D0-USD-15","D0-USD-17","D0-USD-21","D0-USD-22","D0-USD-23","D0-USD-26","D0-USD-27","D0-USD-29","D0-USD-33","D0-USD-34","D0-USD-35","D0-USD-38","D0-USD-39","D0-USD-41","D0-USD-45","D0-USD-46","D0-USD-47","D0-USD-50","D0-USD-51","D0-USD-53","D0-USD-57","D0-USD-58","D0-USD-59"]},\n{"id":"d-gbp","op":"pay_batch","route":"domestic","payments":["D0-GBP-2","D0-GBP-3","D0-GBP-5","D0-GBP-9","D0-GBP-10","D0-GBP-11","D0-GBP-14","D0-GBP-15","D0-GBP-17","D0-GBP-21","D0-GBP-22","D0-GBP-23","D0-GBP-26","D0-GBP-27","D0-GBP-29","D0-GBP-33","D0-GBP-34","D0-GBP-35","D0-GBP-38","D0-GBP-39","D0-GBP-41","D0-GBP-45","D0-GBP-46","D0-GBP-47","D0-GBP-50","D0-GBP-51","D0-GBP-53","D0-GBP-57","D0-GBP-58","D0-GBP-59"]},\n{"id":"d-eur","op":"pay_batch","route":"domestic","payments":["D0-EUR-2","D0-EUR-3","D0-EUR-5","D0-EUR-9","D0-EUR-10","D0-EUR-11","D0-EUR-14","D0-EUR-15","D0-EUR-17","D0-EUR-21","D0-EUR-22","D0-EUR-23","D0-EUR-26","D0-EUR-27","D0-EUR-29","D0-EUR-33","D0-EUR-34","D0-EUR-35","D0-EUR-38","D0-EUR-39","D0-EUR-41","D0-EUR-45","D0-EUR-46","D0-EUR-47","D0-EUR-50","D0-EUR-51","D0-EUR-53","D0-EUR-57","D0-EUR-58","D0-EUR-59"]},\n{"id":"d-chf","op":"pay_batch","route":"domestic","payments":["D0-CHF-2","D0-CHF-8","D0-CHF-14","D0-CHF-20","D0-CHF-26","D0-CHF-32","D0-CHF-38","D0-CHF-44","D0-CHF-50","D0-CHF-56","D0-CHF-3","D0-CHF-9","D0-CHF-15","D0-CHF-21","D0-CHF-27","D0-CHF-33","D0-CHF-39","D0-CHF-45","D0-CHF-51","D0-CHF-57","D0-CHF-4","D0-CHF-10","D0-CHF-16","D0-CHF-22","D0-CHF-28","D0-CHF-34","D0-CHF-40","D0-CHF-46","D0-CHF-52","D0-CHF-58"]}\n]}'
        reply=dict(stop_reason='end_turn',content=[dict(type='text',text=raw)])
        with patch('subprocess.run',side_effect=AssertionError('must never execute text')):
            actions,wrapped=parse_response(reply)
        self.assertEqual(actions,[{'id': 'c-usd', 'op': 'pay_batch', 'route': 'correspondent', 'payments': ['D0-USD-0', 'D0-USD-4', 'D0-USD-8', 'D0-USD-12', 'D0-USD-16', 'D0-USD-20', 'D0-USD-24', 'D0-USD-28', 'D0-USD-32', 'D0-USD-36', 'D0-USD-40', 'D0-USD-44', 'D0-USD-48', 'D0-USD-52', 'D0-USD-56']}, {'id': 'c-gbp', 'op': 'pay_batch', 'route': 'correspondent', 'payments': ['D0-GBP-0', 'D0-GBP-4', 'D0-GBP-8', 'D0-GBP-12', 'D0-GBP-16', 'D0-GBP-20', 'D0-GBP-24', 'D0-GBP-28', 'D0-GBP-32', 'D0-GBP-36', 'D0-GBP-40', 'D0-GBP-44', 'D0-GBP-48', 'D0-GBP-52', 'D0-GBP-56']}, {'id': 'c-eur', 'op': 'pay_batch', 'route': 'correspondent', 'payments': ['D0-EUR-0', 'D0-EUR-4', 'D0-EUR-8', 'D0-EUR-12', 'D0-EUR-16', 'D0-EUR-20', 'D0-EUR-24', 'D0-EUR-28', 'D0-EUR-32', 'D0-EUR-36', 'D0-EUR-40', 'D0-EUR-44', 'D0-EUR-48', 'D0-EUR-52', 'D0-EUR-56']}, {'id': 'd-usd', 'op': 'pay_batch', 'route': 'domestic', 'payments': ['D0-USD-2', 'D0-USD-3', 'D0-USD-5', 'D0-USD-9', 'D0-USD-10', 'D0-USD-11', 'D0-USD-14', 'D0-USD-15', 'D0-USD-17', 'D0-USD-21', 'D0-USD-22', 'D0-USD-23', 'D0-USD-26', 'D0-USD-27', 'D0-USD-29', 'D0-USD-33', 'D0-USD-34', 'D0-USD-35', 'D0-USD-38', 'D0-USD-39', 'D0-USD-41', 'D0-USD-45', 'D0-USD-46', 'D0-USD-47', 'D0-USD-50', 'D0-USD-51', 'D0-USD-53', 'D0-USD-57', 'D0-USD-58', 'D0-USD-59']}, {'id': 'd-gbp', 'op': 'pay_batch', 'route': 'domestic', 'payments': ['D0-GBP-2', 'D0-GBP-3', 'D0-GBP-5', 'D0-GBP-9', 'D0-GBP-10', 'D0-GBP-11', 'D0-GBP-14', 'D0-GBP-15', 'D0-GBP-17', 'D0-GBP-21', 'D0-GBP-22', 'D0-GBP-23', 'D0-GBP-26', 'D0-GBP-27', 'D0-GBP-29', 'D0-GBP-33', 'D0-GBP-34', 'D0-GBP-35', 'D0-GBP-38', 'D0-GBP-39', 'D0-GBP-41', 'D0-GBP-45', 'D0-GBP-46', 'D0-GBP-47', 'D0-GBP-50', 'D0-GBP-51', 'D0-GBP-53', 'D0-GBP-57', 'D0-GBP-58', 'D0-GBP-59']}, {'id': 'd-eur', 'op': 'pay_batch', 'route': 'domestic', 'payments': ['D0-EUR-2', 'D0-EUR-3', 'D0-EUR-5', 'D0-EUR-9', 'D0-EUR-10', 'D0-EUR-11', 'D0-EUR-14', 'D0-EUR-15', 'D0-EUR-17', 'D0-EUR-21', 'D0-EUR-22', 'D0-EUR-23', 'D0-EUR-26', 'D0-EUR-27', 'D0-EUR-29', 'D0-EUR-33', 'D0-EUR-34', 'D0-EUR-35', 'D0-EUR-38', 'D0-EUR-39', 'D0-EUR-41', 'D0-EUR-45', 'D0-EUR-46', 'D0-EUR-47', 'D0-EUR-50', 'D0-EUR-51', 'D0-EUR-53', 'D0-EUR-57', 'D0-EUR-58', 'D0-EUR-59']}, {'id': 'd-chf', 'op': 'pay_batch', 'route': 'domestic', 'payments': ['D0-CHF-2', 'D0-CHF-8', 'D0-CHF-14', 'D0-CHF-20', 'D0-CHF-26', 'D0-CHF-32', 'D0-CHF-38', 'D0-CHF-44', 'D0-CHF-50', 'D0-CHF-56', 'D0-CHF-3', 'D0-CHF-9', 'D0-CHF-15', 'D0-CHF-21', 'D0-CHF-27', 'D0-CHF-33', 'D0-CHF-39', 'D0-CHF-45', 'D0-CHF-51', 'D0-CHF-57', 'D0-CHF-4', 'D0-CHF-10', 'D0-CHF-16', 'D0-CHF-22', 'D0-CHF-28', 'D0-CHF-34', 'D0-CHF-40', 'D0-CHF-46', 'D0-CHF-52', 'D0-CHF-58']}])
        self.assertTrue(wrapped)
        for bad in ('{"actions":[]}\n\n{"actions":[]}',
                    '{broken}\n\n{"actions":[]}',
                    '[1]\n\n{"actions":[]}',
                    '```python\npass\n```\n\n{"actions":[]}',
                    'No action document'):
            reply['content'][0]['text']=bad
            with self.assertRaises(ValueError):parse_response(reply)

    def test_checkpoint_ids_and_feedback(self):
        e=self.engine();e.advance(8)
        a=dict(id='a2',op='pay_batch',route='correspondent',payments=['D0-USD-0'])
        self.assertTrue(e.act(a)['ok'])
        state=copy.deepcopy((e.assets,e.pending,e.fees))
        self.assertTrue(e.act(a)['duplicate'])
        self.assertEqual(state,(e.assets,e.pending,e.fees))
        conflict=dict(a,payments=['D0-USD-4'])
        self.assertFalse(e.act(conflict)['ok'])
        self.assertEqual(state,(e.assets,e.pending,e.fees))
        e.advance(32)
        self.assertIn('conflicting action id',e.view()['recent_execution']['results'][-1]['error'])
        b=dict(a,payments=['D1-USD-0'])
        self.assertTrue(e.act(b)['ok'])
        e.advance(34)
        self.assertEqual(e.obligations['D1-USD-0']['status'],'paid')
        self.assertEqual(e.view()['recent_execution']['t'],32)
        self.assertEqual(e.view()['recent_execution']['results'][0]['accepted_count'],1)

    def test_overdue_is_explicit_and_not_executed(self):
        e=self.engine();e.advance(35)
        p=next(p for p in e.view()['payments'] if p['id']=='D1-USD-0')
        self.assertTrue(p['overdue'])
        before=copy.deepcopy((e.assets,e.pending,e.fees))
        result=e.act(dict(id='late',op='pay',payment=p['id'],route='correspondent'))
        self.assertFalse(result['ok'])
        self.assertEqual(before,(e.assets,e.pending,e.fees))
        self.assertEqual(e.view()['recent_execution']['results'][-1]['error'],'would miss deadline')

    def test_old_interface_recovery_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);dump(p/'manifest.json',dict(version='treasury-bank-11.0'))
            with self.assertRaisesRegex(ValueError,'interface version changed'):
                load_recovery(p,SimpleNamespace(),[],None)

    def test_recovery_replays_execution_feedback(self):
        e=self.engine();args=SimpleNamespace(days=2,start='2026-11-23',seed=42,model='test',
            max_output=16384,input_price=2,output_price=10,retry_uncertain=False)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            dump(p/'manifest.json',dict(vars(args),version=VERSION,policy='model',
                tape_sha256=digest(e.tape),prices=dict(input=2,output=10)))
            for t in (6,8):
                e.advance(t)
                actions=[dict(id='a1',op='pay',payment='D0-USD-1' if t==6 else 'D0-USD-0',
                              route='domestic' if t==6 else 'correspondent')]
                append(p/'api_journal.jsonl',dict(type='attempt',t=t,payload=dict(messages=[dict(content=json.dumps(e.view()))])))
                append(p/'api_journal.jsonl',dict(type='response',t=t,response=dict(stop_reason='end_turn',
                    content=[dict(type='text',text=json.dumps(dict(actions=actions)))])))
                for action in actions:self.assertTrue(e.act(action)['ok'])
            self.assertEqual(len(load_recovery(p,args,e.tape,e.start)),2)

    test_fenced_response_and_rejection=ResponseTests.test_fenced_response_and_rejection
    test_fenced_actions_with_commentary=ResponseTests.test_fenced_actions_with_commentary
    test_uncertain_cost_counts_against_budget=ResponseTests.test_uncertain_cost_counts_against_budget
    def test_bank_balance_and_managed_scope(self):
        self.assertEqual(sum(PROFILE['assets_chf'].values()),40_000_000_000)
        self.assertEqual(sum(PROFILE['funding_chf'].values()),40_000_000_000)
        e=self.engine();v=sum(D(e.values()[c])*D(str(e.market['fx'][c])) for c in CCY)/100
        self.assertLess(abs(v-2_000_000_000),1)
    def engine(self,scenario='bank'):
        dt=datetime(2026,11,23).date();return Engine(make_tape(2,dt,42,scenario),dt,'test')
    def test_same_prefix_independent_receipts(self):
        dt=datetime(2026,11,23).date();a=make_tape(2,dt,42);b=make_tape(30,dt,42)
        self.assertEqual(a,b[:2]);self.assertTrue(any(r['month_end'] for r in b))
        self.assertEqual(sum(p['category']=='customer_payment' for r in b for p in r['payments']),7200)
        self.assertNotEqual(sum(p['amount'] for p in a[0]['payments']),sum(r['amount'] for r in a[0]['receipts']))
    def test_guard_rejection_atomic(self):
        e=self.engine();e.advance(8);before=copy.deepcopy(e.assets)
        self.assertFalse(e.act(dict(id='r',op='recall',ccy='USD',amount=e.assets['corr']['USD']))['ok'])
        self.assertEqual(before,e.assets)
        self.assertFalse(e.act(dict(id='fx',op='fx',ccy='USD',dest='CHF',amount=e.local(30_000_000,'USD')))['ok'])
        self.assertEqual(before,e.assets)
    def test_redemption_required_and_sufficient(self):
        idle=self.engine('redemption_drill');idle.advance(15)
        self.assertEqual(metrics(idle,False)['missed'],1)
        e=self.engine('redemption_drill')
        for h in HOURS:
            e.advance(h);baseline(e,'conventional')
        self.assertEqual(metrics(e,True)['on_time'],1)
        self.assertGreater(metrics(e,True)['workflow_counts']['redeem'],0)
        self.assertEqual(e.blocks,0)
    def test_batch_cannot_duplicate_or_spend_pending(self):
        e=self.engine();e.advance(6)
        r=e.act(dict(id='batch',op='pay_batch',payments=['D0-CHF-0','D0-CHF-1'],route='domestic'))
        self.assertTrue(r['ok']);state=copy.deepcopy(e.assets)
        e.act(dict(id='batch',op='pay_batch',payments=['D0-CHF-0','D0-CHF-1'],route='domestic'))
        self.assertEqual(e.assets,state)
        self.assertFalse(e.act(dict(id='batch',op='pay_batch',payments=['D0-CHF-2'],route='domestic'))['ok'])
        self.assertEqual(e.assets,state)
    def test_two_day_accounting_and_baselines(self):
        for policy in ('conventional','hybrid','cash_only'):
            e=self.engine()
            for d in range(2):
                for h in HOURS:e.advance(d*24+h);baseline(e,policy)
            m=metrics(e,True)
            self.assertTrue(all(abs(v)<100 for v in m['mark_and_rounding_residual_cents'].values()))
            self.assertEqual(m['blocked_actions'],0)
            self.assertEqual(m['on_time'],483)
    def test_token_fund_redemption_to_core(self):
        e=self.engine();e.advance(6);n=e.local(1_000_000,'USD')
        self.assertTrue(e.act(dict(id='mint',op='mint',asset='td',ccy='USD',amount=n))['ok'])
        self.assertEqual(e.assets['td']['USD'],0);e.advance(7)
        self.assertTrue(e.act(dict(id='sub',op='subscribe',instrument='USD_tmmf',amount=n))['ok'])
        e.advance(9);u=e.units['USD_tmmf']
        self.assertTrue(e.act(dict(id='red',op='redeem',instrument='USD_tmmf',units=u))['ok'])
        self.assertFalse(e.act(dict(id='premature',op='burn',asset='td',ccy='USD',amount=n))['ok'])
        e.advance(11)
        self.assertTrue(e.act(dict(id='burn',op='burn',asset='td',ccy='USD',amount=n))['ok'])
        e.advance(12)
        self.assertEqual(metrics(e,False)['redeemed_subscribed_micro_units']['USD_tmmf'],u)
        self.assertTrue(all(v==0 for v in metrics(e,False)['mark_and_rounding_residual_cents'].values()))
    def test_saved_state_recovery(self):
        e=self.engine();args=SimpleNamespace(days=2,start='2026-11-23',seed=42,model='test',
            max_output=16384,input_price=2,output_price=10,retry_uncertain=True)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)
            dump(p/'manifest.json',dict(vars(args),version=VERSION,policy='model',tape_sha256=digest(e.tape),prices=dict(input=2,output=10)))
            for t in (6,8):
                e.advance(t)
                append(p/'api_journal.jsonl',dict(type='attempt',t=t,payload=dict(messages=[dict(content=json.dumps(e.view()))])))
                append(p/'api_journal.jsonl',dict(type='response',t=t,response=dict(stop_reason='end_turn',content=[dict(type='text',text='{"actions":[]}')])))
            e.advance(10)
            append(p/'api_journal.jsonl',dict(type='attempt',t=10,reservation_usd=.2,payload=dict(messages=[dict(content=json.dumps(e.view()))])))
            self.assertEqual(len(load_recovery(p,args,e.tape,e.start)),2)
            self.assertEqual(len(args.uncertain_attempts),1)


# Sustained study: standalone extension; legacy scenarios remain available.
LegacyEngine = Engine
legacy_make_tape = make_tape
legacy_baseline = baseline
legacy_metrics = metrics
legacy_protocol_for = protocol_for
SUSTAINED_POLICIES = ('cash_reserve','local_deposit','token_fund')


def sustained_profile():
    return dict(name='Synthetic USD treasury sleeve, four-week study',
                opening_core_usd=120_000_000,opening_funds_usd=0,
                core_floor_usd=25_000_000,month_end_floor_usd=30_000_000,
                scope='Single-currency operational portfolio, not bank-wide AUM or ALM',
                calendar='Weekdays are banking days; holidays deliberately excluded; fixed CET UTC+1')


def make_tape(days,start,seed,scenario='bank'):
    if scenario!='sustained_20bd':return legacy_make_tape(days,start,seed,scenario)
    if days not in (2,28) or start.weekday()!=0:
        raise ValueError('sustained_20bd requires a Monday start and --days 28 (or --days 2 for a prefix smoke test)')
    # Generate the complete calendar even for smoke tests: the first two days match.
    tape=[];rng=random.Random(seed)
    for d in range(28):
        dt=start+timedelta(days=d);business=dt.weekday()<5
        me=dt.day==calendar.monthrange(dt.year,dt.month)[1]
        payments=[];receipts=[]
        for j in range(60 if business else 4):
            hour=(9,11,13,15,19,23)[j%6] if business else (9,13,19,23)[j]
            payments.append(dict(id=f'S{d}-DOM-{j}',ccy='USD',amount=money(50_000*rng.uniform(.85,1.15)),
                earliest_send=d*24+hour-1,due=d*24+hour,routes=['domestic'],category='routine_payment'))
        for j in range(2):
            payments.append(dict(id=f'S{d}-X-{j}',ccy='USD',amount=money(500_000*rng.uniform(.85,1.15)),
                earliest_send=d*24+22,due=d*24+23,routes=['correspondent','tokenized_deposit','stablecoin'],
                category='after_hours_payment'))
        if dt.weekday()==1:
            payments.append(dict(id=f'S{d}-MORTGAGE',ccy='USD',amount=money(5_000_000),
                earliest_send=d*24+10,due=d*24+11,routes=['domestic'],category='mortgage_batch'))
        # Large fiat obligations force material investments to be unwound.
        if d in (9,23):
            payments.append(dict(id=f'S{d}-WITHDRAWAL',ccy='USD',amount=money(70_000_000),
                earliest_send=d*24+22,due=d*24+23,routes=['domestic'],category='large_withdrawal'))
        if me:
            payments.append(dict(id=f'S{d}-MONTHEND',ccy='USD',amount=money(12_000_000),
                earliest_send=d*24+16,due=d*24+19,routes=['domestic'],category='month_end_settlement'))
        base=4_000_000 if business else 1_200_000
        for h in (12,18):receipts.append(dict(t=d*24+h,ccy='USD',amount=money(base*.5*rng.uniform(.9,1.1))))
        # Scheduled replenishments are forecasts until settled, not spendable cash.
        prev=dt-timedelta(days=1)
        if prev.weekday()==1:receipts.append(dict(t=d*24+12,ccy='USD',amount=money(5_000_000)))
        if d in (10,24):receipts.append(dict(t=d*24+12,ccy='USD',amount=money(70_000_000)))
        if d>0 and prev.day==calendar.monthrange(prev.year,prev.month)[1]:
            receipts.append(dict(t=d*24+12,ccy='USD',amount=money(12_000_000)))
        rates={c:v for c,v in zip(CCY,(420,390,240,90))}
        rates['USD']=420+rng.randint(-5,5)-(25 if d>=7 else 0)+(15 if d>=20 else 0)
        tape.append(dict(day=d,date=dt.isoformat(),month_end=me,rates=rates,
            fx=dict(USD=.88,GBP=1.12,EUR=.94,CHF=1),payments=payments,receipts=receipts,
            scenario=scenario,collateral_release={c:money(25_000_000) if c=='USD' else 0 for c in CCY},
            events=[dict(hour=h,kind=k) for h,k in zip(HOURS,('disclose_day','desk_open','mortgage_review',
                'receipts','funding_review','preclose_review','desk_close','collateral_release','overnight_review'))]))
    if not any(r['month_end'] for r in tape):raise ValueError('select a Monday start whose four-week window includes month-end')
    return tape[:days]


SUSTAINED_RULES='''SUSTAINED SYNTHETIC USD TREASURY STUDY
Four weeks including 20 weekdays and 8 weekend days. No holidays; fixed CET UTC+1.
A two-day run is a smoke-test prefix, not the full study. Nine decisions daily:
06,08,10,12,14,16,18,22,23. Settlements and interest advance hourly between decisions.
Opening core cash USD120m, no inherited funds, no correspondent balance.
USD instruments only; no FX or non-USD operations. Core floor USD25m, increased
at month-end midnight to USD30m and restored next midnight. Plan using the calendar.
Daily obligations and receipt forecasts appear at06. Future rates and future
undisclosed obligations are not available. Only settled receipts may be spent.
Payments must respect earliest_send AND settle by due. Domestic is 24/7; other
routes follow their quotes and recipient eligibility. The desk operates weekdays
08:00-18:00; correspondent/funding orders are accepted through17:00 (one-hour buffer).
Actual per-instrument windows remain authoritative; do not assume tokens remove cutoffs.
Subscriptions, redemptions, mint/burn and payments settle asynchronously. Pending assets
cannot fund another action. A tokenized MMF subscription requires settled td, not core.
USD25m collateral becomes available at22 each day, remains available until updated,
and can support optional borrowing with20% haircut (30% at month-end). Borrowing
settles in1h, accrues the displayed borrowing rate hourly, and must be repaid from core.
Collateral is a synthetic fixed eligibility limit, NOT newly created cash each day.
Keep obligations on time and floors intact FIRST; seek net interest after fees and
financing SECOND. Investment is optional; never invest merely to demonstrate a cycle.
No terminal liquidation is required. Outstanding funds, pending transfers and loans
are reported separately; they are not automatically operational failures.
All rates, liquidity windows, routes and collateral terms are synthetic assumptions.
This is a single-currency portfolio diagnostic, not a bank solvency or regulatory model.
'''


def protocol_for(scenario):
    if scenario!='sustained_20bd':return legacy_protocol_for(scenario)
    mechanics=GUIDE.split('ASSETS / SETTLEMENT / CONTROLS\n',1)[1].split('Collateral is explicitly',1)[0]
    contract=GUIDE.split('ACTION CONTRACT\n',1)[1]
    return SUSTAINED_RULES+'\n'+mechanics+'\nACTION CONTRACT\n'+contract+'\n'+YIELD_TERMS


class Engine(LegacyEngine):
    def __init__(self,tape,start,policy):
        if tape[0].get('scenario')!='sustained_20bd':
            super().__init__(tape,start,policy);return
        SettlementEngine.__init__(self,tape,start,policy)
        self.scenario='sustained_20bd'
        self.assets={a:{c:0 for c in CCY} for a in ('core','td','stable','corr')}
        self.assets['core']['USD']=money(120_000_000)
        self.units={k:0 for k in self.cat}
        for i in self.cat.values():i['eligible']=i['ccy']=='USD'
        self.opening=self.values();self.fx_open=sum(D(self.opening[c])*D(str(self.market['fx'][c])) for c in CCY)
        self.opening_units=dict(self.units);self.batch_requests={};self.request_records={}
        self.feedback_t=None;self.feedback=[]
    def floor(self,c):
        if getattr(self,'scenario',None)!='sustained_20bd':return super().floor(c)
        dt=self.start+timedelta(days=self.t//24)
        return money(30_000_000 if dt.day==calendar.monthrange(dt.year,dt.month)[1] else 25_000_000) if c=='USD' else 0
    def corr_floor(self,c):
        return 0 if self.scenario=='sustained_20bd' else super().corr_floor(c)
    def _action(self,a):
        if self.scenario=='sustained_20bd':
            if a.get('ccy','USD')!='USD' or a['op']=='fx':raise ValueError('USD-only study')
            if a['op']=='pay' and self.t<self.obligations[a['payment']].get('earliest_send',0):
                raise ValueError('payment release time not reached')
        return super()._action(a)
    def view(self):
        v=super().view()
        if self.scenario=='sustained_20bd':
            v.update(bank_profile=sustained_profile(),scenario_rules=SUSTAINED_RULES,
                     cumulative_fx_principal={c:0 for c in CCY},fx_principal_limits={c:0 for c in CCY})
        return v


def baseline(e,policy):
    if e.scenario!='sustained_20bd':return legacy_baseline(e,policy)
    actions=[];h=e.t%24
    def do(op,**kw):
        a=dict(id=f'{policy}-{e.t}-{len(actions)}',op=op,**kw)
        result=e.act(a);actions.append(dict(action=a,result=result));return result
    # All policies share payment access; only their investment schedule differs.
    if h==6:
        short=max(0,money(2_000_000)-e.assets['td']['USD'])
        if short:do('mint',ccy='USD',asset='td',amount=short)
        e.reference_investment_amount=max(0,min(money(30_000_000),e.assets['core']['USD']-e.floor('USD')-money(10_000_000)))
        if policy=='token_fund' and e.reference_investment_amount:do('mint',ccy='USD',asset='td',amount=e.reference_investment_amount)
    if h==8:
        if policy=='token_fund' and e.reference_investment_amount:do('subscribe',instrument='USD_tmmf',amount=e.reference_investment_amount)
        if policy=='local_deposit' and e.business(e.t) and e.reference_investment_amount:do('subscribe',instrument='USD_local',amount=e.reference_investment_amount)
    if h==16:
        k='USD_tmmf' if policy=='token_fund' else 'USD_local'
        if policy!='cash_reserve' and e.units[k]:do('redeem',instrument=k,units=e.units[k])
    if h==18 and policy=='token_fund' and e.reference_investment_amount:do('burn',ccy='USD',asset='td',amount=e.reference_investment_amount)
    due=[p for p in e.obligations.values() if p['status']=='open' and p.get('earliest_send',0)<=e.t and p['due']>e.t]
    for route in ('domestic','tokenized_deposit'):
        ids=[p['id'] for p in due if route in p['routes']]
        if ids:do('pay_batch',payments=ids,route=route)
    return actions


def metrics(e,complete):
    r=legacy_metrics(e,complete)
    if e.scenario!='sustained_20bd':return r
    r.update(bank_profile=sustained_profile(),scope='Single-USD sustained portfolio; not bank-wide profit or production reliability',
        business_days=sum(datetime.fromisoformat(x['date']).weekday()<5 for x in e.tape),
        weekend_days=sum(datetime.fromisoformat(x['date']).weekday()>=5 for x in e.tape),
        net_interest_less_costs_usd=r['net_interest_less_costs_cents']['USD']/100,
        ending_tokenized_fund_value_usd=e.holding('USD_tmmf')/100,
        ending_conventional_fund_value_usd=sum(e.holding(k) for k in e.cat if k!='USD_tmmf')/100,
        interpretation='Repeated dependent decisions on one synthetic event tape; no optimality or independent-scenario count.')
    r['daily_payment_results']=[dict(day=d,date=row['date'],due=sum(p['due']//24==d for p in e.obligations.values()),
        on_time=sum(p['due']//24==d and p['status']=='paid' and p['settled_at']<=p['due'] for p in e.obligations.values())) for d,row in enumerate(e.tape) if d<=e.t//24]
    r['blocked_reasons']=dict(__import__('collections').Counter(x['error'] for x in e.log if x['kind']=='blocked'))
    r['workflow_counts']=dict(__import__('collections').Counter(x['action']['op'] for x in e.log if x['kind']=='accepted'))
    return r


LegacyTests=Tests
class Tests(LegacyTests):
    def test_sustained_calendar_prefix_and_visibility(self):
        dt=datetime(2026,11,23).date();t=make_tape(28,dt,42,'sustained_20bd')
        self.assertEqual(make_tape(2,dt,42,'sustained_20bd'),t[:2])
        self.assertEqual(sum(datetime.fromisoformat(r['date']).weekday()<5 for r in t),20)
        self.assertEqual(sum(r['month_end'] for r in t),1)
        e=Engine(t,dt,'test');e.advance(6)
        self.assertTrue(all(p['due']<24 for p in e.view()['payments']))
        self.assertEqual(e.view()['market']['rates'],t[0]['rates'])
        self.assertEqual(e.collateral['USD'],0)
        e.advance(22);self.assertEqual(e.collateral['USD'],money(25_000_000))
    def test_sustained_references_full_month(self):
        dt=datetime(2026,11,23).date();t=make_tape(28,dt,42,'sustained_20bd')
        for policy in SUSTAINED_POLICIES:
            e=Engine(t,dt,policy)
            for d in range(28):
                for h in HOURS:e.advance(d*24+h);baseline(e,policy)
            r=metrics(e,True)
            self.assertEqual(r['on_time'],sum(len(x['payments']) for x in t),policy)
            self.assertEqual(r['blocked_actions'],0,policy)
            self.assertEqual(r['floor_breach_hours'],0,policy)
            self.assertTrue(all(v==0 for v in r['mark_and_rounding_residual_cents'].values()))
    def test_sustained_recovery_preserves_state(self):
        dt=datetime(2026,11,23).date();t=make_tape(28,dt,42,'sustained_20bd');e=Engine(t,dt,'model')
        args=SimpleNamespace(days=28,start='2026-11-23',seed=42,model='offline',max_output=16384,
            input_price=2,output_price=10,retry_uncertain=False)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);dump(p/'manifest.json',dict(vars(args),version=VERSION,policy='model',tape_sha256=digest(t),prices=dict(input=2,output=10)))
            for hour in (6,8):
                e.advance(hour);view=copy.deepcopy(e.view());results=baseline(e,'token_fund')
                append(p/'api_journal.jsonl',dict(type='attempt',t=hour,payload=dict(messages=[dict(content=json.dumps(view))])))
                append(p/'api_journal.jsonl',dict(type='response',t=hour,response=dict(stop_reason='end_turn',content=[dict(type='text',text=json.dumps(dict(actions=[r['action'] for r in results])))])))
            self.assertEqual(len(load_recovery(p,args,t,dt)),2)
    def test_sustained_month_end_floor_is_calendar_based(self):
        dt=datetime(2026,11,23).date();e=Engine(make_tape(28,dt,42,'sustained_20bd'),dt,'test')
        e.advance(167);self.assertEqual(e.floor('USD'),money(25_000_000))
        e.advance(168);self.assertEqual(e.floor('USD'),money(30_000_000))
        e.advance(192);self.assertEqual(e.floor('USD'),money(25_000_000))

    def test_sustained_release_and_collateral(self):
        dt=datetime(2026,11,23).date();e=Engine(make_tape(28,dt,42,'sustained_20bd'),dt,'test');e.advance(6)
        self.assertFalse(e.act(dict(id='early',op='pay',payment='S0-DOM-0',route='domestic'))['ok'])
        self.assertFalse(e.act(dict(id='loan',op='borrow',ccy='USD',amount=money(1_000_000)))['ok'])
        e.advance(22);self.assertTrue(e.act(dict(id='loan2',op='borrow',ccy='USD',amount=money(1_000_000)))['ok'])
        self.assertEqual(e.loan['USD'],0);e.advance(23);self.assertGreater(e.loan['USD'],0)

def main():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--scenario',choices=['sustained_20bd','bank','redemption_drill',*ISOLATED],default='sustained_20bd');ap.add_argument('--days',type=int,default=28);ap.add_argument('--start',default='2026-11-23')
    ap.add_argument('--seed',type=int,default=42);ap.add_argument('--policy',choices=['all','conventional','hybrid','cash_only','direct_tokens','reference','hold_cash','model',*SUSTAINED_POLICIES],default='all')
    ap.add_argument('--outdir',type=Path);ap.add_argument('--prepare',action='store_true');ap.add_argument('--guide',action='store_true')
    ap.add_argument('--self-test',action='store_true');ap.add_argument('--live',action='store_true');ap.add_argument('--model')
    ap.add_argument('--resume',type=Path,help='recover saved responses, then continue in a NEW results folder')
    ap.add_argument('--retry-uncertain',action='store_true',help='replace a terminal unanswered generation; retain possible billed cost; simulation only')
    ap.add_argument('--max-calls',type=int,default=252);ap.add_argument('--max-output',type=int,default=16384)
    ap.add_argument('--max-usd',type=float);ap.add_argument('--input-price',type=float);ap.add_argument('--output-price',type=float)
    ap.add_argument('--yes',action='store_true');args=ap.parse_args()
    if args.guide:print(protocol_for(args.scenario));return
    if args.self_test:
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests)
        sys.exit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
    if not 1<=args.days<=366:ap.error('days must be 1..366')
    start=datetime.strptime(args.start,'%Y-%m-%d').date()
    try:tape=make_tape(args.days,start,args.seed,args.scenario)
    except ValueError as exc:ap.error(str(exc))
    args.replay={};args.uncertain_attempts=[]
    if args.policy=='direct_tokens' and args.scenario not in ISOLATED:ap.error('direct_tokens is an after-hours diagnostic baseline only')
    if args.scenario in CYCLE_CASES and args.policy not in ('all','model','reference','hold_cash'):ap.error('cycle cases use --policy all, reference, hold_cash or model')
    if args.policy in ('reference','hold_cash') and args.scenario not in CYCLE_CASES:ap.error('reference/hold_cash require a cycle scenario')
    if args.scenario=='sustained_20bd' and args.policy not in ('all','model',*SUSTAINED_POLICIES):ap.error('sustained scenario requires all, model, cash_reserve, local_deposit or token_fund')
    if args.policy in SUSTAINED_POLICIES and args.scenario!='sustained_20bd':ap.error('sustained reference policy requires sustained_20bd')
    if args.live!=(args.policy=='model'):ap.error('--policy model and --live must be used together')
    if args.resume and not args.live:ap.error('--resume requires --policy model --live')
    if args.retry_uncertain and not args.resume:ap.error('--retry-uncertain requires --resume')
    if args.live:
        if not args.model or not os.environ.get('ANTHROPIC_API_KEY'):ap.error('provide --model and export ANTHROPIC_API_KEY')
        if any(x is None or x<=0 for x in (args.max_usd,args.input_price,args.output_price)):ap.error('provide positive --max-usd, --input-price and --output-price')
        if args.max_calls<args.days*len(HOURS):ap.error(f'full run needs {args.days*len(HOURS)} calls; raise --max-calls')
        if args.resume:
            try:args.replay=load_recovery(args.resume,args,tape,start)
            except Exception as exc:ap.error('Recovery refused before any API call: '+str(exc))
        remaining=args.days*len(HOURS)-len(args.replay)
        if args.max_calls<args.days*len(HOURS)+len(args.uncertain_attempts):
            ap.error(f'completion including historical uncertain calls requires --max-calls {args.days*len(HOURS)+len(args.uncertain_attempts)}')
        if args.uncertain_attempts:
            print(f"Retaining {len(args.uncertain_attempts)} uncertain attempt(s), ${sum(r['reservation_usd'] for r in args.uncertain_attempts):.5f} reserved. No action from an unanswered response was executed.")
        if not args.yes and input(f'{remaining} new paid calls; {len(args.replay)} saved responses reused; cumulative reservation limit ${args.max_usd:.2f}. Proceed? [y/N] ').lower()!='y':return
    folder=args.outdir or Path('treasury_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
    folder.mkdir(parents=True,exist_ok=False)
    dump(folder/'bank_profile.json',sustained_profile() if args.scenario=='sustained_20bd' else after_hours_profile(args.scenario) if args.scenario in ISOLATED else PROFILE);dump(folder/'tape.json',tape);dump(folder/'instruments.json',explicit_instrument_terms(catalogue()))
    (folder/'protocol.txt').write_text(protocol_for(args.scenario));(folder/'source.py').write_bytes(Path(__file__).read_bytes())
    manifest=dict(version=VERSION,interface_condition=INTERFACE_CONDITION,scenario=args.scenario,days=args.days,start=args.start,seed=args.seed,policy=args.policy,model=args.model,
                  max_output=args.max_output,planned_calls=args.days*len(HOURS) if args.live else 0,
                  settings='thinking/effort omitted; provider defaults',parser_revision='identical-inline-document-v3',tape_sha256=digest(tape),
                  source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  prices=dict(input=args.input_price,output=args.output_price),max_usd=args.max_usd,
                  recovered_from=str(args.resume.resolve()) if args.resume else None,
                  recovered_parser_revision=json.loads((args.resume/'manifest.json').read_text()).get('parser_revision') if args.resume else None,
                  reused_checkpoints=sorted(args.replay),
                  uncertain_attempt_count=len(args.uncertain_attempts),retry_uncertain=args.retry_uncertain,
                  assumptions='synthetic, unreviewed; no live market feeds or real transactions')
    dump(folder/'manifest.json',manifest)
    if args.prepare:print(f'Prepared {args.days} days, {sum(len(r['payments']) for r in tape)} payments. {folder.resolve()}');return
    policies=['conventional','hybrid','cash_only'] if args.policy=='all' else [args.policy]
    if args.policy=='all' and args.scenario in AFTER_HOURS:policies.append('direct_tokens')
    if args.policy=='all' and args.scenario in CYCLE_CASES:policies=['reference','hold_cash']
    if args.policy=='all' and args.scenario=='sustained_20bd':policies=list(SUSTAINED_POLICIES)
    historical_usd=sum((s['response']['usage']['input_tokens']*args.input_price+
                       s['response']['usage']['output_tokens']*args.output_price)/1e6 for s in args.replay.values())
    for row in args.uncertain_attempts:append(folder/'api_journal.jsonl',row)
    prior_calls=len(args.replay)+len(args.uncertain_attempts)
    summaries=[];usage=dict(calls=prior_calls,usd=historical_usd,
                           uncertain_usd=sum(r['reservation_usd'] for r in args.uncertain_attempts),
                           prior_calls=prior_calls,prior_usd=historical_usd,reused_responses=0,format_wrappers=0)
    for policy in policies:
        e=Engine(tape,start,policy);complete=True
        for day in range(args.days):
            for hour in HOURS:
                e.advance(day*24+hour);before=copy.deepcopy(e.view())
                if args.live:
                    try:
                        proposal=request_model(before,args,folder,usage)
                        results=[dict(action=a,result=e.act(a)) for a in proposal]
                    except Exception as exc:
                        append(folder/'api_journal.jsonl',dict(type='halt',t=e.t,error=type(exc).__name__,message=str(exc)))
                        print('Stopped:',type(exc).__name__,str(exc));complete=False;break
                    time.sleep(1)
                else:results=baseline(e,policy)
                append(folder/f'decisions_{policy}.jsonl',dict(t=e.t,before=before,actions=results))
                if hour==23:
                    e.daily[-1].update(core=dict(e.assets['core']),correspondent=dict(e.assets['corr']),
                        values=e.values(),income=dict(e.income),fees=dict(e.fees),financing=dict(e.financing))
            print(f'{policy}: day {day+1}/{args.days}',flush=True)
            if not complete:break
        # End at final day23:00, so the last checkpoint may submit next-day operations.
        summary=metrics(e,complete);summaries.append(summary)
        for row in e.log:append(folder/f'ledger_{policy}.jsonl',row)
        with open(folder/f'daily_{policy}.csv','w',newline='') as f:
            w=csv.writer(f);w.writerow(['day','date','currency','core','correspondent','net_assets','income_cumulative','fees_cumulative','financing_cumulative'])
            for row in e.daily:
                for c in CCY:w.writerow([row['day'],row['date'],c,*[row[k][c]/100 for k in ['core','correspondent','values','income','fees','financing']]])
    dump(folder/'summary.json',dict(results=summaries,usage=usage))
    lines=['SYNTHETIC TREASURY LAB v14 -- '+('LIVE MODEL' if args.live else 'DETERMINISTIC BASELINES ONLY'),
           'policy | on time / due | missed | blocked | run complete']
    for s in summaries:
        lines.append(f"{s['policy']} | {s['on_time']}/{s['payments_due']} | {s['missed']} | {s['blocked_actions']} | {s['run_complete']}")
        lines.append(f"  Settled total: {s['paid_total']}; paid early, not yet due: {s['paid_early_not_yet_due']}")
    if args.live:lines.append(f"Calls: {usage['calls']-usage['prior_calls']} new; {usage['reused_responses']} reused. JSON wrappers: {usage['format_wrappers']}. Logged cumulative cost: ${usage['usd']:.4f}")
    if args.live:lines.append(f"Additional uncertain-call reservation: ${usage['uncertain_usd']:.5f}; not assumed free or successfully answered.")
    if args.live:lines.append(f"Responses containing tool-like text: {usage.get('tool_like_text_responses',0)}; retained as format deviations, never executed as tools.")
    if args.scenario=='sustained_20bd':
        lines += ['SUSTAINED USD STUDY: holidays excluded; repeated decisions on one tape, not independent scenarios.',
                  *[f"{r['policy']}: net income USD {r['net_interest_less_costs_usd']:,.2f}; floor-breach hours {r['floor_breach_hours']}; blocked reasons {r['blocked_reasons']}" for r in summaries]]
    elif args.scenario in CYCLE_CASES:
        lines += [f'ISOLATED REDEMPTION DIAGNOSTIC: {args.scenario}; USD120m total opening assets, USD25m core floor.',
                  'Same USD94.9m obligations; opening cash/fund allocation differs. Reference is feasible, not optimal.',
                  'hold_cash deliberately does not redeem inherited funds; negative control in required_redemption.',
                  *[f"{r['policy']}: net income USD {r['net_interest_less_costs_usd']:,.2f}; ending tokenized fund USD {r['ending_tokenized_fund_value_usd']:,.2f}; coverage {r['coverage']}" for r in summaries]]
    elif args.scenario in AFTER_HOURS:
        lines += ['ISOLATED AFTER-HOURS DIAGNOSTIC: USD120m sleeve; not the CHF40bn bank.',
                  'Conventional-only cannot settle AH-20M in after_hours; after_hours_control adds domestic eligibility.',
                  *[f"{r['policy']}: net interest less costs USD {r['net_interest_less_costs_usd']:,.2f}; coverage {r['coverage']}" for r in summaries]]
    lines+=['Inherited vs newly subscribed fund redemptions and workflow counts are in summary.json.',
            'Opening bank profile is calibration; bank-wide funding/liability changes are outside scope.',
            'Income, fees, funding and marked holdings are separate in summary.json.',
            'No optimality or production reliability claim. Pending assets are not cash.',f'Files: {folder.resolve()}']
    (folder/'summary.txt').write_text('\n'.join(lines)+'\n');print('\n'.join(lines))

if __name__=='__main__':main()
