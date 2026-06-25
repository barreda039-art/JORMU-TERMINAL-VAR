/* ═══════════════════════════════════════════════════════
   JORMUNDGANDRSSON — ICARO MODULE
   Pestaña dedicada al engine ICARO V2.1
   Lee /api/icaro/status y /api/icaro/capital
   No toca ningún otro módulo del sistema.
═══════════════════════════════════════════════════════ */

// ── ESTADO LOCAL ICARO ────────────────────────────────
const ICARO_STATE = {
  snapshot:       null,
  refreshInterval: null,
  REFRESH_MS:     5000,   // Refresh cada 5 segundos
};

// ── ENTRY POINT ──────────────────────────────────────
function renderIcaroModule() {
  _icaroFetchAndRender();
  // Limpiar interval anterior si existe
  if (ICARO_STATE.refreshInterval) clearInterval(ICARO_STATE.refreshInterval);
  ICARO_STATE.refreshInterval = setInterval(_icaroFetchAndRender, ICARO_STATE.REFRESH_MS);
}

async function _icaroFetchAndRender() {
  try {
    const [statusRes, capitalRes] = await Promise.all([
      fetch('http://127.0.0.1:5000/api/icaro/status'),
      fetch('http://127.0.0.1:5000/api/icaro/capital'),
    ]);
    const statusData  = await statusRes.json();
    const capitalData = await capitalRes.json();

    if (statusData.ok) {
      ICARO_STATE.snapshot = {
        ...statusData.icaro,
        ...capitalData,
      };
      _icaroRender(ICARO_STATE.snapshot);
    }
  } catch (e) {
    _icaroRenderOffline();
  }
}

// ── RENDER PRINCIPAL ─────────────────────────────────
function _icaroRender(d) {
  const el = document.getElementById('icaro-content');
  if (!el) return;

  const online     = d.online;
  const ks         = d.killswitch_global || d.killswitch_active;
  const regime     = d.regime_label     || '—';
  const fragility  = d.fragility_score  != null ? d.fragility_score.toFixed(4)  : '—';
  const convexity  = d.convexity_score  != null ? d.convexity_score.toFixed(4)  : '—';
  const convWindow = d.convexity_window || '—';
  const crashProb  = d.crash_probability != null ? (d.crash_probability * 100).toFixed(2) + '%' : '—';
  const decision   = d.execution_decision  || 'NO_ACTION';
  const stage      = d.deployment_stage    || 'NO_DEPLOYMENT';
  const quality    = d.signal_quality      || '—';
  const qualScore  = d.signal_quality_score != null ? d.signal_quality_score.toFixed(2) : '—';
  const liveAction = d.live_action          || '—';
  const capUtil    = d.capital_utilization  != null ? (d.capital_utilization * 100).toFixed(1) + '%' : '0%';
  const timestamp  = d.timestamp ? new Date(d.timestamp).toLocaleTimeString() : '—';

  // Capital
  const nav         = d.nav           || 0;
  const reservePct  = d.reserve_pct   || 20;
  const icaroCap    = d.icaro_capital || 0;
  const availNav    = d.available_nav || (nav - icaroCap);

  // Betas
  const probeCap  = icaroCap * 0.35;
  const hedgeCap  = icaroCap * 0.85;
  const fullCap   = icaroCap * 1.75;
  const convCap   = icaroCap * 2.25;

  // Color helpers
  const regimeColor   = _icaroRegimeColor(regime);
  const decisionColor = _icaroDecisionColor(decision);
  const ksColor       = ks ? '#ff4444' : '#44ff88';
  const onlineColor   = online ? '#44ff88' : '#888';
  const onlineLabel   = online ? '● LIVE' : '○ OFFLINE';

  el.innerHTML = `

    <!-- ROW 1: STATUS BAR -->
    <div class="icaro-status-bar">
      <span class="icaro-engine-name">ICARO V2.1</span>
      <span class="icaro-online" style="color:${onlineColor}">${onlineLabel}</span>
      <span class="icaro-ts">Último snapshot: ${timestamp}</span>
      <span class="icaro-action-badge" style="color:${decisionColor}">${liveAction}</span>
    </div>

    <!-- ROW 2: REGIME + SIGNAL -->
    <div class="icaro-top-row">

      <div class="panel icaro-panel">
        <div class="panel-header">
          <span class="panel-title">RÉGIMEN DE MERCADO</span>
          <span class="panel-badge" style="color:${regimeColor}">${regime}</span>
        </div>
        <div class="icaro-metrics-grid">
          <div class="icaro-metric">
            <span class="icaro-metric-label">FRAGILITY SCORE</span>
            <span class="icaro-metric-val ${_icaroFragClass(d.fragility_score)}">${fragility}</span>
          </div>
          <div class="icaro-metric">
            <span class="icaro-metric-label">CRASH PROBABILITY</span>
            <span class="icaro-metric-val ${d.crash_probability > 0.15 ? 'neg' : 'pos'}">${crashProb}</span>
          </div>
          <div class="icaro-metric">
            <span class="icaro-metric-label">CONVEXITY SCORE</span>
            <span class="icaro-metric-val gold">${convexity}</span>
          </div>
          <div class="icaro-metric">
            <span class="icaro-metric-label">CONV. WINDOW</span>
            <span class="icaro-metric-val gold">${convWindow}</span>
          </div>
        </div>
      </div>

      <div class="panel icaro-panel">
        <div class="panel-header">
          <span class="panel-title">SEÑAL ACTIVA</span>
          <span class="panel-badge" style="color:${decisionColor}">${decision}</span>
        </div>
        <div class="icaro-metrics-grid">
          <div class="icaro-metric">
            <span class="icaro-metric-label">DEPLOYMENT STAGE</span>
            <span class="icaro-metric-val gold">${stage}</span>
          </div>
          <div class="icaro-metric">
            <span class="icaro-metric-label">SIGNAL QUALITY</span>
            <span class="icaro-metric-val">${quality}</span>
          </div>
          <div class="icaro-metric">
            <span class="icaro-metric-label">QUALITY SCORE</span>
            <span class="icaro-metric-val gold">${qualScore}</span>
          </div>
          <div class="icaro-metric">
            <span class="icaro-metric-label">KILLSWITCH</span>
            <span class="icaro-metric-val" style="color:${ksColor}">${ks ? 'ACTIVO ⚠' : 'FALSE'}</span>
          </div>
        </div>
      </div>

    </div>

    <!-- ROW 3: CAPITAL RESERVADO -->
    <div class="panel icaro-panel" style="margin-top:1px">
      <div class="panel-header">
        <span class="panel-title">CAPITAL RESERVADO</span>
        <span class="panel-badge gold-badge">ICARO UNIVERSE</span>
      </div>
      <div class="icaro-capital-grid">
        <div class="icaro-capital-block">
          <div class="icaro-cap-label">NAV TOTAL</div>
          <div class="icaro-cap-val gold">$${_icaroFmt(nav)}</div>
        </div>
        <div class="icaro-capital-block">
          <div class="icaro-cap-label">RESERVA ICARO</div>
          <div class="icaro-cap-val gold">$${_icaroFmt(icaroCap)}</div>
          <div class="icaro-cap-sub">${reservePct}% del NAV</div>
        </div>
        <div class="icaro-capital-block">
          <div class="icaro-cap-label">DISPONIBLE GENERAL</div>
          <div class="icaro-cap-val">$${_icaroFmt(availNav)}</div>
          <div class="icaro-cap-sub">${(100 - reservePct).toFixed(0)}% del NAV</div>
        </div>
        <div class="icaro-capital-block">
          <div class="icaro-cap-label">UTILIZACIÓN</div>
          <div class="icaro-cap-val ${d.capital_utilization > 0.5 ? 'gold' : ''}">${capUtil}</div>
        </div>
      </div>

      <!-- Slider de reserva -->
      <div class="icaro-reserve-control">
        <span class="icaro-reserve-label">RESERVA ICARO</span>
        <input
          type="range" min="5" max="60" step="5"
          value="${reservePct}"
          class="icaro-slider"
          id="icaro-reserve-slider"
          onchange="_icaroUpdateReserve(this.value)"
        />
        <span class="icaro-reserve-pct" id="icaro-reserve-display">${reservePct}%</span>
        <button class="icaro-btn-apply" onclick="_icaroApplyReserve()">APLICAR</button>
      </div>
    </div>

    <!-- ROW 4: DEPLOYMENT STAGES -->
    <div class="panel icaro-panel" style="margin-top:1px">
      <div class="panel-header">
        <span class="panel-title">DEPLOYMENT STAGES</span>
        <span class="panel-badge">β × CAPITAL ICARO</span>
      </div>
      <div class="icaro-stages-grid">
        ${_icaroStageRow('PROBE',      0.35, probeCap, stage)}
        ${_icaroStageRow('HEDGE',      0.85, hedgeCap, stage)}
        ${_icaroStageRow('FULL DEPLOY',1.75, fullCap,  stage)}
        ${_icaroStageRow('CONVEXITY',  2.25, convCap,  stage)}
      </div>
    </div>

    <!-- ROW 5: ENGINE CONTROL -->
    <div class="panel icaro-panel" style="margin-top:1px">
      <div class="panel-header">
        <span class="panel-title">ENGINE CONTROL</span>
        <span class="panel-badge">ALPACA DATA SOURCE</span>
      </div>
      <div class="icaro-engine-row">
        <div class="icaro-engine-info">
          <span class="icaro-info-item">Engine: ICARO V2.1 | Proceso independiente</span>
          <span class="icaro-info-item">Data: Alpaca API (SPY · VIX · QQQ · IWM · HYG · LQD · VXX)</span>
          <span class="icaro-info-item">Ciclo: cada 60 min | HMM refit: cada 21 días</span>
        </div>
        <div class="icaro-engine-actions">
          <div class="icaro-runner-note">
            Arrancar el engine por separado:<br>
            <code class="icaro-code">py -3.11 backend/icaro_runner.py</code>
          </div>
        </div>
      </div>
    </div>
  `;

  // Sincronizar slider
  const slider = document.getElementById('icaro-reserve-slider');
  if (slider) slider._pendingValue = reservePct;
}

// ── RENDER OFFLINE ────────────────────────────────────
function _icaroRenderOffline() {
  const el = document.getElementById('icaro-content');
  if (!el) return;
  el.innerHTML = `
    <div class="icaro-status-bar">
      <span class="icaro-engine-name">ICARO V2.1</span>
      <span class="icaro-online" style="color:#888">○ OFFLINE</span>
      <span class="icaro-ts">Sin conexión con el backend</span>
    </div>
    <div class="panel icaro-panel" style="margin-top:8px;padding:24px;text-align:center">
      <div style="color:#888;font-size:12px;letter-spacing:1px">
        ICARO engine no detectado.<br><br>
        Para iniciar el engine, ejecuta en una terminal separada:<br><br>
        <code class="icaro-code">py -3.11 backend/icaro_runner.py</code><br><br>
        El terminal detectará el engine automáticamente.
      </div>
    </div>
  `;
}

// ── CONTROL DE RESERVA ────────────────────────────────
function _icaroUpdateReserve(val) {
  const display = document.getElementById('icaro-reserve-display');
  if (display) display.textContent = val + '%';
  const slider = document.getElementById('icaro-reserve-slider');
  if (slider) slider._pendingValue = parseFloat(val);
}

async function _icaroApplyReserve() {
  const slider = document.getElementById('icaro-reserve-slider');
  if (!slider) return;
  const val = parseFloat(slider.value);

  try {
    const res = await fetch('http://127.0.0.1:5000/api/icaro/capital', {
      method:  'PUT',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ reserve_pct: val }),
    });
    const data = await res.json();
    if (data.ok) {
      console.log(`[ICARO] Reserva actualizada: ${val}%`);
      _icaroFetchAndRender();
    }
  } catch (e) {
    console.error('[ICARO] Error actualizando reserva:', e);
  }
}

// ── HELPERS UI ────────────────────────────────────────
function _icaroStageRow(label, beta, capital, activeStage) {
  const stageKey = label.replace(' ', '_').toUpperCase();
  const isActive = activeStage && activeStage.includes(label.split(' ')[0]);
  const dotColor = isActive ? '#FFD400' : '#333';
  const valColor = isActive ? 'gold'    : '';

  return `
    <div class="icaro-stage-row ${isActive ? 'icaro-stage-active' : ''}">
      <span class="icaro-stage-dot" style="background:${dotColor}"></span>
      <span class="icaro-stage-label">${label}</span>
      <span class="icaro-stage-beta">β ${beta.toFixed(2)}</span>
      <span class="icaro-stage-cap ${valColor}">$${_icaroFmt(capital)}</span>
      <span class="icaro-stage-status">${isActive ? '▶ ACTIVO' : '○ inactivo'}</span>
    </div>
  `;
}

function _icaroRegimeColor(regime) {
  if (!regime) return '#888';
  if (regime === 'HIGH_VOL_STRESS') return '#ff6b6b';
  if (regime === 'NORMAL_REGIME')   return '#FFD400';
  if (regime === 'LOW_VOL_TREND')   return '#44ff88';
  return '#888';
}

function _icaroDecisionColor(decision) {
  if (!decision) return '#888';
  if (decision === 'EXECUTE')     return '#44ff88';
  if (decision === 'NO_ACTION')   return '#888';
  if (decision === 'KILLSWITCH')  return '#ff4444';
  return '#FFD400';
}

function _icaroFragClass(score) {
  if (score == null) return '';
  if (score > 0.60)  return 'neg';
  if (score > 0.30)  return 'gold';
  return 'pos';
}

function _icaroFmt(n) {
  if (!n && n !== 0) return '—';
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
