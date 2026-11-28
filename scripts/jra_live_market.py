"""Read official odds for upcoming races at bounded intervals; retain past quotes."""
from datetime import datetime, timezone, timedelta
import re
from bs4 import BeautifulSoup
from jra_live_revision import create_revision


def numbers(text):
    return [float(x) for x in re.findall(r'\d+(?:\.\d+)?', text.replace(',', ''))]


def prices_for(raw, kind, wanted):
    selector = {'wide':'table.wide','quinella':'table.umaren','trio':'table.fuku3'}[kind]
    prices = {}
    for table in BeautifulSoup(raw, 'html.parser').select(selector):
        base = [int(n) for n in re.findall(r'\d+', table.caption.get_text())]
        for row in table.select('tr'):
            if not row.th or not row.td:
                continue
            if not row.th.get_text(strip=True).isdigit():
                continue
            pair = tuple(sorted(base+[int(row.th.get_text(strip=True))]))
            if pair in wanted:
                odds = numbers(row.td.get_text(' ',strip=True))
                prices[pair] = odds[:1]+odds[-1:] if odds else []
    return prices


def update_market(data, races, fetch, stamp, date):
    """Check races in the next 90 minutes every five minutes. Keep last good data."""
    market = data.setdefault('market', {})
    now = datetime.fromisoformat(stamp)
    for race in races:
        remaining = (datetime.fromisoformat(race['start_at'])-now).total_seconds()
        if not 0 < remaining <= 90*60:
            continue
        key = str(race['race_no'])
        item = market.setdefault(key, {'snapshots':[]})
        previous = item.get('attempted_at')
        has_revision = bool(item['snapshots'] and item['snapshots'][-1].get('revision'))
        if previous and has_revision and (now-datetime.fromisoformat(previous)).total_seconds() < 300:
            continue
        item['attempted_at'] = stamp
        try:
            token = race['market']['source']['request_fields']['cname']
            raw, source = fetch('accessO.html',token,date,race['venue_key']+'_market')
            soup = BeautifulSoup(raw,'html.parser')
            table = soup.select_one('table.tanpuku')
            if not table:
                raise ValueError('単勝表未取得')
            known = {h['number']:h['name'] for h in race['horses']}
            runners = []
            for tr in table.select('tbody tr'):
                def txt(cls):
                    el=tr.select_one('.'+cls)
                    return el.get_text('',strip=True) if el else ''
                n = int(txt('num'))
                if txt('horse') != known.get(n):
                    raise ValueError('出走馬照合不一致')
                odds = numbers(txt('odds_tan'))
                runners.append(dict(number=n,win=odds[0] if odds else None,status='取消' if '取消' in tr.get_text() else '除外' if '除外' in tr.get_text() else '出走',body=txt('h_weight'),jockey=txt('jockey')))
            if {h['number'] for h in runners} != set(known):
                raise ValueError('全頭照合不一致')
            quotes = []
            for plan in race['bet_plans']:
                if not plan['selected_for_example']:
                    continue
                kind = plan['kind']
                token = plan['tickets'][0]['market']['source']['request_fields']['cname']
                price_raw, price_source = fetch('accessO.html', token,date,race['venue_key']+'_market')
                wanted = {tuple(sorted(t['numbers'])) for t in plan['tickets']}
                values = prices_for(price_raw,kind,wanted)
                for ticket in plan['tickets']:
                    ns = tuple(sorted(ticket['numbers']))
                    odds = values.get(ns,[])
                    quotes.append(dict(kind=kind,numbers=ns,lower=odds[0] if odds else None,upper=odds[-1] if odds else None,minimum=ticket['minimum_odds'],example_stake_yen=ticket['example_stake_yen'],source=price_source))
            page_time = soup.select_one('.cell.time')
            snapshot=dict(checked_at=source['retrieved_at'],page_time=page_time.get_text(' ',strip=True) if page_time else None,runners=runners,tickets=quotes,source=source)
            calculated=datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds')
            if datetime.fromisoformat(calculated) >= datetime.fromisoformat(race['start_at']):
                continue
            snapshot['revision']=create_revision(race,data,races,snapshot,calculated)
            item['snapshots'].append(snapshot)
            item['snapshots']=item['snapshots'][-30:]
            item['error']=None
        except Exception as error:
            item['error']=str(error)
