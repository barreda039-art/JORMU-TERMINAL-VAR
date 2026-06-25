# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — QUANT ENGINE CENTRAL
# Orquesta las 4 capas cada 15 minutos para los 7 activos
# Opera 24/5 en paralelo con decisión dinámica de liquidez
# ═══════════════════════════════════════════════════════════

import time
import threading
import json
from datetime import datetime, timezone
from factors.macro_regime      import MacroRegime
from factors.market_structure  import MarketStructure
from factors.institutional_zones import InstitutionalZones
from factors.entry_confirmation  import EntryConfirmation
from risk_manager import RiskManager

class QuantEngine:

    # Activos y sus epics reales en Capital.com DEMO
    ASSETS = {
        'EURUSD': 'EURUSD',      # EUR/USD
        'GBPUSD': 'GBPUSD',      # GBP/USD
        'USDJPY': 'USDJPY',      # USD/JPY
        'SPX500': 'US500',       # US 500
        'NAS100': 'US100',       # US Tech 100
        'XAUUSD': 'GOLD',        # Gold Spot
        'USOIL':  'OIL_CRUDE',   # Crude Oil Spot
    }

    # Estrategia asignada por activo
    ASSET_STRATEGY = {
        'EURUSD': 'STR-001', 'GBPUSD': 'STR-001', 'USDJPY': 'STR-001',
        'SPX500': 'STR-002', 'NAS100': 'STR-002',
        'XAUUSD': 'STR-003',
        'USOIL':  'STR-004',
    }

    # Timeframe de análisis
    ANALYSIS_TF   = 'HOUR'       # 1H para estructura
    CONFIRMATION_TF = 'MINUTE_15' # 15M para entrada
    CANDLES_NEEDED = 100

    def __init__(self, capital_client, config: dict = None):
        self.client        = capital_client
        self.running       = False
        self.thread        = None
        self.interval      = 15 * 60  # 15 minutos en segundos

        # Capas del sistema
        self.macro          = MacroRegime(capital_client)
        self.structure      = MarketStructure()
        self.zones          = InstitutionalZones()
        self.confirmation   = EntryConfirmation()
        self.risk           = RiskManager(capital_client, config)

        # Estado del engine
        self.last_run       = None
        self.signals        = []      # Señales generadas (pendientes de aprobación)
        self.auto_signals   = []      # Señales de alta confianza (auto-ejecución)
        self.analysis_cache = {}      # Cache del último análisis por activo
        self.paused_assets  = set()   # Activos pausados desde el dashboard

        # Estrategias activas (sincronizado con carpeta STRATEGIES/)
        self.active_strategies = {
            'STR-001': True,
            'STR-002': True,
            'STR-003': True,
            'STR-004': True,
        }

        # Callbacks para notificar al servidor Flask
        self.on_signal       = None   # Llama cuando hay nueva señal
        self.on_auto_execute = None   # Llama cuando ejecuta automáticamente
        self.on_analysis     = None   # Llama cuando termina análisis de un activo

        print('[ENGINE] Quant Engine inicializado')

    # ── CONTROL ───────────────────────────────────────────────
    def start(self):
        """Inicia el engine en un thread separado"""
        if self.running:
            print('[ENGINE] Ya está corriendo')
            return

        self.running = True
        self.thread  = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        print(f'[ENGINE] Iniciado — análisis cada {self.interval//60} minutos')

    def stop(self):
        self.running = False
        print('[ENGINE] Detenido')

    def pause_asset(self, asset: str):
        self.paused_assets.add(asset)
        print(f'[ENGINE] {asset} pausado')

    def resume_asset(self, asset: str):
        self.paused_assets.discard(asset)
        print(f'[ENGINE] {asset} reanudado')

    def set_strategy_active(self, strategy_id: str, active: bool):
        self.active_strategies[strategy_id] = active
        print(f'[ENGINE] {strategy_id} → {"ACTIVA" if active else "PAUSADA"}')

    # ── LOOP PRINCIPAL ────────────────────────────────────────
    def _run_loop(self):
        """Loop 24/5 — analiza el mercado cada 15 minutos"""
        while self.running:
            try:
                now = datetime.now(timezone.utc)
                # No operar los fines de semana
                if now.weekday() >= 5:  # 5=Sábado, 6=Domingo
                    print('[ENGINE] Fin de semana — mercado cerrado')
                    time.sleep(3600)
                    continue

                print(f'\n[ENGINE] ═══ ANÁLISIS INICIADO {now.strftime("%Y-%m-%d %H:%M")} UTC ═══')
                self._run_analysis_cycle()
                self.last_run = now

                print(f'[ENGINE] ═══ CICLO COMPLETADO — próximo en {self.interval//60}min ═══\n')
                time.sleep(self.interval)

            except Exception as e:
                print(f'[ENGINE] Error en loop: {e}')
                time.sleep(60)  # Esperar 1 min antes de reintentar

    # ── CICLO DE ANÁLISIS ─────────────────────────────────────
    def _run_analysis_cycle(self):
        """Analiza todos los activos en paralelo"""

        # 1. Obtener precios en tiempo real
        live_prices = self._get_live_prices()
        if not live_prices:
            print('[ENGINE] No se pudieron obtener precios en tiempo real')
            return

        # 2. Analizar régimen macro (Capa 1) — una vez para todos
        regime = self.macro.analyze(live_prices)
        print(f'[ENGINE] Régimen: {regime["mode"]} | VIX: {regime["vix_level"]} | DXY: {regime["dxy_trend"]}')

        # 3. Obtener balance actual del fondo
        balance_data = self.client.get_account_balance()
        nav          = balance_data.get('balance', 1000) if balance_data.get('ok') else 1000
        self.risk.update_peak_nav(nav)

        # 4. Obtener posiciones abiertas
        pos_data         = self.client.get_positions()
        open_positions   = pos_data.get('positions', []) if pos_data.get('ok') else []

        # 5. Analizar cada activo en un thread separado
        threads = []
        for asset, epic in self.ASSETS.items():
            strategy = self.ASSET_STRATEGY[asset]

            # Saltar si la estrategia o el activo están pausados
            if not self.active_strategies.get(strategy, True):
                continue
            if asset in self.paused_assets:
                continue

            t = threading.Thread(
                target=self._analyze_asset,
                args=(asset, epic, regime, live_prices, nav, open_positions),
                daemon=True
            )
            threads.append(t)
            t.start()

        # Esperar a que todos los análisis terminen
        for t in threads:
            t.join(timeout=30)

    def _analyze_asset(self, asset, epic, regime, live_prices, nav, open_positions):
        """Análisis completo de un activo — las 4 capas"""
        try:
            print(f'[ENGINE] Analizando {asset}...')

            # Verificar sesión y liquidez
            session = self.macro.is_active_session(asset)
            if not session['tradeable']:
                print(f'[ENGINE] {asset} — sesión de baja liquidez, saltando')
                return

            # Verificar spread en tiempo real
            live = live_prices.get(asset, {})
            if not live:
                # Intentar obtener precio directo
                price_data = self.client.get_price(epic)
                if price_data.get('ok'):
                    live = price_data
                else:
                    print(f'[ENGINE] {asset} — sin precio en tiempo real')
                    return

            # Sesgo del régimen para este activo
            macro_bias = regime['bias'].get(asset, 'NEUTRAL')

            # ── CAPA 2: Estructura de mercado (1H) ───────────
            candles_1h = self._get_candles(epic, 'HOUR', 60)
            if not candles_1h:
                print(f'[ENGINE] {asset} — sin velas 1H')
                return

            structure_result = self.structure.analyze(candles_1h, asset)

            # Verificar alineación con régimen macro
            if macro_bias != 'NEUTRAL' and structure_result['direction'] != macro_bias:
                # Estructura en contra del régimen — score penalizado
                structure_result['score'] = max(0, structure_result['score'] - 8)
                print(f'[ENGINE] {asset} — estructura vs régimen, score reducido')

            # ── CAPA 3: Zonas institucionales (15M) ──────────
            candles_15m = self._get_candles(epic, 'MINUTE_15', 100)
            if not candles_15m:
                candles_15m = candles_1h  # Fallback a 1H

            zones_result = self.zones.analyze(
                candles_15m, asset,
                structure_result['direction']
            )

            # Si no hay zona institucional activa, no tiene sentido continuar
            if not zones_result['ob_signal']['active'] and \
               not zones_result['fvg_signal']['active'] and \
               not zones_result['liq_signal']['swept']:
                print(f'[ENGINE] {asset} — sin zona institucional activa')
                self._cache_analysis(asset, structure_result, zones_result, None, None, regime)
                return

            # ── CAPA 4: Confirmación de entrada ──────────────
            direction = zones_result['direction'] if zones_result['direction'] != 'NEUTRAL' else structure_result['direction']
            if direction == 'NEUTRAL':
                print(f'[ENGINE] {asset} — sin dirección clara')
                return

            entry_result = self.confirmation.analyze(
                candles_15m[-20:], asset, live, direction
            )

            # ── SCORE TOTAL ───────────────────────────────────
            # Capa 1 ya actuó como filtro de régimen
            # Capas 2, 3, 4 tienen sus scores
            # Ajuste por calidad de sesión
            session_adj = session['quality']

            total_score = int((
                structure_result['score'] +    # 0-25
                zones_result['score']     +    # 0-45
                entry_result['score']          # 0-30
            ) * session_adj)

            total_score = min(total_score, 100)

            print(f'[ENGINE] {asset} | Score: {total_score} | Dir: {direction} | '
                  f'Struct: {structure_result["score"]} | Zones: {zones_result["score"]} | '
                  f'Entry: {entry_result["score"]}')

            # ── CACHE ─────────────────────────────────────────
            self._cache_analysis(asset, structure_result, zones_result, entry_result, direction, regime, total_score)

            # ── GENERAR SEÑAL ─────────────────────────────────
            if total_score >= 45:  # Umbral mínimo para generar señal
                signal = self._build_signal(
                    asset, epic, direction, total_score,
                    structure_result, zones_result, entry_result,
                    regime, nav
                )

                # Validar con Risk Manager
                validation = self.risk.validate(signal, nav, open_positions)

                if validation['approved']:
                    signal['size']     = validation['size']
                    signal['risk_usd'] = validation['risk_usd']

                    if total_score >= 80:
                        # EJECUCIÓN AUTOMÁTICA
                        print(f'[ENGINE] ★ AUTO-EXECUTE: {asset} {direction} Score:{total_score}')
                        self._execute_signal(signal)
                    else:
                        # ALERTA PARA APROBACIÓN MANUAL
                        print(f'[ENGINE] ◆ SEÑAL: {asset} {direction} Score:{total_score} — esperando aprobación')
                        self.signals.append(signal)
                        if self.on_signal:
                            self.on_signal(signal)
                else:
                    print(f'[ENGINE] {asset} — Risk Manager rechazó: {validation["reason"]}')

        except Exception as e:
            print(f'[ENGINE] Error analizando {asset}: {e}')

    # ── EJECUCIÓN ─────────────────────────────────────────────
    def _execute_signal(self, signal: dict):
        """Ejecuta una orden en Capital.com"""
        try:
            epic      = signal['epic']
            direction = 'BUY' if signal['direction'] == 'BULLISH' else 'SELL'
            size      = signal['size']

            # Calcular stop en puntos desde el precio
            entry = signal.get('entry_price', 0)
            sl    = signal.get('sl', 0)
            tp    = signal.get('tp', 0)

            stop_distance  = abs(entry - sl) if entry and sl else None
            limit_distance = abs(tp - entry) if entry and tp else None

            result = self.client.open_position(
                epic=epic,
                direction=direction,
                size=size,
                stop_distance=round(stop_distance, 5) if stop_distance else None,
                limit_distance=round(limit_distance, 5) if limit_distance else None,
            )

            if result.get('ok'):
                signal['executed']        = True
                signal['deal_reference']  = result.get('dealReference')
                signal['executed_at']     = datetime.now(timezone.utc).isoformat()
                self.auto_signals.append(signal)
                print(f'[ENGINE] ✓ Ejecutado: {signal["asset"]} {direction} × {size} | Ref: {result.get("dealReference")}')
                if self.on_auto_execute:
                    self.on_auto_execute(signal)
            else:
                print(f'[ENGINE] ✗ Error ejecutando: {result.get("error")}')

        except Exception as e:
            print(f'[ENGINE] Error en ejecución: {e}')

    def approve_signal(self, signal_id: str) -> dict:
        """Aprueba manualmente una señal desde la Autopsia"""
        signal = next((s for s in self.signals if s['id'] == signal_id), None)
        if not signal:
            return {'ok': False, 'error': 'Señal no encontrada'}

        self._execute_signal(signal)
        self.signals = [s for s in self.signals if s['id'] != signal_id]
        return {'ok': True}

    def reject_signal(self, signal_id: str) -> dict:
        """Rechaza manualmente una señal"""
        self.signals = [s for s in self.signals if s['id'] != signal_id]
        return {'ok': True}

    # ── HELPERS ───────────────────────────────────────────────
    def _get_live_prices(self) -> dict:
        """Obtiene precios en tiempo real del cache del WebSocket"""
        cached = self.client.get_cached_prices()
        if cached:
            return cached
        # Fallback: obtener precios uno por uno
        prices = {}
        for asset, epic in self.ASSETS.items():
            result = self.client.get_price(epic)
            if result.get('ok'):
                prices[asset] = result
        return prices

    def _get_candles(self, epic: str, resolution: str, count: int) -> list:
        """Obtiene velas históricas de Capital.com"""
        result = self.client.get_prices_history(epic, resolution, count)
        if result.get('ok'):
            # Filtrar velas con datos completos
            candles = [c for c in result['candles'] if all([
                c.get('open'), c.get('high'), c.get('low'), c.get('close')
            ])]
            return candles
        return []

    def _build_signal(self, asset, epic, direction, score, structure, zones, entry, regime, nav) -> dict:
        """Construye el objeto de señal completo"""
        import uuid
        atr = zones.get('atr', 0) or entry.get('atr', 0)

        return {
            'id':              str(uuid.uuid4())[:8],
            'asset':           asset,
            'epic':            epic,
            'strategy':        self.ASSET_STRATEGY[asset],
            'direction':       direction,
            'total_score':     score,
            'confidence':      'HIGH' if score >= 80 else 'MED' if score >= 60 else 'LOW',
            'entry_price':     entry.get('entry_price'),
            'sl':              entry.get('sl'),
            'tp':              entry.get('tp'),
            'sl_distance':     abs((entry.get('entry_price') or 0) - (entry.get('sl') or 0)),
            'rr':              entry.get('rr', 0),
            'atr':             atr,
            'size_multiplier': regime.get('size_multiplier', 1.0),
            'structure':       structure.get('structure'),
            'ob_active':       zones['ob_signal'].get('active', False),
            'fvg_active':      zones['fvg_signal'].get('active', False),
            'liq_swept':       zones['liq_signal'].get('swept', False),
            'regime':          regime.get('mode'),
            'macro_bias':      regime['bias'].get(asset, 'NEUTRAL'),
            'session_quality': self.macro.is_active_session(asset)['quality'],
            'generated_at':    datetime.now(timezone.utc).isoformat(),
            'executed':        False,
            'size':            0,
            'context': (
                f"Estructura: {structure.get('structure')} | "
                f"{'OB activo' if zones['ob_signal'].get('active') else ''} "
                f"{'FVG activo' if zones['fvg_signal'].get('active') else ''} "
                f"{'Liquidez cazada' if zones['liq_signal'].get('swept') else ''} | "
                f"Régimen: {regime.get('mode')} | Sesgo: {regime['bias'].get(asset, 'NEUTRAL')}"
            ).strip(),
        }

    def _cache_analysis(self, asset, structure, zones, entry, direction, regime, score=0):
        """Guarda el último análisis para mostrarlo en el dashboard"""
        self.analysis_cache[asset] = {
            'asset':     asset,
            'score':     score,
            'direction': direction,
            'structure': structure,
            'zones':     {
                'ob_active':  zones['ob_signal'].get('active', False),
                'fvg_active': zones['fvg_signal'].get('active', False),
                'liq_swept':  zones['liq_signal'].get('swept', False),
                'ob_count':   len(zones.get('order_blocks', [])),
                'fvg_count':  len(zones.get('fvgs', [])),
            },
            'regime_bias': regime['bias'].get(asset, 'NEUTRAL'),
            'updated_at':  datetime.now(timezone.utc).isoformat(),
        }
        if self.on_analysis:
            self.on_analysis(asset, self.analysis_cache[asset])

    # ── STATUS ────────────────────────────────────────────────
    def get_status(self) -> dict:
        return {
            'running':          self.running,
            'last_run':         self.last_run.isoformat() if self.last_run else None,
            'interval_min':     self.interval // 60,
            'pending_signals':  len(self.signals),
            'auto_executed':    len(self.auto_signals),
            'paused_assets':    list(self.paused_assets),
            'active_strategies':self.active_strategies,
            'analysis_cache':   self.analysis_cache,
            'risk_status':      self.risk.get_status(),
        }

    def get_signals(self) -> list:
        return self.signals

    def get_auto_signals(self) -> list:
        return self.auto_signals
