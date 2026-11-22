"""Measure frozen purchase orders against official placings and combinations."""
import json
from hashlib import sha256
from pathlib import Path
from jra_rank_coverage import ordered_horses


def field_limits(size, *, legacy=False):
    """Inclusive partner and coverage endpoints in the forecast order."""
    partner, cover = ((4,7) if size>=16 else (4,6) if size>=13 else
                      (3,5) if size>=10 else (3,4))
    return min(size,partner if legacy else 4),min(size,cover)


def role_positions(horses, role):
    """Competition ranks for displayed values. Missing observations have no position."""
    values = {}
    for h in horses:
        index = h.get('role_indices', {})
        value = index.get(role, {}).get('value')
        if h.get('status_at_snapshot') in ('withdrawn','excluded') or (
                index.get('method') == 'debut_cohort_reference' and not index.get('matched_starters')):
            value = None
        values[h['number']] = value
    return {n:1+sum(v is not None and v > value for v in values.values())
            if value is not None else None for n,value in values.items()}


def order_errors(race):
    active = sorted((h for h in race['horses'] if h.get('status_at_snapshot') not in ('withdrawn','excluded')),
                    key=lambda h:h.get('rank') or 999)
    review = race.get('analysis',{}).get('purchase_order',{})
    if [h.get('rank') for h in active] != list(range(1,len(active)+1)):
        return ['印順位の欠落または重複']
    ranks = [h['number'] for h in active]
    if review.get('first_seven') != ranks[:7]:
        return ['印順と保存した候補順が不一致']
    main = [p for p in race.get('bet_plans',[]) if p.get('selected_for_example')]
    if main and (not ranks or '◎' not in active[0].get('mark','')):
        return ['本線の1番手の印が◎と一致しない']
    partner,cover=field_limits(len(active),legacy=review.get('policy')!='podium-first')
    if 'partner_end' in review and (review['partner_end'],review.get('cover_end'))!=(partner,cover):
        return ['頭数と候補範囲が不一致']
    places = {k:role_positions(active,k) for k in ('top2','top3')}
    errors = []
    for h in active:
        n=h['number']; row=h.get('purchase_order',{})
        if row.get('rank')!=h['rank'] or any(k not in row or row[k]!=places[k][n] for k in places):
            errors.append(f'{n}番の印順・役割順位が元データと不一致')
        if row.get('disagreement') and not row.get('reason'):
            errors.append(f'{n}番の実績上位と印順の違いに理由がない')
    for p in main:
        for t in p['tickets']:
            picked=set(t['numbers'])
            if p['kind']=='quinella':
                ok=len(picked)==2 and picked<=set(ranks[:partner]) and bool(picked.intersection(ranks[:2]))
            elif p['kind']=='wide':
                ok=len(picked)==2 and ranks[0] in picked and picked<=set(ranks[:partner])
            elif p['kind']=='trio':
                ok=len(picked)==3 and ranks[0] in picked and bool(picked.intersection(ranks[1:partner])) and picked<=set(ranks[:cover])
            else:
                ok=False
            if not ok:
                errors.append('本線が印順の指定フォーメーションから外れている')
    return errors


def evaluate(order, result, partner_end=4, cover_end=7):
    ranks = {h['number']: h['finish'] for h in result['rows'] if isinstance(h['finish'], int)}
    placed = {n for n, finish in ranks.items() if finish <= 3}
    if len(order) != len(set(order)) or len(placed) < 3 or not placed <= set(order):
        raise ValueError('馬番・確定着順の照合が必要')
    first = ranks.get(order[0], 999)
    partner = bool(placed.intersection(order[1:partner_end]))
    cover = placed <= set(order[:cover_end])
    q = {tuple(sorted((a,b))) for a in order[:2] for b in order[:partner_end] if a != b}
    trio = {tuple(sorted((order[0],a,b))) for a in order[1:partner_end] for b in order[1:cover_end] if a != b}
    def wins(kind):
        return {tuple(sorted(p['numbers'])) for p in result['payouts'] if p['kind'] == kind}
    return dict(axis_top2=first <= 2, axis_top3=first <= 3, partner_2_4=partner,
                axis_and_partner=first <= 3 and partner, cover_7=cover, joint=first <= 3 and partner and cover,
                quinella=bool(q & wins('quinella')), trio=bool(trio & wins('trio')))


def audit_dates(repo, dates):
    rows = []
    for date in dates:
        path = repo/'predictions'/('report_'+date.replace('-','')+'_jra_predictions_v1.json')
        raw = path.read_bytes()
        d = json.loads(raw)
        end = {}
        for venue in d['venues']:
            feed = json.loads((repo/'data/results/jra'/date/'v1'/(venue['venue_key']+'.json')).read_bytes())
            if feed['forecast_ref']['sha256'] != sha256(raw).hexdigest():
                raise ValueError('固定予想と結果の参照が不一致')
            end.update({r['race_uid']: r for r in feed['races']})
        for r in d['races']:
            if r['class_text']=='新馬' or r['surface']=='hurdle':
                continue
            rr=end[r['race_uid']]
            names={h['number']:h['name'] for h in rr['rows']}
            assert rr['official_confirmed'] and rr['rows_complete'] and d['fixed_at'] < r['start_at']
            assert all(names[h['number']]==h['name'] for h in r['horses'])
            methods={}
            positions={}
            sized={}
            for method in ('rank','market','top2','top3'):
                hs,_=ordered_horses(r['horses'],method)
                nums=[h['number'] for h in hs]
                methods[method]=evaluate(nums,rr)
                sized[method]=evaluate(nums,rr,*field_limits(len(nums)))
                finishes={row['number']:row['finish'] for row in rr['rows'] if isinstance(row['finish'],int)}
                positions[method]=[finishes.get(h['number']) for h in hs[:7]]
            rows.append(dict(race_uid=r['race_uid'],date=date,size=len(hs),methods=methods,sized=sized,positions=positions))
    def aggregate(group):
        return {m:{k:sum(r['methods'][m][k] for r in group) for k in group[0]['methods'][m]} for m in group[0]['methods']}
    if not rows:raise ValueError('対象となる確定済みの既走平地がありません')
    by_slot={}
    for method in rows[0]['methods']:
        by_slot[method]=[]
        for i in range(7):
            finishes=[row['positions'][method][i] for row in rows if len(row['positions'][method])>i]
            by_slot[method].append(dict(slot=i+1,races=len(finishes),top2=sum(v is not None and v<=2 for v in finishes),
                                        top3=sum(v is not None and v<=3 for v in finishes)))
    bands=[]
    for lo,hi in [(1,9),(10,12),(13,15),(16,18)]:
        group=[r for r in rows if lo<=r['size']<=hi]
        if not group:continue
        partner,cover=field_limits(hi)
        bands.append(dict(lo=lo,hi=hi,races=len(group),partner=partner,cover=cover,
                          fixed=aggregate(group),sized=aggregate([dict(r,methods=r['sized']) for r in group])))
    return dict(races=len(rows),dates=dates,summary=aggregate(rows),by_slot=by_slot,field_bands=bands,
                by_date={date:aggregate([r for r in rows if r['date']==date]) for date in dates},rows=rows)


if __name__=='__main__':
    from argparse import ArgumentParser
    parser=ArgumentParser(description='固定したJRA既走平地の買い順を公式成績と照合')
    parser.add_argument('dates',nargs='+')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit_dates(Path(__file__).resolve().parents[1],args.dates)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

