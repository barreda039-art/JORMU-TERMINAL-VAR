# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — ICARO BRIDGE
# Puente entre el backend de ICARO y el sistema principal.
# Lee snapshots, expone estado, no ejecuta lógica cuantitativa.
# ═══════════════════════════════════════════════════════════

import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# Directorio donde icaro_runner.py escribe los snapshots
SNAPSHOT_DIR  = Path(__file__).parent / 'icaro_storage' / 'snapshots'
SNAPSHOT_FILE = SNAPSHOT_DIR / 'latest_snapshot.json'

# Snapshot vacío — estado por defecto cuando ICARO no ha corrido aún
_EMPTY_SNAPSHOT = {
    'engine_name':             'ICARO V2.1',
    'snapshot_version':        'v2.1.0',
    'timestamp':               None,
    'status':                  'OFFLINE',          # OFFLINE | RUNNING | ERROR
    'regime_label':            'UNKNOWN',
    'fragility_score':         None,
    'continuation_score':      None,
    'crash_probability':       None,
    'convexity_score':         None,
    'convexity_window':        None,
    'probe_success_probability': None,
    'state':                   'UNKNOWN',
    'execution_decision':      'NO_ACTION',
    'deployment_stage':        'NO_DEPLOYMENT',
    'deployment_action':       'NO_CONVEXITY_ACTION',
    'capital_utilization':     0.0,
    'killswitch_global':       False,
    'signal_quality':          'NO_SIGNAL_OK',
    'signal_quality_score':    0.0,
    'live_action':             'UNKNOWN',
    'recommended_exposure_pct': 0.0,
    'icaro_capital':           0.0,     # Inyectado por RiskManager
    'icaro_reserve_pct':       20.0,    # Default, configurable desde terminal
}


class IcaroBridge:
    """
    Puente de solo lectura entre ICARO y JORMUNDGANDRSSON.

    Responsabilidades:
    - Leer el último snapshot escrito por icaro_runner.py
    - Mantener una copia en memoria para acceso rápido
    - Detectar si ICARO está vivo o muerto (watchdog)
    - Exponer el snapshot al MacroRegime y al RiskManager

    NO ejecuta lógica cuantitativa.
    NO se comunica con Alpaca.
    NO toma decisiones de trading.
    """

    # Si el snapshot tiene más de N segundos, ICARO se considera STALE
    STALE_THRESHOLD_SECONDS = 3600  # 1 hora

    def __init__(self):
        self._snapshot      = dict(_EMPTY_SNAPSHOT)
        self._lock          = threading.Lock()
        self._watcher       = None
        self._watching       = False
        self._last_file_mtime = None

        # Crear directorio de storage si no existe
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

        # Intentar cargar snapshot existente al arrancar
        self._load_snapshot_from_disk()

        print('[ICARO BRIDGE] Inicializado')

    # ── CONTROL ───────────────────────────────────────────────

    def start_watching(self, interval_seconds: int = 30):
        """
        Inicia watcher en background — detecta nuevos snapshots automáticamente.
        Llama esto desde server.py al arrancar.
        """
        if self._watching:
            return

        self._watching = True
        self._watcher  = threading.Thread(
            target=self._watch_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._watcher.start()
        print(f'[ICARO BRIDGE] Watcher iniciado — revisando cada {interval_seconds}s')

    def stop_watching(self):
        self._watching = False
        print('[ICARO BRIDGE] Watcher detenido')

    # ── LECTURA ───────────────────────────────────────────────

    def get_snapshot(self) -> dict:
        """Retorna copia del último snapshot. Thread-safe."""
        with self._lock:
            return dict(self._snapshot)

    def get_regime(self) -> dict:
        """
        Retorna solo los campos relevantes para MacroRegime.
        Uso: macro_regime.py llama esto para enriquecer su análisis.
        """
        snap = self.get_snapshot()
        return {
            'regime_label':      snap.get('regime_label', 'UNKNOWN'),
            'fragility_score':   snap.get('fragility_score'),
            'crash_probability': snap.get('crash_probability'),
            'convexity_score':   snap.get('convexity_score'),
            'convexity_window':  snap.get('convexity_window'),
            'killswitch_global': snap.get('killswitch_global', False),
            'status':            snap.get('status', 'OFFLINE'),
        }

    def get_signal(self) -> dict:
        """
        Retorna solo los campos relevantes para ICARO Strategy.
        Uso: ICARO_V2.strategy.py llama esto para decidir si actuar.
        """
        snap = self.get_snapshot()
        return {
            'execution_decision':       snap.get('execution_decision', 'NO_ACTION'),
            'deployment_stage':         snap.get('deployment_stage', 'NO_DEPLOYMENT'),
            'deployment_action':        snap.get('deployment_action', 'NO_CONVEXITY_ACTION'),
            'signal_quality':           snap.get('signal_quality', 'NO_SIGNAL_OK'),
            'signal_quality_score':     snap.get('signal_quality_score', 0.0),
            'killswitch_global':        snap.get('killswitch_global', False),
            'capital_utilization':      snap.get('capital_utilization', 0.0),
            'recommended_exposure_pct': snap.get('recommended_exposure_pct', 0.0),
            'icaro_capital':            snap.get('icaro_capital', 0.0),
            'status':                   snap.get('status', 'OFFLINE'),
        }

    def get_capital_context(self) -> dict:
        """
        Retorna contexto de capital para RiskManager.
        Uso: risk_manager.py llama esto para calcular capital disponible.
        """
        snap = self.get_snapshot()
        return {
            'icaro_reserve_pct':    snap.get('icaro_reserve_pct', 20.0),
            'capital_utilization':  snap.get('capital_utilization', 0.0),
            'killswitch_global':    snap.get('killswitch_global', False),
            'deployment_stage':     snap.get('deployment_stage', 'NO_DEPLOYMENT'),
        }

    def is_alive(self) -> bool:
        """True si ICARO está online y el snapshot es reciente."""
        snap = self.get_snapshot()
        if snap.get('status') == 'OFFLINE':
            return False
        if not snap.get('timestamp'):
            return False
        try:
            ts  = datetime.fromisoformat(snap['timestamp'])
            age = (datetime.now(timezone.utc) - ts).total_seconds()
            return age < self.STALE_THRESHOLD_SECONDS
        except Exception:
            return False

    def is_killswitch_active(self) -> bool:
        """Acceso directo al killswitch global — RiskManager lo usa como gate."""
        return self.get_snapshot().get('killswitch_global', False)

    # ── ESCRITURA (solo para actualizar capital inyectado) ─────

    def update_capital(self, nav: float, reserve_pct: float):
        """
        RiskManager llama esto para informar a ICARO cuánto capital tiene.
        Solo actualiza el campo en memoria — no toca el snapshot de ICARO.
        """
        with self._lock:
            self._snapshot['icaro_capital']    = round(nav * reserve_pct / 100, 2)
            self._snapshot['icaro_reserve_pct'] = reserve_pct

    def update_reserve_pct(self, reserve_pct: float):
        """Actualiza el % de reserva configurable desde el terminal."""
        with self._lock:
            self._snapshot['icaro_reserve_pct'] = reserve_pct
        print(f'[ICARO BRIDGE] Reserva actualizada: {reserve_pct}% del NAV')

    # ── WATCHER INTERNO ───────────────────────────────────────

    def _watch_loop(self, interval: int):
        """Detecta cambios en el archivo de snapshot y recarga en memoria."""
        while self._watching:
            try:
                if SNAPSHOT_FILE.exists():
                    mtime = SNAPSHOT_FILE.stat().st_mtime
                    if mtime != self._last_file_mtime:
                        self._load_snapshot_from_disk()
                        self._last_file_mtime = mtime
            except Exception as e:
                print(f'[ICARO BRIDGE] Error en watcher: {e}')
            time.sleep(interval)

    def _load_snapshot_from_disk(self):
        """Lee el snapshot del disco y lo carga en memoria."""
        if not SNAPSHOT_FILE.exists():
            return

        try:
            with open(SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Preservar campos que el sistema inyecta (capital, reserve_pct)
            with self._lock:
                icaro_capital   = self._snapshot.get('icaro_capital', 0.0)
                reserve_pct     = self._snapshot.get('icaro_reserve_pct', 20.0)

                self._snapshot  = {**_EMPTY_SNAPSHOT, **data}
                self._snapshot['icaro_capital']    = icaro_capital
                self._snapshot['icaro_reserve_pct'] = reserve_pct
                self._snapshot['status']           = 'RUNNING'

            print(f'[ICARO BRIDGE] Snapshot cargado — {data.get("timestamp", "sin timestamp")}')

        except json.JSONDecodeError as e:
            print(f'[ICARO BRIDGE] Snapshot corrupto: {e}')
        except Exception as e:
            print(f'[ICARO BRIDGE] Error cargando snapshot: {e}')

    # ── DEBUG ─────────────────────────────────────────────────

    def get_status_summary(self) -> dict:
        """Resumen completo para el endpoint /api/icaro/status."""
        snap = self.get_snapshot()
        return {
            'online':              self.is_alive(),
            'killswitch_active':   self.is_killswitch_active(),
            'status':              snap.get('status', 'OFFLINE'),
            'timestamp':           snap.get('timestamp'),
            'regime_label':        snap.get('regime_label', 'UNKNOWN'),
            'fragility_score':     snap.get('fragility_score'),
            'crash_probability':   snap.get('crash_probability'),
            'convexity_score':     snap.get('convexity_score'),
            'convexity_window':    snap.get('convexity_window'),
            'execution_decision':  snap.get('execution_decision', 'NO_ACTION'),
            'deployment_stage':    snap.get('deployment_stage', 'NO_DEPLOYMENT'),
            'signal_quality':      snap.get('signal_quality', 'NO_SIGNAL_OK'),
            'signal_quality_score': snap.get('signal_quality_score', 0.0),
            'killswitch_global':   snap.get('killswitch_global', False),
            'capital_utilization': snap.get('capital_utilization', 0.0),
            'icaro_capital':       snap.get('icaro_capital', 0.0),
            'icaro_reserve_pct':   snap.get('icaro_reserve_pct', 20.0),
            'live_action':         snap.get('live_action', 'UNKNOWN'),
        }


# ── SINGLETON ─────────────────────────────────────────────────
# Una sola instancia compartida por todo el sistema.
# server.py, risk_manager.py, macro_regime.py y ICARO_V2.strategy.py
# importan este objeto directamente.

icaro_bridge = IcaroBridge()
