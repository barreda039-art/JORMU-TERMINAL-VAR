/* ═══════════════════════════════════════════════════
   JORMUNDGANDRSSON — STATE MANAGER
   Gestión central del estado del fondo
═══════════════════════════════════════════════════ */

const JORM = {

  /* ── MODO OPERACIONAL ── */
  mode: 'DEMO',   /* 'DEMO' | 'LIVE' */
  version: '1.0.0',

  /* ── CONFIGURACIÓN DEL FONDO ── */
  fund: {
    name: 'JORM-ALPHA-01',
    inception: '2025-01-01',
    baseCurrency: 'USD',
    initialCapital: 10000,
    currentNAV: 10000,
    hwm: 10000,       /* High Water Mark */
  },

  /* ── ESTADO DE BROKERS ── */
  brokers: {
    capitalcom: { connected: false, mode: 'DEMO', balance: 0, name: 'Capital.com' },
    ib:         { connected: false, mode: 'PAPER', balance: 0, name: 'Interactive Brokers' },
  },

  /* ── API KEYS (se guardan en localStorage) ── */
  apiKeys: {
    capitalcom_key:    '',
    capitalcom_secret: '',
    capitalcom_env:    'demo',
    ib_port:           7497,
    ib_client_id:      1,
    alpha_vantage:     '',
    finnhub:           '',
    polygon:           '',
  },

  /* ── ESTRATEGIAS ACTIVAS (carpeta STRATEGIES) ── */
  strategies: [],

  /* ── POSICIONES ABIERTAS ── */
  positions: [],

  /* ── HISTORIAL DE TRADES ── */
  tradeHistory: [],

  /* ── ALERTAS DEL SISTEMA ── */
  alerts: [],

  /* ── PARÁMETROS DE RIESGO ── */
  risk: {
    maxDrawdown:      10,   /* % máx drawdown antes de circuit breaker */
    maxDailyLoss:     3,    /* % máx pérdida diaria */
    maxPositions:     10,   /* máx posiciones simultáneas */
    maxExposure:      80,   /* % máx del capital expuesto */
    maxSinglePos:     5,    /* % máx por posición individual */
    riskPerTrade:     1,    /* % riesgo por trade (Kelly base) */
    correlationLimit: 0.70, /* límite de correlación portfolio */
    circuitBreaker:   false,
  },

  /* ── DATOS DE MERCADO ── */
  market: {
    regime: 'RISK-ON',
    vix: 18.4,
    dxy: 104.2,
    t10y: 4.32,
    sp500: 5847.32,
    gold: 2318.50,
    oil: 81.40,
    btc: 67420,
    fearGreed: 62,
    putCallRatio: 0.84,
  },

  /* ── MÉTRICAS DEL FONDO ── */
  metrics: {
    totalPnL:    0,
    dailyPnL:    0,
    monthlyPnL:  0,
    totalReturn: 0,
    sharpe:      0,
    maxDD:       0,
    currentDD:   0,
    winRate:     0,
    profitFactor:0,
    totalTrades: 0,
    winTrades:   0,
    lossTrades:  0,
  },

  /* ── TICKER SYMBOLS ── */
  tickerSymbols: [
    { sym: 'SPX500', price: 5847.32, chg: +0.84 },
    { sym: 'NAS100', price: 20841.5, chg: +1.12 },
    { sym: 'EURUSD', price: 1.08420, chg: -0.14 },
    { sym: 'GBPUSD', price: 1.27340, chg: -0.08 },
    { sym: 'USDJPY', price: 154.820, chg: +0.32 },
    { sym: 'XAUUSD', price: 2318.50, chg: +0.45 },
    { sym: 'USOIL',  price: 81.400,  chg: -0.67 },
    { sym: 'BTCUSD', price: 67420.0, chg: +2.14 },
    { sym: 'VIX',    price: 18.40,   chg: -3.20 },
    { sym: 'DXY',    price: 104.200, chg: +0.22 },
    { sym: 'T10Y',   price: 4.320,   chg: +0.04 },
    { sym: 'ETHBTC', price: 0.05312, chg: -0.88 },
  ],

  /* ── HISTORIAL NAV — se puebla tras conectar al backend ── */
  navHistory: [],

  /* ── SEÑALES ACTIVAS ── */
  signals: [],

  /* ── OPORTUNIDADES DETECTADAS (autopsia) ── */
  opportunities: [],

  /* ── MÉTODOS UTILITARIOS ── */
  formatCurrency(n, decimals = 2) {
    return (n >= 0 ? '+$' : '-$') + Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  },
  formatPct(n, decimals = 2) {
    return (n >= 0 ? '+' : '') + n.toFixed(decimals) + '%';
  },
  formatPrice(n, decimals = 4) {
    return n.toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  },
  now() {
    return new Date().toTimeString().slice(0, 8);
  },
  timestamp() {
    const d = new Date();
    return d.toISOString().slice(0, 16).replace('T', ' ');
  },

  /* ── SAVE / LOAD (localStorage) ── */
  save() {
    const data = {
      mode: this.mode,
      fund: this.fund,
      apiKeys: this.apiKeys,
      risk: this.risk,
      strategies: this.strategies,
      tradeHistory: this.tradeHistory,
    };
    localStorage.setItem('jorm_state', JSON.stringify(data));
  },
  load() {
    try {
      const raw = localStorage.getItem('jorm_state');
      if (!raw) return;
      const data = JSON.parse(raw);
      if (data.mode)        this.mode = data.mode;
      if (data.fund)        Object.assign(this.fund, data.fund);
      if (data.apiKeys)     Object.assign(this.apiKeys, data.apiKeys);
      if (data.risk)        Object.assign(this.risk, data.risk);
      // Strategies se cargan siempre desde el backend — ignorar cache local
      // if (data.strategies)  this.strategies = data.strategies;
      if (data.tradeHistory)this.tradeHistory = data.tradeHistory;
    } catch(e) { console.warn('State load error:', e); }
  },
};

/* ── NAV HISTORY — punto inicial tras definir JORM ── */
function generateNavHistory() {
  // Llamada después de definir JORM, así fund.initialCapital ya existe
  return [{
    date: new Date().toISOString().slice(0, 10),
    nav:  JORM.fund.initialCapital,
  }];
}
// Inicializar con el punto de partida real
JORM.navHistory = generateNavHistory();

/* ── STRATEGIES — cargadas desde backend en initSystem() ── */
JORM.strategies = [];  // Se pobla vía API.syncStrategies() al arrancar

/* ── POSICIONES — se sincronizan desde Capital.com al conectar ── */
JORM.positions = [];

/* ── TRADE HISTORY — se carga desde el backend al conectar ── */
// JORM.tradeHistory arranca vacío (inicializado en el objeto JORM)

/* ── COMPUTE METRICS — recalcula con datos reales ── */
function computeMetrics() {
  const closed = JORM.tradeHistory;
  const wins   = closed.filter(t => t.pnl > 0);
  const losses = closed.filter(t => t.pnl < 0);

  JORM.metrics.totalTrades  = closed.length;
  JORM.metrics.winTrades    = wins.length;
  JORM.metrics.lossTrades   = losses.length;
  JORM.metrics.winRate      = closed.length > 0
    ? Math.round((wins.length / closed.length) * 1000) / 10 : 0;
  JORM.metrics.totalPnL     = Math.round(closed.reduce((s, t) => s + t.pnl, 0) * 100) / 100;
  JORM.metrics.dailyPnL     = Math.round(
    closed.filter(t => new Date(t.date) > new Date(Date.now() - 86400000))
          .reduce((s, t) => s + t.pnl, 0) * 100) / 100;

  const grossWin  = wins.reduce((s, t) => s + t.pnl, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.pnl, 0));
  JORM.metrics.profitFactor = grossLoss > 0
    ? Math.round((grossWin / grossLoss) * 100) / 100 : 0;

  // NAV = capital inicial + PnL cerrado + PnL abierto
  const openPnL = JORM.positions.reduce((s, p) => s + (p.pnl || 0), 0);
  JORM.fund.currentNAV  = JORM.fund.initialCapital + JORM.metrics.totalPnL + openPnL;
  JORM.metrics.totalReturn = Math.round(
    ((JORM.fund.currentNAV / JORM.fund.initialCapital) - 1) * 10000) / 100;

  // Sharpe y maxDD se calculan con datos reales cuando haya suficiente historial
  JORM.metrics.sharpe = 0;
  JORM.metrics.maxDD  = 0;
  JORM.metrics.currentDD = 0;
}

computeMetrics();

/* ── ALERTAS INICIALES DEL SISTEMA ── */
JORM.alerts = [
  { type: 'ok',   text: 'Sistema inicializado correctamente', time: JORM.now() },
  { type: 'info', text: 'Modo DEMO activo — Capital.com sandbox', time: JORM.now() },
  { type: 'info', text: 'Conecta Capital.com en CONFIG para cargar datos reales', time: JORM.now() },
];

/* ── OPORTUNIDADES — se generan desde el Quant Engine ── */
JORM.opportunities = [];
