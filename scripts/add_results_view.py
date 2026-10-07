"""Add a result-only overlay, preserving the exact committed forecast originals."""
from datetime import datetime, timezone, timedelta
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[1]
JST = timezone(timedelta(hours=9))


def committed_bytes(relative):
    return subprocess.run(['git', 'show', 'HEAD:'+relative], cwd=ROOT,
                          check=True, capture_output=True).stdout


def main():
    config = json.loads((ROOT/'data/results/targets.json').read_text(encoding='utf-8'))
    targets = config['targets']
    refresh_note = ('ボタンは保存済みの最新結果を読み込みます。本日10/7はおおむね10分間隔で公式結果を更新（処理に遅延する場合あり）。取得日時を必ず確認してください。'
                    if config.get('refresh_status') == 'scheduled' else
                    'ボタンは保存済みの結果を読み込みます。定期更新はGitHubの追加接続設定待ちです。現時点では表示された保存日時の結果です。')
    archive = ROOT/'predictions/archive/20261007_original'
    archive.mkdir(parents=True, exist_ok=True)
    manifest_path = archive/'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8')) if manifest_path.exists() else {
        'archived_at': datetime.now(JST).isoformat(timespec='seconds'),
        'reason': 'ユーザー依頼で同じ公開URLへ結果取得UIを追加。事前予想の内容は変更しない。',
        'source_commit': subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip(),
        'files': []}
    for target in targets:
        jp = ROOT/target['forecast']
        hp = jp.with_suffix('.html')
        html = hp.read_text(encoding='utf-8-sig')
        if 'id="results-panel"' in html:
            import re
            html = re.sub(r'<p class="result-note">ボタンは保存済みの.*?</p>',
                          '<p class="result-note">'+refresh_note+'</p>', html, count=1)
            hp.write_text(html, encoding='utf-8')
            continue
        for file in (hp, jp):
            original = committed_bytes(file.relative_to(ROOT).as_posix())
            backup = archive/file.name
            if backup.exists() and backup.read_bytes() != original:
                raise ValueError('An original archive already exists with different content')
            backup.write_bytes(original)
            manifest['files'].append(dict(path=file.relative_to(ROOT).as_posix(),
                                          archive=backup.relative_to(ROOT).as_posix(),
                                          sha256=sha256(original).hexdigest()))
        relative = f'../data/results/nar/{target["date"]}/{target["venue"]}.json'
        live = f'https://raw.githubusercontent.com/ZunchiLab/KBA/main/data/results/nar/{target["date"]}/{target["venue"]}.json'
        e = lambda value: escape(value, quote=True)
        panel = f'''<section id="results-panel" class="panel results-panel" data-forecast-url="{e(jp.name)}" data-result-url="{e(relative)}" data-live-url="{e(live)}" aria-busy="false">
<h2>結果を取得して、予想と照合</h2>
<p>確定着順・払戻・掲載買い目の的中判定を、事前予想と並べて表示します。</p>
<div class="results-actions"><button type="button" class="results-button">結果を取得</button><span class="results-status" role="status" aria-live="polite">まだ結果を取得していません。</span></div>
<div class="results-summary" aria-label="確定結果の集計"></div>
<p class="result-note">{e(refresh_note)}</p>
<p class="result-note">価格未達の点も組合せの的中は表示しますが、購入対象の的中とは分けます。実購入・実収支は未記録です。</p>
<p><a href="archive/20261007_original/{e(hp.name)}">結果表示を追加する前の予想原本</a></p>
<noscript><p>結果表示にはJavaScriptが必要です。各レースの公式リンクでも確認できます。</p></noscript>
</section>'''
        marker = '<section class="panel"><h2>先に買い目候補を見る</h2>'
        if marker not in html:
            raise ValueError('Expected report insertion point missing')
        html = html.replace(marker, panel+marker, 1)
        html = html.replace('</head>', '<link rel="stylesheet" href="../assets/css/results.css"></head>', 1)
        html = html.replace('</body>', '<script type="module" src="../assets/js/results.js"></script></body>', 1)
        html = html.replace('データ・価格は自動更新しません。', '予想・保存価格は更新しません。公式結果だけを別欄へ取得できます。')
        hp.write_text(html, encoding='utf-8')
        print('Added result view: '+hp.name)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
