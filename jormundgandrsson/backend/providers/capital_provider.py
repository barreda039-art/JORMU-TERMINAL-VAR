# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — CAPITAL PROVIDER
# Wrapper fino sobre CapitalClient existente.
# NO modifica capital_client.py — solo lo consume.
#
# Añade:
#   - Mapeo lógico símbolo → epic de Capital.com
#   - Acumulación de delta bid/ask para order flow
#   - Acceso a clientsentiment (% long/short)
#   - Normalización de respuestas para el Data Bus
# ═══════════════════════════════════════════════════════════

import time
import threading
from collections import deque
from cache.ttl_cache import cache


# ── MAPEO SÍMBOLO → EPIC DE CAPITAL.COM ──────────────────────
# Símbolo lógico que usamos internamente → epic real en Capital.com DEMO
SYMBOL_TO_EPIC = {
    'EURUSD': 'EURUSD',
    'GBPUSD': 'GBPUSD',
    'USDJPY': 'USDJPY',
    'SPX500': 'US500',
    'NAS100': 'US100',
    'XAUUSD': 'GOLD',
    'USOIL':  'OIL_CRUDE',
    # Macros adicionales para Autopsia / MMON
    'DXY':    'CS.D.DOLALIDX.TODAY.IP',
    'VIX':    'CS.D.USAVIX.TODAY.IP',
    'GBPJPY': 'GBPJPY',
    'EURGBP': 'EURGBP',
    'AUDUSD': 'AUDUSD',
    'USDCAD': 'USDCAD',
    'XAGUSD': 'SILVER',
}

# Los 7 assets principales del Quant Engine
CORE_ASSETS = ['EURUSD', 'GBPUSD', 'USDJPY', 'SPX500', 'NAS100', 'XAUUSD', 'USOIL']

# Buffer de ticks para order flow: últimas N actualizaciones por símbolo
ORDER_FLOW_WINDOW = 100


class CapitalProvider:
    """
    Proveedor de datos de Capital.com para el Data Bus.
    Recibe la instancia de CapitalClient ya existente en server.py.
    """

    def __init__(self, capital_client):
        self.client = capital_client

        # Buffers de order flow: { symbol: deque([(bid, ask, timestamp), ...]) }
        self._of_buffers: dict = {sym: deque(maxlen=ORDER_FLOW_WINDOW) for sym in CORE_ASSETS}
        self._of_lock = threading.Lock()

    # ── PRECIOS ───────────────────────────────────────────────

    def get_price(self, symbol: str) -> dict:
        """
        Precio en tiempo real de un símbolo.
        Primero busca en caché (5s TTL), si no llama a Capital.com.
        """
        cached = cache.get('prices', symbol)
        if cached:
            return cached

        epic   = SYMBOL_TO_EPIC.get(symbol, symbol)
        result = self.client.get_price(epic)

        if result.get('ok'):
            normalized = {
                'symbol':     symbol,
                'epic':       epic,
                'bid':        result.get('bid'),
                'ask':        result.get('ask'),
                'mid':        result.get('mid'),
                'change_pct': result.get('change'),
                'high':       result.get('high'),
                'low':        result.get('low'),
                'status':     result.get('status'),
                'timestamp':  time.time(),
                'source':     'capital.com',
            }
            # Alimentar buffer de order flow
            self._push_tick(symbol, result.get('bid'), result.get('ask'))

            cache.set('prices', symbol, normalized)
            return normalized

        return {'symbol': symbol, 'error': result.get('error'), 'ok': False}

    def get_prices_bulk(self, symbols: list = None) -> dict:
        """
        Precios de múltiples símbolos. Retorna dict { symbol: price_data }.
        Si symbols es None, usa los 7 assets del core.
        """
        symbols = symbols or CORE_ASSETS
        result  = {}
        for sym in symbols:
            result[sym] = self.get_price(sym)
        return result

    def get_candles(self, symbol: str, resolution: str = 'HOUR', count: int = 100) -> list:
        """
        Velas OHLCV históricas. TTL 5min para datos intraday.
        resolution: MINUTE | MINUTE_5 | MINUTE_15 | MINUTE_30 | HOUR | HOUR_4 | DAY | WEEK
        """
        cache_key = f'{symbol}_{resolution}_{count}'
        cached    = cache.get('correlations', cache_key)   # reutiliza TTL de correlaciones
        if cached:
            return cached

        epic   = SYMBOL_TO_EPIC.get(symbol, symbol)
        result = self.client.get_prices_history(epic, resolution, count)

        if result.get('ok'):
            candles = result.get('candles', [])
            cache.set('correlations', cache_key, candles)
            return candles

        return []

    # ── ORDER FLOW ────────────────────────────────────────────

    def _push_tick(self, symbol: str, bid, ask):
        """Registra un tick en el buffer de order flow del símbolo."""
        if bid is None or ask is None:
            return
        with self._of_lock:
            if symbol in self._of_buffers:
                self._of_buffers[symbol].append({
                    'bid': bid,
                    'ask': ask,
                    'ts':  time.time(),
                })

    def get_orderflow(self, symbol: str) -> dict:
        """
        Calcula métricas de order flow desde el buffer de ticks acumulados.

        Delta = acumulación de (ask - bid) como proxy de presión compradora/vendedora.
        Imbalance = delta normalizado entre -1 y 1.
        """
        cached = cache.get('orderflow', symbol)
        if cached:
            return cached

        with self._of_lock:
            ticks = list(self._of_buffers.get(symbol, []))

        if len(ticks) < 2:
            return {
                'symbol':    symbol,
                'delta':     0,
                'imbalance': 0,
                'pressure':  'NEUTRAL',
                'ticks':     len(ticks),
                'note':      'Acumulando ticks...',
            }

        # Spread medio como baseline
        spreads    = [t['ask'] - t['bid'] for t in ticks]
        avg_spread = sum(spreads) / len(spreads) if spreads else 0

        # Delta: diferencia entre movimientos de ask vs bid
        # Sube el ask más que el bid → presión compradora
        ask_moves  = [ticks[i]['ask'] - ticks[i-1]['ask'] for i in range(1, len(ticks))]
        bid_moves  = [ticks[i]['bid'] - ticks[i-1]['bid'] for i in range(1, len(ticks))]

        buy_pressure  = sum(m for m in ask_moves if m > 0)
        sell_pressure = abs(sum(m for m in bid_moves if m < 0))
        total         = buy_pressure + sell_pressure

        imbalance = 0.0
        if total > 0:
            imbalance = round((buy_pressure - sell_pressure) / total, 4)

        pressure = 'NEUTRAL'
        if imbalance > 0.2:
            pressure = 'BUYING'
        elif imbalance < -0.2:
            pressure = 'SELLING'

        result = {
            'symbol':      symbol,
            'delta':       round(buy_pressure - sell_pressure, 6),
            'imbalance':   imbalance,
            'pressure':    pressure,
            'avg_spread':  round(avg_spread, 6),
            'buy_pressure': round(buy_pressure, 6),
            'sell_pressure': round(sell_pressure, 6),
            'ticks':       len(ticks),
            'timestamp':   time.time(),
            'source':      'capital.com/orderflow',
        }

        cache.set('orderflow', symbol, result)
        return result

    # ── CLIENT SENTIMENT ─────────────────────────────────────

    def get_sentiment(self, symbols: list = None) -> dict:
        """
        % Long / % Short de clientes de Capital.com por instrumento.
        Endpoint: /api/v1/clientsentiment
        Retorna dict { symbol: { long_pct, short_pct, bias } }
        """
        symbols  = symbols or CORE_ASSETS
        cache_key = ','.join(sorted(symbols))
        cached   = cache.get('sentiment', cache_key)
        if cached:
            return cached

        if not self.client.connected:
            return {}

        try:
            self.client._refresh_if_needed()
            # Capital.com acepta múltiples epics separados por coma
            epics_str = ','.join(SYMBOL_TO_EPIC.get(s, s) for s in symbols)
            r = self.client.session.get(
                f'{self.client.base_url}/clientsentiment',
                headers=self.client._headers(),
                params={'epics': epics_str},
                timeout=10,
            )

            sentiment_map = {}
            if r.status_code == 200:
                items = r.json().get('clientSentiments', [])
                # Invertir mapeo epic → symbol para lookup
                epic_to_sym = {v: k for k, v in SYMBOL_TO_EPIC.items()}
                for item in items:
                    epic     = item.get('instrumentName', '')
                    long_pct = item.get('longPositionPercentage', 50)
                    short_pct = item.get('shortPositionPercentage', 50)
                    sym      = epic_to_sym.get(epic, epic)
                    bias     = 'BULL' if long_pct > 55 else 'BEAR' if short_pct > 55 else 'NEUT'
                    sentiment_map[sym] = {
                        'long_pct':  round(long_pct, 1),
                        'short_pct': round(short_pct, 1),
                        'bias':      bias,
                        'source':    'capital.com/sentiment',
                    }

            cache.set('sentiment', cache_key, sentiment_map)
            return sentiment_map

        except Exception as e:
            print(f'[CAPITAL PROVIDER] Error sentiment: {e}')
            return {}

    # ── CORRELACIONES ─────────────────────────────────────────

    def get_correlations(self, symbols: list = None, days: int = 30) -> dict:
        """
        Matriz de correlación calculada sobre velas diarias reales.
        Retorna { 'assets': [...], 'matrix': [[...]], 'timestamp': ... }
        """
        symbols   = symbols or CORE_ASSETS
        cache_key = f'corr_{days}d'
        cached    = cache.get('correlations', cache_key)
        if cached:
            return cached

        closes = {}
        for sym in symbols:
            candles = self.get_candles(sym, resolution='DAY', count=days + 5)
            if candles:
                closes[sym] = [c['close'] for c in candles if c.get('close')]

        if len(closes) < 2:
            return {'assets': symbols, 'matrix': [], 'error': 'Datos insuficientes'}

        # Calcular correlaciones de Pearson manualmente (sin numpy para no añadir deps)
        def pearson(x, y):
            n = min(len(x), len(y))
            if n < 5:
                return 0.0
            x, y = x[-n:], y[-n:]
            mx, my = sum(x)/n, sum(y)/n
            num    = sum((x[i]-mx)*(y[i]-my) for i in range(n))
            dx     = (sum((v-mx)**2 for v in x))**0.5
            dy     = (sum((v-my)**2 for v in y))**0.5
            if dx == 0 or dy == 0:
                return 0.0
            return round(num / (dx * dy), 4)

        assets = [s for s in symbols if s in closes]
        matrix = []
        for s1 in assets:
            row = []
            for s2 in assets:
                if s1 == s2:
                    row.append(1.0)
                else:
                    row.append(pearson(closes[s1], closes[s2]))
            matrix.append(row)

        result = {
            'assets':    assets,
            'matrix':    matrix,
            'days':      days,
            'timestamp': time.time(),
            'source':    'capital.com/candles',
        }

        cache.set('correlations', cache_key, result)
        return result
