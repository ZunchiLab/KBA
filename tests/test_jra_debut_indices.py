import unittest,sys,copy,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from jra_debut_indices import apply_debut_indices,audit_debut,normalized,ROLES
from jra_role_indices import apply_indices,audit_indices
from test_jra_role_indices import race,ASOF

def sample(i=1,finish=1,day='2026-10-20',**kw):
    source=dict(url='https://jra.jp/results/'+str(i),retrieved_at=day+'T18:00:00+09:00',raw_sha256='a'*64)
    return dict(observation_id='old-'+str(i),race_uid='race-'+str(i),date=day,horse_id='oldhorse-'+str(i),name='旧馬'+str(i),sire='父：テスト',trainer='厩舎(美浦)',jockey='騎手',surface='turf',distance_m=1600,field=12,finish=finish,official_confirmed=True,rows_complete=True,card_source=source,result_source=source,**kw)

def debut():
    r=race();r.update(class_text='新馬',source=dict(url='https://jra.jp/card',retrieved_at=ASOF,raw_sha256='b'*64))
    for h in r['horses']:h.update(sire='テスト' if h['number']==1 else '他父',trainer='厩舎(美浦)' if h['number']==1 else '別厩舎',jockey='騎手' if h['number']==1 else '別騎手',past=[])
    return r

class DebutTests(unittest.TestCase):
    def calculate(self,r=None,obs=None):return apply_indices(r or debut(),as_of=ASOF,computed_at=ASOF,debut_observations=obs if obs is not None else [sample()])
    def test_numeric_reference_from_real_associations_preserves_originals(self):
        r=debut();before=copy.deepcopy(r);out=self.calculate(r)
        self.assertEqual(r,before);self.assertEqual(out['bet_plans'],before['bet_plans'])
        self.assertEqual(audit_indices(out,ASOF),[])
        d=out['horses'][0]['role_indices'];self.assertFalse(d['probability']);self.assertEqual(d['matched_starters'],1)
        self.assertEqual(d['training_status'],'未採点');self.assertTrue(all(0<d[k]['value']<100 for k in ROLES))
    def test_multiple_associations_and_duplicate_sample_count_once(self):
        d=self.calculate(obs=[sample(),sample()])['horses'][0]['role_indices']
        self.assertEqual(len(d['components']),1);self.assertEqual(d['components'][0]['association_weight'],1)
        self.assertEqual(len(d['components'][0]['matched_features']),3)
    def test_unknown_has_explicit_neutral_starting_point_not_zero_or_market_copy(self):
        r=debut();r['horses'][1]['market']={'win':1.1}
        d=self.calculate(r)['horses'][1]['role_indices'];self.assertEqual(d['matched_starters'],0)
        self.assertEqual([d[k]['value'] for k in ROLES],[50]*4);self.assertIn('平均能力を確認した意味ではなく',d['reason'])
    def test_no_sample_anywhere_does_not_create_order_differences(self):
        out=self.calculate(obs=[])
        self.assertTrue(all(h['role_indices'][k]['value']==50 for h in out['horses'] for k in ROLES))
    def test_current_future_late_sources_different_surface_and_unconfirmed_omitted(self):
        for changes in [dict(date='2026-11-01'),dict(date='2026-11-02'),dict(surface='dirt'),dict(official_confirmed=False),dict(result_source=dict(url='https://jra.jp',retrieved_at='2026-11-01T09:00:00+09:00',raw_sha256='c'*64))]:
            x=sample();x.update(changes);d=self.calculate(obs=[x])['horses'][0]['role_indices'];self.assertEqual(d['matched_starters'],0);self.assertTrue(d['cohort_omitted'])
    def test_own_historical_start_must_stop_claim_of_debut(self):
        r=debut();r['horses'][0]['horse_id']='oldhorse-1'
        with self.assertRaises(ValueError):self.calculate(r)
    def test_known_bad_performances_not_filtered_away(self):
        d=self.calculate(obs=[sample(1,1),sample(2,12)])['horses'][0]['role_indices'];self.assertEqual(d['matched_starters'],2)
        self.assertEqual({c['finish'] for c in d['components']},{1,12})
    def test_jockey_weight_and_spaces_normalized_without_discarding_name(self):
        self.assertEqual(normalized('△石神 深道'),normalized('石神深道'));self.assertNotEqual(normalized('田中 勝春'),normalized('田中 博康'))
    def test_distinct_roles_do_not_copy_same_reference(self):
        r=debut();r['horses'][1].update(sire='父B',trainer='厩舎B',jockey='騎手B')
        b=sample(2,2);b.update(sire='父B',trainer='厩舎B',jockey='騎手B')
        out=self.calculate(r,obs=[sample(1,1),b]);a,b=[h['role_indices'] for h in out['horses'][:2]]
        self.assertGreater(a['first']['value'],b['first']['value']);self.assertGreater(b['second']['value'],a['second']['value'])
    def test_gate_rejects_post_event_or_unsupported_components(self):
        out=self.calculate();d=out['horses'][0]['role_indices'];d['computed_at']='2026-11-01T12:00:00+09:00'
        self.assertTrue(audit_debut(out['horses'][0],out,ASOF));d['computed_at']=ASOF
        d['components'][0]['sire']='違う父';self.assertTrue(audit_debut(out['horses'][0],out,ASOF))
    def test_withdrawal_is_not_assigned_neutral_score(self):
        r=debut();r['horses'][0]['status_at_snapshot']='withdrawn';d=self.calculate(r)['horses'][0]['role_indices']
        self.assertEqual(d['method'],'not_applicable');self.assertIsNone(d['first']['value'])
    def test_new_forecast_cannot_skip_debut_review_or_score_invalid_distance(self):
        r=debut();out=apply_indices(r,as_of=ASOF,computed_at=ASOF)
        self.assertIn('debut_reference_review_missing',[x[0] for x in audit_indices(out,ASOF)])
        for v in [math.nan,math.inf,True,-1]:
            x=sample();x['distance_m']=v;d=self.calculate(obs=[x])['horses'][0]['role_indices']
            self.assertEqual(d['matched_starters'],0)

if __name__=='__main__':unittest.main()
