/* ═══════════════════════════════════════════════════════
   JORMUNDGANDRSSON — CHARTS MODULE
   Todos los charts del sistema con tema institucional
═══════════════════════════════════════════════════════ */

const JORM_CHARTS = {};

const C = {
  gold:   '#FFD400',
  green:  '#25C76F',
  red:    '#FF4D4D',
  blue:   '#3498DB',
  text1:  '#CCCCCC',
  text3:  '#666666',
  bg2:    '#111111',
  bg3:    '#161616',
  border: '#1F1F1F',
  gridLine: 'rgba(255,255,255,0.04)',
};

const BASE_OPTS = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 400 },
  plugins: {
    legend: { display: false },
    tooltip: {
      backgroundColor: '#0A0A0A',
      borderColor: C.gold,
      borderWidth: 1,
      titleColor: C.gold,
      bodyColor: C.text1,
      titleFont: { family: "'JetBrains Mono', monospace", size: 9 },
      bodyFont:  { family: "'JetBrains Mono', monospace", size: 9 },
      padding: 6,
      cornerRadius: 0,
    },
  },
  scales: {
    x: {
      grid: { color: C.gridLine, drawBorder: false },
      ticks: { color: C.text3, font: { family: "'JetBrains Mono', monospace", size: 8 }, maxTicksLimit: 8 },
      border: { color: C.border },
    },
    y: {
      grid: { color: C.gridLine, drawBorder: false },
      ticks: { color: C.text3, font: { family: "'JetBrains Mono', monospace", size: 8 } },
      border: { color: C.border },
    },
  },
};

/* ── NAV CHART ── */
function initNavChart() {
  const ctx = document.getElementById('nav-chart');
  if (!ctx) return;
  if (JORM_CHARTS.nav) { JORM_CHARTS.nav.destroy(); }

  const history = JORM.navHistory;
  const labels = history.map(h => h.date.slice(5));
  const data   = history.map(h => h.nav);

  JORM_CHARTS.nav = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        data,
        borderColor: C.gold,
        borderWidth: 1.5,
        pointRadius: 0,
        pointHoverRadius: 3,
        pointHoverBackgroundColor: C.gold,
        fill: true,
        backgroundColor: (ctx) => {
          const gradient = ctx.chart.ctx.createLinearGradient(0, 0, 0, ctx.chart.height);
          gradient.addColorStop(0, 'rgba(255,212,0,0.15)');
          gradient.addColorStop(1, 'rgba(255,212,0,0.00)');
          return gradient;
        },
        tension: 0.3,
      }],
    },
    options: {
      ...BASE_OPTS,
      plugins: {
        ...BASE_OPTS.plugins,
        tooltip: {
          ...BASE_OPTS.plugins.tooltip,
          callbacks: {
            label: (ctx) => ' NAV: $' + ctx.raw.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
          },
        },
      },
    },
  });
}

/* ── STRAT PNL BAR CHART ── */
function initStratPnlChart() {
  const ctx = document.getElementById('strat-pnl-chart');
  if (!ctx) return;
  if (JORM_CHARTS.stratPnl) JORM_CHARTS.stratPnl.destroy();

  const strats = JORM.strategies;
  const labels = strats.map(s => s.name.split('-')[0] + '-' + s.name.split('-')[1]);
  const data   = strats.map(s => s.metrics.pnl);
  const colors = data.map(v => v >= 0 ? C.green : C.red);

  JORM_CHARTS.stratPnl = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: colors.map(c => c + '33'),
        borderColor: colors,
        borderWidth: 1,
        borderRadius: 0,
      }],
    },
    options: {
      ...BASE_OPTS,
      plugins: {
        ...BASE_OPTS.plugins,
        tooltip: {
          ...BASE_OPTS.plugins.tooltip,
          callbacks: {
            label: (ctx) => ' PNL: ' + (ctx.raw >= 0 ? '+$' : '-$') + Math.abs(ctx.raw).toFixed(2),
          },
        },
      },
    },
  });
}

/* ── ALLOCATION DOUGHNUT ── */
function initAllocChart() {
  const ctx = document.getElementById('alloc-chart');
  if (!ctx) return;
  if (JORM_CHARTS.alloc) JORM_CHARTS.alloc.destroy();

  const strats = JORM.strategies.filter(s => s.status !== 'PAUSED');
  const labels = strats.map(s => s.id);
  const colors = [C.gold, C.green, C.blue, '#E67E22', '#9B59B6'];

  JORM_CHARTS.alloc = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: strats.map((_, i) => Math.round(100 / strats.length)),
        backgroundColor: colors.map(c => c + '55'),
        borderColor: colors,
        borderWidth: 1,
      }],
    },
    options: {
      ...BASE_OPTS,
      cutout: '65%',
      plugins: {
        ...BASE_OPTS.plugins,
        legend: {
          display: true,
          position: 'right',
          labels: {
            color: C.text3,
            font: { family: "'JetBrains Mono', monospace", size: 8 },
            boxWidth: 8, padding: 6,
          },
        },
      },
      scales: {},
    },
  });
}

/* ── DAILY PNL BARS ── */
function initDailyPnlChart() {
  const ctx = document.getElementById('daily-pnl-chart');
  if (!ctx) return;
  if (JORM_CHARTS.daily) JORM_CHARTS.daily.destroy();

  const days = 20;
  const labels = [];
  const data = [];
  for (let i = days; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    labels.push(d.toISOString().slice(5, 10));
    data.push(Math.round((Math.random() - 0.38) * 200 * 100) / 100);
  }

  JORM_CHARTS.daily = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data,
        backgroundColor: data.map(v => v >= 0 ? C.green + '55' : C.red + '55'),
        borderColor:      data.map(v => v >= 0 ? C.green : C.red),
        borderWidth: 1,
        borderRadius: 0,
      }],
    },
    options: {
      ...BASE_OPTS,
      plugins: { ...BASE_OPTS.plugins },
    },
  });
}

/* ── DRAWDOWN CHART ── */
function initDrawdownChart() {
  const ctx = document.getElementById('drawdown-chart');
  if (!ctx) return;
  if (JORM_CHARTS.drawdown) JORM_CHARTS.drawdown.destroy();

  const history = JORM.navHistory;
  const labels = history.map(h => h.date.slice(5));
  let hwm = history[0].nav;
  const ddData = history.map(h => {
    if (h.nav > hwm) hwm = h.nav;
    return Math.round(((h.nav / hwm) - 1) * 10000) / 100;
  });

  JORM_CHARTS.drawdown = new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [{
        label: 'Drawdown %',
        data: ddData,
        borderColor: C.red,
        borderWidth: 1.5,
        pointRadius: 0,
        fill: true,
        backgroundColor: 'rgba(255,77,77,0.1)',
        tension: 0.3,
      }],
    },
    options: {
      ...BASE_OPTS,
      scales: {
        ...BASE_OPTS.scales,
        y: {
          ...BASE_OPTS.scales.y,
          ticks: {
            ...BASE_OPTS.scales.y.ticks,
            callback: v => v + '%',
          },
        },
      },
    },
  });
}

/* ── PNL HISTOGRAM ── */
function initPnlHistChart() {
  const ctx = document.getElementById('pnl-hist-chart');
  if (!ctx) return;
  if (JORM_CHARTS.pnlHist) JORM_CHARTS.pnlHist.destroy();

  const trades = JORM.tradeHistory.slice(-30).map(t => t.pnl);
  const labels = JORM.tradeHistory.slice(-30).map((_, i) => '#' + (i + 1));

  JORM_CHARTS.pnlHist = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: trades,
        backgroundColor: trades.map(v => v >= 0 ? C.green + '55' : C.red + '55'),
        borderColor:      trades.map(v => v >= 0 ? C.green : C.red),
        borderWidth: 1,
      }],
    },
    options: { ...BASE_OPTS },
  });
}

/* ── VOL PROFILE CHART ── */
function initVolProfileChart() {
  const ctx = document.getElementById('vol-profile-chart');
  if (!ctx) return;
  if (JORM_CHARTS.volProfile) JORM_CHARTS.volProfile.destroy();

  const levels = 14;
  const basePrice = 5800;
  const step = 10;
  const poc = 7;
  const labels = [];
  const volumes = [];
  const colors  = [];

  for (let i = 0; i < levels; i++) {
    labels.push((basePrice + i * step).toFixed(0));
    const vol = i === poc ? 100 : Math.round(20 + Math.random() * 60);
    volumes.push(vol);
    colors.push(i === poc ? C.gold + '99' : i > poc - 2 && i < poc + 2 ? C.green + '66' : C.blue + '44');
  }

  JORM_CHARTS.volProfile = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: volumes,
        backgroundColor: colors,
        borderColor: colors.map(c => c.slice(0,7)),
        borderWidth: 1,
        borderRadius: 0,
      }],
    },
    options: {
      ...BASE_OPTS,
      indexAxis: 'y',
      scales: {
        x: { ...BASE_OPTS.scales.x, display: false },
        y: { ...BASE_OPTS.scales.y, ticks: { color: C.text3, font: { family: "'JetBrains Mono', monospace", size: 8 } } },
      },
    },
  });
}

/* ── UPDATE NAV TF ── */
function setNavTF(tf) {
  document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');

  const days = { '1W': 7, '1M': 30, '3M': 90, '6M': 180, '1Y': 365 }[tf] || 30;
  const sliced = JORM.navHistory.slice(-days);
  if (JORM_CHARTS.nav) {
    JORM_CHARTS.nav.data.labels   = sliced.map(h => h.date.slice(5));
    JORM_CHARTS.nav.data.datasets[0].data = sliced.map(h => h.nav);
    JORM_CHARTS.nav.update('none');
  }
}

/* ── INIT ALL CHARTS ── */
function initAllCharts() {
  setTimeout(() => {
    initNavChart();
    initStratPnlChart();
    initAllocChart();
    initDailyPnlChart();
    initDrawdownChart();
    initPnlHistChart();
    initVolProfileChart();
  }, 100);
}
