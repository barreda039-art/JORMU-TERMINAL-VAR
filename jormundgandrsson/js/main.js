/* ═══════════════════════════════════════════════════════
   RISK MODULE
═══════════════════════════════════════════════════════ */
function renderRiskModule() {
  renderRiskRules();
  renderCompounding();
  renderCorrMatrix();
}

function renderRiskRules() {
  const el = document.getElementById('risk-rules-content');
  if (!el) return;
  const r = JORM.risk;
  const m = JORM.metrics;

  const rules = [
    { name: 'Max Drawdown',       val: r.maxDrawdown + '%',   cur: Math.abs(m.maxDD) + '%',  status: Math.abs(m.maxDD) < r.maxDrawdown ? 'ok' : 'breach' },
    { name: 'Max Pérdida Diaria', val: r.maxDailyLoss + '%',  cur: '0.8%',                    status: 'ok' },
    { name: 'Max Posiciones',     val: r.maxPositions,        cur: JORM.positions.length,     status: JORM.positions.length < r.maxPositions ? 'ok' : 'breach' },
    { name: 'Max Exposición',     val: r.maxExposure + '%',   cur: '58%',                     status: 'ok' },
    { name: 'Max Pos. Individual',val: r.maxSinglePos + '%',  cur: '4.2%',                    status: 'ok' },
    { name: 'Riesgo por Trade',   val: r.riskPerTrade + '%',  cur: '1.0%',                    status: 'ok' },
    { name: 'Corr. Límite',       val: r.correlationLimit,    cur: '0.45',                    status: 'ok' },
    { name: 'Circuit Breaker',    val: 'AUTO',                cur: r.circuitBreaker ? 'ACTIVO' : 'STANDBY', status: r.circuitBreaker ? 'breach' : 'ok' },
  ];

  el.innerHTML = rules.map(rule => `
    <div class="risk-rule-row">
      <span class="rule-name">${rule.name}</span>
      <span class="rule-val">${rule.val}</span>
      <span class="rule-status ${rule.status}">${rule.cur}</span>
    </div>
  `).join('');
}

function renderCompounding() {
  const el = document.getElementById('compound-content');
  if (!el) return;
  const nav = JORM.fund.currentNAV;
  const kelly = JORM.risk.riskPerTrade;

  const rows = [
    { key: 'Método',           val: 'Kelly Criterion ajustado',  cls: 'gold' },
    { key: 'Kelly Fracción',   val: (kelly / 4).toFixed(2) + 'x', cls: '' },
    { key: 'Riesgo/Trade',     val: kelly + '% del NAV',          cls: 'gold' },
    { key: 'Capital por Trade',val: '$' + (nav * kelly / 100).toFixed(2), cls: '' },
    { key: 'Proyección 30D',   val: '$' + (nav * Math.pow(1.003, 22)).toFixed(2), cls: 'green' },
    { key: 'Proyección 90D',   val: '$' + (nav * Math.pow(1.003, 66)).toFixed(2), cls: 'green' },
    { key: 'Proyección 1Y',    val: '$' + (nav * Math.pow(1.003, 252)).toFixed(2), cls: 'green' },
    { key: 'Reinversión',      val: '100% — Compounding total',   cls: 'gold' },
  ];

  el.innerHTML = rows.map(r => `
    <div class="compound-row">
      <span class="compound-key">${r.key}</span>
      <span class="compound-val ${r.cls}">${r.val}</span>
    </div>
  `).join('');
}

function renderCorrMatrix() {
  const el = document.getElementById('corr-matrix');
  if (!el) return;

  const assets = JORM.strategies.map(s => s.name.slice(0,8));
  const size = assets.length;
  const matrix = Array.from({length:size}, (_, i) =>
    Array.from({length:size}, (_, j) => {
      if (i === j) return 1;
      return Math.round((Math.random() * 1.6 - 0.8) * 100) / 100;
    })
  );

  function corrColor(v) {
    if (v >= 0.7)  return '#25C76F';
    if (v >= 0.3)  return 'rgba(37,199,111,0.5)';
    if (v <= -0.7) return '#FF4D4D';
    if (v <= -0.3) return 'rgba(255,77,77,0.5)';
    return 'var(--text3)';
  }

  el.innerHTML = `
    <table class="corr-table">
      <thead><tr><th></th>${assets.map(a => `<th>${a}</th>`).join('')}</tr></thead>
      <tbody>
        ${matrix.map((row, i) => `
          <tr>
            <th>${assets[i]}</th>
            ${row.map((v, j) => `
              <td class="corr-cell" style="color:${corrColor(v)}">
                ${v === 1 ? '—' : v.toFixed(2)}
              </td>
            `).join('')}
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

/* ═══════════════════════════════════════════════════════
   CONFIG MODULE
═══════════════════════════════════════════════════════ */
function renderConfigModule() {
  renderBrokerConfig();
  renderDataSourceConfig();
  renderFundConfig();
}

function renderBrokerConfig() {
  const el = document.getElementById('config-brokers');
  if (!el) return;

  el.innerHTML = `
    <div class="config-field">
      <div class="config-label">CAPITAL.COM — API KEY</div>
      <input class="inst-input" style="width:100%" type="password" placeholder="sk-..." value="${JORM.apiKeys.capitalcom_key}" oninput="JORM.apiKeys.capitalcom_key=this.value">
    </div>
    <div class="config-field">
      <div class="config-label">CAPITAL.COM — API SECRET</div>
      <input class="inst-input" style="width:100%" type="password" placeholder="secret..." value="${JORM.apiKeys.capitalcom_secret}" oninput="JORM.apiKeys.capitalcom_secret=this.value">
    </div>
    <div class="config-field">
      <div class="config-label">CAPITAL.COM — ENTORNO</div>
      <select class="inst-select" style="width:100%" onchange="JORM.apiKeys.capitalcom_env=this.value">
        <option value="demo" ${JORM.apiKeys.capitalcom_env==='demo'?'selected':''}>DEMO (api-capital.com/demo)</option>
        <option value="live" ${JORM.apiKeys.capitalcom_env==='live'?'selected':''}>LIVE (api-capital.com)</option>
      </select>
    </div>
    <div class="config-field">
      <div class="config-label">IB — TWS PORT</div>
      <input class="inst-input" style="width:100%" type="number" value="${JORM.apiKeys.ib_port}" oninput="JORM.apiKeys.ib_port=+this.value">
    </div>
    <div class="config-field">
      <div class="config-label">IB — CLIENT ID</div>
      <input class="inst-input" style="width:100%" type="number" value="${JORM.apiKeys.ib_client_id}" oninput="JORM.apiKeys.ib_client_id=+this.value">
    </div>
    <div style="grid-column:1/-1;display:flex;gap:6px;margin-top:4px;flex-wrap:wrap">
      <button class="hdr-btn gold-btn" style="padding:6px 18px;font-size:10px;letter-spacing:2px" onclick="connectCapitalCom()">▶ CONECTAR CAPITAL.COM</button>
      <button class="hdr-btn red-btn" onclick="disconnectCapitalCom()">■ DESCONECTAR</button>
      <button class="hdr-btn" onclick="startLiveStreaming()">⚡ INICIAR STREAMING</button>
      <button class="hdr-btn" onclick="testBrokerConnection('ib')">TEST IB TWS</button>
      <button class="hdr-btn" onclick="saveConfig()">GUARDAR CONFIG</button>
    </div>
    <div style="grid-column:1/-1;margin-top:6px;padding:8px;background:var(--bg2);border:1px solid var(--border2)">
      <div style="font-size:8px;color:var(--gold);letter-spacing:1px;margin-bottom:6px">ESTADO DE CONEXIÓN</div>
      <div id="connection-status-detail" style="font-size:9px;color:var(--text3)">
        Sin conectar — Presiona CONECTAR CAPITAL.COM para iniciar sesión
      </div>
    </div>
  `;
}

function renderDataSourceConfig() {
  const el = document.getElementById('config-datasources');
  if (!el) return;

  const sources = [
    { key: 'alpha_vantage', label: 'ALPHA VANTAGE KEY', ph: 'AV...' },
    { key: 'finnhub',       label: 'FINNHUB API KEY',   ph: 'fhk_...' },
    { key: 'polygon',       label: 'POLYGON.IO KEY',    ph: 'pk_...' },
  ];

  el.innerHTML = sources.map(s => `
    <div class="config-field">
      <div class="config-label">${s.label}</div>
      <input class="inst-input" style="width:100%" type="password" placeholder="${s.ph}"
        value="${JORM.apiKeys[s.key]}" oninput="JORM.apiKeys['${s.key}']=this.value">
    </div>
  `).join('') + `
    <div style="grid-column:1/-1;padding:8px;background:var(--bg2);border:1px solid var(--border2)">
      <div style="font-size:8px;color:var(--gold);letter-spacing:1px;margin-bottom:6px">FUENTES GRATUITAS (SIN KEY)</div>
      ${['FRED (Federal Reserve)','CFTC COT Reports','CBOE VIX Data','US Treasury Yields','BLS (CPI/PPI)','ForexFactory Calendar'].map(s => `
        <div style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:9px">
          <div style="width:6px;height:6px;border-radius:50%;background:var(--green)"></div>
          <span style="color:var(--text2)">${s}</span>
          <span style="color:var(--green);margin-left:auto">ACTIVO</span>
        </div>
      `).join('')}
    </div>
  `;
}

function renderFundConfig() {
  const el = document.getElementById('config-fund');
  if (!el) return;
  const r = JORM.risk;

  el.innerHTML = `
    <div class="config-field">
      <div class="config-label">MAX DRAWDOWN (%)</div>
      <input class="inst-input" style="width:100%" type="number" value="${r.maxDrawdown}" oninput="JORM.risk.maxDrawdown=+this.value">
    </div>
    <div class="config-field">
      <div class="config-label">MAX PÉRDIDA DIARIA (%)</div>
      <input class="inst-input" style="width:100%" type="number" step="0.5" value="${r.maxDailyLoss}" oninput="JORM.risk.maxDailyLoss=+this.value">
    </div>
    <div class="config-field">
      <div class="config-label">MAX POSICIONES SIMULTÁNEAS</div>
      <input class="inst-input" style="width:100%" type="number" value="${r.maxPositions}" oninput="JORM.risk.maxPositions=+this.value">
    </div>
    <div class="config-field">
      <div class="config-label">RIESGO POR TRADE (%)</div>
      <input class="inst-input" style="width:100%" type="number" step="0.25" value="${r.riskPerTrade}" oninput="JORM.risk.riskPerTrade=+this.value">
    </div>
    <div class="config-field">
      <div class="config-label">MAX EXPOSICIÓN TOTAL (%)</div>
      <input class="inst-input" style="width:100%" type="number" value="${r.maxExposure}" oninput="JORM.risk.maxExposure=+this.value">
    </div>
    <div class="config-field">
      <div class="config-label">LÍMITE CORRELACIÓN</div>
      <input class="inst-input" style="width:100%" type="number" step="0.05" value="${r.correlationLimit}" oninput="JORM.risk.correlationLimit=+this.value">
    </div>
    <div style="grid-column:1/-1;display:flex;gap:6px;margin-top:4px">
      <button class="hdr-btn gold-btn" onclick="saveConfig()">GUARDAR PARÁMETROS</button>
    </div>
  `;
}

function testBrokerConnection(broker) {
  JORM.alerts.unshift({ type: 'info', text: `Probando conexión ${broker.toUpperCase()}...`, time: JORM.now() });
  renderAlerts();
  setTimeout(() => {
    JORM.alerts.unshift({ type: 'warn', text: `${broker.toUpperCase()}: Configure API key en CONFIG para conectar`, time: JORM.now() });
    renderAlerts();
  }, 1500);
}

function saveConfig() {
  JORM.save();
  JORM.alerts.unshift({ type: 'ok', text: 'Configuración guardada en localStorage', time: JORM.now() });
  renderAlerts();
}

/* ═══════════════════════════════════════════════════════
   MAIN.JS — Entry point
═══════════════════════════════════════════════════════ */

/* ── NAVIGATION ── */
function showModule(name) {
  document.querySelectorAll('.module').forEach(m => m.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));

  const mod = document.getElementById('module-' + name);
  const btn = document.getElementById('nav-' + name);
  if (mod) mod.classList.add('active');
  if (btn) btn.classList.add('active');

  if (name === 'dashboard')  { renderDashboard(); initAllCharts(); }
  if (name === 'autopsia')   { renderAutopsia(); setTimeout(initVolProfileChart, 100); }
  if (name === 'strategies') { renderStrategiesModule(); }
  if (name === 'positions')  { renderPositionsModule(); }
  if (name === 'risk')       { renderRiskModule(); setTimeout(() => { initDrawdownChart(); initPnlHistChart(); }, 100); }
  if (name === 'icaro')      { renderIcaroModule(); }
  if (name === 'config')     { renderConfigModule(); }
}

function renderPositionsModule() {
  const summary = document.getElementById('pos-summary');
  const fullBody = document.getElementById('positions-full-body');
  const histBody = document.getElementById('history-body');
  const histCount = document.getElementById('history-count');

  const longs  = JORM.positions.filter(p => p.side === 'BUY');
  const shorts = JORM.positions.filter(p => p.side === 'SELL');
  const openPnl = JORM.positions.reduce((s, p) => s + p.pnl, 0);

  if (summary) summary.innerHTML = [
    { l:'POSICIONES LARGAS', v:longs.length, c:'green' },
    { l:'POSICIONES CORTAS', v:shorts.length, c:'red' },
    { l:'PNL ABIERTO', v:(openPnl>=0?'+$':'-$')+Math.abs(openPnl).toFixed(2), c:openPnl>=0?'green':'red' },
    { l:'EXPOSICIÓN BRUTA', v:'$'+(JORM.positions.length*10000).toLocaleString(), c:'' },
    { l:'CAPITAL LIBRE', v:(JORM.risk.maxExposure-58)+'% disponible', c:'gold' },
  ].map(i => `<div class="pos-summary-cell"><div class="metric-lbl">${i.l}</div><div class="metric-val ${i.c}" style="font-size:14px">${i.v}</div></div>`).join('');

  if (fullBody) fullBody.innerHTML = JORM.positions.map(p => `
    <tr>
      <td class="muted">${JORM.timestamp()}</td>
      <td class="sym">${p.symbol}</td>
      <td class="gold">${p.strategy}</td>
      <td class="${p.side==='BUY'?'long':'short'}">${p.side==='BUY'?'LONG':'SHORT'}</td>
      <td>${p.size}</td>
      <td>${p.entry.toLocaleString()}</td>
      <td>${p.current.toLocaleString()}</td>
      <td style="color:var(--red)">${p.sl}</td>
      <td style="color:var(--green)">${p.tp}</td>
      <td class="${p.pnl>=0?'pos':'neg'}">${p.pnl>=0?'+':''}$${Math.abs(p.pnl).toFixed(2)}</td>
      <td class="${p.pnlPct>=0?'pos':'neg'}">${p.pnlPct>=0?'+':''}${p.pnlPct.toFixed(2)}%</td>
      <td class="muted">${p.duration}</td>
      <td class="gold">—</td>
      <td><button class="hdr-btn red-btn" onclick="closePosition('${p.id}')">CERRAR</button></td>
    </tr>
  `).join('') || '<tr><td colspan="14" style="text-align:center;color:var(--text4);padding:16px">Sin posiciones abiertas</td></tr>';

  if (histCount) histCount.textContent = JORM.tradeHistory.length + ' trades cerrados';
  if (histBody) histBody.innerHTML = JORM.tradeHistory.slice(0,50).map(t => `
    <tr>
      <td class="muted">${t.date}</td>
      <td class="sym">${t.symbol}</td>
      <td class="gold">${t.strategy}</td>
      <td class="${t.side==='BUY'?'long':'short'}">${t.side==='BUY'?'LONG':'SHORT'}</td>
      <td>${t.entry}</td>
      <td>${t.exit}</td>
      <td class="${t.pnl>=0?'pos':'neg'}">${t.pnl>=0?'+':''}$${Math.abs(t.pnl).toFixed(2)}</td>
      <td class="${t.pnlPct>=0?'pos':'neg'}">${t.pnlPct>=0?'+':''}${t.pnlPct.toFixed(2)}%</td>
      <td class="muted">${t.duration}</td>
      <td class="gold">${t.rr}</td>
    </tr>
  `).join('');
}

/* ── MODE SWITCH ── */
function setMode(mode) {
  JORM.mode = mode;
  document.getElementById('btn-demo').classList.toggle('active', mode === 'DEMO');
  document.getElementById('btn-demo').classList.toggle('demo', mode === 'DEMO');
  document.getElementById('btn-live').classList.toggle('active', mode === 'LIVE');
  document.getElementById('btn-live').classList.toggle('live', mode === 'LIVE');
  JORM.alerts.unshift({ type: mode === 'LIVE' ? 'warn' : 'ok', text: `Modo cambiado a ${mode}`, time: JORM.now() });
  renderBrokerStatus();
  renderAlerts();
}

/* ── BROKER STATUS ── */
function renderBrokerStatus() {
  const el = document.getElementById('broker-status');
  if (!el) return;
  el.innerHTML = `
    <div class="broker-pill">
      <div class="broker-dot ${JORM.mode === 'DEMO' ? 'demo-mode' : 'disconnected'}"></div>
      <span style="color:${JORM.mode==='DEMO'?'var(--blue)':'var(--text3)'}">CAPITAL.COM</span>
      <span style="color:${JORM.mode==='DEMO'?'var(--blue)':'var(--text4)'}"> ${JORM.mode}</span>
    </div>
    <div class="broker-pill">
      <div class="broker-dot disconnected"></div>
      <span style="color:var(--text3)">IB TWS</span>
      <span style="color:var(--text4)"> OFFLINE</span>
    </div>
  `;
}

/* ── CLOCK ── */
function startClock() {
  const el = document.getElementById('system-clock');
  function update() {
    if (el) el.textContent = new Date().toTimeString().slice(0, 8);
  }
  update();
  setInterval(update, 1000);
}

/* ── TICKER ── */
function renderTicker() {
  const el = document.getElementById('ticker-inner');
  if (!el) return;
  const items = [...JORM.tickerSymbols, ...JORM.tickerSymbols];
  el.innerHTML = items.map(t => `
    <div class="tick-item">
      <span class="tick-sym">${t.sym}</span>
      <span class="tick-price">${t.price.toLocaleString()}</span>
      <span class="tick-chg ${t.chg > 0 ? 'up' : t.chg < 0 ? 'dn' : 'flat'}">
        ${t.chg > 0 ? '+' : ''}${t.chg.toFixed(2)}%
      </span>
    </div>
  `).join('');
}

/* ── LIVE TICKER SIMULATION ── */
function startTickerUpdates() {
  setInterval(() => {
    JORM.tickerSymbols.forEach(t => {
      t.price = Math.round(t.price * (1 + (Math.random() - 0.5) * 0.0003) * 10000) / 10000;
      t.chg   = Math.round((t.chg + (Math.random() - 0.5) * 0.05) * 100) / 100;
    });
    renderTicker();
  }, 3000);
}

/* ── BOOT SEQUENCE ── */
function boot() {
  JORM.load();

  const steps = [
    [5,  'LOADING CORE MODULES...'],
    [20, 'INITIALIZING DATA PIPELINE...'],
    [40, 'CONNECTING CAPITAL.COM API (DEMO)...'],
    [55, 'LOADING STRATEGIES FOLDER...'],
    [70, 'INITIALIZING RISK MANAGER...'],
    [85, 'LOADING MARKET DATA...'],
    [95, 'STARTING AUTOPSIA ENGINE...'],
    [100,'SYSTEM READY — JORMUNDGANDRSSON TERMINAL'],
  ];

  const bar    = document.getElementById('boot-bar');
  const status = document.getElementById('boot-status');
  let step = 0;

  const interval = setInterval(() => {
    if (step >= steps.length) {
      clearInterval(interval);
      setTimeout(() => {
        const overlay = document.getElementById('boot-overlay');
        overlay.classList.add('hidden');
        setTimeout(() => overlay.style.display = 'none', 600);
        initSystem();
      }, 400);
      return;
    }
    bar.style.width    = steps[step][0] + '%';
    status.textContent = steps[step][1];
    step++;
  }, 220);
}

function initSystem() {
  startClock();
  renderTicker();
  startTickerUpdates();
  renderBrokerStatus();
  setMode('DEMO');

  /* init demo mode buttons */
  document.getElementById('btn-demo').classList.add('active', 'demo');

  showModule('dashboard');
}

/* ── START ── */
window.addEventListener('DOMContentLoaded', boot);
