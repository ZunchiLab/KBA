"""Official per-race payouts, separate from forecast prices and example returns."""
from html import escape

PAYOUT_KINDS = {'win':'単勝','place':'複勝','bracket_quinella':'枠連','quinella':'馬連','wide':'ワイド','exacta':'馬単','trio':'三連複','trifecta':'三連単'}

def payout_html(result):
    if not result or not (result.get('rows') or result.get('refunds')):
        return ''
    esc=lambda value:escape(str(value),quote=True)
    payouts=result.get('refunds',[]);statuses=result.get('payouts_status',{})
    kinds=dict(PAYOUT_KINDS)
    if any(p['kind'] in ('枠単','bracket_exacta') for p in payouts):kinds['bracket_exacta']='枠単'
    rows=[]
    for kind,label in kinds.items():
        entries=[p for p in payouts if p['kind'] in [kind,label]]
        caption=label+'（枠番）' if kind in ['bracket_quinella','bracket_exacta'] else label
        lines=[]
        for p in entries:
            separator='→' if kind in ['exacta','trifecta','bracket_exacta'] else '−'
            nums=separator.join(map(str,p['numbers']))
            lines.append('<div class="payout-line"><span>'+esc(nums)+'</span><b>'+f'{p["yen_per_100"]:,}'+'円</b></div>')
        if not lines:
            text='発売なし' if statuses.get(kind)=='not_offered' else '未掲載・確認待ち'
            lines=['<span class="payout-pending">'+text+'</span>']
        rows.append('<tr data-kind="'+kind+'"><th scope="row">'+caption+'</th><td>'+''.join(lines)+'</td></tr>')
    finish=[]
    for place in [1,2,3]:
        numbers=[str(r['number']) for r in result.get('rows',[]) if r.get('finish')==place]
        if numbers:finish.append(str(place)+'着 '+ '・'.join(numbers))
    top='<p class="official-top-finish">'+esc(' / '.join(finish))+'</p>' if finish else ''
    source=result.get('source') or {};stamp=source.get('retrieved_at')
    checked='<p class="payout-checked">公式確認 '+esc(stamp[11:19])+' JST · 各100円あたり</p>' if stamp else ''
    return '<details class="official-payouts" open><summary>結果・払戻（全'+str(len(kinds))+'式別／100円）</summary>'+top+'<table class="payout-table"><thead><tr><th scope="col">式別</th><th scope="col">的中番号・払戻金</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table>'+checked+'</details>'
