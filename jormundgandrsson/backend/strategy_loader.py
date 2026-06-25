# ═══════════════════════════════════════════════════════════
#  JORMUNDGANDRSSON — STRATEGY LOADER
#  Compatible con Python 3.11
# ═══════════════════════════════════════════════════════════
from __future__ import annotations

import os
import sys
import importlib.util
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional, Callable

# ── RUTA DE LA CARPETA STRATEGIES ───────────────────────────
STRATEGIES_DIR = Path(__file__).parent.parent / 'strategies'

# ── REGISTRO EN MEMORIA ─────────────────────────────────────
_registry: Dict[str, dict] = {}
_file_map:  Dict[str, str]  = {}
_lock    = threading.Lock()
_watchers: List[Callable] = []

# ── CALLBACKS ────────────────────────────────────────────────
def on_change(callback):
    _watchers.append(callback)

def _notify():
    for cb in _watchers:
        try:
            cb(list(_registry.values()))
        except Exception as e:
            print(f'[LOADER] Callback error: {e}')

# ── CARGA DE UN ARCHIVO ──────────────────────────────────────
def _load_file(filepath: str) -> Optional[dict]:
    try:
        spec = importlib.util.spec_from_file_location('_strat_tmp', filepath)
        if spec is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        strat = getattr(mod, 'STRATEGY', None)
        if not isinstance(strat, dict):
            print(f'[LOADER] {filepath}: no contiene STRATEGY dict — ignorado')
            return None

        for field in ('id', 'name', 'assets'):
            if field not in strat:
                print(f'[LOADER] {filepath}: falta campo "{field}" — ignorado')
                return None

        strat.setdefault('description', '')
        strat.setdefault('type',        'Custom')
        strat.setdefault('version',     '1.0.0')
        strat.setdefault('timeframe',   '—')
        strat.setdefault('status',      'DEMO')
        strat.setdefault('mode',        'DEMO')
        strat.setdefault('startDate',   '2025-01-01')
        strat.setdefault('params',      {})
        strat.setdefault('metrics', {
            'totalTrades': 0, 'winRate': 0, 'pnl': 0,
            'pnlPct': 0, 'sharpe': 0, 'maxDD': 0, 'profitFactor': 0,
        })
        strat['_source_file'] = os.path.basename(filepath)
        return strat

    except Exception as e:
        print(f'[LOADER] Error cargando {filepath}: {e}')
        return None

# ── ESCANEO INICIAL ──────────────────────────────────────────
def scan_all() -> List[dict]:
    if not STRATEGIES_DIR.exists():
        STRATEGIES_DIR.mkdir(parents=True, exist_ok=True)
        print(f'[LOADER] Carpeta creada: {STRATEGIES_DIR}')

    loaded = []
    with _lock:
        _registry.clear()
        _file_map.clear()

        for fp in sorted(STRATEGIES_DIR.glob('*.py')):
            if fp.name.startswith('_'):
                continue
            strat = _load_file(str(fp))
            if strat:
                _registry[strat['id']] = strat
                _file_map[str(fp)]     = strat['id']
                loaded.append(strat['name'])
                print(f'[LOADER] OK {strat["name"]} ({strat["id"]}) — {fp.name}')

    print(f'[LOADER] {len(loaded)} estrategia(s): {", ".join(loaded) or "ninguna"}')
    return list(_registry.values())

# ── RECARGA / ELIMINACIÓN ────────────────────────────────────
def reload_file(filepath: str):
    strat = _load_file(filepath)
    with _lock:
        old_id = _file_map.get(filepath)
        if old_id and old_id in _registry:
            del _registry[old_id]
        if strat:
            _registry[strat['id']] = strat
            _file_map[filepath]    = strat['id']
            print(f'[LOADER] Recargado: {strat["name"]}')
        else:
            _file_map.pop(filepath, None)
    _notify()

def remove_file(filepath: str):
    with _lock:
        old_id = _file_map.pop(filepath, None)
        if old_id:
            removed = _registry.pop(old_id, None)
            if removed:
                print(f'[LOADER] Removido: {removed["name"]}')
    _notify()

# ── GETTERS / SETTERS ────────────────────────────────────────
def get_all() -> List[dict]:
    with _lock:
        return list(_registry.values())

def get_by_id(strategy_id: str) -> Optional[dict]:
    with _lock:
        return _registry.get(strategy_id)

def update_metrics(strategy_id: str, metrics: dict):
    with _lock:
        if strategy_id in _registry:
            _registry[strategy_id]['metrics'].update(metrics)

def set_status(strategy_id: str, status: str):
    with _lock:
        if strategy_id in _registry:
            _registry[strategy_id]['status'] = status
    _notify()

# ── HOT-RELOAD WATCHER ───────────────────────────────────────
class _StrategyWatcher(threading.Thread):
    def __init__(self, interval: int = 3):
        super().__init__(daemon=True, name='StrategyWatcher')
        self.interval  = interval
        self._mtimes:  Dict[str, float] = {}
        self._running  = False

    def _snapshot(self) -> Dict[str, float]:
        result: Dict[str, float] = {}
        if STRATEGIES_DIR.exists():
            for fp in STRATEGIES_DIR.glob('*.py'):
                if not fp.name.startswith('_'):
                    try:
                        result[str(fp)] = fp.stat().st_mtime
                    except OSError:
                        pass
        return result

    def run(self):
        self._running = True
        self._mtimes  = self._snapshot()
        print(f'[LOADER] Watcher activo — revisando cada {self.interval}s')

        while self._running:
            time.sleep(self.interval)
            try:
                current = self._snapshot()
                for fp, mtime in current.items():
                    if fp not in self._mtimes:
                        print(f'[LOADER] Nuevo: {os.path.basename(fp)}')
                        reload_file(fp)
                    elif mtime != self._mtimes[fp]:
                        print(f'[LOADER] Modificado: {os.path.basename(fp)}')
                        reload_file(fp)
                for fp in list(self._mtimes.keys()):
                    if fp not in current:
                        print(f'[LOADER] Eliminado: {os.path.basename(fp)}')
                        remove_file(fp)
                self._mtimes = current
            except Exception as e:
                print(f'[LOADER] Watcher error: {e}')

    def stop(self):
        self._running = False

_watcher_instance: Optional[_StrategyWatcher] = None

def start_watching(interval: int = 3):
    global _watcher_instance
    if _watcher_instance and _watcher_instance.is_alive():
        return
    scan_all()
    _watcher_instance = _StrategyWatcher(interval=interval)
    _watcher_instance.start()

def stop_watching():
    global _watcher_instance
    if _watcher_instance:
        _watcher_instance.stop()
        _watcher_instance = None

# ── ICARO ENRICHMENT ─────────────────────────────────────────
def enrich_icaro_from_snapshot(snapshot: dict):
    if not snapshot:
        return
    metrics_patch = {
        'regime':      snapshot.get('regime_label', ''),
        'fragility':   round(snapshot.get('fragility_score', 0) * 100, 1),
        'crashProb':   round(snapshot.get('crash_probability', 0) * 100, 1),
        'convexity':   round(snapshot.get('convexity_score', 0) * 100, 1),
        'signalScore': round(snapshot.get('signal_quality_score', 0) * 100, 1),
        'decision':    snapshot.get('execution_decision', '—'),
        'liveAction':  snapshot.get('live_action', '—'),
        'sharpe':      round(snapshot.get('signal_quality_score', 0) * 2.5, 2),
    }
    update_metrics('STR-ICARO-001', metrics_patch)
