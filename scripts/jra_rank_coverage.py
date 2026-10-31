"""Read-only rank concentration diagnostics using the UI's exact tie handling."""
ROLES=('first','second','top2','top3')

def ordered_horses(horses, method):
    hs=[h for h in horses if h.get('status_at_snapshot') not in ('withdrawn','excluded')]
    def value(h):
        return h.get('market',{}).get('win') if method=='market' else h.get('role_indices',{}).get(method,{}).get('value') if method in ROLES else h.get(method)
    def key(h):
        v=value(h)
        return (v is None,v if method in ('rank','market','number') else -v if v is not None else 0,h.get('rank') or 999,h['number'])
    available=sum(value(h) is not None for h in hs)
    if method in ROLES and hs and all(h.get('role_indices',{}).get('method')=='debut_cohort_reference' for h in hs):
        available=sum(bool(h['role_indices']['matched_starters']) for h in hs)
    return sorted(hs,key=key),available

def needed_prefix(numbers, actual_rows):
    if len(set(numbers))!=len(numbers):raise ValueError('表示馬番が重複')
    placed={h['number'] for h in actual_rows if isinstance(h.get('finish'),int) and not isinstance(h['finish'],bool) and h['finish']<=3}
    if not placed or not placed<=set(numbers):raise ValueError('公式3着以内馬と対象馬の照合が未完了')
    positions={n:i+1 for i,n in enumerate(numbers)}
    return max(positions[n] for n in placed)
