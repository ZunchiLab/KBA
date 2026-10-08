"""Include official result snapshots in HTML so they remain visible offline."""
from html import escape
from hashlib import sha256
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def finish_text(result, number):
    row = next((row for row in result['rows'] if row['number'] == number), None)
    if row:
        finish = row['finish']
        return str(finish)+'着' if isinstance(finish, int) else str(finish)
    return {'partial': '全着順待ち', 'not_started': '発走前',
            'cancelled': '競走取り止め', 'error': '取得保留'}.get(result['status'], '未確定')


def render_snapshot(target, forecast, data):
    if forecast.get('schema_version') == 'kba.forecast/1' and forecast.get('venues'):
        from render_day_prediction import render_day_snapshot
        render_day_snapshot(target)
        return
    forecast_text = (ROOT/target['forecast']).read_text(encoding='utf-8-sig').replace('\r\n', '\n')
    if data['forecast_sha256'] != sha256(forecast_text.encode('utf-8')).hexdigest() or data['forecast_version'] != forecast['version'] or data['date_jst'] != forecast['date_jst'] or data['baba_code'] != forecast['baba_code']:
        raise ValueError('Snapshot does not match the frozen forecast')
    path = (ROOT/target['forecast']).with_suffix('.html')
    html = path.read_text(encoding='utf-8-sig')
    if 'id="results-panel"' not in html:
        return
    results = {result['race']: result for result in data['races']}
    for race in forecast['races']:
        result = results[race['race']]
        known = {horse['number']: horse['name'] for horse in race['horses']}
        if any(row['number'] not in known or re.sub(r'\s+', '', row['name']) != re.sub(r'\s+', '', known[row['number']]) for row in result['rows']):
            raise ValueError('Cannot render results for a different horse')
        start = re.search(r'<section class="race" id="r'+str(race['race'])+r'"[^>]*>', html)
        if not start:
            raise ValueError('Expected race section missing')
        next_race = re.search(r'<section class="race" id="r\d+"', html[start.end():])
        end = start.end()+next_race.start() if next_race else len(html)
        chunk = html[start.start():end]
        # This block contains no nested sections and is distinct from forecast text.
        chunk = re.sub(r'<section class="race-result"[^>]*>.*?</section>', '', chunk, flags=re.S)
        label = {'confirmed': '全着順・払戻確定', 'partial': '速報・全着順待ち',
                 'pending': '未確定', 'not_started': '保存時は発走前',
                 'cancelled': '競走取り止め', 'error': '取得保留'}[result['status']]
        e = lambda value: escape(str(value), quote=True)
        rows = ''.join('<tr><td>'+e(horse['mark'])+'</td><td>'+e(horse['number'])+' '+e(horse['name'])+'</td><td>'+e(finish_text(result, horse['number']))+'</td></tr>' for horse in race['horses'])
        block = '<section class="race-result" aria-label="'+str(race['race'])+'Rの印と着順"><h3>事前の印と結果 · '+str(race['race'])+'R</h3><p class="result-note">'+e(label)+' · 保存結果更新 '+e(data['updated_at'][11:16])+' JST</p><div class="scroll"><table class="result-table"><thead><tr><th>事前印</th><th>馬番・馬名</th><th>着順</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>'
        chunk, count = re.subn(r'(<div class="race-body">)', lambda match: match[1]+block, chunk, count=1)
        if count != 1:
            raise ValueError('Expected race body missing')
        horse_pattern = r'(<article\b[^>]*class="horse[^\"]*"[^>]*>.*?<span class="number">(\d+)</span>.*?<div class="horse-meta">.*?</div>)(?:<p class="result-horse-finish[^\"]*"[^>]*>.*?</p>)?'
        def horse_finish(match):
            number = int(match[2])
            if number not in known:
                raise ValueError('Unexpected horse card')
            row = next((row for row in result['rows'] if row['number'] == number), None)
            podium = row and isinstance(row['finish'], int) and row['finish'] <= 3
            return match[1]+'<p class="result-horse-finish'+(' podium' if podium else '')+'">結果：'+e(finish_text(result, number))+'</p>'
        chunk, count = re.subn(horse_pattern, horse_finish, chunk, flags=re.S)
        if count != len(race['horses']):
            raise ValueError('Horse card count does not match forecast')
        html = html[:start.start()]+chunk+html[end:]
    seed = json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    script = '<script type="application/json" id="results-bootstrap">'+seed+'</script>'
    if 'id="results-bootstrap"' in html:
        html = re.sub(r'<script type="application/json" id="results-bootstrap">.*?</script>', lambda _: script, html, count=1, flags=re.S)
    else:
        html = html.replace('</body>', script+'</body>', 1)
    status = '保存データ更新：'+data['updated_at'][5:10].replace('-', '/')+' '+data['updated_at'][11:16]+' JST。印と着順を表示中。'
    html = re.sub(r'(<span class="results-status"[^>]*>).*?(</span>)', lambda match: match[1]+escape(status)+match[2], html, count=1, flags=re.S)
    html = html.replace('まだ結果を取得していません。', escape(status))
    if path.read_text(encoding='utf-8-sig') != html:
        path.write_text(html, encoding='utf-8')


def main():
    config = json.loads((ROOT/'data/results/targets.json').read_text(encoding='utf-8'))
    for target in config['targets']:
        forecast = json.loads((ROOT/target['forecast']).read_text(encoding='utf-8-sig'))
        result_path = ROOT/'data/results/nar'/target['date']/(target['venue']+'.json')
        if result_path.exists():
            render_snapshot(target, forecast, json.loads(result_path.read_text(encoding='utf-8')))


if __name__ == '__main__':
    main()
