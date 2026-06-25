/* ═══════════════════════════════════════════════════════
   JORMUNDGANDRSSON — STRATEGIES MODULE
═══════════════════════════════════════════════════════ */

function renderStrategiesModule() {
  renderStratList();
}

function renderStratList() {
  const el = document.getElementById('strat-list-panel');
  if (!el) return;

  el.innerHTML = JORM.strategies.map(s => `
    <div class="folder-item ${s.status === 'PAUSED' ? 'paused' : ''}"
         id="strat-item-${s.id}"
         onclick="showStrategyDetail('${s.id}')">
      <div class="fi-status ${s.status.toLowerCase()}"></div>
      <div style="flex:1">
        <div class="fi-name">${s.name}</div>
        <div style="font-size:8px;color:var(--text4);margin-top:1px">${s.assets.join(' · ')}</div>
      </div>
      <div style="text-align:right">
        <div class="fi-pnl ${s.metrics.pnl >= 0 ? 'pos' : 'neg'}" style="font-size:10px">
          ${s.metrics.pnl >= 0 ? '+' : ''}$${Math.abs(s.metrics.pnl).toFixed(0)}
        </div>
        <div class="fi-badge ${s.status.toLowerCase()}" style="margin-top:2px">${s.status}</div>
      </div>
    </div>
  `).join('');
}

function showStrategyDetail(id) {
  const s = JORM.strategies.find(x => x.id === id);
  if (!s) return;

  document.querySelectorAll('.folder-item').forEach(el => el.classList.remove('active'));
  const item = document.getElementById('strat-item-' + id);
  if (item) item.classList.add('active');

  const el = document.getElementById('strat-detail-area');
  if (!el) return;

  const statusColor = s.status === 'LIVE' ? 'var(--green)' : s.status === 'DEMO' ? 'var(--blue)' : 'var(--text4)';

  el.innerHTML = `
    <div class="strat-detail">
      <div class="strat-header-block">
        <div class="strat-title-block">
          <div class="strat-detail-name">${s.name}</div>
          <div class="strat-detail-meta">${s.id} · ${s.type} · TF: ${s.timeframe} · Activos: ${s.assets.join(', ')}</div>
          <div style="font-size:9px;color:var(--text3);margin-top:4px">${s.description}</div>
        </div>
        <div class="strat-action-btns">
          <button class="hdr-btn" onclick="toggleStrategy('${s.id}')">
            ${s.status === 'PAUSED' ? '▶ ACTIVAR' : '⏸ PAUSAR'}
          </button>
          <button class="hdr-btn red-btn" onclick="removeStrategy('${s.id}')">✕ QUITAR</button>
        </div>
        <div style="padding:8px 12px;border:1px solid ${statusColor};background:${statusColor}22;text-align:center">
          <div style="font-size:11px;font-weight:700;color:${statusColor}">${s.status}</div>
          <div style="font-size:8px;color:var(--text4);margin-top:1px">${s.mode}</div>
        </div>
      </div>

      <!-- METRICS ROW -->
      <div style="grid-column:1/-1;display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:var(--border)">
        ${[
          { l:'PNL TOTAL', v:(s.metrics.pnl>=0?'+$':'-$')+Math.abs(s.metrics.pnl).toFixed(2), c:s.metrics.pnl>=0?'green':'red' },
          { l:'RETORNO',   v:(s.metrics.pnlPct>=0?'+':'')+s.metrics.pnlPct.toFixed(2)+'%', c:s.metrics.pnlPct>=0?'green':'red' },
          { l:'WIN RATE',  v:s.metrics.winRate+'%', c:'gold' },
          { l:'SHARPE',    v:s.metrics.sharpe.toFixed(2), c:'green' },
          { l:'MAX DD',    v:s.metrics.maxDD+'%', c:'red' },
          { l:'PROF.FACT', v:s.metrics.profitFactor.toFixed(2), c:'green' },
        ].map(m => `
          <div class="metric-cell">
            <div class="metric-lbl">${m.l}</div>
            <div class="metric-val ${m.c}">${m.v}</div>
          </div>
        `).join('')}
      </div>

      <!-- PARAMS -->
      <div class="strat-detail-panel">
        <div class="panel-header"><span class="panel-title">PARÁMETROS</span></div>
        <div style="padding:8px">
          ${Object.entries(s.params).map(([k,v]) => `
            <div style="display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--border);font-size:9px">
              <span style="color:var(--text3)">${k}</span>
              <span style="color:var(--text0);font-weight:600">${v}</span>
            </div>
          `).join('')}
        </div>
      </div>

      <!-- TRADE LOG for this strategy -->
      <div class="strat-detail-panel">
        <div class="panel-header">
          <span class="panel-title">TRADES RECIENTES</span>
          <span class="panel-badge">${s.metrics.totalTrades} total</span>
        </div>
        <div class="trade-log-wrap" style="max-height:200px">
          ${JORM.tradeHistory.filter(t => t.strategy === s.id).slice(0,15).map(t => `
            <div class="log-row">
              <span class="log-time">${t.date.slice(5,16)}</span>
              <span class="log-side ${t.side.toLowerCase()}">${t.side}</span>
              <span class="log-sym">${t.symbol}</span>
              <span class="log-detail">@ ${t.entry}</span>
              <span class="log-pnl ${t.pnl>=0?'pos':'neg'}">${t.pnl>=0?'+':''}$${Math.abs(t.pnl).toFixed(2)}</span>
            </div>
          `).join('') || '<div style="padding:12px;text-align:center;color:var(--text4)">Sin trades registrados</div>'}
        </div>
      </div>
    </div>
  `;
}

function toggleStrategy(id) {
  const s = JORM.strategies.find(x => x.id === id);
  if (!s) return;
  s.status = s.status === 'PAUSED' ? (s.mode === 'DEMO' ? 'DEMO' : 'LIVE') : 'PAUSED';
  JORM.alerts.unshift({ type: s.status === 'PAUSED' ? 'warn' : 'ok', text: `${s.name} → ${s.status}`, time: JORM.now() });
  renderStratList();
  showStrategyDetail(id);
  renderFolderTree();
}

function removeStrategy(id) {
  const s = JORM.strategies.find(x => x.id === id);
  if (!s || !confirm(`Quitar ${s.name} de STRATEGIES/?\nLos trades históricos se conservan.`)) return;
  JORM.strategies = JORM.strategies.filter(x => x.id !== id);
  JORM.alerts.unshift({ type: 'warn', text: `${s.name} removida de STRATEGIES/`, time: JORM.now() });
  renderStratList();
  renderFolderTree();
  document.getElementById('strat-detail-area').innerHTML = `
    <div class="strat-empty-state">
      <div class="empty-icon">▪</div>
      <div class="empty-title">ESTRATEGIA REMOVIDA</div>
      <div class="empty-sub">Selecciona otra o crea una nueva</div>
    </div>`;
}

function filterStrategies(q) {
  const els = document.querySelectorAll('#strat-list-panel .folder-item');
  els.forEach(el => {
    const text = el.textContent.toLowerCase();
    el.style.display = text.includes(q.toLowerCase()) ? '' : 'none';
  });
}

function openNewStrategyModal() {
  const el = document.getElementById('new-strategy-form');
  if (el) el.innerHTML = `
    <div style="display:flex;flex-direction:column;gap:10px">
      <div class="config-field">
        <div class="config-label">NOMBRE DE ESTRATEGIA</div>
        <input class="inst-input" id="ns-name" placeholder="MOMENTUM-ALPHA-02" style="width:100%">
      </div>
      <div class="config-field">
        <div class="config-label">TIPO</div>
        <select class="inst-select" id="ns-type" style="width:100%">
          <option>Momentum + Breakout</option>
          <option>Mean Reversion</option>
          <option>Multi-factor Macro</option>
          <option>Statistical Arbitrage</option>
          <option>Breakout + COT</option>
        </select>
      </div>
      <div class="config-field">
        <div class="config-label">ACTIVOS</div>
        <input class="inst-input" id="ns-assets" placeholder="SPX500, NAS100" style="width:100%">
      </div>
      <div class="config-field">
        <div class="config-label">TIMEFRAME</div>
        <input class="inst-input" id="ns-tf" placeholder="1H / 4H" style="width:100%">
      </div>
      <div class="config-field">
        <div class="config-label">DESCRIPCIÓN</div>
        <textarea class="inst-input" id="ns-desc" rows="3" style="width:100%;resize:none"></textarea>
      </div>
      <div class="config-field">
        <div class="config-label">MODO INICIAL</div>
        <select class="inst-select" id="ns-mode" style="width:100%">
          <option>DEMO</option><option>LIVE</option>
        </select>
      </div>
      <div style="display:flex;gap:6px;justify-content:flex-end;margin-top:6px">
        <button class="hdr-btn" onclick="closeModal('modal-new-strategy')">CANCELAR</button>
        <button class="hdr-btn gold-btn" onclick="createStrategy()">CREAR → STRATEGIES/</button>
      </div>
    </div>
  `;
  document.getElementById('modal-new-strategy').style.display = 'flex';
}

function createStrategy() {
  const name    = document.getElementById('ns-name').value.trim().toUpperCase();
  const type    = document.getElementById('ns-type').value;
  const assets  = document.getElementById('ns-assets').value.split(',').map(a => a.trim()).filter(Boolean);
  const tf      = document.getElementById('ns-tf').value.trim();
  const desc    = document.getElementById('ns-desc').value.trim();
  const mode    = document.getElementById('ns-mode').value;

  if (!name) { alert('El nombre es requerido'); return; }

  const newStrat = {
    id: 'STR-' + String(JORM.strategies.length + 1).padStart(3,'0'),
    name, type, assets, timeframe: tf || '1H', description: desc, status: mode, mode,
    startDate: new Date().toISOString().slice(0,10),
    params: { riskPerTrade: 1.0, maxPositions: 3 },
    metrics: { totalTrades: 0, winRate: 0, pnl: 0, pnlPct: 0, sharpe: 0, maxDD: 0, profitFactor: 0 },
  };

  JORM.strategies.push(newStrat);
  JORM.alerts.unshift({ type: 'ok', text: `Nueva estrategia cargada: ${name} → STRATEGIES/`, time: JORM.now() });
  closeModal('modal-new-strategy');
  renderStratList();
  renderFolderTree();
  showStrategyDetail(newStrat.id);
}

function closeModal(id) {
  document.getElementById(id).style.display = 'none';
}
