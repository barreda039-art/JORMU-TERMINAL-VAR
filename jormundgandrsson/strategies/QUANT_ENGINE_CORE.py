# ═══════════════════════════════════════════════════════════
#  JORMUNDGANDRSSON — STRATEGY DEFINITION FILE
#  Archivo: QUANT_ENGINE_CORE.py
#  Cada archivo .py en esta carpeta se registra automáticamente
#  en el terminal como una estrategia activa.
# ═══════════════════════════════════════════════════════════

STRATEGY = {
    # ── IDENTIFICACIÓN ──────────────────────────────────────
    'id':          'STR-QE-001',
    'name':        'QUANT-ENGINE-CORE',
    'description': 'Motor cuantitativo institucional. Order Blocks, FVG, '
                   'liquidez y confirmación multi-capa. '
                   'Auto-ejecución ≥80, aprobación manual 60-79.',
    'type':        'Multi-factor Structural',
    'version':     '1.0.0',

    # ── UNIVERSO ─────────────────────────────────────────────
    'assets':    ['EURUSD', 'GBPUSD', 'USDJPY', 'SPX500', 'NAS100', 'XAUUSD', 'USOIL'],
    'timeframe': '15M / 1H / 4H',

    # ── ESTADO OPERACIONAL ───────────────────────────────────
    'status': 'LIVE',   # LIVE | DEMO | PAUSED
    'mode':   'DEMO',   # DEMO | LIVE
    'startDate': '2025-01-01',

    # ── PARÁMETROS DEL ENGINE ────────────────────────────────
    'params': {
        'autoExecuteThreshold':    80,
        'manualApprovalThreshold': 60,
        'riskPerTrade':            1.0,
        'maxPositions':            7,
        'intervalMinutes':         15,
        'layers': 'MacroRegime · MarketStructure · InstitutionalZones · EntryConfirmation',
    },

    # ── MÉTRICAS (se actualizan en runtime) ──────────────────
    'metrics': {
        'totalTrades': 0, 'winRate': 0, 'pnl': 0,
        'pnlPct': 0, 'sharpe': 0, 'maxDD': 0, 'profitFactor': 0,
    },
}
