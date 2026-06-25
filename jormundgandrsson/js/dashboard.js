/* ═══════════════════════════════════════════════════════
   JORMUNDGANDRSSON — DASHBOARD MODULE
═══════════════════════════════════════════════════════ */

function renderDashboard() {
  renderHeaderMetrics();
  renderFundMetrics();
  renderFolderTree();
  renderTradeLog();
  renderPositionsTable();
  renderRiskGauges();
  renderAlerts();
}

/* ── HEADER METRICS (top bar) ── */
function renderHeaderMetrics() {
  const el = document.getElementById('header-metrics');
  if (!el) return;
  const m = JORM.metrics;
  const f = JORM.fund;

  const items = [
    { label: 'NAV',       val: '$' + f.currentNAV.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2}), cls: 'gold' },
    { label: 'PNL HOY',   val: JORM.formatCurrency(m.dailyPnL), cls: m.dailyPnL >= 0 ? 'pos' : 'neg' },
    { label: 'PNL TOTAL', val: JORM.formatCurrency(m.totalPnL), cls: m.totalPnL >= 0 ? 'pos' : 'neg' },
    { label: 'RETORNO',   val: JORM.formatPct(m.totalReturn), cls: m.totalReturn >= 0 ? 'pos' : 'neg' },
    { label: 'WIN RATE',  val: m.winRate + '%', cls: 'gold' },
    { label: 'SHARPE',    val: m.sharpe.toFixed(2), cls: 'gold' },
    { label: 'DRAWDOWN',  val: m.maxDD + '%', cls: 'neg' },
    { label: 'POSICIONES',val: JORM.positions.length + ' / ' + JORM.risk.maxPositions, cls: '' },
  ];

  el.innerHTML = items.map(i => `
    <div class="hdr-metric">
      <span class="hdr-metric-label">${i.label}</span>
      <span class="hdr-metric-val ${i.cls}">${i.val}</span>
    </div>
  `).join('');
}

/* ── FUND METRICS GRID ── */
function renderFundMetrics() {
  const el = document.getElementById('fund-metrics');
  if (!el) return;
  const m = JORM.metrics;
  const f = JORM.fund;

  const cards = [
    { label: 'CAPITAL NAV',    val: '$' + f.currentNAV.toLocaleString('en-US',{minimumFractionDigits:2}), cls: 'gold', sub: 'Fondo total', subcls: '' },
    { label: 'PNL TOTAL',      val: JORM.formatCurrency(m.totalPnL), cls: m.totalPnL >= 0 ? 'green' : 'red', sub: JORM.formatPct(m.totalReturn) + ' total', subcls: m.totalReturn >= 0 ? 'up' : 'dn' },
    { label: 'WIN RATE',       val: m.winRate + '%', cls: 'gold', sub: m.winTrades + 'W / ' + m.lossTrades + 'L', subcls: '' },
    { label: 'SHARPE RATIO',   val: m.sharpe.toFixed(2), cls: 'green', sub: 'Anualizado', subcls: '' },
    { label: 'MAX DRAWDOWN',   val: m.maxDD + '%', cls: 'red', sub: 'Desde HWM', subcls: '' },
    { label: 'PROFIT FACTOR',  val: m.profitFactor.toFixed(2), cls: 'green', sub: 'Gross P/L ratio', subcls: '' },
  ];

  el.innerHTML = cards.map(c => `
    <div class="metric-cell">
      <div class="metric-lbl">${c.label}</div>
      <div class="metric-val ${c.cls}">${c.val}</div>
      <div class="metric-sub ${c.subcls}">${c.sub}</div>
    </div>
  `).join('');
}

/* ── FOLDER TREE ── */
function renderFolderTree() {
  const el = document.getElementById('folder-tree');
  if (!el) return;

  el.innerHTML = JORM.strategies.map(s => `
    <div class="folder-item ${s.status === 'PAUSED' ? 'paused' : ''}"
         onclick="showStrategyDetail('${s.id}')">
      <div class="fi-status ${s.status.toLowerCase()}"></div>
      <div class="fi-name">${s.name}</div>
      <div class="fi-pnl ${s.metrics.pnl >= 0 ? 'pos' : 'neg'}">
        ${s.metrics.pnl >= 0 ? '+' : ''}$${Math.abs(s.metrics.pnl).toFixed(0)}
      </div>
      <div class="fi-badge ${s.status.toLowerCase()}">${s.status}</div>
    </div>
  `).join('');

  document.getElementById('folder-count') && (document.getElementById('folder-count').textContent = JORM.strategies.length + ' archivos');
}

/* ── TRADE LOG ── */
function renderTradeLog() {
  const el = document.getElementById('trade-log');
  const badge = document.getElementById('trade-count-badge');
  if (!el) return;

  const recent = [...JORM.tradeHistory].reverse().slice(0, 30);
  if (badge) badge.textContent = JORM.tradeHistory.length + ' trades';

  el.innerHTML = recent.map(t => `
    <div class="log-row">
      <span class="log-time">${t.date.slice(11)}</span>
      <span class="log-side ${t.side.toLowerCase()}">${t.side}</span>
      <span class="log-sym">${t.symbol}</span>
      <span class="log-strat">${t.strategy}</span>
      <span class="log-detail">@ ${t.entry} → ${t.exit}</span>
      <span class="log-pnl ${t.pnl >= 0 ? 'pos' : 'neg'}">${t.pnl >= 0 ? '+' : ''}$${Math.abs(t.pnl).toFixed(2)}</span>
    </div>
  `).join('');
}

/* ── POSITIONS TABLE (dashboard compact) ── */
function renderPositionsTable() {
  const tbody = document.getElementById('positions-body');
  const badge = document.getElementById('pos-count-badge');
  if (!tbody) return;

  if (badge) badge.textContent = JORM.positions.length + ' activas';

  tbody.innerHTML = JORM.positions.map(p => `
    <tr>
      <td class="sym">${p.symbol}</td>
      <td class="${p.side === 'BUY' ? 'long' : 'short'}">${p.side === 'BUY' ? 'LONG' : 'SHORT'}</td>
      <td>${p.size}</td>
      <td>${p.entry.toLocaleString()}</td>
      <td>${p.current.toLocaleString()}</td>
      <td class="muted">${p.sl}</td>
      <td class="muted">${p.tp}</td>
      <td class="${p.pnl >= 0 ? 'pos' : 'neg'}">${p.pnl >= 0 ? '+' : ''}$${Math.abs(p.pnl).toFixed(2)}</td>
      <td class="${p.pnlPct >= 0 ? 'pos' : 'neg'}">${p.pnlPct >= 0 ? '+' : ''}${p.pnlPct.toFixed(2)}%</td>
      <td class="gold muted">${p.strategy}</td>
      <td><button class="hdr-btn red-btn" onclick="closePosition('${p.id}')">CERRAR</button></td>
    </tr>
  `).join('') || '<tr><td colspan="11" style="text-align:center;color:var(--text4);padding:16px">Sin posiciones abiertas</td></tr>';
}

/* ── RISK GAUGES ── */
function renderRiskGauges() {
  const el = document.getElementById('risk-gauges');
  if (!el) return;

  const r = JORM.risk;
  const m = JORM.metrics;
  const pos = JORM.positions.length;
  const exposure = Math.round((pos / r.maxPositions) * 100);
  const ddPct    = Math.abs(m.maxDD);
  const ddLimit  = r.maxDrawdown;
  const dailyLoss = Math.abs(Math.min(0, m.dailyPnL));
  const dailyMax  = (JORM.fund.currentNAV * r.maxDailyLoss / 100);

  const gauges = [
    { label: 'EXPOSICIÓN TOTAL',  cur: exposure + '%',   max: r.maxExposure + '%', pct: exposure / r.maxExposure * 100 },
    { label: 'DRAWDOWN ACTUAL',   cur: '-' + ddPct + '%', max: '-' + ddLimit + '%', pct: ddPct / ddLimit * 100 },
    { label: 'PÉRDIDA DIARIA',    cur: '$' + dailyLoss.toFixed(0), max: '$' + dailyMax.toFixed(0), pct: dailyLoss / dailyMax * 100 },
    { label: 'POSICIONES ABIERTAS', cur: pos + ' / ' + r.maxPositions, max: 'MAX ' + r.maxPositions, pct: pos / r.maxPositions * 100 },
    { label: 'CIRCUIT BREAKER',   cur: r.circuitBreaker ? 'ACTIVO' : 'STANDBY', max: 'DD > ' + r.maxDrawdown + '%', pct: 0 },
  ];

  el.innerHTML = gauges.map(g => {
    const cls = g.pct > 80 ? 'danger' : g.pct > 50 ? 'warn' : 'safe';
    return `
      <div class="gauge-row">
        <div class="gauge-header">
          <span class="gauge-label">${g.label}</span>
          <span class="gauge-vals">
            <span class="gauge-cur" style="color:${cls === 'danger' ? 'var(--red)' : cls === 'warn' ? 'var(--yellow)' : 'var(--green)'}">${g.cur}</span>
            <span class="gauge-max"> / ${g.max}</span>
          </span>
        </div>
        <div class="gauge-bar">
          <div class="gauge-fill ${cls}" style="width:${Math.min(g.pct,100)}%"></div>
        </div>
      </div>
    `;
  }).join('');
}

/* ── ALERTS ── */
function renderAlerts() {
  const el = document.getElementById('alerts-panel');
  const badge = document.getElementById('alert-count-badge');
  if (!el) return;

  const warns = JORM.alerts.filter(a => a.type === 'warn' || a.type === 'err');
  if (badge) badge.textContent = warns.length;

  el.innerHTML = JORM.alerts.map(a => `
    <div class="alert-item">
      <div class="alert-dot ${a.type}"></div>
      <div class="alert-body">
        <div class="alert-text">${a.text}</div>
        <div class="alert-time">${a.time}</div>
      </div>
    </div>
  `).join('');
}

/* ── POSITION ACTIONS ── */
function closePosition(id) {
  const pos = JORM.positions.find(p => p.id === id);
  if (!pos) return;
  if (!confirm(`Cerrar ${pos.symbol} ${pos.side}? PNL actual: $${pos.pnl.toFixed(2)}`)) return;

  JORM.tradeHistory.unshift({
    id: 'T' + Date.now(),
    date: JORM.timestamp(),
    symbol: pos.symbol,
    strategy: pos.strategy,
    side: pos.side,
    entry: pos.entry,
    exit: pos.current,
    pnl: pos.pnl,
    pnlPct: pos.pnlPct,
    duration: pos.duration,
    rr: '1.5',
  });

  JORM.positions = JORM.positions.filter(p => p.id !== id);
  JORM.alerts.unshift({ type: 'ok', text: `Posición cerrada: ${pos.symbol} PNL $${pos.pnl.toFixed(2)}`, time: JORM.now() });
  renderDashboard();
}

function closeAllPositions() {
  if (!confirm('Cerrar TODAS las posiciones abiertas?')) return;
  JORM.positions.forEach(p => {
    JORM.tradeHistory.unshift({ id: 'T' + Date.now() + Math.random(), date: JORM.timestamp(), symbol: p.symbol, strategy: p.strategy, side: p.side, entry: p.entry, exit: p.current, pnl: p.pnl, pnlPct: p.pnlPct, duration: p.duration, rr: '1.5' });
  });
  JORM.positions = [];
  JORM.alerts.unshift({ type: 'warn', text: 'Todas las posiciones cerradas manualmente', time: JORM.now() });
  renderDashboard();
}

function exportPositions() {
  const rows = [['Símbolo','Lado','Tamaño','Entrada','Actual','SL','TP','PNL $','PNL %','Estrategia']];
  JORM.positions.forEach(p => rows.push([p.symbol,p.side,p.size,p.entry,p.current,p.sl,p.tp,p.pnl.toFixed(2),p.pnlPct.toFixed(2)+'%',p.strategy]));
  const csv = rows.map(r => r.join(',')).join('\n');
  const a = document.createElement('a');
  a.href = 'data:text/csv,' + encodeURIComponent(csv);
  a.download = 'jorm_positions_' + new Date().toISOString().slice(0,10) + '.csv';
  a.click();
}
