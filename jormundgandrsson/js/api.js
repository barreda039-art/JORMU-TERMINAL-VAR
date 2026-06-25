/* ═══════════════════════════════════════════════════════════
   JORMUNDGANDRSSON — API Connector v2
   Conecta el terminal HTML con el backend Python
   + Engine polling en tiempo real
═══════════════════════════════════════════════════════════ */

const API = {
  base: 'http://localhost:5000/api',
  pollInterval:   null,
  engineInterval: null,
  connected: false,

  // ── FETCH HELPER ──────────────────────────────────────
  async call(method, path, body = null) {
    try {
      const opts = { method, headers: { 'Content-Type': 'application/json' } };
      if (body) opts.body = JSON.stringify(body);
      const r = await fetch(this.base + path, opts);
      return await r.json();
    } catch (e) {
      return { ok: false, error: 'Backend no disponible — ¿está corriendo server.py?' };
    }
  },

  get:    (path)       => API.call('GET',    path),
  post:   (path, body) => API.call('POST',   path, body),
  put:    (path, body) => API.call('PUT',    path, body),
  delete: (path, body) => API.call('DELETE', path, body),

  // ── CONEXIÓN ──────────────────────────────────────────
  async connect() {
    updateConnectionUI('connecting');
    const result = await this.post('/session/create');

    if (result.ok) {
      this.connected = true;
      updateConnectionUI('connected');
      updateStatusDetail(`✓ Conectado a Capital.com ${result.env?.toUpperCase() || 'DEMO'} — Sesión activa`);
      JORM.alerts.unshift({ type: 'ok', text: `Capital.com conectado — ${result.env?.toUpperCase() || 'DEMO'}`, time: JORM.now() });

      await this.syncAccountBalance();
      await this.syncPositions();
      this.startPolling();
      this.startEnginePolling();

    } else {
      this.connected = false;
      updateConnectionUI('error');
      updateStatusDetail('✗ Error: ' + (result.error || 'Verifica credenciales en .env'));
      JORM.alerts.unshift({ type: 'err', text: 'Error: ' + (result.error || 'Verifica credenciales'), time: JORM.now() });
    }
    renderAlerts();
    renderBrokerStatus();
    return result;
  },

  async disconnect() {
    this.stopPolling();
    this.stopEnginePolling();
    this.connected = false;
    updateConnectionUI('disconnected');
    JORM.alerts.unshift({ type: 'warn', text: 'Capital.com desconectado', time: JORM.now() });
    renderAlerts();
    renderBrokerStatus();
  },

  // ── CUENTA ────────────────────────────────────────────
  async syncAccountBalance() {
    const result = await this.get('/account/balance');
    if (result.ok) {
      JORM.fund.currentNAV = result.balance;
      JORM.metrics.totalPnL = result.profit;
      JORM.fund.name = result.accountName || JORM.fund.name;
      renderFundMetrics();
      renderHeaderMetrics();
    }
    return result;
  },

  // ── POSICIONES ────────────────────────────────────────
  async syncPositions() {
    const result = await this.get('/positions');
    if (result.ok && result.positions) {
      JORM.positions = result.positions.map(p => ({
        id:       p.dealId,
        symbol:   p.epic,
        strategy: detectStrategy(p.epic),
        side:     p.direction,
        size:     p.size,
        entry:    p.level,
        current:  p.direction === 'BUY' ? p.bid : p.ask,
        sl:       p.stopLevel  || '—',
        tp:       p.limitLevel || '—',
        pnl:      p.pnl || 0,
        pnlPct:   p.level ? ((p.pnl / (p.level * p.size)) * 100) || 0 : 0,
        duration: calcDuration(p.createdAt),
      }));
      renderPositionsTable();
      const badge = document.getElementById('pos-count-badge');
      if (badge) badge.textContent = JORM.positions.length + ' activas';
    }
    return result;
  },

  // ── PRECIOS ───────────────────────────────────────────
  async syncPrices() {
    const result = await this.get('/market/prices');
    if (result.ok && result.prices) {
      Object.entries(result.prices).forEach(([epic, data]) => {
        const tick = JORM.tickerSymbols.find(t =>
          t.sym === epic || t.sym === epic.replace('/', '')
        );
        if (tick && data.mid) {
          const prev = tick.price;
          tick.price = data.mid;
          tick.chg   = prev > 0 ? Math.round(((data.mid - prev) / prev) * 10000) / 100 : 0;
        }
      });
      renderTicker();
    }
  },

  // ── ENGINE CONTROL ────────────────────────────────────
  async startEngine() {
    const result = await this.post('/engine/start');
    if (result.ok) {
      JORM.alerts.unshift({ type: 'ok', text: 'Quant Engine iniciado — análisis cada 15 min', time: JORM.now() });
      renderAlerts();
      this.startEnginePolling();
    }
    return result;
  },

  async stopEngine() {
    const result = await this.post('/engine/stop');
    if (result.ok) {
      JORM.alerts.unshift({ type: 'warn', text: 'Quant Engine detenido', time: JORM.now() });
      renderAlerts();
      this.stopEnginePolling();
    }
    return result;
  },

  async runEngineNow() {
    const result = await this.post('/engine/run-now');
    if (result.ok) {
      JORM.alerts.unshift({ type: 'info', text: 'Ciclo de análisis iniciado manualmente', time: JORM.now() });
      renderAlerts();
    }
    return result;
  },

  async approveSignal(signalId) {
    const result = await this.post(`/engine/signals/approve/${signalId}`);
    if (result.ok) {
      JORM.alerts.unshift({ type: 'ok', text: `Señal aprobada — enviando a Capital.com`, time: JORM.now() });
      renderAlerts();
      await this.syncPositions();
      await this.syncAccountBalance();
    }
    return result;
  },

  async rejectSignal(signalId) {
    await this.post(`/engine/signals/reject/${signalId}`);
    await this.syncEngineStatus();
  },

  // ── ENGINE POLLING ────────────────────────────────────
  async syncEngineStatus() {
    const result = await this.get('/engine/status');
    if (!result.ok) return;

    const status = result.status;
    JORM.engine = status;

    // Actualizar panel de análisis en Autopsia
    renderEngineStatus(status);

    // Sincronizar señales pendientes
    const signals = await this.get('/engine/signals');
    if (signals.ok) {
      JORM.opportunities = signals.signals.map(s => ({
        symbol:     s.asset,
        direction:  s.direction === 'BULLISH' ? 'LONG' : 'SHORT',
        score:      s.total_score,
        entryPrice: s.entry_price || 0,
        sl:         s.sl || 0,
        tp:         s.tp || 0,
        context:    s.context || '',
        confidence: s.confidence,
        strategy:   s.strategy,
        id:         s.id,
      }));
      renderOpportunities();

      // Alerta en dashboard si hay señales nuevas
      if (signals.signals.length > 0) {
        const badge = document.getElementById('opp-count');
        if (badge) {
          badge.textContent = signals.signals.length + ' señales';
          badge.style.color = 'var(--gold)';
          badge.style.borderColor = 'var(--gold)';
        }
      }
    }
  },

  startEnginePolling() {
    if (this.engineInterval) clearInterval(this.engineInterval);
    this.engineInterval = setInterval(() => {
      if (!this.connected) return;
      this.syncEngineStatus();
    }, 5000);  // cada 5 segundos
    console.log('[ENGINE POLL] Iniciado cada 5s');
    this.syncEngineStatus(); // inmediato
  },

  stopEnginePolling() {
    if (this.engineInterval) {
      clearInterval(this.engineInterval);
      this.engineInterval = null;
    }
  },

  // ── POLLING GENERAL (2s) ─────────────────────────────
  startPolling() {
    if (this.pollInterval) clearInterval(this.pollInterval);
    this.pollInterval = setInterval(async () => {
      if (!this.connected) return;
      await this.syncPrices();
      await this.syncPositions();
      await this.syncAccountBalance();
    }, 2000);
  },

  stopPolling() {
    if (this.pollInterval) { clearInterval(this.pollInterval); this.pollInterval = null; }
  },

  // ── ÓRDENES ───────────────────────────────────────────
  async openPosition(epic, direction, size, stopDistance, limitDistance) {
    const payload = { epic, direction, size };
    if (stopDistance)  payload.stopDistance  = stopDistance;
    if (limitDistance) payload.limitDistance = limitDistance;

    const result = await this.post('/positions/open', payload);
    if (result.ok) {
      JORM.alerts.unshift({ type: 'ok', text: `Orden enviada: ${direction} ${epic} × ${size}`, time: JORM.now() });
      setTimeout(async () => {
        await this.syncPositions();
        await this.syncAccountBalance();
      }, 2000);
    } else {
      JORM.alerts.unshift({ type: 'err', text: `Error: ${result.error}`, time: JORM.now() });
    }
    renderAlerts();
    return result;
  },

  async closePosition(dealId, direction, size) {
    const result = await this.delete(`/positions/close/${dealId}`, { direction, size });
    if (result.ok) {
      JORM.alerts.unshift({ type: 'ok', text: `Posición cerrada: ${dealId}`, time: JORM.now() });
      await this.syncPositions();
      await this.syncAccountBalance();
    } else {
      JORM.alerts.unshift({ type: 'err', text: `Error cerrando: ${result.error}`, time: JORM.now() });
    }
    renderAlerts();
    return result;
  },

  async updateRiskConfig(config) { return await this.put('/risk/config', config); },
  async toggleCircuitBreaker(active) { return await this.post('/risk/circuit-breaker', { active }); },
};

// ── RENDER ENGINE STATUS EN AUTOPSIA ──────────────────────
function renderEngineStatus(status) {
  const el = document.getElementById('engine-status-panel');
  if (!el) return;

  const cache = status.analysis_cache || {};
  const assets = ['EURUSD','GBPUSD','USDJPY','SPX500','NAS100','XAUUSD','USOIL'];

  const dirColor = d => d === 'BULLISH' ? 'var(--green)' : d === 'BEARISH' ? 'var(--red)' : 'var(--text3)';
  const dirArrow = d => d === 'BULLISH' ? '▲' : d === 'BEARISH' ? '▼' : '—';

  el.innerHTML = `
    <div style="padding:6px 8px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between">
      <div style="font-size:9px;color:var(--text3)">
        ESTADO: <span style="color:${status.running ? 'var(--green)' : 'var(--red)'};font-weight:700">
          ${status.running ? '● CORRIENDO' : '○ DETENIDO'}
        </span>
      </div>
      <div style="font-size:9px;color:var(--text3)">
        Último ciclo: <span style="color:var(--text1)">${status.last_run ? new Date(status.last_run).toTimeString().slice(0,8) : '—'}</span>
      </div>
      <div style="font-size:9px;color:var(--text3)">
        Señales: <span style="color:var(--gold);font-weight:700">${status.pending_signals}</span> pendientes |
        <span style="color:var(--green)">${status.auto_executed}</span> auto-ejecutadas
      </div>
      <div style="display:flex;gap:4px">
        <button class="hdr-btn gold-btn" onclick="API.startEngine()">▶ ENGINE</button>
        <button class="hdr-btn" onclick="API.runEngineNow()">⚡ FORZAR</button>
        <button class="hdr-btn red-btn" onclick="API.stopEngine()">■ STOP</button>
      </div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:1px;background:var(--border)">
      ${assets.map(asset => {
        const data = cache[asset];
        const score = data?.score || 0;
        const dir   = data?.direction || 'NEUTRAL';
        const struct= data?.structure?.structure || '—';
        const obActive = data?.zones?.ob_active;
        const fvgActive= data?.zones?.fvg_active;
        const liqSwept = data?.zones?.liq_swept;
        const bias  = data?.regime_bias || 'NEUTRAL';
        const updated = data?.updated_at ? new Date(data.updated_at).toTimeString().slice(0,8) : '—';
        const scoreColor = score >= 70 ? 'var(--green)' : score >= 50 ? 'var(--yellow)' : 'var(--text3)';

        return `
          <div style="background:var(--bg1);padding:8px;text-align:center">
            <div style="font-size:11px;font-weight:700;color:var(--text0);margin-bottom:4px">${asset}</div>
            <div style="font-size:22px;font-weight:700;color:${scoreColor};margin-bottom:2px">${score || '—'}</div>
            <div style="font-size:9px;font-weight:700;color:${dirColor(dir)}">${dirArrow(dir)} ${dir}</div>
            <div style="font-size:8px;color:var(--text3);margin-top:4px">${struct}</div>
            <div style="display:flex;justify-content:center;gap:3px;margin-top:4px">
              ${obActive  ? '<span style="font-size:7px;color:var(--gold);border:1px solid var(--gold);padding:1px 3px">OB</span>' : ''}
              ${fvgActive ? '<span style="font-size:7px;color:var(--blue);border:1px solid var(--blue);padding:1px 3px">FVG</span>' : ''}
              ${liqSwept  ? '<span style="font-size:7px;color:var(--green);border:1px solid var(--green);padding:1px 3px">LIQ</span>' : ''}
            </div>
            <div style="font-size:7px;color:var(--text4);margin-top:3px">${updated}</div>
          </div>
        `;
      }).join('')}
    </div>
  `;
}

// ── HELPERS ───────────────────────────────────────────────
function detectStrategy(epic) {
  const strat = JORM.strategies.find(s => s.assets.some(a => a.includes(epic) || epic.includes(a)));
  return strat ? strat.id : 'MANUAL';
}

function calcDuration(createdAt) {
  if (!createdAt) return '—';
  const ms   = Date.now() - new Date(createdAt).getTime();
  const mins = Math.floor(ms / 60000);
  if (mins < 60) return mins + 'm';
  const hrs  = Math.floor(mins / 60);
  return hrs < 24 ? hrs + 'h ' + (mins % 60) + 'm' : Math.floor(hrs / 24) + 'd';
}

function updateStatusDetail(msg) {
  const el = document.getElementById('connection-status-detail');
  if (el) el.textContent = msg;
}

function updateConnectionUI(state) {
  const el = document.getElementById('broker-status');
  if (!el) return;
  const states = {
    connecting:   { color: 'var(--yellow)', dot: 'warn',        label: 'CONECTANDO...' },
    connected:    { color: 'var(--green)',  dot: 'connected',   label: 'CAPITAL.COM' },
    disconnected: { color: 'var(--text4)', dot: 'disconnected', label: 'CAPITAL.COM' },
    error:        { color: 'var(--red)',   dot: 'disconnected', label: 'ERROR CONEXIÓN' },
  };
  const s = states[state] || states.disconnected;
  el.innerHTML = `
    <div class="broker-pill">
      <div class="broker-dot ${s.dot}" style="background:${s.color}"></div>
      <span style="color:${s.color}">${s.label}</span>
      <span style="color:var(--text4)"> ${JORM.mode}</span>
    </div>
    <div class="broker-pill">
      <div class="broker-dot disconnected"></div>
      <span style="color:var(--text3)">IB TWS</span>
      <span style="color:var(--text4)"> OFFLINE</span>
    </div>
  `;
}

async function connectCapitalCom()    { await API.connect(); }
async function disconnectCapitalCom() { await API.disconnect(); }
async function startLiveStreaming() {
  const epics = ['EURUSD','GBPUSD','USDJPY','GOLD','US500','US100','OIL_CRUDE'];
  const result = await API.post('/stream/start', { epics });
  if (result.ok) {
    JORM.alerts.unshift({ type: 'ok', text: `Streaming iniciado: ${epics.length} instrumentos`, time: JORM.now() });
    renderAlerts();
  }
}
