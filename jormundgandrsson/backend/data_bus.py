# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — DATA BUS
# Orquestador central de datos de mercado.
# Singleton compartido por todos los módulos del sistema.
#
# Principio: las estrategias, paneles y módulos NUNCA hablan
# directamente con ninguna API. Todo pasa por aquí.
#
# Uso:
#   from data_bus import data_bus
#   snapshot = data_bus.get_market_snapshot()
# ═══════════════════════════════════════════════════════════

import time
import threading
from cache.ttl_cache import cache


class DataBus:
    """
    Orquestador central de datos de mercado.
    Se inicializa una vez en server.py y se pasa/importa donde se necesite.
    """

    def __init__(self):
        self._capital  = None   # CapitalProvider  — inyectado en init()
        self._finnhub  = None   # FinnhubProvider  — inyectado en init()
        self._ff       = None   # ForexFactoryProvider — inyectado en init()
        self._alpaca   = None   # AlpacaProvider   — inyectado en init()
        self._engine   = None   # QuantEngine ref  — inyectado en init()
        self._bridge   = None   # IcaroBridge ref  — inyectado en init()

        self._initialized = False
        self._lock        = threading.Lock()
        print('[DATA BUS] Instancia creada — pendiente de init()')

    def init(self, capital_client, quant_engine, icaro_bridge):
        """
        Inicializa el bus con las dependencias del sistema.
        Llamar UNA SOLA VEZ desde server.py después de crear los objetos principales.

        Args:
            capital_client: instancia de CapitalClient (ya conectada o no)
            quant_engine:   instancia de QuantEngine
            icaro_bridge:   instancia de IcaroBridge (singleton)
        """
        with self._lock:
            if self._initialized:
                print('[DATA BUS] Ya inicializado — ignorando llamada duplicada')
                return

            # Instanciar providers
            from providers.capital_provider    import CapitalProvider
            from providers.finnhub_provider    import FinnhubProvider
            from providers.forexfactory_provider import ForexFactoryProvider
            from providers.alpaca_provider     import AlpacaProvider

            self._capital = CapitalProvider(capital_client)
            self._finnhub = FinnhubProvider()
            self._ff      = ForexFactoryProvider()
            self._alpaca  = AlpacaProvider()
            self._engine  = quant_engine
            self._bridge  = icaro_bridge

            self._initialized = True
            print('[DATA BUS] ✓ Inicializado — todos los providers activos')

    # ── PRECIOS ───────────────────────────────────────────────

    def get_prices(self, symbols: list = None) -> dict:
        """
        Precios en tiempo real de los símbolos pedidos.
        Fuente: Capital.com (7 assets core) + Alpaca (ETFs ref).
        """
        self._require_init()
        return self._capital.get_prices_bulk(symbols)

    def get_candles(self, symbol: str, resolution: str = 'HOUR', count: int = 100) -> list:
        """
        Velas OHLCV históricas.
        Para FX/índices/commodities: Capital.com.
        Para ETFs (SPY, QQQ, TLT...): Alpaca.
        """
        self._require_init()
        # ETFs van por Alpaca
        alpaca_symbols = ['SPY', 'QQQ', 'IWM', 'TLT', 'SHY', 'HYG', 'LQD', 'VIXY', 'GLD', 'VXX']
        if symbol.upper() in alpaca_symbols:
            tf_map = {'DAY': '1Day', 'HOUR': '1Hour', 'MINUTE_15': '15Min'}
            alpaca_tf = tf_map.get(resolution, '1Day')
            return self._alpaca.get_bars(symbol, timeframe=alpaca_tf, limit=count)

        return self._capital.get_candles(symbol, resolution, count)

    # ── CORRELACIONES ─────────────────────────────────────────

    def get_correlations(self, symbols: list = None, days: int = 30) -> dict:
        """
        Matriz de correlación calculada sobre velas diarias reales de Capital.com.
        """
        self._require_init()
        return self._capital.get_correlations(symbols, days)

    # ── ORDER FLOW ────────────────────────────────────────────

    def get_orderflow(self, symbol: str) -> dict:
        """
        Order flow acumulado: delta bid/ask, imbalance, presión dominante.
        Se acumula automáticamente con cada llamada a get_prices().
        """
        self._require_init()
        # Asegurar que tenemos ticks recientes
        self._capital.get_price(symbol)
        return self._capital.get_orderflow(symbol)

    # ── NEWS ──────────────────────────────────────────────────

    def get_news(self, symbols: list = None, limit: int = 20) -> list:
        """
        Noticias filtradas por relevancia para los símbolos dados.
        Fuente: Finnhub.
        """
        self._require_init()
        items = self._finnhub.get_news(symbols)
        return items[:limit]

    # ── CALENDARIO ────────────────────────────────────────────

    def get_calendar(self) -> list:
        """
        Próximos eventos del calendario económico.
        Fuente primaria: Finnhub. Fallback: ForexFactory RSS.
        """
        self._require_init()
        events = self._finnhub.get_calendar()

        if not events:
            print('[DATA BUS] Finnhub calendario vacío — usando ForexFactory fallback')
            events = self._ff.get_calendar()

        return events

    # ── SENTIMENT / POSITIONING ───────────────────────────────

    def get_sentiment(self, symbols: list = None) -> dict:
        """
        % Long / % Short de clientes de Capital.com por instrumento.
        Mejor proxy disponible para COT en tiempo real.
        """
        self._require_init()
        return self._capital.get_sentiment(symbols)

    # ── RÉGIMEN ICARO ─────────────────────────────────────────

    def get_regime(self) -> dict:
        """
        Snapshot completo de ICARO V2.1.
        Incluye: regime_label, fragility_score, convexity_score,
                 crash_probability, execution_decision, killswitch_global.
        Fuente: icaro_bridge (lee latest_snapshot.json — actualizado cada hora por icaro_runner).
        """
        self._require_init()
        cached = cache.get('icaro', 'snapshot')
        if cached:
            return cached

        try:
            status = self._bridge.get_status_summary()
            cache.set('icaro', 'snapshot', status)
            return status
        except Exception as e:
            print(f'[DATA BUS] Error leyendo ICARO: {e}')
            return {'status': 'OFFLINE', 'error': str(e)}

    # ── QUANT ENGINE SCORES ───────────────────────────────────

    def get_quant_scores(self) -> dict:
        """
        Scores y análisis del Quant Engine por asset.
        Fuente: analysis_cache del QuantEngine (actualizado cada 15min).
        Retorna dict { asset: { total_score, direction, ob_active, fvg_active, ... } }
        """
        self._require_init()
        cached = cache.get('quant_scores', 'all')
        if cached:
            return cached

        try:
            raw = self._engine.analysis_cache or {}
            # Normalizar para el Bus
            scores = {}
            for asset, data in raw.items():
                scores[asset] = {
                    'total_score':  data.get('total_score', 0),
                    'direction':    data.get('direction', 'NEUTRAL'),
                    'regime':       data.get('regime', 'UNKNOWN'),
                    'macro_bias':   data.get('macro_bias', 'NEUTRAL'),
                    'ob_active':    data.get('ob_active', False),
                    'fvg_active':   data.get('fvg_active', False),
                    'liq_swept':    data.get('liq_swept', False),
                    'structure':    data.get('structure', 'UNKNOWN'),
                    'analyzed_at':  data.get('analyzed_at'),
                }
            cache.set('quant_scores', 'all', scores)
            return scores
        except Exception as e:
            print(f'[DATA BUS] Error leyendo Quant Engine: {e}')
            return {}

    # ── VIX PROXY ─────────────────────────────────────────────

    def get_vix(self) -> dict:
        """
        VIX proxy via VIXY/VXX de Alpaca.
        """
        self._require_init()
        return self._alpaca.get_vix_proxy()

    # ── SNAPSHOT COMPLETO (MÉTODO ESTRELLA) ───────────────────

    def get_market_snapshot(self, symbols: list = None) -> dict:
        """
        Snapshot completo del estado del mercado.
        Las estrategias llaman ESTE método y reciben todo.

        Retorna:
        {
            'prices':      { symbol: price_data },
            'regime':      { icaro snapshot },
            'quant':       { asset: scores },
            'news':        [ noticias ],
            'calendar':    [ eventos ],
            'sentiment':   { symbol: % long/short },
            'correlations':{ matrix },
            'vix':         { proxy data },
            'timestamp':   float,
            'bus_version': str,
        }
        """
        self._require_init()

        # Snapshot completo — cada llamada usa su propio caché interno
        snapshot = {
            'prices':       self.get_prices(symbols),
            'regime':       self.get_regime(),
            'quant':        self.get_quant_scores(),
            'news':         self.get_news(symbols, limit=15),
            'calendar':     self.get_calendar(),
            'sentiment':    self.get_sentiment(symbols),
            'correlations': self.get_correlations(symbols),
            'vix':          self.get_vix(),
            'timestamp':    time.time(),
            'bus_version':  '1.0.0',
        }

        return snapshot

    # ── DIAGNÓSTICO ───────────────────────────────────────────

    def status(self) -> dict:
        """Estado de todos los providers para el panel de Config."""
        if not self._initialized:
            return {'initialized': False}

        return {
            'initialized': True,
            'providers': {
                'capital':     {'connected': self._capital.client.connected},
                'alpaca':      self._alpaca.status(),
                'finnhub':     self._finnhub.status(),
                'forexfactory': {'available': True, 'mode': 'rss_fallback'},
                'icaro_bridge': {'online': self._bridge.is_alive()},
                'quant_engine': {'running': self._engine.running},
            },
            'cache': cache.stats(),
        }

    def invalidate_cache(self, tipo: str = None) -> None:
        """Invalida caché — útil para forzar refresh desde el frontend."""
        if tipo:
            cache.invalidate(tipo)
        else:
            for t in ['prices', 'orderflow', 'correlations', 'quant_scores',
                      'news', 'calendar', 'sentiment', 'icaro']:
                cache.invalidate(t)

    # ── PRIVADOS ──────────────────────────────────────────────

    def _require_init(self):
        if not self._initialized:
            raise RuntimeError(
                '[DATA BUS] No inicializado. Llamar data_bus.init() en server.py primero.'
            )


# ── SINGLETON ─────────────────────────────────────────────────
# Una sola instancia compartida por todo el sistema.
# server.py lo inicializa. Todo lo demás lo importa.
data_bus = DataBus()
