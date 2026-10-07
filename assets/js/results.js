const panel = document.querySelector('#results-panel');

function node(tag, text, cls) {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = String(text);
  if (cls) el.className = cls;
  return el;
}

function formatTime(value) {
  return value ? new Intl.DateTimeFormat('ja-JP', { timeZone: 'Asia/Tokyo', month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value)) + ' JST' : '未取得';
}

function money(value) { return value.toLocaleString('ja-JP') + '円'; }
function finishLabel(value) { return Number.isInteger(value) ? value + '着' : value || '未確定'; }

function table(headers, rows, cls = 'result-table') {
  const wrap = node('div', undefined, 'scroll');
  const t = node('table', undefined, cls);
  const head = node('thead');
  const hr = node('tr');
  headers.forEach(value => hr.append(node('th', value)));
  head.append(hr);
  const body = node('tbody');
  rows.forEach(values => {
    const row = node('tr');
    values.forEach(value => row.append(node('td', value)));
    body.append(row);
  });
  t.append(head, body); wrap.append(t);
  return wrap;
}

function details(title, content) {
  const el = node('details');
  el.append(node('summary', title), content);
  return el;
}

function comboKey(numbers, kind) {
  return (['ワイド', '馬連複', '三連複', '枠連複'].includes(kind) ? [...numbers].sort((a, b) => a - b) : numbers).join('-');
}

function judgeTicket(bet, ticket, result) {
  if (result.status === 'cancelled') return { status: '返還', yen: 100, cls: 'result-refund' };
  if (!['confirmed', 'partial'].includes(result.status)) return { status: '未確定', yen: null, cls: 'result-pending' };
  const withdrawn = new Set(result.rows.filter(h => ['取消', '除外', '競走除外', '出走取消'].includes(h.finish)).map(h => h.number));
  if (ticket.numbers.some(n => withdrawn.has(n))) return { status: '返還', yen: 100, cls: 'result-refund' };
  const payouts = result.refunds.filter(p => p.kind === bet.type);
  if (!payouts.length) return { status: '払戻未確認', yen: null, cls: 'result-pending' };
  const payout = payouts.find(p => comboKey(p.numbers, bet.type) === comboKey(ticket.numbers, bet.type));
  if (!payout && result.status === 'partial') return { status: '全着順待ち', yen: null, cls: 'result-pending' };
  return payout ? { status: '的中', yen: payout.yen_per_100, cls: 'result-hit' } : { status: '不的中', yen: 0, cls: 'result-miss' };
}

function ticketSummary(race, result) {
  const section = node('div');
  if (!race.bets.length) {
    section.append(node('p', '事前判断：見送り。掲載買い目はありません。', 'result-note'));
    return section;
  }
  section.append(node('h3', '掲載買い目との照合'));
  for (const bet of race.bets) {
    let hits = 0, refunds = 0, eligibleHits = 0, stake = 0, returned = 0, allKnown = true;
    const rows = bet.tickets.map(ticket => {
      const judgement = judgeTicket(bet, ticket, result);
      if (judgement.status === '的中') hits++;
      if (judgement.status === '返還') refunds++;
      const eligible = ticket.price_condition_at_snapshot === true;
      if (eligible) {
        stake += ticket.example_stake_yen;
        if (judgement.status === '的中') eligibleHits++;
        if (judgement.yen === null) allKnown = false;
        else returned += judgement.yen * ticket.example_stake_yen / 100;
      }
      return [ticket.numbers.join('→'), judgement.status, judgement.yen === null ? '—' : money(judgement.yen),
        eligible ? '保存時に価格達成*' : ticket.price_condition_at_snapshot === false ? '価格未達・見送り' : '価格未取得・見送り'];
    });
    section.append(node('p', `${bet.type}：組合せ的中 ${hits}/${bet.tickets.length}点、返還 ${refunds}点。そのうち保存価格を満たした的中は${eligibleHits}点。`, hits ? 'result-hit' : 'result-note'));
    if (allKnown && ['confirmed', 'cancelled'].includes(result.status)) {
      section.append(node('p', `仮想検証：保存時に価格達成の${money(stake)}分を購入し、直前条件も満たしたと仮定 → 払戻・返還 ${money(returned)}。実購入・実収支ではありません。`, 'result-note'));
    }
    section.append(details(`${bet.type}の全${bet.tickets.length}点・価格条件を見る`, table(['組合せ', '結果', '100円払戻', '事前の価格判定'], rows, 'result-ticket-table')));
  }
  section.append(node('p', '*価格達成だけで購入確定にはなりません。直前価格・状態・実購入時刻は未記録。最終払戻から事前の見送りを変更しません。', 'result-note'));
  return section;
}

function renderRace(race, result) {
  const raceEl = document.querySelector('#r' + race.race);
  if (!raceEl) return;
  let block = raceEl.querySelector('.race-result');
  if (!block) {
    block = node('section', undefined, 'race-result');
    block.setAttribute('aria-label', race.race + 'Rの結果');
    raceEl.querySelector('.race-body').prepend(block);
  }
  block.replaceChildren(node('h3', '公式結果 · ' + race.race + 'R'));
  const now = Date.now();
  const labels = { confirmed: '着順・払戻確定', partial: '速報（掲載済みの着順・払戻を表示、全着順待ち）', pending: '未確定', not_started: now >= Date.parse(race.start_at) ? '未確定（保存時は発走前）' : '発走前', error: '結果取得失敗・判定保留', cancelled: '競走取り止め・返還' };
  block.append(node('p', labels[result.status] || '未取得', result.status === 'error' ? 'results-error' : 'result-note'));
  if (result.source) block.append(node('p', '公式取得：' + formatTime(result.source.retrieved_at), 'result-note'));
  if (result.refresh_error) block.append(node('p', '再取得に失敗したため、前回の確定結果を表示しています。', 'results-error'));
  const official = node('a', '公式結果を開く ↗');
  official.href = result.source?.url || result.official_url || race.source.url.replace('DebaTable', 'RaceMarkTable');
  official.target = '_blank'; official.rel = 'noopener';
  if (['confirmed', 'partial'].includes(result.status)) {
    const podium = node('div', undefined, 'result-podium');
    result.rows.filter(h => Number.isInteger(h.finish) && h.finish <= 3).forEach(h => podium.append(node('span', `${h.finish}着 ${h.number} ${h.name}`)));
    block.append(podium);
    const pick = race.horses.find(h => h.rank === 1);
    const finish = result.rows.find(h => h.number === pick.number)?.finish;
    block.append(node('p', `事前${pick.mark} ${pick.number} ${pick.name}：${finish === undefined && result.status === 'partial' ? '全着順待ち' : finishLabel(finish)}`, Number.isInteger(finish) && finish <= 3 ? 'result-hit' : result.status === 'partial' ? 'result-note' : 'result-miss'));
    block.append(ticketSummary(race, result));
    const hmap = new Map(race.horses.map(h => [h.number, h]));
    block.append(node('h4', result.status === 'partial' ? '事前印と掲載済み着順（全着順待ち）' : '全頭の事前印と着順'));
    block.append(table(['事前印', '馬番・馬名', '着順', 'タイム'], result.rows.map(h => [hmap.get(h.number).mark + ' / ' + hmap.get(h.number).rank + '位', h.number + ' ' + h.name, finishLabel(h.finish), h.time || '—'])));
    block.append(details('公式払戻金（100円あたり）', table(['券種', '組合せ', '払戻'], result.refunds.map(p => [p.kind, p.combination, money(p.yen_per_100)]))));
  } else if (result.status === 'cancelled') block.append(ticketSummary(race, result));
  else block.append(node('p', result.note || '次回の保存結果を再取得してください。', 'result-note'));
  block.append(official);
  for (const horseEl of raceEl.querySelectorAll('.horse')) {
    const number = Number(horseEl.querySelector('.number').textContent);
    let finishEl = horseEl.querySelector('.result-horse-finish');
    if (!finishEl) {
      finishEl = node('p', undefined, 'result-horse-finish');
      horseEl.querySelector('.horse-meta').after(finishEl);
    }
    const finish = result.rows.find(h => h.number === number)?.finish;
    finishEl.textContent = '結果：' + (['confirmed', 'partial'].includes(result.status) ? finish === undefined ? '全着順待ち' : finishLabel(finish) : labels[result.status]);
    finishEl.classList.toggle('podium', ['confirmed', 'partial'].includes(result.status) && Number.isInteger(finish) && finish <= 3);
  }
}

async function fetchJson(url) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const requestUrl = new URL(url, location.href);
    requestUrl.searchParams.set('_updated', String(Date.now()));
    const response = await fetch(requestUrl, { cache: 'no-store', credentials: 'omit', signal: controller.signal });
    if (!response.ok) throw new Error('HTTP ' + response.status);
    return await response.json();
  } finally { clearTimeout(timer); }
}

async function latestResultUrl(force) {
  const key = 'kba-result-main-reference';
  let cached;
  try { cached = JSON.parse(localStorage.getItem(key) || 'null'); } catch {}
  if (force || !cached || Date.now() - cached.checkedAt > 110000 || !/^[a-f0-9]{40}$/.test(cached.sha)) {
    const ref = await fetchJson('https://api.github.com/repos/ZunchiLab/KBA/git/ref/heads/main');
    if (!/^[a-f0-9]{40}$/.test(ref.object?.sha || '')) throw new Error('最新の更新を確認できません。');
    cached = { sha: ref.object.sha, checkedAt: Date.now() };
    try { localStorage.setItem(key, JSON.stringify(cached)); } catch {}
  }
  // An immutable commit URL avoids an old CDN response for the moving main URL.
  return panel.dataset.liveUrl.replace('/KBA/main/', '/KBA/' + cached.sha + '/');
}

async function readForecast() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  let raw;
  try {
    const response = await fetch(panel.dataset.forecastUrl, { cache: 'no-store', credentials: 'omit', signal: controller.signal });
    if (!response.ok) throw new Error('事前予想データを取得できません。');
    raw = (await response.text()).replace(/^\uFEFF/, '').replace(/\r\n/g, '\n');
  } finally { clearTimeout(timer); }
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(raw));
  const digest = [...new Uint8Array(bytes)].map(b => b.toString(16).padStart(2, '0')).join('');
  return { forecast: JSON.parse(raw), digest };
}

function validate(data, forecast, digest) {
  if (data.schema_version !== 1 || data.forecast_sha256 !== digest || data.forecast_version !== forecast.version || data.date_jst !== forecast.date_jst || data.baba_code !== forecast.baba_code || !Number.isFinite(Date.parse(data.updated_at)) || !Array.isArray(data.races)) {
    throw new Error('予想と結果データの対応を確認できません。判定を保留します。');
  }
  const seen = new Set();
  for (const result of data.races) {
    const race = forecast.races.find(r => r.race === result.race);
    if (!race || seen.has(result.race) || !['confirmed', 'partial', 'pending', 'not_started', 'error', 'cancelled'].includes(result.status) || !Array.isArray(result.rows) || !Array.isArray(result.refunds)) throw new Error('結果形式を確認できません。');
    seen.add(result.race);
    if (['confirmed', 'partial'].includes(result.status)) {
      const horses = new Map(race.horses.map(h => [h.number, h.name]));
      if ((result.status === 'confirmed' && result.rows.length !== horses.size) || new Set(result.rows.map(h => h.number)).size !== result.rows.length || result.rows.some(h => horses.get(h.number)?.replace(/\s/g, '') !== h.name.replace(/\s/g, ''))) throw new Error('出走馬との対応を確認できません。');
    }
  }
  if (seen.size !== forecast.races.length) throw new Error('結果の対象レースが不足しています。');
}

function summary(data, forecast) {
  const area = panel.querySelector('.results-summary');
  area.replaceChildren();
  const confirmed = data.races.filter(r => r.status === 'confirmed');
  const partial = data.races.filter(r => r.status === 'partial');
  let wins = 0, top3 = 0;
  for (const result of confirmed) {
    const race = forecast.races.find(r => r.race === result.race);
    const pick = race.horses.find(h => h.rank === 1);
    const finish = result.rows.find(h => h.number === pick.number)?.finish;
    if (finish === 1) wins++;
    if (Number.isInteger(finish) && finish <= 3) top3++;
  }
  for (const [value, label] of [[`${confirmed.length}/${forecast.races.length}R`, '着順・払戻確定'], [`${wins}/${confirmed.length}R`, '事前◎の1着（同着含む）'], [`${top3}/${confirmed.length}R`, '事前◎の3着以内']]) {
    const stat = node('div', undefined, 'results-stat');
    stat.append(node('strong', value), node('small', label)); area.append(stat);
  }
  if (partial.length) area.append(node('p', `別に${partial.length}Rの速報を表示しています。全着順待ちのレースは上の確定集計に含めません。`, 'result-note'));
}

if (panel) {
  const button = panel.querySelector('button');
  const status = panel.querySelector('.results-status');
  let lastData = null;
  let refreshTimer = null;
  try {
    const saved = JSON.parse(document.querySelector('#results-bootstrap')?.textContent || 'null');
    if (saved?.schema_version === 1 && Number.isFinite(Date.parse(saved.updated_at))) lastData = saved;
  } catch {}
  async function loadResults(force = false) {
    if (button.disabled) return;
    button.disabled = true; panel.setAttribute('aria-busy', 'true');
    status.classList.remove('results-error'); status.textContent = '保存済みの公式結果を取得中…';
    try {
      const { forecast, digest } = await readForecast();
      let data, fallback = false;
      try { data = await fetchJson(await latestResultUrl(force)); }
      catch {
        fallback = true;
        try { data = await fetchJson(panel.dataset.liveUrl); }
        catch { data = await fetchJson(panel.dataset.resultUrl); }
      }
      validate(data, forecast, digest);
      if (lastData && Date.parse(lastData.updated_at) > Date.parse(data.updated_at)) {
        validate(lastData, forecast, digest);
        data = lastData; fallback = true;
      }
      data.races.forEach(result => renderRace(forecast.races.find(r => r.race === result.race), result));
      summary(data, forecast);
      const failed = data.races.filter(r => r.status === 'error' || r.refresh_error).length;
      const staleMinutes = Math.max(5, (data.refresh_interval_minutes || 10) * 3);
      const stale = !data.complete && Date.now() - Date.parse(data.updated_at) > staleMinutes * 60000;
      status.textContent = '保存データ更新：' + formatTime(data.updated_at) +
        (fallback ? '。最新の更新確認に接続できず、保存済みの結果を表示。' : '。') +
        (failed ? `${failed}Rは取得失敗・前回結果を含みます。` : '') +
        (stale ? `結果データの更新が${staleMinutes}分以上止まっています。取得処理が遅れている可能性があります。` : '');
      status.classList.toggle('results-error', failed > 0 || stale || fallback);
      button.textContent = '結果を再取得'; lastData = data;
      if (data.complete && refreshTimer) {
        clearInterval(refreshTimer); refreshTimer = null;
      } else if (!data.complete && !refreshTimer) {
        refreshTimer = setInterval(() => {
          if (!document.hidden) loadResults();
        }, 60000);
      }
    } catch (error) {
      status.textContent = '最新結果への更新に失敗しました。' + (lastData ? 'このページに保存された印と着順を表示しています。' : '時間をおいて再取得してください。');
      console.warn('NAR results update failed', error);
      status.classList.add('results-error');
    } finally { button.disabled = false; panel.setAttribute('aria-busy', 'false'); }
  }
  button.addEventListener('click', () => loadResults(true));
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && lastData && !lastData.complete) loadResults(true);
  });
  if (lastData && !lastData.complete) {
    refreshTimer = setInterval(() => {
      if (!document.hidden) loadResults();
    }, 60000);
  }
  // Saved marks/finishes are already in the HTML; refresh them on opening the page.
  loadResults();
}
