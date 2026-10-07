"""Generate a static, API-independent catalog. Python standard library only."""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from html import escape, unescape
from urllib.parse import quote
import json, re

ROOT = Path(__file__).resolve().parents[1]
E = lambda value: escape(str(value), quote=True)

def report(path):
    text = path.read_text(encoding='utf-8-sig')
    match = re.search(r'<title[^>]*>(.*?)</title>', text, flags=re.I | re.S)
    title = unescape(re.sub('<[^>]+>', '', match.group(1))).strip() if match else path.stem
    title = ' '.join(title.split())
    date_match = re.search(r'(20\d{2})[-_]?(\d{2})[-_]?(\d{2})', path.name)
    date = '-'.join(date_match.groups()) if date_match else None
    data = {}
    sidecar = path.with_suffix('.json')
    if sidecar.exists():
        data = json.loads(sidecar.read_text(encoding='utf-8-sig'))
    date = data.get('date_jst') or data.get('target_date') or date
    version_match = re.search(r'_v(\d+)\.html$', path.name)
    version = int(version_match.group(1)) if version_match else None
    group = re.sub(r'_v\d+\.html$', '', path.name) if version else path.name
    name_lower = path.name.lower()
    is_review = data.get('document_type') == 'review'
    category = 'review' if is_review else 'nar' if '_nar_' in name_lower or data.get('baba_code') else 'overseas' if '凱旋門' in path.name else 'jra' if 'jra' in name_lower else 'other'
    venues = [v['label'] for v in data.get('venues', []) if v.get('label')]
    if not venues and category in ('jra', 'nar'):
        venues = list(dict.fromkeys(r['venue'] for r in data.get('races', []) if r.get('venue')))
    venue = data.get('venue') or '・'.join(venues) or {'nar':'地方競馬','jra':'JRA','overseas':'凱旋門賞','other':'競馬予想','review':'開催後の振り返り'}[category]
    scope = data.get('prediction_scope')
    scope_text = f'{min(scope)}〜{max(scope)}R 再評価' if scope else ''
    heading = f'{venue}競馬の本気予想' if venue=='大井' and not is_review else title
    if len(heading)>75:heading=heading[:74]+'…'
    note = scope_text or ('全24Rの予想' if '全24R' in title else '全頭評価と予想の記録' if 'allraces' in name_lower or '_predictions' in name_lower else '予想の記録')
    if is_review:note='開催後の振り返り · 全頭の印と着順 · 買い方と購入記録の補助'
    has_results = 'id="results-panel"' in text
    if has_results:note+=' · 結果取得対応'
    if 'reverse' in name_lower:note='別の観点から評価した予想'
    if 'スマホ' in path.name:note+=' · スマホ版'
    elif '印付き' in path.name:note+=' · 印・得点順'
    elif 'pedigree_training' in name_lower:note+=' · 血統・調教'
    horse_names=[h['name'] for race in data.get('races',[]) for h in race.get('horses',[])]
    if is_review:horse_names=[h['name'] for race in data.get('results',[]) for h in race.get('rows',[])]
    return {'file':path.name,'href':'predictions/'+quote(path.name),'date':date,'category':category,'venue':venue,
            'title':title,'heading':heading,'note':note,'version':version,'group':group,'fixed_at':data.get('fixed_at') or data.get('generated_at'),
            'scope':scope,'phase':data.get('phase'),'superseded':False,'horse_names':horse_names,'has_results':has_results,
            'document_type':'review' if is_review else 'prediction','reviewed_at':data.get('reviewed_at')}

def main():
    entries=[report(path) for path in (ROOT/'predictions').glob('*.html')]
    entries.sort(key=lambda x:(x['date'] or '',x['version'] or 0,x['fixed_at'] or '',x['file']),reverse=True)
    max_versions={}
    for entry in entries:
        if entry['version']:max_versions[entry['group']]=max(max_versions.get(entry['group'],0),entry['version'])
    for entry in entries:
        entry['superseded']=bool(entry['version'] and entry['version']<max_versions[entry['group']])
    cards=[]
    badges={'nar':'地方競馬','jra':'中央競馬','overseas':'海外競馬','other':'競馬予想','review':'振り返り'}
    for entry in entries:
        date=(entry['date'] or '日付不明').replace('-','.')
        version=f"v{entry['version']} · {'旧版' if entry['superseded'] else '最新版'}" if entry['version'] else '予想の記録'
        fixed=f" · {entry['fixed_at'][11:16]}固定" if entry['fixed_at'] else ''
        if entry['document_type']=='review':
            version=f"v{entry['version']} · 開催後の記録"
            fixed=''
        open_label='振り返りを読む' if entry['document_type']=='review' else '予想を読む'
        search=' '.join(str(entry[k] or '') for k in ('date','title','venue','heading','note','file'))+' '+' '.join(entry['horse_names'])
        cards.append(f'''<article class="report-card" data-category="{E(entry['category'])}" data-month="{E((entry['date'] or '')[:7])}" data-superseded="{str(entry['superseded']).lower()}" data-search="{E(search)}"><a href="{E(entry['href'])}"><div class="card-top"><time datetime="{E(entry['date'] or '')}">{E(date)}</time><span class="badge {E(entry['category'])} {'old' if entry['superseded'] else ''}">{E(badges[entry['category']])}</span></div><h3>{E(entry['heading'])}</h3><p class="report-note">{E(entry['note'])}</p><div class="card-bottom"><span>{E(version+fixed)}</span><span class="open">{E(open_label)} ↗</span></div></a></article>''')
    latest=next((x for x in entries if not x['superseded'] and x['document_type']=='prediction'),None)
    featured=''
    if latest:
        version=f"v{latest['version']}" if latest['version'] else '最新の記録'
        fixed=latest['fixed_at'][11:16]+' JST固定' if latest['fixed_at'] else '判断時刻は予想内に掲載'
        featured=f'''<article class="featured"><div class="featured-top"><span class="eyebrow">LATEST PREDICTION</span><span class="badge">{E(badges[latest['category']])} · {E(version)}</span></div><div class="featured-date">{E((latest['date'] or '').replace('-','.'))}</div><h2>{E(latest['venue'])}の予想</h2><p>{E(latest['note'])}</p><div class="featured-info"><span>{E(fixed)}</span><span>購入条件・全頭評価を掲載</span></div><a class="primary-link" href="{E(latest['href'])}"><span>最新の予想を読む</span><span aria-hidden="true">→</span></a></article>'''
    months=sorted({x['date'][:7] for x in entries if x['date']},reverse=True)
    month_html=''.join(f'<option value="{month}">{month[:4]}年{int(month[5:]):02d}月</option>' for month in months)
    template=(ROOT/'scripts/index.template.html').read_text(encoding='utf-8')
    latest_review=next((x for x in entries if x['document_type']=='review' and not x['superseded']),None)
    support='<a class="support-link" href="tools/bet-planner.html"><b>買い方・予算の補助 →</b><span>点数・着順の縛り・購入記録を確認</span></a>' if (ROOT/'tools/bet-planner.html').exists() else ''
    if latest_review:support+=f'<a class="support-link" href="{E(latest_review["href"])}"><b>{E(latest_review["date"])}の振り返り →</b><span>なぜ当たったか・外れたか、次回の判断へ</span></a>'
    if (ROOT/'docs/common-spec.html').exists():support+='<a class="support-link" href="docs/common-spec.html"><b>JRA・地方の共通仕様 →</b><span>会場タブ・結果更新・買い目・GitHub保存</span></a>'
    support=f'<section class="support-grid" aria-label="振り返り・購入補助・共通仕様">{support}</section>' if support else ''
    replacements={'<!-- FEATURED -->':featured,'<!-- SUPPORT -->':support,'<!-- COUNT -->':str(len(entries)),'<!-- MONTHS -->':month_html,'<!-- CARDS -->':'\n'.join(cards)}
    for marker,value in replacements.items():template=template.replace(marker,value)
    (ROOT/'index.html').write_text(template,encoding='utf-8')
    (ROOT/'data').mkdir(exist_ok=True)
    catalog={'generated_at':datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds'),'reports':entries}
    (ROOT/'data/catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Generated index.html and data/catalog.json: {len(entries)} reports, {len(months)} months')

if __name__=='__main__':main()
