# ═══════════════════════════════════════════════════════════
#  JORMUNDGANDRSSON — STRATEGY DEFINITION FILE
#  Archivo: ICARO_V2.py
# ═══════════════════════════════════════════════════════════

STRATEGY = {
    # ── IDENTIFICACIÓN ──────────────────────────────────────
    'id':          'STR-ICARO-001',
    'name':        'ICARO-V2',
    'description': 'Motor cuantitativo avanzado: HMM regime detection, '
                   'Monte Carlo, Kelly Criterion, fragility & convexity scoring. '
                   'Integración FastAPI en curso.',
    'type':        'Multi-Engine Quant',
    'version':     '2.1.0',

    # ── UNIVERSO ─────────────────────────────────────────────
    'assets':    ['EURUSD', 'GBPUSD', 'USDJPY', 'SPX500', 'NAS100', 'XAUUSD', 'USOIL'],
    'timeframe': 'Multi-TF',

    # ── ESTADO OPERACIONAL ───────────────────────────────────
    'status': 'DEMO',
    'mode':   'DEMO',
    'startDate': '2025-01-01',

    # ── PARÁMETROS ───────────────────────────────────────────
    'params': {
        'deploymentStage':  'INTEGRATION',
        'killswitchGlobal': False,
        'kellyFraction':    0.25,
        'maxDrawdownLimit': 15.0,
        'engines': 'Signal · Regime · Fragility · Convexity · Capital · Audit',
    },

    # ── MÉTRICAS (se actualizan en runtime desde snapshots) ──
    'metrics': {
        'totalTrades': 0, 'winRate': 0, 'pnl': 0,
        'pnlPct': 0, 'sharpe': 0, 'maxDD': 0, 'profitFactor': 0,
    },
}
