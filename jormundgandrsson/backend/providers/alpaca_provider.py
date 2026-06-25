# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — ALPACA PROVIDER
# Wrapper fino sobre AlpacaDataProvider ya existente en icaro_runner.
# NO duplica lógica — importa la clase directamente.
#
# Expone al Data Bus:
#   - Precios de ETFs de referencia (SPY, QQQ, TLT, VIXY...)
#   - Velas diarias de equities para el módulo MMON
#   - VIX proxy via VIXY
# ═══════════════════════════════════════════════════════════

import os
import time
import sys
from pathlib import Path
from cache.ttl_cache import cache

# ── IMPORTAR AlpacaDataProvider SIN EJECUTAR EL RUNNER ───────
# icaro_runner.py contiene la clase — la importamos directamente
# sin instanciar el IcaroRunner completo.
try:
    # Asegurar que el directorio backend esté en el path
    _backend_dir = Path(__file__).parent.parent
    if str(_backend_dir) not in sys.path:
        sys.path.insert(0, str(_backend_dir))

    from icaro_runner import AlpacaDataProvider as _AlpacaDataProvider
    _ALPACA_AVAILABLE = True
except ImportError as e:
    print(f'[ALPACA PROVIDER] Warning: No se pudo importar AlpacaDataProvider: {e}')
    _AlpacaDataProvider = None
    _ALPACA_AVAILABLE   = False


# ETFs de referencia institucional
REFERENCE_ETFS = {
    'SPY':  'S&P 500 ETF',
    'QQQ':  'Nasdaq 100 ETF',
    'IWM':  'Russell 2000 ETF',
    'TLT':  'US 20Y Treasury ETF (yield proxy)',
    'SHY':  'US 1-3Y Treasury ETF (short yield)',
    'HYG':  'High Yield Corporate Bond ETF',
    'LQD':  'Investment Grade Bond ETF',
    'VIXY': 'VIX Short-Term Futures ETF (VIX proxy)',
    'GLD':  'Gold ETF',
    'USO':  'Oil ETF',
    'VXX':  'VIX ETP',
}


class AlpacaProvider:
    """
    Proveedor Alpaca para el Data Bus.
    Alimenta datos de equities/ETFs que Capital.com no cubre bien.
    """

    def __init__(self):
        api_key    = os.getenv('ALPACA_API_KEY', '')
        api_secret = os.getenv('ALPACA_API_SECRET', '')

        if _ALPACA_AVAILABLE and api_key and api_secret:
            self._provider = _AlpacaDataProvider(api_key, api_secret)
            print(f'[ALPACA PROVIDER] Conectado — available: {self._provider.connected}')
        else:
            self._provider = None
            if not _ALPACA_AVAILABLE:
                print('[ALPACA PROVIDER] AlpacaDataProvider no disponible')
            else:
                print('[ALPACA PROVIDER] Credenciales no configuradas — modo offline')

    @property
    def connected(self) -> bool:
        return self._provider is not None and self._provider.connected

    # ── ETF / EQUITY BARS ─────────────────────────────────────

    def get_bars(self, symbol: str, timeframe: str = '1Day', limit: int = 60) -> list:
        """
        Velas OHLCV de un ETF o equity via Alpaca.
        Retorna lista de dicts: { time, open, high, low, close, volume }
        """
        cache_key = f'{symbol}_{timeframe}_{limit}'
        cached    = cache.get('correlations', cache_key)
        if cached is not None:
            return cached

        if not self.connected:
            return []

        try:
            df = self._provider.get_bars(symbol, timeframe=timeframe, limit=limit)
            if df is None or df.empty:
                return []

            candles = []
            for idx, row in df.iterrows():
                candles.append({
                    'time':   str(idx),
                    'open':   round(float(row.get('open',  0)), 4),
                    'high':   round(float(row.get('high',  0)), 4),
                    'low':    round(float(row.get('low',   0)), 4),
                    'close':  round(float(row.get('close', 0)), 4),
                    'volume': int(row.get('volume', 0)),
                })

            cache.set('correlations', cache_key, candles)
            return candles

        except Exception as e:
            print(f'[ALPACA PROVIDER] Error bars {symbol}: {e}')
            return []

    def get_latest_price(self, symbol: str) -> dict:
        """
        Precio más reciente de un ETF/equity.
        Útil para VIX proxy (VIXY), yield proxy (TLT), etc.
        """
        cache_key = f'price_{symbol}'
        cached    = cache.get('prices', cache_key)
        if cached:
            return cached

        if not self.connected:
            return {'symbol': symbol, 'ok': False, 'error': 'Alpaca no conectado'}

        try:
            quote = self._provider.get_latest_quote(symbol)
            if quote:
                # Alpaca quote: bid_price, ask_price, bid_size, ask_size
                bid = quote.get('bp', 0) or quote.get('bid_price', 0)
                ask = quote.get('ap', 0) or quote.get('ask_price', 0)
                mid = round((bid + ask) / 2, 4) if bid and ask else bid or ask

                result = {
                    'symbol':    symbol,
                    'bid':       bid,
                    'ask':       ask,
                    'mid':       mid,
                    'timestamp': time.time(),
                    'source':    'alpaca',
                    'ok':        True,
                }
                cache.set('prices', cache_key, result)
                return result

            return {'symbol': symbol, 'ok': False, 'error': 'Sin datos'}

        except Exception as e:
            print(f'[ALPACA PROVIDER] Error quote {symbol}: {e}')
            return {'symbol': symbol, 'ok': False, 'error': str(e)}

    def get_vix_proxy(self) -> dict:
        """
        VIX proxy via VIXY ETF.
        Retorna precio y nivel de riesgo interpretado.
        """
        cached = cache.get('prices', 'vix_proxy')
        if cached:
            return cached

        # Intentar con VIXY primero, fallback a VXX
        for symbol in ['VIXY', 'VXX']:
            price_data = self.get_latest_price(symbol)
            if price_data.get('ok'):
                mid = price_data.get('mid', 0)

                # Interpretar nivel de VIX proxy
                if mid < 15:
                    level = 'LOW'
                    regime = 'COMPLACENCY'
                elif mid < 20:
                    level = 'NORMAL'
                    regime = 'NEUTRAL'
                elif mid < 30:
                    level = 'ELEVATED'
                    regime = 'CAUTION'
                elif mid < 40:
                    level = 'HIGH'
                    regime = 'FEAR'
                else:
                    level = 'EXTREME'
                    regime = 'PANIC'

                result = {
                    'proxy_symbol': symbol,
                    'price':        mid,
                    'level':        level,
                    'regime':       regime,
                    'timestamp':    time.time(),
                    'source':       'alpaca/vixy',
                    'ok':           True,
                }
                cache.set('prices', 'vix_proxy', result)
                return result

        return {'ok': False, 'error': 'Sin datos de VIX proxy', 'level': 'UNKNOWN'}

    def get_reference_snapshot(self) -> dict:
        """
        Snapshot de ETFs de referencia institucional.
        Útil para el panel de Régimen Macro y MMON.
        """
        cached = cache.get('prices', 'alpaca_snapshot')
        if cached:
            return cached

        snapshot = {}
        key_etfs = ['SPY', 'QQQ', 'TLT', 'HYG', 'VIXY']

        for sym in key_etfs:
            data = self.get_latest_price(sym)
            if data.get('ok'):
                snapshot[sym] = {
                    'price':  data.get('mid'),
                    'source': 'alpaca',
                }

        # Añadir VIX interpretado
        vix = self.get_vix_proxy()
        if vix.get('ok'):
            snapshot['VIX_PROXY'] = vix

        cache.set('prices', 'alpaca_snapshot', snapshot)
        return snapshot

    def status(self) -> dict:
        return {
            'connected':  self.connected,
            'provider':   'alpaca',
            'etfs_available': list(REFERENCE_ETFS.keys()),
        }
