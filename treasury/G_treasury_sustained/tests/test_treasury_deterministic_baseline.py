import unittest
from treasury_deterministic_baseline import decide, schedule
class BaselineTests(unittest.TestCase):
 def p(self, id, amount, due=9, earliest=8, routes=('domestic',)):
  return dict(id=id,amount=amount,due=due,earliest_send=earliest,routes=list(routes))
 def test_pays_at_earliest_and_deadline_order(self):
  obs=dict(t=8,core_cents=1000,floor_cents=200,payments=[self.p('b',100,12),self.p('a',200,9)])
  r=decide(obs)
  self.assertEqual([a['payment'] for a in r['actions']],['a','b'])
  self.assertEqual(r['projected_core_cents_if_all_accepted'],700)
 def test_preserves_floor(self):
  obs=dict(t=8,core_cents=300,floor_cents=200,payments=[self.p('a',101)])
  r=decide(obs)
  self.assertEqual(len(r['actions']),0)
  self.assertEqual(r['unfunded'][0]['shortfall_cents'],1)
 def test_no_unconfirmed_route(self):
  obs=dict(t=22,core_cents=1000,floor_cents=0,payments=[self.p('x',100,23,22,('stablecoin',))])
  self.assertEqual(decide(obs)['unfunded'][0]['reason'],'no_confirmed_route')
 def test_deterministic(self):
  o=dict(t=8,core_cents=1000,floor_cents=0,payments=[self.p('z',100)])
  self.assertEqual(decide(o),decide(o))
 def test_borrow_requires_explicit_authority(self):
  o=dict(t=8,core_cents=300,floor_cents=200,payments=[self.p('z',200)],available_funding_cents=100,allowed_ops=['pay','borrow'])
  self.assertEqual(len(decide(o)['actions']),0)
  self.assertEqual([a['op'] for a in decide(o,enable_borrow=True)['actions']],['borrow','pay'])
if __name__=='__main__':unittest.main()
