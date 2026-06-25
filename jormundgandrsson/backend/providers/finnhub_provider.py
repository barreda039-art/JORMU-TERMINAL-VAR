# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — FINNHUB PROVIDER
# News en tiempo real + calendario económico via Finnhub API.
# API Key: d8ubo19r01qinhuh0mb0d8ubo19r01qinhuh0mbg
# Rate limit: 60 calls/min — respetamos con un limiter interno.
# ═══════════════════════════════════════════════════════════

import time
import threading
import requests
from cache.ttl_cache import cache

FINNHUB_API_KEY = 'd8ubo19r01qinhuh0mb0d8ubo19r01qinhuh0mbg'
FINNHUB_BASE    = 'https://finnhub.io/api/v1'

# Categorías de noticias a consumir
NEWS_CATEGORIES = ['forex', 'general']

# Palabras clave por símbolo para filtrar noticias relevantes
SYMBOL_KEYWORDS = {
    'EURUSD': ['EUR', 'euro', 'ECB', 'European', 'eurozone'],
    'GBPUSD': ['GBP', 'sterling', 'pound', 'BOE', 'Bank of England', 'UK'],
    'USDJPY': ['JPY', 'yen', 'BOJ', 'Bank of Japan', 'Japan'],
    'SPX500': ['S&P', 'SPX', 'equities', 'stocks', 'Fed', 'Federal Reserve'],
    'NAS100': ['Nasdaq', 'tech', 'technology', 'QQQ', 'NAS100'],
    'XAUUSD': ['gold', 'XAU', 'bullion', 'precious metals'],
    'USOIL':  ['oil', 'crude', 'WTI', 'OPEC', 'energy'],
}

# Impacto por palabras clave en el headline
HIGH_IMPACT_KEYWORDS = [
    'Fed', 'Federal Reserve', 'rate decision', 'inflation', 'CPI', 'NFP',
    'nonfarm', 'GDP', 'recession', 'ECB', 'BOE', 'BOJ', 'FOMC',
    'interest rate', 'Powell', 'Lagarde', 'emergency', 'crash', 'crisis',
]


class RateLimiter:
    """
    Limita las llamadas a Finnhub a máx 55/min (margen de seguridad vs límite de 60).
    """
    def __init__(self, max_calls: int = 55, window: int = 60):
        self.max_calls = max_calls
        self.window    = window
        self.calls     = []
        self.lock      = threading.Lock()

    def wait_if_needed(self):
        with self.lock:
            now = time.time()
            # Limpiar llamadas fuera de la ventana
            self.calls = [t for t in self.calls if now - t < self.window]
            if len(self.calls) >= self.max_calls:
                # Esperar hasta que la llamada más antigua salga de la ventana
                wait_time = self.window - (now - self.calls[0]) + 0.1
                if wait_time > 0:
                    time.sleep(wait_time)
                self.calls = [t for t in self.calls if time.time() - t < self.window]
            self.calls.append(time.time())

    def calls_remaining(self) -> int:
        now = time.time()
        with self.lock:
            recent = [t for t in self.calls if now - t < self.window]
            return self.max_calls - len(recent)


class FinnhubProvider:
    """
    Proveedor de noticias y calendario económico via Finnhub.
    """

    def __init__(self):
        self._limiter = RateLimiter(max_calls=55, window=60)
        self._session = requests.Session()
        self._session.headers.update({'X-Finnhub-Token': FINNHUB_API_KEY})
        print('[FINNHUB] Provider inicializado')

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """GET con rate limiter y manejo de errores."""
        self._limiter.wait_if_needed()
        try:
            url = f'{FINNHUB_BASE}{endpoint}'
            r   = self._session.get(url, params=params or {}, timeout=10)
            if r.status_code == 200:
                return {'ok': True, 'data': r.json()}
            elif r.status_code == 429:
                print('[FINNHUB] Rate limit alcanzado — esperando 10s')
                time.sleep(10)
                return {'ok': False, 'error': 'rate_limit'}
            else:
                return {'ok': False, 'error': f'HTTP {r.status_code}'}
        except Exception as e:
            print(f'[FINNHUB] Error: {e}')
            return {'ok': False, 'error': str(e)}

    # ── NEWS ──────────────────────────────────────────────────

    def get_news(self, symbols: list = None) -> list:
        """
        Noticias de mercado filtradas por relevancia para los símbolos dados.
        Retorna lista de items normalizados con sentiment y relevancia.
        """
        cached = cache.get('news', 'all')
        if cached:
            return self._filter_by_symbols(cached, symbols)

        all_items = []
        for category in NEWS_CATEGORIES:
            result = self._get('/news', params={'category': category})
            if result.get('ok'):
                items = result['data'] if isinstance(result['data'], list) else []
                for item in items[:30]:   # máx 30 por categoría
                    normalized = self._normalize_news_item(item)
                    if normalized:
                        all_items.append(normalized)

        # Deduplicar por headline
        seen       = set()
        deduped    = []
        for item in all_items:
            key = item.get('headline', '')[:60]
            if key not in seen:
                seen.add(key)
                deduped.append(item)

        # Ordenar por timestamp descendente
        deduped.sort(key=lambda x: x.get('timestamp', 0), reverse=True)

        cache.set('news', 'all', deduped)
        return self._filter_by_symbols(deduped, symbols)

    def _normalize_news_item(self, raw: dict) -> dict:
        """Normaliza un item de Finnhub al formato interno."""
        headline = raw.get('headline', '') or raw.get('summary', '')
        if not headline:
            return None

        # Detectar impacto por palabras clave
        headline_upper = headline.upper()
        impact = 'LOW'
        for kw in HIGH_IMPACT_KEYWORDS:
            if kw.upper() in headline_upper:
                impact = 'HIGH'
                break

        # Detectar símbolos relevantes
        relevant_symbols = []
        for sym, keywords in SYMBOL_KEYWORDS.items():
            for kw in keywords:
                if kw.lower() in headline.lower():
                    relevant_symbols.append(sym)
                    break

        # Sentiment básico por palabras clave
        # Finnhub no siempre retorna sentiment en news generales
        sentiment = self._infer_sentiment(headline)

        return {
            'headline':  headline,
            'summary':   raw.get('summary', ''),
            'source':    raw.get('source', 'Finnhub'),
            'url':       raw.get('url', ''),
            'timestamp': raw.get('datetime', int(time.time())),
            'impact':    impact,
            'sentiment': sentiment,
            'symbols':   relevant_symbols,
        }

    def _infer_sentiment(self, text: str) -> str:
        """Inferencia de sentiment básica por keywords."""
        text_lower = text.lower()
        bull_words = ['rise', 'rally', 'surge', 'gain', 'bullish', 'strong', 'beat',
                      'exceed', 'recover', 'growth', 'positive', 'optimism', 'jump']
        bear_words = ['fall', 'drop', 'plunge', 'decline', 'bearish', 'weak', 'miss',
                      'disappoint', 'recession', 'fear', 'crisis', 'crash', 'cut', 'risk']

        bull_score = sum(1 for w in bull_words if w in text_lower)
        bear_score = sum(1 for w in bear_words if w in text_lower)

        if bull_score > bear_score:
            return 'BULL'
        elif bear_score > bull_score:
            return 'BEAR'
        return 'NEUTRAL'

    def _filter_by_symbols(self, items: list, symbols: list) -> list:
        """Si se especifican símbolos, filtra solo noticias relevantes para ellos."""
        if not symbols:
            return items
        filtered = []
        for item in items:
            item_syms = item.get('symbols', [])
            # Incluir si la noticia es relevante para alguno de los símbolos pedidos,
            # o si es de alto impacto (relevante para todos)
            if item.get('impact') == 'HIGH' or any(s in item_syms for s in symbols):
                filtered.append(item)
        return filtered

    # ── CALENDARIO ECONÓMICO ─────────────────────────────────

    def get_calendar(self) -> list:
        """
        Próximos eventos del calendario económico.
        Finnhub /calendar/economic retorna eventos de la semana actual.
        En tier gratuito puede estar vacío — ForexFactory actúa como fallback en data_bus.
        """
        cached = cache.get('calendar', 'finnhub')
        if cached is not None:
            return cached

        from datetime import datetime, timedelta
        today     = datetime.utcnow()
        from_date = today.strftime('%Y-%m-%d')
        to_date   = (today + timedelta(days=7)).strftime('%Y-%m-%d')

        result = self._get('/calendar/economic', params={
            'from': from_date,
            'to':   to_date,
        })

        events = []
        if result.get('ok'):
            data = result['data']
            # Finnhub puede retornar lista directa o { economicCalendar: [...] }
            if isinstance(data, list):
                raw_events = data
            elif isinstance(data, dict):
                raw_events = data.get('economicCalendar', [])
            else:
                raw_events = []

            for ev in raw_events:
                normalized = self._normalize_calendar_event(ev)
                if normalized:
                    events.append(normalized)

            events.sort(key=lambda x: x.get('time', ''))

        # Cachear incluso si vacío para no martillar la API
        cache.set('calendar', 'finnhub', events)
        return events

    def _normalize_calendar_event(self, raw: dict) -> dict:
        """Normaliza un evento del calendario al formato interno."""
        event_name = raw.get('event', '')
        if not event_name:
            return None

        # Mapear impacto de Finnhub al nuestro
        impact_map = {'high': 'HIGH', 'medium': 'MED', 'low': 'LOW', 'na': 'LOW'}
        impact = impact_map.get(str(raw.get('impact', 'low')).lower(), 'LOW')

        return {
            'event':    event_name,
            'country':  raw.get('country', ''),
            'time':     raw.get('time', ''),
            'impact':   impact,
            'previous': raw.get('prev', ''),
            'estimate': raw.get('estimate', ''),
            'actual':   raw.get('actual', ''),
            'unit':     raw.get('unit', ''),
            'source':   'finnhub',
        }

    def status(self) -> dict:
        """Estado del provider para diagnóstico."""
        return {
            'calls_remaining': self._limiter.calls_remaining(),
            'api_key_set':     bool(FINNHUB_API_KEY),
        }
