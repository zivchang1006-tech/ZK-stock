let records = [];

async function loadFromJson() {
  const badge = document.getElementById('lastUpdateBadge');
  badge.innerText = '讀取 data.json 中...';
  try {
    const res = await fetch('./data.json?t=' + Date.now());
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    records = data.map(function(d) {
      let pct = d.tsm_pct;
      if (pct === undefined) {
        const prevP = (d.tsm_adr || 0) - (d.tsm_chg || 0);
        pct = prevP > 0 ? Number(((d.tsm_chg / prevP) * 100).toFixed(2)) : 0;
      }
      return Object.assign({}, d, { tsm_pct: pct });
    });
    const first = records.at(0);
    badge.innerText = first && first.update_time ? '自動更新：' + first.update_time : '已載入 ' + records.length + ' 筆';
    renderTable();
  } catch (e) {
    badge.innerText = '⚠️ 讀取異常：' + e.message;
    document.getElementById('tableBody').innerHTML = '<tr><td colspan="19" style="text-align:center;padding:30px;color:#f87171">讀取 data.json 失敗：' + e.message + '</td></tr>';
  }
}

function numClass(v) { return v > 0 ? 'tw-up' : (v < 0 ? 'tw-down' : ''); }
function dotHtml(s) { return '<i class="dot dot-' + s + '"></i>'; }

function evaluateRow(c, p) {
  const items = []; let score = 0;
  const add = function(n, st, pt, desc) { score += pt; items.push({ name: n, status: st, pts: pt, desc: desc }); };

  if (c.vol < 8000) add('現貨量', 'green', -1, c.vol + '億 (<8000億)');
  else add('現貨量', 'red', 1, c.vol + '億 (>=8000億)');

  if (p && p.margin > 0) {
    if (c.margin > p.margin) add('融資餘額', 'green', -1, '較前日增');
    else if (c.margin < p.margin) add('融資餘額', 'red', 1, '較前日減');
    else add('融資餘額', 'neutral', 0, '持平');
  } else add('融資餘額', 'neutral', 0, '無前日資料');

  if (p && p.usd > 0) {
    if (c.usd < p.usd) add('美元台幣', 'red', 1, '台幣升值');
    else if (c.usd > p.usd) add('美元台幣', 'green', -1, '台幣貶值');
    else add('美元台幣', 'neutral', 0, '持平');
  } else add('美元台幣', 'neutral', 0, '無前日資料');

  [['外資現貨', c.foreign], ['投信現貨', c.trust], ['自營商現貨', c.dealer]].forEach(function(x) {
    const lbl = x.at(0), v = x.at(1);
    if (v > 0) add(lbl, 'red', 1, '買超 ' + v + '億');
    else if (v < 0) add(lbl, 'green', -1, '賣超 ' + v + '億');
    else add(lbl, 'neutral', 0, '0億');
  });

  if (p) {
    if (c.f_oi < p.f_oi) add('外資期未平倉', 'green', -1, '空單增加');
    else if (c.f_oi > p.f_oi) add('外資期未平倉', 'red', 1, '空單減少');
    else add('外資期未平倉', 'neutral', 0, '持平');
  } else add('外資期未平倉', 'neutral', 0, '無前日資料');

  [['五大淨額', c.top5], ['十大淨額', c.top10]].forEach(function(x) {
    const lbl = x.at(0), v = x.at(1);
    if (v > 0) add(lbl, 'red', 1, '淨多 ' + v + '口');
    else if (v < 0) add(lbl, 'green', -1, '淨空 ' + v + '口');
    else add(lbl, 'neutral', 0, '0口');
  });

  if (c.pc_ratio > 0 && c.pc_ratio < 95) add('P/C比', 'green', -1, c.pc_ratio + '% (<95%)');
  else if (c.pc_ratio > 100) add('P/C比', 'red', 1, c.pc_ratio + '% (>100%)');
  else add('P/C比', 'neutral', 0, c.pc_ratio + '%');

  if (c.f_opt > 0) add('外資選擇權', 'red', 1, c.f_opt + '萬');
  else if (c.f_opt < 0) add('外資選擇權', 'green', -1, c.f_opt + '萬');
  else add('外資選擇權', 'neutral', 0, '0萬');

  [['小台散戶比', c.mtx_retail], ['微台散戶比', c.tmf_retail]].forEach(function(x) {
    const lbl = x.at(0), v = x.at(1);
    if (v > 0) add(lbl, 'green', -1, '散戶多 ' + v + '%');
    else if (v < 0) add(lbl, 'red', 1, '散戶空 ' + v + '%');
    else add(lbl, 'neutral', 0, '0%');
  });

  if (c.tsm_pct > 0) add('台積電ADR', 'red', 1, '+' + c.tsm_pct + '%');
  else if (c.tsm_pct < 0) add('台積電ADR', 'green', -1, c.tsm_pct + '%');
  else add('台積電ADR', 'neutral', 0, '0%');

  let tr = { text: '震盪整理', cls: 'badge-flat' };
  if (score >= 4) tr = { text: '強勢偏多', cls: 'badge-strong-up' };
  else if (score >= 1) tr = { text: '溫和偏多', cls: 'badge-up' };
  else if (score <= -4) tr = { text: '強勢偏空', cls: 'badge-strong-down' };
  else if (score <= -1) tr = { text: '溫和偏空', cls: 'badge-down' };
  return { score: score, trend: tr, items: items };
}

function renderTable() {
  records.sort(function(a, b) { return b.date.localeCompare(a.date); });
  const tbody = document.getElementById('tableBody');
  tbody.innerHTML = '';
  records.forEach(function(r, idx) {
    const ev = evaluateRow(r, records.at(idx + 1) || null);
    const st = function(n) { const f = ev.items.find(function(i) { return i.name === n; }); return f ? f.status : 'neutral'; };
    const row = document.createElement('tr');
    row.innerHTML =
      '<td class="sticky-col">' + r.date + '</td>' +
      '<td>' + Number(r.index).toLocaleString() + '</td>' +
      '<td>' + dotHtml(st('現貨量')) + r.vol + '</td>' +
      '<td>' + dotHtml(st('融資餘額')) + r.margin + '</td>' +
      '<td>' + dotHtml(st('美元台幣')) + r.usd + '</td>' +
      '<td class="' + numClass(r.foreign) + '">' + dotHtml(st('外資現貨')) + r.foreign + '</td>' +
      '<td class="' + numClass(r.trust) + '">' + dotHtml(st('投信現貨')) + r.trust + '</td>' +
      '<td class="' + numClass(r.dealer) + '">' + dotHtml(st('自營商現貨')) + r.dealer + '</td>' +
      '<td class="' + numClass(r.f_oi) + '">' + dotHtml(st('外資期未平倉')) + Number(r.f_oi).toLocaleString() + '</td>' +
      '<td class="' + numClass(r.top5) + '">' + dotHtml(st('五大淨額')) + Number(r.top5).toLocaleString() + '</td>' +
      '<td class="' + numClass(r.top10) + '">' + dotHtml(st('十大淨額')) + Number(r.top10).toLocaleString() + '</td>' +
      '<td>' + dotHtml(st('P/C比')) + r.pc_ratio + '%</td>' +
      '<td class="' + numClass(r.f_opt) + '">' + dotHtml(st('外資選擇權')) + Number(r.f_opt).toLocaleString() + '</td>' +
      '<td class="' + numClass(r.mtx_retail) + '">' + dotHtml(st('小台散戶比')) + r.mtx_retail + '%</td>' +
      '<td class="' + numClass(r.tmf_retail) + '">' + dotHtml(st('微台散戶比')) + r.tmf_retail + '%</td>' +
      '<td class="' + numClass(r.tsm_pct) + '">' + dotHtml(st('台積電ADR')) + r.tsm_pct + '%</td>' +
      '<td style="text-align:center"><span class="badge ' + ev.trend.cls + '">' + ev.trend.text + '</span></td>' +
      '<td style="text-align:center"><button class="score-btn ' + numClass(ev.score) + '" onclick="showDetails(' + idx + ')">' + (ev.score > 0 ? '+' + ev.score : ev.score) + ' 分</button></td>' +
      '<td style="text-align:center"><button class="action-link" onclick="editRow(' + idx + ')">編輯</button><button class="action-link del-link" onclick="deleteRow(' + idx + ')">刪除</button></td>';
    tbody.appendChild(row);
  });
}

function showDetails(idx) {
  const r = records.at(idx);
  const ev = evaluateRow(r, records.at(idx + 1) || null);
  document.getElementById('detailTitle').innerText = r.date + ' 分數明細（總分：' + (ev.score > 0 ? '+' + ev.score : ev.score) + ' 分）';
  document.getElementById('detailContent').innerHTML = ev.items.map(function(i) {
    return '<div class="detail-item"><div>' + dotHtml(i.status) + '<strong>' + i.name + '</strong> <span style="color:#94a3b8;font-size:12px">' + i.desc + '</span></div><span class="' + numClass(i.pts) + '">' + (i.pts > 0 ? '+' + i.pts : i.pts) + '</span></div>';
  }).join('');
  document.getElementById('detailModal').classList.add('active');
}

function openModal(isEdit) {
  if (!isEdit) { document.getElementById('dataForm').reset(); document.getElementById('editIndex').value = '-1'; document.getElementById('modalTitle').innerText = '新增每日盤後數據'; }
  document.getElementById('formModal').classList.add('active');
}
function closeModal() { document.getElementById('formModal').classList.remove('active'); }

function saveData(e) {
  e.preventDefault();
  const idx = parseInt(document.getElementById('editIndex').value);
  const item = {
    date: document.getElementById('f_date').value, index: +document.getElementById('f_index').value,
    vol: +document.getElementById('f_vol').value, margin: +document.getElementById('f_margin').value,
    usd: +document.getElementById('f_usd').value, foreign: +document.getElementById('f_foreign').value,
    trust: +document.getElementById('f_trust').value, dealer: +document.getElementById('f_dealer').value,
    f_oi: +document.getElementById('f_f_oi').value, top5: +document.getElementById('f_top5').value,
    top10: +document.getElementById('f_top10').value, pc_ratio: +document.getElementById('f_pc_ratio').value,
    f_opt: +document.getElementById('f_f_opt').value, mtx_retail: +document.getElementById('f_mtx_retail').value,
    tmf_retail: +document.getElementById('f_tmf_retail').value, tsm_pct: +document.getElementById('f_tsm_pct').value, tsm_adr: 0
  };
  if (idx >= 0) records.splice(idx, 1, item); else records.push(item);
  closeModal(); renderTable();
}

function editRow(idx) {
  const r = records.at(idx);
  document.getElementById('editIndex').value = idx;
  document.getElementById('modalTitle').innerText = '編輯盤後數據';
  ['date','index','vol','margin','usd','foreign','trust','dealer','f_oi','top5','top10','pc_ratio','f_opt','mtx_retail','tmf_retail','tsm_pct'].forEach(function(k) {
    document.getElementById('f_' + k).value = r[k];
  });
  openModal(true);
}

function deleteRow(idx) {
  if (confirm('確定要刪除 ' + records.at(idx).date + ' 嗎？')) { records.splice(idx, 1); renderTable(); }
}

loadFromJson();
