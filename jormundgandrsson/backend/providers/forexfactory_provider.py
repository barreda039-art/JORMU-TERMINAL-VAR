# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — FOREXFACTORY PROVIDER
# Calendario económico via ForexFactory.
# Fuente primaria: JSON interno de FF (sin bloqueos de IP)
# Fuente secundaria: RSS XML de FF
# Sin API key — datos públicos.
# ═══════════════════════════════════════════════════════════

import time
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from cache.ttl_cache import cache

# Fuentes en orden de prioridad
FF_JSON_URL = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
FF_JSON_NEXT = 'https://nfs.faireconomy.media/ff_calendar_nextweek.json'
FF_RSS_URL  = 'https://www.forexfactory.com/ff_calendar_thisweek.xml'

COUNTRY_TO_CURRENCY = {
    'USD': 'USD', 'EUR': 'EUR', 'GBP': 'GBP', 'JPY': 'JPY',
    'AUD': 'AUD', 'CAD': 'CAD', 'CHF': 'CHF', 'NZD': 'NZD',
    'CNY': 'CNY', 'All': 'ALL',
}

IMPACT_MAP = {
    'High':         'HIGH',
    'Medium':       'MED',
    'Low':          'LOW',
    'Non-Economic': 'LOW',
    '':             'LOW',
}


class ForexFactoryProvider:
    """
    Proveedor de calendario económico via ForexFactory.
    Intenta JSON primero (más confiable), luego RSS XML como fallback.
    """

    def __init__(self):
        self._session = requests.Session()
        self._session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/xml, */*',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        print('[FOREXFACTORY] Provider inicializado')

    def get_calendar(self) -> list:
        """
        Obtiene el calendario de la semana actual (+ próxima).
        Intenta JSON primero, luego RSS XML como fallback.
        """
        cached = cache.get('calendar', 'forexfactory')
        if cached is not None:
            return cached

        events = []

        # Intento 1: JSON interno de ForexFactory (más confiable, sin bloqueos)
        events = self._fetch_json(FF_JSON_URL)
        if events:
            print(f'[FOREXFACTORY] JSON this week: {len(events)} eventos')
        
        # Añadir próxima semana si conseguimos esta
        if events:
            next_events = self._fetch_json(FF_JSON_NEXT)
            if next_events:
                events += next_events
                print(f'[FOREXFACTORY] JSON next week: {len(next_events)} eventos adicionales')

        # Intento 2: RSS XML
        if not events:
            events = self._fetch_rss()
            if events:
                print(f'[FOREXFACTORY] RSS: {len(events)} eventos')

        if not events:
            print('[FOREXFACTORY] Sin datos de calendario — ambas fuentes fallaron')

        # Ordenar: primero por fecha/hora, luego HIGH impact primero
        events.sort(key=lambda x: (x.get('time', ''), 0 if x.get('impact') == 'HIGH' else 1))

        cache.set('calendar', 'forexfactory', events)
        return events

    # ── JSON (fuente primaria) ────────────────────────────────

    def _fetch_json(self, url: str) -> list:
        """Descarga y parsea el JSON de ForexFactory."""
        try:
            r = self._session.get(url, timeout=15)
            if r.status_code != 200:
                print(f'[FOREXFACTORY] JSON HTTP {r.status_code} para {url}')
                return []

            raw = r.json()
            if not isinstance(raw, list):
                return []

            events = []
            for item in raw:
                normalized = self._normalize_json_event(item)
                if normalized:
                    events.append(normalized)
            return events

        except Exception as e:
            print(f'[FOREXFACTORY] Error JSON {url}: {e}')
            return []

    def _normalize_json_event(self, raw: dict) -> dict:
        """Normaliza un evento del JSON de ForexFactory."""
        title   = raw.get('title', '') or raw.get('name', '')
        country = raw.get('country', '')
        impact  = raw.get('impact', '')
        date    = raw.get('date', '')

        if not title:
            return None

        # El JSON de FF usa 'impact' como High/Medium/Low/Holiday
        if impact == 'Holiday':
            return None

        return {
            'event':    title.strip(),
            'country':  country,
            'currency': COUNTRY_TO_CURRENCY.get(country, country),
            'time':     date,
            'impact':   IMPACT_MAP.get(impact, 'LOW'),
            'forecast': raw.get('forecast', '') or '',
            'previous': raw.get('previous', '') or '',
            'actual':   raw.get('actual', '') or '',
            'source':   'forexfactory/json',
        }

    # ── RSS XML (fallback) ────────────────────────────────────

    def _fetch_rss(self) -> list:
        """Descarga y parsea el RSS XML de ForexFactory."""
        try:
            r = self._session.get(FF_RSS_URL, timeout=15)
            if r.status_code != 200:
                print(f'[FOREXFACTORY] RSS HTTP {r.status_code}')
                return []
            return self._parse_rss(r.text)
        except Exception as e:
            print(f'[FOREXFACTORY] Error RSS: {e}')
            return []

    def _parse_rss(self, xml_text: str) -> list:
        """Parsea el XML RSS de ForexFactory."""
        try:
            root   = ET.fromstring(xml_text)
            events = []

            items = root.findall('.//item') or root.findall('.//event')

            for item in items:
                try:
                    title    = self._text(item, 'title') or self._text(item, 'event')
                    country  = self._text(item, 'country')
                    date_str = self._text(item, 'date')
                    time_str = self._text(item, 'time')
                    impact   = self._text(item, 'impact')
                    forecast = self._text(item, 'forecast')
                    previous = self._text(item, 'previous')
                    actual   = self._text(item, 'actual')

                    if not title:
                        continue

                    event_time = date_str
                    if time_str:
                        event_time += f' {time_str}'

                    events.append({
                        'event':    title.strip(),
                        'country':  country,
                        'currency': COUNTRY_TO_CURRENCY.get(country, country),
                        'time':     event_time,
                        'impact':   IMPACT_MAP.get(impact, 'LOW'),
                        'forecast': forecast,
                        'previous': previous,
                        'actual':   actual,
                        'source':   'forexfactory/rss',
                    })
                except Exception:
                    continue

            return events

        except ET.ParseError as e:
            print(f'[FOREXFACTORY] Error parseando XML: {e}')
            return []

    def _text(self, element, tag: str) -> str:
        child = element.find(tag)
        if child is not None and child.text:
            return child.text.strip()
        return ''
