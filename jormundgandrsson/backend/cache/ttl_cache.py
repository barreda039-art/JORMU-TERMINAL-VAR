# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — TTL CACHE
# Caché en memoria con expiración por tipo de dato.
# Sin dependencias externas — solo stdlib Python.
# ═══════════════════════════════════════════════════════════

import time
import threading
from typing import Any, Optional

# TTLs en segundos por tipo de dato
TTL = {
    'prices':       5,      # Precios en tiempo real
    'orderflow':    5,      # Delta bid/ask acumulado
    'correlations': 300,    # Correlaciones (velas 1D — cambia poco)
    'quant_scores': 900,    # Scores del Quant Engine (cadencia 15min)
    'news':         60,     # Noticias Finnhub (rate limit 60 calls/min)
    'calendar':     900,    # Calendario económico
    'sentiment':    300,    # Capital.com client sentiment
    'icaro':        900,    # Snapshot ICARO (pipeline pesado)
    'default':      60,     # Fallback
}


class TTLCache:
    """
    Caché thread-safe con expiración automática por tipo de dato.
    
    Uso:
        cache = TTLCache()
        cache.set('prices', 'EURUSD', data)
        val = cache.get('prices', 'EURUSD')   # None si expiró
    """

    def __init__(self):
        self._store: dict = {}   # { (tipo, key): (value, expires_at) }
        self._lock  = threading.Lock()

    def get(self, tipo: str, key: str) -> Optional[Any]:
        """Retorna el valor si existe y no ha expirado. None si expiró o no existe."""
        with self._lock:
            entry = self._store.get((tipo, key))
            if entry is None:
                return None
            value, expires_at = entry
            if time.time() > expires_at:
                del self._store[(tipo, key)]
                return None
            return value

    def set(self, tipo: str, key: str, value: Any, ttl_override: int = None) -> None:
        """Almacena un valor con el TTL del tipo dado (o un override específico)."""
        ttl_seconds = ttl_override or TTL.get(tipo, TTL['default'])
        expires_at  = time.time() + ttl_seconds
        with self._lock:
            self._store[(tipo, key)] = (value, expires_at)

    def invalidate(self, tipo: str, key: str = None) -> None:
        """
        Invalida entradas del caché.
        Si key es None, invalida todas las entradas de ese tipo.
        """
        with self._lock:
            if key is not None:
                self._store.pop((tipo, key), None)
            else:
                keys_to_delete = [k for k in self._store if k[0] == tipo]
                for k in keys_to_delete:
                    del self._store[k]

    def stats(self) -> dict:
        """Retorna estadísticas del caché para diagnóstico."""
        now = time.time()
        with self._lock:
            total   = len(self._store)
            expired = sum(1 for (_, expires_at) in self._store.values() if now > expires_at)
            by_type: dict = {}
            for (tipo, _), (_, expires_at) in self._store.items():
                if tipo not in by_type:
                    by_type[tipo] = {'alive': 0, 'expired': 0}
                if now > expires_at:
                    by_type[tipo]['expired'] += 1
                else:
                    by_type[tipo]['alive'] += 1
        return {
            'total_entries': total,
            'expired':       expired,
            'alive':         total - expired,
            'by_type':       by_type,
        }


# Singleton — una sola instancia compartida por todos los providers
cache = TTLCache()
