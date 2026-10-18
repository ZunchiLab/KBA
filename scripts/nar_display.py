"""NAR display adapters. Frozen ordinal numbers are never ability scores."""
from copy import deepcopy

PAYOUT_ALIASES = {'枠連複':'枠連', '馬連複':'馬連', '馬連単':'馬単', '枠連単':'枠単'}

def ordinal_score(h):
    definition = h.get('score_definition', '')
    return (h.get('model_features', {}).get('method') == 'manual_relative_order'
            or h.get('score_method') in ('manual_relative_order', 'ordinal_display')
            or ('2点刻み' in definition and '順位' in definition))

def score_summary(h):
    rank = str(h['rank'])+'位' if h.get('rank') else '順位保留'
    if ordinal_score(h) and h.get('score') is not None:
        return rank+' / 順位表示用数値'+str(h.get('score'))+'（能力指数ではありません）'
    if h.get('score') is None:
        return rank+' / 能力指数は未算出'
    return rank+' / '+h.get('score_definition', '比較指数')+' '+str(h['score'])

def adapt_result(data):
    result = deepcopy(data)
    result['authority'] = 'nar'
    for race in result.get('races', []):
        for payout in race.get('refunds', []):
            payout['kind'] = PAYOUT_ALIASES.get(payout['kind'], payout['kind'])
            payout['number_type'] = 'bracket' if payout['kind'].startswith('枠') else 'horse'
    return result
