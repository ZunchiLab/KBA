"""Read official NAR results without modifying frozen prediction files.

Python standard library only. Result HTML is archived separately for audit.
"""
from argparse import ArgumentParser
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import re
import time

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))
BASE = 'https://www.keiba.go.jp/KeibaWeb/TodayRaceInfo/RaceMarkTable?'


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return ' '.join(''.join(x if isinstance(x, str) else x.text()+' ' for x in self.children).split())

    def nodes(self):
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.nodes()

    def find(self, cls):
        return next((n for n in self.nodes() if cls in n.attrs.get('class', '').split()), None)

    def direct(self, tag):
        return [n for n in self.children if isinstance(n, Node) and n.tag == tag]


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {'img', 'meta', 'link', 'br', 'hr', 'input', 'source', 'area', 'wbr'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack = self.stack[:i]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def text(node, cls):
    found = node.find(cls) if node else None
    return found.text() if found else ''


def fields(row):
    return {n.attrs.get('class', '').split()[0]: n.text()
            for n in row.direct('td') if n.attrs.get('class', '').split()}


def parse(raw, forecast, race, source):
    root = Document(raw.decode('utf-8-sig')).root
    title = next((n.text() for n in root.nodes() if n.tag == 'h4' and '競走' in n.text()), '')
    year, month, day = map(int, forecast['date_jst'].split('-'))
    compact = re.sub(r'\s+', '', title)
    if f'{year}年{month}月{day}日' not in compact or f'第{race["race"]}競走' not in compact or forecast['venue'] not in compact:
        # Some future result pages have no race heading yet.
        if root.find('gradeTable') is None:
            return dict(status='pending', rows=[], refunds=[], source=source,
                        note='公式の確定着順・払戻は未掲載。')
        raise ValueError('Official race identity does not match frozen forecast')
    grade = root.find('gradeTable')
    rows = []
    if grade:
        for row in grade.nodes():
            if row.tag != 'tr':
                continue
            f = fields(row)
            if not f.get('c', '').isdigit():
                continue
            finish = int(f['a']) if f.get('a', '').isdigit() else f.get('a', '')
            rows.append(dict(number=int(f['c']), name=f.get('d', ''), finish=finish,
                             time=f.get('k', ''), margin=f.get('l', ''), last_3f=f.get('m', ''),
                             jockey=f.get('h', ''), body_weight=f.get('j', ''),
                             final_popularity=int(f['o']) if f.get('o', '').isdigit() else None,
                             final_win_odds=f.get('p') or None))
    known = {h['number']: h['name'] for h in race['horses']}
    if len({h['number'] for h in rows}) != len(rows):
        raise ValueError('Duplicate result horse number')
    for h in rows:
        if h['number'] not in known or re.sub(r'\s+', '', h['name']) != re.sub(r'\s+', '', known[h['number']]):
            raise ValueError('Official horse identity does not match frozen forecast')
    refunds = []
    refund_root = root.find('newRefundTable')
    if refund_root:
        for table in refund_root.nodes():
            if table.tag != 'table':
                continue
            kind = None
            for row in table.nodes():
                if row.tag != 'tr':
                    continue
                f = fields(row)
                if f.get('title'):
                    kind = f['title']
                money = re.sub(r'[^0-9]', '', f.get('refundMoney', ''))
                combo = f.get('a') or f.get('d') or ''
                if kind and money and combo:
                    refunds.append(dict(kind=kind, combination=combo,
                                        numbers=list(map(int, re.findall(r'\d+', combo))),
                                        yen_per_100=int(money), popularity=f.get('c', '')))
    numeric = [h for h in rows if isinstance(h['finish'], int)]
    finished = any(h['finish'] == 1 for h in numeric)
    payout_kinds = {p['kind'] for p in refunds}
    confirmed = finished and len(rows) == len(known) and {'単勝', '三連単'} <= payout_kinds
    partial = finished and not confirmed
    race_title = root.find('raceTitle')
    cancelled = not numeric and race_title and re.search(r'競走(?:取り止め|取止)|この競走は取り止め', race_title.text())
    return dict(status='confirmed' if confirmed else 'partial' if partial else 'cancelled' if cancelled else 'pending',
                rows=rows if confirmed or partial else [], refunds=refunds if confirmed or partial else [],
                source=source, note='公式着順と払戻を照合済み。' if confirmed else
                '公式に掲載された速報。全頭の着順・払戻が揃うまで最終集計を保留。' if partial else
                '公式の競走取り止め。' if cancelled else '確定着順・払戻が揃うまで判定を保留。')


def write_atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    tmp.replace(path)


def update(target, now, force=False, refresh_status='manual_pending_workflow_permission', refresh_interval=None):
    forecast_path = ROOT / target['forecast']
    if forecast_path.parent != ROOT/'predictions':
        raise ValueError('Forecast must be directly in predictions/')
    forecast_raw = forecast_path.read_bytes()
    forecast_text = forecast_raw.decode('utf-8-sig').replace('\r\n', '\n')
    forecast = json.loads(forecast_text)
    forecast_digest = sha256(forecast_text.encode('utf-8')).hexdigest()
    if target['date'] != forecast['date_jst'] or target['venue'] != forecast['venue_key']:
        raise ValueError('Target metadata mismatch')
    out = ROOT/'data/results/nar'/target['date']/(target['venue']+'.json')
    previous = json.loads(out.read_text(encoding='utf-8')) if out.exists() else {}
    if previous.get('forecast_sha256') not in (None, forecast_digest, sha256(forecast_raw).hexdigest()):
        raise ValueError('Frozen forecast changed; do not mix results with a new forecast')
    if previous.get('complete') and not force:
        print(f'{target["venue"]}: all target races confirmed; no further polling')
        return
    old_races = {r['race']: r for r in previous.get('races', [])}
    results = []
    for race in forecast['races']:
        n = race['race']
        result = dict(race=n, name=race['name'], start_at=race['start_at'])
        start = datetime.fromisoformat(race['start_at'])
        old = old_races.get(n)
        if old and old['status'] in ('confirmed', 'cancelled') and not force:
            results.append(old)
            continue
        if start > now:
            result.update(status='not_started', rows=[], refunds=[], source=None,
                          note='保存時点では発走前。')
            results.append(result)
            continue
        url = BASE+urlencode(dict(k_raceDate=forecast['date_jst'].replace('-', '/'),
                                 k_babaCode=forecast['baba_code'], k_raceNo=n))
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0 (KBA results archive)'}), timeout=25) as response:
                raw = response.read()
            at = datetime.now(JST)
            digest = sha256(raw).hexdigest()
            relative = Path('data/results/sources')/target['date']/target['venue']/f'r{n}_{at.strftime("%H%M%S")}_{digest[:12]}.html'
            source = dict(url=url, retrieved_at=at.isoformat(timespec='seconds'),
                          sha256=digest, saved_file=relative.as_posix())
            result.update(parse(raw, forecast, race, source))
            (ROOT/relative).parent.mkdir(parents=True, exist_ok=True)
            (ROOT/relative).write_bytes(raw)
        except Exception as ex:
            if old and old['status'] in ('confirmed', 'cancelled'):
                result = dict(old, refresh_error=str(ex), last_attempt_at=datetime.now(JST).isoformat(timespec='seconds'))
            else:
                result.update(status='error', rows=[], refunds=[], source=None,
                              note='公式結果の取得・照合に失敗。', error=str(ex),
                              last_attempt_at=datetime.now(JST).isoformat(timespec='seconds'), official_url=url)
        results.append(result)
        time.sleep(0.4)
    payload = dict(schema_version=1, date_jst=forecast['date_jst'], venue=forecast['venue'],
                   venue_key=forecast['venue_key'], baba_code=forecast['baba_code'],
                   forecast_version=forecast['version'], forecast_fixed_at=forecast['fixed_at'],
                   forecast_file=forecast_path.name, forecast_sha256=forecast_digest,
                   forecast_digest_method='UTF-8 without BOM, CRLF normalized to LF',
                   updated_at=datetime.now(JST).isoformat(timespec='seconds'),
                   complete=all(r['status'] in ('confirmed', 'cancelled') for r in results),
                   refresh_interval_minutes=(refresh_interval or 10) if refresh_status in ('scheduled', 'continuous') else None,
                   refresh_status=refresh_status, races=results,
                   actual_purchase=None, note='結果専用データ。事前予想・価格・採否を変更しない。')
    write_atomic(out, payload)
    counts = {status: sum(r['status'] == status for r in results) for status in ('confirmed', 'partial', 'pending', 'not_started', 'error', 'cancelled')}
    print(f'{target["venue"]}: {counts}; {payload["updated_at"]}')


def main():
    args = ArgumentParser()
    args.add_argument('--active-only', action='store_true')
    args.add_argument('--force', action='store_true', help='Recheck already confirmed races')
    options = args.parse_args()
    config = json.loads((ROOT/'data/results/targets.json').read_text(encoding='utf-8'))
    now = datetime.now(JST)
    for target in config['targets']:
        if options.active_only and (target['date'] != now.date().isoformat() or not 9 <= now.hour < 23):
            continue
        update(target, now, options.force, config.get('refresh_status', 'manual_pending_workflow_permission'),
               config.get('refresh_interval_minutes'))


if __name__ == '__main__':
    main()
