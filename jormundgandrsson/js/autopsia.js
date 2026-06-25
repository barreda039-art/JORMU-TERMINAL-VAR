/* ═══════════════════════════════════════════════════════
   JORMUNDGANDRSSON — AUTOPSIA DE MERCADO
   Bloomberg-style institutional market analysis
═══════════════════════════════════════════════════════ */

function renderAutopsia() {
  renderRegime();
  renderCalendar();
  renderFlows();
  renderCorrelations();
  renderNewsFlow();
  renderOrderFlow();
  renderOptions();
  renderQuantTech();
  renderOpportunities();
}

/* ── RÉGIMEN MACRO ── */
function renderRegime() {
  const el = document.getElementById('regime-content');
  const badge = document.getElementById('regime-badge');
  if (!el) return;

  const mk = JORM.market;
  const isBull = mk.regime === 'RISK-ON';

  if (badge) {
    badge.textContent = mk.regime;
    badge.style.color = isBull ? 'var(--green)' : 'var(--red)';
    badge.style.borderColor = isBull ? 'var(--green)' : 'var(--red)';
  }

  const rows = [
    { key: 'RÉGIMEN',    val: mk.regime, cls: isBull ? 'bull' : 'bear' },
    { key: 'VIX',        val: mk.vix.toFixed(1), cls: mk.vix < 20 ? 'bull' : mk.vix < 30 ? 'neut' : 'bear' },
    { key: 'DXY',        val: mk.dxy.toFixed(1), cls: 'neut' },
    { key: 'T10Y YIELD', val: mk.t10y.toFixed(2) + '%', cls: mk.t10y > 4.5 ? 'bear' : 'neut' },
    { key: 'SP500',      val: mk.sp500.toLocaleString(), cls: 'bull' },
    { key: 'GOLD',       val: '$' + mk.gold.toLocaleString(), cls: 'bull' },
    { key: 'OIL',        val: '$' + mk.oil.toFixed(2), cls: 'neut' },
    { key: 'FEAR/GREED', val: mk.fearGreed + ' — ' + (mk.fearGreed > 60 ? 'GREED' : mk.fearGreed > 40 ? 'NEUTRAL' : 'FEAR'), cls: mk.fearGreed > 60 ? 'bull' : mk.fearGreed > 40 ? 'neut' : 'bear' },
    { key: 'PUT/CALL',   val: mk.putCallRatio.toFixed(2), cls: mk.putCallRatio < 0.8 ? 'bull' : mk.putCallRatio > 1.1 ? 'bear' : 'neut' },
  ];

  const score = isBull ? 78 : 35;

  el.innerHTML = `
    <div class="regime-score">
      <div class="regime-score-val ${isBull ? 'bull' : 'bear'}">${score}</div>
      <div class="regime-score-label">RISK SCORE · ${mk.regime}</div>
    </div>
    ${rows.map(r => `
      <div class="regime-row">
        <span class="regime-key">${r.key}</span>
        <span class="regime-val ${r.cls}">${r.val}</span>
      </div>
    `).join('')}
  `;
}

/* ── CALENDARIO MACRO ── */
function renderCalendar() {
  const el = document.getElementById('calendar-content');
  if (!el) return;

  const events = [
    { time: '08:30', name: 'Initial Jobless Claims', impact: 'MED', country: 'US', forecast: '215K', prev: '219K' },
    { time: '10:00', name: 'ISM Services PMI',       impact: 'HIGH', country: 'US', forecast: '52.5', prev: '51.4' },
    { time: '14:00', name: 'FOMC Meeting Minutes',   impact: 'HIGH', country: 'US', forecast: '—', prev: '—' },
    { time: '15:30', name: 'Fed Speaker Waller',     impact: 'MED', country: 'US', forecast: '—', prev: '—' },
    { time: 'TOM',   name: 'NFP Non-Farm Payrolls',  impact: 'HIGH', country: 'US', forecast: '185K', prev: '199K' },
    { time: 'TOM',   name: 'Unemployment Rate',      impact: 'HIGH', country: 'US', forecast: '3.9%', prev: '3.9%' },
    { time: 'FRI',   name: 'CPI (Core) YoY',         impact: 'HIGH', country: 'US', forecast: '3.6%', prev: '3.8%' },
    { time: 'FRI',   name: 'Michigan Sentiment',     impact: 'MED', country: 'US', forecast: '79.0', prev: '77.9' },
  ];

  el.innerHTML = events.map(e => `
    <div class="cal-item">
      <div class="cal-impact ${e.impact}"></div>
      <div class="cal-time">${e.time}</div>
      <div class="cal-info">
        <div class="cal-name">${e.name}</div>
        <div class="cal-detail">Est: <span style="color:var(--text1)">${e.forecast}</span> · Prev: ${e.prev}</div>
      </div>
      <div class="cal-forecast" style="color:${e.impact === 'HIGH' ? 'var(--red)' : e.impact === 'MED' ? 'var(--yellow)' : 'var(--text3)'}">
        ${e.impact}
      </div>
    </div>
  `).join('');
}

/* ── FLUJOS DE CAPITAL (COT + positioning) ── */
function renderFlows() {
  const el = document.getElementById('flows-content');
  if (!el) return;

  const flows = [
    { asset: 'EURUSD', longPct: 42, shortPct: 58, signal: 'bear', cot: 'Short especulativo' },
    { asset: 'GBPUSD', longPct: 61, shortPct: 39, signal: 'bull', cot: 'Long especulativo' },
    { asset: 'GOLD',   longPct: 74, shortPct: 26, signal: 'bull', cot: 'Comerciales largos' },
    { asset: 'OIL',    longPct: 55, shortPct: 45, signal: 'neut', cot: 'Neutro — consolidando' },
    { asset: 'SPX',    longPct: 67, shortPct: 33, signal: 'bull', cot: 'Smart money comprador' },
    { asset: 'BTC',    longPct: 71, shortPct: 29, signal: 'bull', cot: 'Retail alcista' },
  ];

  el.innerHTML = flows.map(f => `
    <div class="flow-row">
      <span class="flow-asset">${f.asset}</span>
      <div class="flow-bar-wrap">
        <div class="flow-long-bar" style="width:${f.longPct}%"></div>
        <div class="flow-short-bar" style="width:${f.shortPct}%"></div>
      </div>
      <span class="flow-pct" style="color:var(--text3)">${f.longPct}L</span>
      <span class="flow-signal ${f.signal}">${f.signal.toUpperCase()}</span>
    </div>
  `).join('');
}

/* ── CORRELACIONES ── */
function renderCorrelations() {
  const el = document.getElementById('corr-content');
  if (!el) return;

  const assets = ['SPX', 'NAS', 'VIX', 'DXY', 'GOLD', 'OIL'];
  const matrix = [
    [ 1.00,  0.94, -0.88, -0.42,  0.21,  0.38],
    [ 0.94,  1.00, -0.82, -0.38,  0.18,  0.35],
    [-0.88, -0.82,  1.00,  0.35, -0.24, -0.41],
    [-0.42, -0.38,  0.35,  1.00, -0.72, -0.58],
    [ 0.21,  0.18, -0.24, -0.72,  1.00,  0.44],
    [ 0.38,  0.35, -0.41, -0.58,  0.44,  1.00],
  ];

  function corrColor(v) {
    if (v === 1) return 'var(--text4)';
    if (v >= 0.7)  return 'var(--green)';
    if (v >= 0.3)  return 'rgba(37,199,111,0.5)';
    if (v <= -0.7) return 'var(--red)';
    if (v <= -0.3) return 'rgba(255,77,77,0.5)';
    return 'var(--text3)';
  }

  el.innerHTML = `
    <table class="corr-table">
      <thead>
        <tr>
          <th></th>
          ${assets.map(a => `<th>${a}</th>`).join('')}
        </tr>
      </thead>
      <tbody>
        ${matrix.map((row, i) => `
          <tr>
            <th>${assets[i]}</th>
            ${row.map((v, j) => `
              <td class="corr-cell" style="color:${corrColor(v)};background:${v === 1 ? 'var(--bg2)' : ''}">
                ${v === 1 ? '—' : v.toFixed(2)}
              </td>
            `).join('')}
          </tr>
        `).join('')}
      </tbody>
    </table>
    <div style="margin-top:8px;padding:4px 0;font-size:8px;color:var(--text4);display:flex;gap:12px">
      <span style="color:var(--green)">■ Alta positiva (>0.7)</span>
      <span style="color:var(--red)">■ Alta negativa (<-0.7)</span>
      <span style="color:var(--text3)">■ Baja correlación</span>
    </div>
  `;
}

/* ── NEWS FLOW ── */
const ALL_NEWS = [
  { headline: 'Fed Waller signals potential rate cuts if inflation continues to cool in coming months', source: 'Reuters', time: '09:45', impact: 'HIGH', sentiment: 'BULL', assets: ['SPX','GOLD','EURUSD'] },
  { headline: 'US ISM Services PMI beats expectations at 53.8 vs 52.5 forecast — economy resilient', source: 'Bloomberg', time: '10:02', impact: 'HIGH', sentiment: 'BULL', assets: ['SPX','DXY'] },
  { headline: 'Dollar weakens as treasury yields fall ahead of key jobs data Friday', source: 'FT', time: '08:30', impact: 'MED', sentiment: 'BEAR', assets: ['DXY','EURUSD','GOLD'] },
  { headline: 'ECB expected to hold rates at next meeting — eurozone inflation sticky', source: 'Reuters', time: '07:15', impact: 'MED', sentiment: 'NEUT', assets: ['EURUSD','GBPUSD'] },
  { headline: 'Oil inventories rise more than expected — WTI under pressure near $81', source: 'EIA', time: '10:30', impact: 'HIGH', sentiment: 'BEAR', assets: ['OIL'] },
  { headline: 'Gold hits 2-week high as real yields decline and safe-haven demand increases', source: 'Kitco', time: '11:20', impact: 'MED', sentiment: 'BULL', assets: ['GOLD'] },
  { headline: 'NVIDIA earnings: Q3 guidance beats by 15% — AI demand remains robust', source: 'CNBC', time: '16:05', impact: 'HIGH', sentiment: 'BULL', assets: ['NAS100'] },
  { headline: 'China PMI data disappoints again — risk-off sentiment building in Asia session', source: 'WSJ', time: '02:00', impact: 'MED', sentiment: 'BEAR', assets: ['SPX','OIL'] },
  { headline: 'UK inflation falls to 3.2% YoY — GBP selling continues ahead of BoE meeting', source: 'BBC', time: '06:00', impact: 'HIGH', sentiment: 'BEAR', assets: ['GBPUSD'] },
  { headline: 'Bitcoin ETF inflows hit $240M — institutional accumulation resumes', source: 'CoinDesk', time: '13:00', impact: 'LOW', sentiment: 'BULL', assets: ['BTC'] },
];

let currentNewsFilter = 'ALL';

function renderNewsFlow() {
  const el = document.getElementById('news-content');
  if (!el) return;

  let news = ALL_NEWS;
  if (currentNewsFilter === 'BULL') news = news.filter(n => n.sentiment === 'BULL');
  if (currentNewsFilter === 'BEAR') news = news.filter(n => n.sentiment === 'BEAR');
  if (currentNewsFilter === 'HIGH') news = news.filter(n => n.impact === 'HIGH');

  el.innerHTML = news.map(n => `
    <div class="news-item">
      <div class="news-item-header">
        <span class="news-impact ${n.impact}">${n.impact}</span>
        <span class="news-sentiment ${n.sentiment}">${n.sentiment}</span>
        <span style="font-size:8px;color:var(--text4);margin-left:4px">${n.assets.join(' · ')}</span>
        <span class="news-source">${n.source}</span>
      </div>
      <div class="news-headline">${n.headline}</div>
      <div class="news-time">${n.time}</div>
    </div>
  `).join('');
}

function filterNews(f) {
  currentNewsFilter = f;
  document.querySelectorAll('.news-filter').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  renderNewsFlow();
}

/* ── ORDER FLOW ── */
function renderOrderFlow() {
  const el = document.getElementById('orderflow-content');
  if (!el) return;

  const levels = [
    { price: '5855', buyVol: 850, sellVol: 320, delta: +530 },
    { price: '5850', buyVol: 1240, sellVol: 890, delta: +350 },
    { price: '5847', buyVol: 980, sellVol: 1150, delta: -170 },
    { price: '5845', buyVol: 2100, sellVol: 780, delta: +1320 },
    { price: '5842', buyVol: 560, sellVol: 940, delta: -380 },
    { price: '5840', buyVol: 1800, sellVol: 620, delta: +1180 },
    { price: '5838', buyVol: 430, sellVol: 1100, delta: -670 },
    { price: '5835', buyVol: 750, sellVol: 430, delta: +320 },
  ];

  const maxVol = Math.max(...levels.map(l => Math.max(l.buyVol, l.sellVol)));

  el.innerHTML = `
    <div style="display:grid;grid-template-columns:52px 1fr 50px 46px;gap:3px;padding:3px 0;margin-bottom:3px;font-size:8px;color:var(--text4);border-bottom:1px solid var(--border)">
      <span>PRECIO</span><span>VOLUMEN</span><span style="text-align:right">VOL</span><span style="text-align:right">DELTA</span>
    </div>
    ${levels.map(l => `
      <div class="of-row">
        <span class="of-price">${l.price}</span>
        <div class="of-bar-wrap">
          <div class="of-bar buy" style="width:${l.buyVol/maxVol*100}%"></div>
          <div class="of-bar sell" style="position:absolute;right:0;top:0;height:100%;width:${l.sellVol/maxVol*100}%;background:rgba(255,77,77,0.35)"></div>
        </div>
        <span class="of-vol">${(l.buyVol+l.sellVol/1000).toFixed(1)}K</span>
        <span class="of-delta ${l.delta >= 0 ? 'pos' : 'neg'}">${l.delta >= 0 ? '+' : ''}${l.delta}</span>
      </div>
    `).join('')}
    <div style="margin-top:6px;padding:5px;background:var(--bg2);border:1px solid var(--border2);font-size:9px">
      <div style="display:flex;justify-content:space-between;margin-bottom:3px">
        <span style="color:var(--text3)">DELTA ACUMULADO</span>
        <span style="color:var(--green);font-weight:700">+2,150</span>
      </div>
      <div style="display:flex;justify-content:space-between;margin-bottom:3px">
        <span style="color:var(--text3)">AGRESIVOS COMPRADORES</span>
        <span style="color:var(--green)">58%</span>
      </div>
      <div style="display:flex;justify-content:space-between">
        <span style="color:var(--text3)">SEÑAL DE PRESIÓN</span>
        <span style="color:var(--green);font-weight:700">COMPRADORA</span>
      </div>
    </div>
  `;
}

function updateOrderFlow() { renderOrderFlow(); }

/* ── OPTIONS + VIX ── */
function renderOptions() {
  const el = document.getElementById('options-content');
  const badge = document.getElementById('vix-badge');
  if (!el) return;

  const vix = JORM.market.vix;
  const regime = vix < 15 ? { lbl: 'COMPLACENCIA', cls: 'low' } : vix < 25 ? { lbl: 'NORMAL', cls: 'med' } : { lbl: 'MIEDO', cls: 'high' };

  if (badge) badge.textContent = 'VIX: ' + vix.toFixed(1);

  el.innerHTML = `
    <div class="vix-gauge">
      <div>
        <div class="vix-val ${regime.cls}">${vix.toFixed(1)}</div>
        <div class="vix-label">VIX INDEX</div>
      </div>
      <div>
        <div class="vix-regime" style="color:${vix < 20 ? 'var(--green)' : vix < 30 ? 'var(--yellow)' : 'var(--red)'}">${regime.lbl}</div>
        <div style="font-size:8px;color:var(--text4);margin-top:3px">Perc. 30D: 42%</div>
      </div>
    </div>
    <div class="opt-section">
      <div class="opt-section-title">PUT/CALL RATIO</div>
      <div class="opt-row"><span class="opt-key">Total P/C</span><span class="opt-val bullish">0.84</span></div>
      <div class="opt-row"><span class="opt-key">Equity P/C</span><span class="opt-val bullish">0.71</span></div>
      <div class="opt-row"><span class="opt-key">Index P/C</span><span class="opt-val bearish">1.12</span></div>
    </div>
    <div class="opt-section">
      <div class="opt-section-title">GAMMA EXPOSURE (GEX)</div>
      <div class="opt-row"><span class="opt-key">GEX Net</span><span class="opt-val bullish">+$4.2B</span></div>
      <div class="opt-row"><span class="opt-key">Call Wall</span><span class="opt-val gold">5,900</span></div>
      <div class="opt-row"><span class="opt-key">Put Wall</span><span class="opt-val bearish">5,750</span></div>
      <div class="opt-row"><span class="opt-key">Max Pain</span><span class="opt-val gold">5,850</span></div>
    </div>
    <div class="opt-section">
      <div class="opt-section-title">SKEW + IV</div>
      <div class="opt-row"><span class="opt-key">IV Rank</span><span class="opt-val">34%</span></div>
      <div class="opt-row"><span class="opt-key">SKEW</span><span class="opt-val">128.4</span></div>
      <div class="opt-row"><span class="opt-key">0DTE Volume</span><span class="opt-val bearish">HIGH</span></div>
    </div>
  `;
}

/* ── QUANT TECH ── */
function renderQuantTech() {
  const el = document.getElementById('quant-tech-content');
  if (!el) return;

  const panels = [
    {
      title: 'MOMENTUM SCORES',
      rows: [
        { key: 'SPX 1H', val: '+72', cls: 'green' },
        { key: 'SPX 4H', val: '+84', cls: 'green' },
        { key: 'SPX D',  val: '+61', cls: 'green' },
        { key: 'EURUSD 1H', val: '-38', cls: 'red' },
        { key: 'EURUSD 4H', val: '-52', cls: 'red' },
        { key: 'GOLD 4H', val: '+77', cls: 'green' },
      ],
    },
    {
      title: 'Z-SCORE PRECIOS',
      rows: [
        { key: 'SPX vs 20MA', val: '+1.84σ', cls: 'yellow' },
        { key: 'EURUSD vs MA', val: '-2.10σ', cls: 'green' },
        { key: 'GOLD vs MA', val: '+0.92σ', cls: '' },
        { key: 'OIL vs MA', val: '-0.45σ', cls: '' },
        { key: 'VIX vs MA', val: '-1.23σ', cls: 'green' },
        { key: 'DXY vs MA', val: '+0.67σ', cls: '' },
      ],
    },
    {
      title: 'ESTRUCTURA DE MERCADO',
      rows: [
        { key: 'SPX Estructura', val: 'HH/HL ↑', cls: 'green' },
        { key: 'NAS Estructura', val: 'HH/HL ↑', cls: 'green' },
        { key: 'EUR Estructura', val: 'LH/LL ↓', cls: 'red' },
        { key: 'GOLD Estructura', val: 'HH/HL ↑', cls: 'green' },
        { key: 'Breadth A/D', val: '72% + adv', cls: 'green' },
        { key: 'Above 200MA', val: '68%', cls: 'green' },
      ],
    },
    {
      title: 'NIVELES CLAVE',
      rows: [
        { key: 'SPX Resistencia', val: '5,900', cls: 'red' },
        { key: 'SPX Soporte',     val: '5,780', cls: 'green' },
        { key: 'SPX VWAP',       val: '5,831', cls: 'yellow' },
        { key: 'GOLD POC',       val: '2,300', cls: 'yellow' },
        { key: 'EURUSD Soporte', val: '1.0790', cls: 'green' },
        { key: 'DXY Resistencia',val: '105.20', cls: 'red' },
      ],
    },
  ];

  el.innerHTML = panels.map(p => `
    <div class="qt-panel">
      <div class="qt-title">${p.title}</div>
      ${p.rows.map(r => `
        <div class="qt-row">
          <span class="qt-key">${r.key}</span>
          <span class="qt-val" style="color:${r.cls === 'green' ? 'var(--green)' : r.cls === 'red' ? 'var(--red)' : r.cls === 'yellow' ? 'var(--yellow)' : 'var(--text1)'}">${r.val}</span>
        </div>
      `).join('')}
    </div>
  `).join('');
}

/* ── OPORTUNIDADES DETECTADAS ── */
function renderOpportunities() {
  const el = document.getElementById('opp-content');
  const badge = document.getElementById('opp-count');
  if (!el) return;

  const opps = JORM.opportunities;
  if (badge) badge.textContent = opps.length + ' señales';

  el.innerHTML = opps.map(o => `
    <div class="opp-card">
      <div class="opp-score ${o.confidence.toLowerCase()}">${o.score}</div>
      <div class="opp-info">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:3px">
          <span class="opp-sym">${o.symbol}</span>
          <span class="opp-dir ${o.direction.toLowerCase()}">${o.direction === 'LONG' ? '▲ LONG' : '▼ SHORT'}</span>
          <span style="font-size:8px;color:var(--text3)">${o.strategy}</span>
        </div>
        <div class="opp-context">${o.context}</div>
      </div>
      <div class="opp-entry">
        <div class="opp-entry-price">${o.entryPrice.toLocaleString()}</div>
        <div class="opp-entry-label">ENTRADA</div>
        <div style="font-size:8px;margin-top:3px;color:var(--green)">TP: ${o.tp}</div>
        <div style="font-size:8px;color:var(--red)">SL: ${o.sl}</div>
      </div>
      <button class="opp-approve-btn" onclick="approveOpportunity('${o.symbol}')">APROBAR ▶</button>
    </div>
  `).join('') || '<div style="padding:16px;text-align:center;color:var(--text4)">Sin oportunidades detectadas</div>';
}

function approveOpportunity(symbol) {
  const opp = JORM.opportunities.find(o => o.symbol === symbol);
  if (!opp) return;

  if (!confirm(`Enviar señal al Risk Manager?\n${symbol} ${opp.direction} @ ${opp.entryPrice}\nSL: ${opp.sl} | TP: ${opp.tp}`)) return;

  JORM.alerts.unshift({
    type: 'warn',
    text: `Señal enviada a Risk Manager: ${symbol} ${opp.direction} — pendiente validación`,
    time: JORM.now(),
  });

  JORM.opportunities = JORM.opportunities.filter(o => o.symbol !== symbol);
  renderOpportunities();
  renderAlerts();

  setTimeout(() => {
    JORM.alerts.unshift({ type: 'ok', text: `Risk Manager validó: ${symbol} ${opp.direction} — ejecutando en Capital.com DEMO`, time: JORM.now() });
    renderAlerts();
  }, 2000);
}
