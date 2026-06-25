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

  /* ── HISTORIAL NAV (datos de demostración) ── */
  navHistory: generateNavHistory(),

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
      if (data.strategies)  this.strategies = data.strategies;
      if (data.tradeHistory)this.tradeHistory = data.tradeHistory;
    } catch(e) { console.warn('State load error:', e); }
  },
};

/* ── GENERATE DEMO NAV HISTORY ── */
function generateNavHistory() {
  const days = 90;
  const history = [];
  let nav = 10000;
  const start = new Date();
  start.setDate(start.getDate() - days);

  for (let i = 0; i <= days; i++) {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    const daily = (Math.random() - 0.42) * 0.018;
    nav = nav * (1 + daily);
    history.push({
      date: d.toISOString().slice(0, 10),
      nav: Math.round(nav * 100) / 100,
    });
  }
  return history;
}

/* ── DEMO STRATEGIES ── */
JORM.strategies = [
  {
    id: 'STR-001',
    name: 'MOMENTUM-ALPHA',
    description: 'Multi-factor momentum en índices US. Combina RSI, MACD y volumen relativo con filtro de régimen VIX.',
    type: 'Momentum + Breakout',
    assets: ['SPX500', 'NAS100'],
    timeframe: '1H / 4H',
    status: 'LIVE',
    mode: 'DEMO',
    startDate: '2025-01-15',
    params: {
      rsiPeriod: 14, macdFast: 12, macdSlow: 26,
      riskPerTrade: 1.5, maxPositions: 3, vixFilter: 25,
    },
    metrics: {
      totalTrades: 47, winRate: 68.1, pnl: 1284.50,
      pnlPct: 12.84, sharpe: 1.92, maxDD: -4.2, profitFactor: 2.31,
    },
  },
  {
    id: 'STR-002',
    name: 'MEAN-REV-FX',
    description: 'Mean reversion estadístico en pares Forex majors. Z-score + Bollinger + ATR para sizing.',
    type: 'Mean Reversion',
    assets: ['EURUSD', 'GBPUSD', 'USDJPY'],
    timeframe: '15M / 1H',
    status: 'LIVE',
    mode: 'DEMO',
    startDate: '2025-02-01',
    params: {
      zScoreThresh: 2.0, bbPeriod: 20, bbStdDev: 2.0,
      riskPerTrade: 1.0, maxPositions: 4, atrMultiplier: 1.5,
    },
    metrics: {
      totalTrades: 89, winRate: 61.8, pnl: 743.20,
      pnlPct: 7.43, sharpe: 1.44, maxDD: -5.8, profitFactor: 1.87,
    },
  },
  {
    id: 'STR-003',
    name: 'GOLD-MACRO',
    description: 'Estrategia macro en Gold (XAUUSD). Correlación DXY + yields + sentimiento para timing.',
    type: 'Multi-factor Macro',
    assets: ['XAUUSD'],
    timeframe: '4H / D',
    status: 'DEMO',
    mode: 'DEMO',
    startDate: '2025-03-10',
    params: {
      dxyCorr: -0.75, yieldCorr: -0.60,
      riskPerTrade: 2.0, maxPositions: 2, fearGreedFilter: 30,
    },
    metrics: {
      totalTrades: 18, winRate: 72.2, pnl: 392.80,
      pnlPct: 3.93, sharpe: 2.14, maxDD: -3.1, profitFactor: 2.78,
    },
  },
  {
    id: 'STR-004',
    name: 'OIL-BREAKOUT',
    description: 'Breakout en USOIL con filtro de inventarios EIA y posicionamiento COT.',
    type: 'Breakout + COT',
    assets: ['USOIL'],
    timeframe: '1H / 4H',
    status: 'PAUSED',
    mode: 'DEMO',
    startDate: '2025-01-20',
    params: {
      breakoutPeriod: 20, cotFilter: true,
      riskPerTrade: 1.0, maxPositions: 2,
    },
    metrics: {
      totalTrades: 31, winRate: 54.8, pnl: -142.30,
      pnlPct: -1.42, sharpe: 0.82, maxDD: -6.4, profitFactor: 1.12,
    },
  },
];

/* ── DEMO POSITIONS ── */
JORM.positions = [
  { id: 'P001', symbol: 'SPX500', strategy: 'STR-001', side: 'BUY',  size: 0.5,  entry: 5812.0,  current: 5847.3, sl: 5770.0,  tp: 5920.0,  pnl: 17.65,  pnlPct: 0.61, duration: '3h 22m' },
  { id: 'P002', symbol: 'EURUSD', strategy: 'STR-002', side: 'SELL', size: 10000, entry: 1.0862, current: 1.0842, sl: 1.0910, tp: 1.0790, pnl: 20.00,  pnlPct: 0.18, duration: '1h 45m' },
  { id: 'P003', symbol: 'XAUUSD', strategy: 'STR-003', side: 'BUY',  size: 0.1,  entry: 2298.0,  current: 2318.5, sl: 2268.0,  tp: 2360.0,  pnl: 20.50,  pnlPct: 0.89, duration: '6h 10m' },
  { id: 'P004', symbol: 'NAS100', strategy: 'STR-001', side: 'BUY',  size: 0.2,  entry: 20750.0, current: 20841.5,sl: 20600.0, tp: 21100.0, pnl: 18.30,  pnlPct: 0.44, duration: '2h 58m' },
  { id: 'P005', symbol: 'GBPUSD', strategy: 'STR-002', side: 'BUY',  size: 8000, entry: 1.2720,  current: 1.2734, sl: 1.2680,  tp: 1.2810,  pnl: 11.20,  pnlPct: 0.11, duration: '4h 15m' },
];

/* ── DEMO TRADE HISTORY ── */
(function() {
  const syms = ['SPX500','NAS100','EURUSD','GBPUSD','XAUUSD','USOIL','USDJPY'];
  const strats = ['STR-001','STR-002','STR-003'];
  const sides = ['BUY','SELL'];
  for (let i = 0; i < 40; i++) {
    const pnl = (Math.random() - 0.38) * 120;
    const d = new Date();
    d.setHours(d.getHours() - Math.floor(Math.random() * 240));
    JORM.tradeHistory.push({
      id: 'T' + String(i).padStart(3,'0'),
      date: d.toISOString().slice(0,16).replace('T',' '),
      symbol: syms[Math.floor(Math.random()*syms.length)],
      strategy: strats[Math.floor(Math.random()*strats.length)],
      side: sides[Math.floor(Math.random()*2)],
      entry: (100 + Math.random() * 5000).toFixed(2),
      exit:  (100 + Math.random() * 5000).toFixed(2),
      pnl: Math.round(pnl * 100) / 100,
      pnlPct: Math.round((pnl / 100) * 100) / 100,
      duration: Math.floor(Math.random() * 480) + 'm',
      rr: (0.5 + Math.random() * 2.5).toFixed(2),
    });
  }
})();

/* ── COMPUTE METRICS ── */
(function computeMetrics() {
  const closed = JORM.tradeHistory;
  const wins = closed.filter(t => t.pnl > 0);
  JORM.metrics.totalTrades = closed.length;
  JORM.metrics.winTrades   = wins.length;
  JORM.metrics.lossTrades  = closed.length - wins.length;
  JORM.metrics.winRate     = closed.length > 0 ? Math.round((wins.length / closed.length) * 1000) / 10 : 0;
  JORM.metrics.totalPnL    = Math.round(closed.reduce((s, t) => s + t.pnl, 0) * 100) / 100;
  JORM.metrics.dailyPnL    = Math.round(closed.filter(t => {
    return new Date(t.date) > new Date(Date.now() - 86400000);
  }).reduce((s, t) => s + t.pnl, 0) * 100) / 100;

  const grossWin  = wins.reduce((s, t) => s + t.pnl, 0);
  const grossLoss = Math.abs(closed.filter(t => t.pnl < 0).reduce((s, t) => s + t.pnl, 0));
  JORM.metrics.profitFactor = grossLoss > 0 ? Math.round((grossWin / grossLoss) * 100) / 100 : 0;

  JORM.fund.currentNAV = JORM.fund.initialCapital + JORM.metrics.totalPnL;
  JORM.metrics.totalReturn = Math.round(((JORM.fund.currentNAV / JORM.fund.initialCapital) - 1) * 10000) / 100;
  JORM.metrics.sharpe = 1.84; /* demo */
  JORM.metrics.maxDD  = -8.32;

  const openPnL = JORM.positions.reduce((s, p) => s + p.pnl, 0);
  JORM.metrics.dailyPnL += openPnL;
})();

/* ── DEMO ALERTS ── */
JORM.alerts = [
  { type: 'ok',   text: 'Sistema inicializado correctamente', time: JORM.now() },
  { type: 'info', text: 'Modo DEMO activo — Capital.com sandbox', time: JORM.now() },
  { type: 'warn', text: 'STR-004 pausada: drawdown excedió 6%', time: '09:32:15' },
  { type: 'ok',   text: 'STR-001 ejecutó BUY SPX500 @ 5812.0', time: '08:45:22' },
  { type: 'ok',   text: 'STR-003 ejecutó BUY XAUUSD @ 2298.0', time: '07:20:44' },
  { type: 'warn', text: 'VIX en 18.4 — monitoreando régimen', time: '07:00:00' },
];

/* ── DEMO OPPORTUNITIES (AUTOPSIA) ── */
JORM.opportunities = [
  {
    symbol: 'XAUUSD', direction: 'LONG', score: 87,
    entryPrice: 2314.50, sl: 2295.0, tp: 2355.0,
    context: 'DXY debilitándose · Yields bajando · COT: comerciales largos · Régimen risk-off parcial',
    confidence: 'HIGH', strategy: 'STR-003',
  },
  {
    symbol: 'EURUSD', direction: 'LONG', score: 71,
    entryPrice: 1.0835, sl: 1.0800, tp: 1.0920,
    context: 'Z-score: -2.1 · Soporte 1.0820 testeado · Put/Call bajando · News: neutral',
    confidence: 'MED', strategy: 'STR-002',
  },
  {
    symbol: 'NAS100', direction: 'SHORT', score: 58,
    entryPrice: 20850, sl: 20980, tp: 20450,
    context: 'Momentum sobreextendido · VIX en aumento · GEX negativo sobre 20900',
    confidence: 'LOW', strategy: 'STR-001',
  },
];
