# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — ICARO RUNNER
# Proceso independiente que ejecuta el pipeline de ICARO V2.1.
# Usa Alpaca como fuente de datos (SPY, VIX, QQQ, IWM, HYG, LQD, VXX).
# Escribe snapshots en icaro_storage/snapshots/latest_snapshot.json
# para que icaro_bridge.py los consuma.
#
# Arrancar por separado:
#   py -3.11 icaro_runner.py
#
# NO modifica nada del sistema principal de JORMUNDGANDRSSON.
# ═══════════════════════════════════════════════════════════

import json
import os
import sys
import time
import threading
from datetime import datetime, timezone
from pathlib import Path

# ── DEPENDENCIAS ──────────────────────────────────────────────
try:
    import numpy  as np
    import pandas as pd
except ImportError:
    print('[ICARO RUNNER] ERROR: numpy y pandas son requeridos.')
    print('  pip install numpy pandas --break-system-packages')
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass

# ── PATHS ─────────────────────────────────────────────────────
BASE_DIR      = Path(__file__).parent
STORAGE_DIR   = BASE_DIR / 'icaro_storage'
SNAPSHOT_DIR  = STORAGE_DIR / 'snapshots'
SIGNALS_DIR   = STORAGE_DIR / 'signals'
LOGS_DIR      = STORAGE_DIR / 'logs'

for d in [SNAPSHOT_DIR, SIGNALS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

SNAPSHOT_FILE = SNAPSHOT_DIR / 'latest_snapshot.json'

# ── CONFIGURACIÓN ─────────────────────────────────────────────
ICARO_CONFIG = {
    # Alpaca API — cargar desde .env
    'alpaca_api_key':    os.getenv('ALPACA_API_KEY', ''),
    'alpaca_api_secret': os.getenv('ALPACA_API_SECRET', ''),
    'alpaca_base_url':   os.getenv('ALPACA_BASE_URL', 'https://data.alpaca.markets'),

    # Pipeline settings
    'run_interval_minutes': 60,       # Correr cada hora
    'warmup_days':          60,      # Días mínimos de historia para HMM
    'hmm_components':       3,
    'hmm_refit_stride':     21,       # Días entre refits del HMM

    # Instrumentos — los mismos que ICARO V2.1 original
    'benchmark_symbol':     'SPY',
    'vix_symbol':           'VIXY',   # Proxy VIX en Alpaca (ETF)
    'multi_symbols':        ['SPY', 'QQQ', 'IWM', 'HYG', 'LQD', 'VXX'],

    # Thresholds — DO NOT TOUCH (calibrados en Colab)
    'killswitch_dd':             -0.20,
    'max_capital_utilization':    1.0,
    'probe_beta':                 0.35,
    'hedge_beta':                 0.85,
    'full_deploy_beta':           1.75,
    'convexity_acceleration':     2.25,
    'transaction_cost_bps':       8.0,
    'slippage_bps':               12.0,

    # Score map — DO NOT TOUCH
    'score_map': {
        'TRUE_POSITIVE_HIGH_CONVICTION': 1.0,
        'TRUE_POSITIVE':                 0.85,
        'EARLY_WARNING':                 0.6,
        'NO_SIGNAL_OK':                  0.75,
        'FALSE_POSITIVE':                0.10,
        'MISSED_CRASH':                  0.0,
    },
}


# ══════════════════════════════════════════════════════════════
# ALPACA DATA PROVIDER
# ══════════════════════════════════════════════════════════════

class AlpacaDataProvider:
    """
    Proveedor de datos de mercado via Alpaca API.
    Solo para ICARO — no interfiere con Capital.com.
    """

    BASE_URL = 'https://data.alpaca.markets/v2'

    def __init__(self, api_key: str, api_secret: str):
        self.api_key    = api_key
        self.api_secret = api_secret
        self.connected  = False

        if not api_key or not api_secret:
            print('[ALPACA] ADVERTENCIA: Credenciales no configuradas en .env')
            print('  Agrega ALPACA_API_KEY y ALPACA_API_SECRET al archivo .env')
        else:
            self.connected = True
            print('[ALPACA] Provider inicializado')

    def get_bars(self, symbol: str, timeframe: str = '1Day',
                 limit: int = 300) -> pd.DataFrame:
        """
        Obtiene barras OHLCV de Alpaca.
        timeframe: '1Day', '1Hour', '15Min'
        """
        if not self.connected:
            return pd.DataFrame()

        try:
            import requests

            from datetime import timedelta as _td
            _end   = datetime.now(timezone.utc)
            _start = _end - _td(days=limit * 2)

            url    = f'{self.BASE_URL}/stocks/{symbol}/bars'
            params = {
                'timeframe':  timeframe,
                'limit':      limit,
                'start':      _start.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'end':        _end.strftime('%Y-%m-%dT%H:%M:%SZ'),
                'feed':       'iex',
            }
            headers = {
                'APCA-API-KEY-ID':     self.api_key,
                'APCA-API-SECRET-KEY': self.api_secret,
            }

            r = requests.get(url, params=params, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()

            bars = data.get('bars', [])
            if not bars:
                print(f'[ALPACA] Sin datos para {symbol}')
                return pd.DataFrame()

            df = pd.DataFrame(bars)
            df['t'] = pd.to_datetime(df['t'])
            df = df.rename(columns={
                't': 'timestamp', 'o': 'open', 'h': 'high',
                'l': 'low',       'c': 'close', 'v': 'volume'
            })
            df = df.set_index('timestamp').sort_index()

            return df[['open', 'high', 'low', 'close', 'volume']]

        except Exception as e:
            print(f'[ALPACA] Error obteniendo {symbol}: {e}')
            return pd.DataFrame()

    def get_latest_quote(self, symbol: str) -> dict:
        """Obtiene el último precio de un símbolo."""
        if not self.connected:
            return {}
        try:
            import requests
            url     = f'{self.BASE_URL}/stocks/{symbol}/quotes/latest'
            headers = {
                'APCA-API-KEY-ID':     self.api_key,
                'APCA-API-SECRET-KEY': self.api_secret,
            }
            r = requests.get(url, headers=headers, timeout=10)
            r.raise_for_status()
            return r.json().get('quote', {})
        except Exception as e:
            print(f'[ALPACA] Error quote {symbol}: {e}')
            return {}


# ══════════════════════════════════════════════════════════════
# ICARO PIPELINE CORE
# Extracción quirúrgica de la lógica cuantitativa de ICARO V2.1.
# Preserva la lógica exacta — no se modifica ningún threshold.
# ══════════════════════════════════════════════════════════════

class IcaroPipeline:
    """
    Pipeline cuantitativo de ICARO V2.1.
    Produce el snapshot con todos los campos del signal_contract.
    """

    def __init__(self, data_provider: AlpacaDataProvider, config: dict):
        self.data     = data_provider
        self.config   = config
        self._hmm_model = None
        self._hmm_fitted_at = None
        print('[ICARO PIPELINE] Inicializado')

    def run(self) -> dict:
        """
        Ejecuta el pipeline completo y retorna el snapshot.
        Orden de ejecución según el blueprint (DO NOT REORDER):
          data → features → regime → fragility → convexity → signal → capital → audit
        """
        ts = datetime.now(timezone.utc).isoformat()
        print(f'\n[ICARO] ═══ PIPELINE INICIADO {ts} ═══')

        try:
            # 1. DATA ENGINE
            print('[ICARO] [1/7] Cargando datos...')
            benchmark_df, multi_df = self._build_dataset()
            if benchmark_df is None or benchmark_df.empty or 'close' not in benchmark_df.columns:
                return self._error_snapshot('Sin datos de benchmark (SPY)')

            # 2. FEATURE ENGINE
            print('[ICARO] [2/7] Construyendo features...')
            feature_df = self._build_features(benchmark_df)
            if feature_df.empty:
                return self._error_snapshot('Error construyendo features')

            # 3. REGIME ENGINE (HMM)
            print('[ICARO] [3/7] Calculando régimen (HMM)...')
            feature_df = self._build_regime(feature_df)

            # 4. FRAGILITY ENGINE
            print('[ICARO] [4/7] Calculando fragility...')
            feature_df = self._build_fragility(feature_df, multi_df)

            # 5. CONVEXITY ENGINE
            print('[ICARO] [5/7] Calculando convexity...')
            feature_df = self._build_convexity(feature_df)

            # 6. SIGNAL ENGINE
            print('[ICARO] [6/7] Evaluando señal...')
            snapshot = self._build_signal(feature_df)

            # 7. AUDIT
            print('[ICARO] [7/7] Auditando...')
            snapshot['timestamp']      = ts
            snapshot['status']         = 'RUNNING'
            snapshot['engine_name']    = 'ICARO V2.1'
            snapshot['snapshot_version'] = 'v2.1.0'

            print(f'[ICARO] Pipeline completado — {snapshot.get("regime_label")} | '
                  f'Decision: {snapshot.get("execution_decision")} | '
                  f'Quality: {snapshot.get("signal_quality_score", 0):.2f}')

            return snapshot

        except Exception as e:
            print(f'[ICARO] ERROR en pipeline: {e}')
            import traceback
            traceback.print_exc()
            return self._error_snapshot(str(e))

    # ── DATA ENGINE ───────────────────────────────────────────

    def _build_dataset(self):
        """Carga datos históricos de Alpaca."""
        # Benchmark (SPY)
        benchmark_df = self.data.get_bars(
            self.config['benchmark_symbol'],
            timeframe='1Day',
            limit=300
        )

        # VIX proxy (VIXY ETF como proxy de VIX)
        vix_df = self.data.get_bars(
            self.config['vix_symbol'],
            timeframe='1Day',
            limit=300
        )

        if not vix_df.empty and not benchmark_df.empty:
            benchmark_df['vix_close'] = vix_df['close'].reindex(
                benchmark_df.index, method='ffill'
            )
        else:
            # Fallback: VIX sintético basado en volatilidad realizada
            benchmark_df['vix_close'] = (
                benchmark_df['close'].pct_change()
                .rolling(21).std() * np.sqrt(252) * 100
            ).clip(5, 80)

        # Multi-market
        multi_frames = {}
        for sym in self.config['multi_symbols']:
            df = self.data.get_bars(sym, timeframe='1Day', limit=100)
            if not df.empty:
                multi_frames[sym] = df

        multi_df = multi_frames if multi_frames else {}

        return benchmark_df, multi_df

    # ── FEATURE ENGINE ────────────────────────────────────────

    def _build_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Construye features estructurales sobre el benchmark."""
        if len(df) < 60:
            return pd.DataFrame()

        df = df.copy()
        c  = df['close']

        # Returns
        df['returns_1d']  = c.pct_change(1)
        df['returns_5d']  = c.pct_change(5)
        df['returns_21d'] = c.pct_change(21)

        # Volatilidad realizada
        df['vol_21']  = df['returns_1d'].rolling(21).std()  * np.sqrt(252)
        df['vol_63']  = df['returns_1d'].rolling(63).std()  * np.sqrt(252)
        df['vol_252'] = df['returns_1d'].rolling(252).std() * np.sqrt(252)

        # VIX features
        df['vix_sma_21']          = df['vix_close'].rolling(21).mean()
        df['vix_expansion_ratio'] = df['vix_close'] / df['vix_sma_21'].clip(lower=0.01)

        # Drawdown desde máximo
        rolling_max         = c.expanding().max()
        df['drawdown']      = (c - rolling_max) / rolling_max.clip(lower=0.01)
        df['drawdown_21d']  = df['drawdown'].rolling(21).min()

        # Momentum
        df['mom_63']  = c / c.shift(63)  - 1
        df['mom_126'] = c / c.shift(126) - 1
        df['mom_252'] = c / c.shift(252) - 1

        # Trend strength
        df['sma_50']  = c.rolling(50).mean()
        df['sma_200'] = c.rolling(200).mean()
        df['above_sma_200'] = (c > df['sma_200']).astype(int)

        return df.dropna(subset=['vol_21', 'vix_sma_21'])

    # ── REGIME ENGINE (HMM) ───────────────────────────────────

    def _build_regime(self, df: pd.DataFrame) -> pd.DataFrame:
        """HMM de 3 estados sobre vol y returns."""
        try:
            from hmmlearn import hmm

            features = df[['returns_1d', 'vol_21', 'vix_close']].dropna()

            # Normalizar
            from sklearn.preprocessing import StandardScaler
            scaler  = StandardScaler()
            X       = scaler.fit_transform(features.values)

            # Refit del modelo según stride
            needs_refit = (
                self._hmm_model is None or
                self._hmm_fitted_at is None or
                (datetime.now(timezone.utc) - self._hmm_fitted_at).days >= self.config['hmm_refit_stride']
            )

            if needs_refit:
                model = hmm.GaussianHMM(
                    n_components=self.config['hmm_components'],
                    covariance_type='full',
                    n_iter=1000,
                    random_state=42,
                )
                model.fit(X)
                self._hmm_model     = model
                self._hmm_fitted_at = datetime.now(timezone.utc)
                print('[ICARO] HMM refitted')

            states = self._hmm_model.predict(X)
            df.loc[features.index, 'hmm_state'] = states

            # Mapear estados a etiquetas interpretables
            state_vol = {}
            for s in range(self.config['hmm_components']):
                mask = states == s
                if mask.sum() > 0:
                    state_vol[s] = features['vol_21'].values[mask].mean()

            sorted_states = sorted(state_vol, key=state_vol.get)
            state_labels  = {
                sorted_states[0]: 'LOW_VOL_TREND',
                sorted_states[1]: 'NORMAL_REGIME',
                sorted_states[2]: 'HIGH_VOL_STRESS',
            }

            df['regime_label'] = df['hmm_state'].map(
                lambda x: state_labels.get(int(x), 'UNKNOWN') if pd.notna(x) else 'UNKNOWN'
            )

        except ImportError:
            print('[ICARO] hmmlearn no instalado — usando régimen basado en VIX')
            df = self._regime_fallback(df)
        except Exception as e:
            print(f'[ICARO] Error HMM: {e} — usando fallback')
            df = self._regime_fallback(df)

        return df

    def _regime_fallback(self, df: pd.DataFrame) -> pd.DataFrame:
        """Régimen basado en VIX cuando hmmlearn no está disponible."""
        vix = df['vix_close']
        conditions = [
            vix > 30,
            (vix >= 20) & (vix <= 30),
        ]
        choices = ['HIGH_VOL_STRESS', 'NORMAL_REGIME']
        df['regime_label'] = np.select(conditions, choices, default='LOW_VOL_TREND')
        return df

    # ── FRAGILITY ENGINE ──────────────────────────────────────

    def _build_fragility(self, df: pd.DataFrame, multi_df: dict) -> pd.DataFrame:
        """
        Fragility score = combinación de señales de estrés.
        Rango: 0.0 (muy sano) → 1.0 (muy frágil)
        """
        df = df.copy()

        # Componente 1: VIX percentile histórico
        vix_pct = df['vix_close'].rank(pct=True)

        # Componente 2: Drawdown actual
        dd_score = (-df['drawdown']).clip(0, 0.4) / 0.4

        # Componente 3: Vol expansion
        vol_expansion = (df['vix_expansion_ratio'] - 1).clip(0, 1)

        # Componente 4: Momentum negativo
        mom_score = (-df['mom_63']).clip(0, 0.3) / 0.3

        # Componente 5: Multi-market stress (si disponible)
        multi_stress = pd.Series(0.0, index=df.index)
        if multi_df:
            stress_list = []
            for sym, mdf in multi_df.items():
                if 'close' in mdf.columns and len(mdf) > 21:
                    ret = mdf['close'].pct_change(21).reindex(df.index, method='ffill')
                    stress_list.append((-ret).clip(0, 0.15) / 0.15)
            if stress_list:
                multi_stress = pd.concat(stress_list, axis=1).mean(axis=1)

        # Score ponderado (pesos calibrados en ICARO V2.1)
        df['fragility_score'] = (
            0.25 * vix_pct      +
            0.20 * dd_score     +
            0.20 * vol_expansion +
            0.15 * mom_score    +
            0.20 * multi_stress
        ).clip(0, 1).round(4)

        return df

    # ── CONVEXITY ENGINE ──────────────────────────────────────

    def _build_convexity(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Convexity score = potencial de rebound asimétrico.
        Alto cuando: fragility alta + momentum muy negativo + vol elevada.
        """
        df = df.copy()

        fragility = df['fragility_score']
        mom_neg   = (-df['mom_63']).clip(0, 0.5) / 0.5
        vol_high  = (df['vol_21'] - 0.10).clip(0, 0.40) / 0.40

        df['convexity_score'] = (
            0.40 * fragility +
            0.35 * mom_neg   +
            0.25 * vol_high
        ).clip(0, 1).round(4)

        # Convexity window
        conv = df['convexity_score']
        df['convexity_window'] = np.select(
            [conv >= 0.70, conv >= 0.40, conv >= 0.20],
            ['HIGH',       'MID',        'LOW'],
            default='NONE'
        )

        # Continuation score (probabilidad de que el régimen continúe)
        df['continuation_score'] = (1 - df['fragility_score']).round(4)

        # Crash probability (basado en fragility + VIX expansion)
        df['crash_probability'] = (
            0.60 * df['fragility_score'] +
            0.40 * (df['vix_expansion_ratio'] - 1).clip(0, 1)
        ).clip(0, 1).round(4)

        return df

    # ── SIGNAL ENGINE ─────────────────────────────────────────

    def _build_signal(self, df: pd.DataFrame) -> dict:
        """
        Evalúa los gates y produce el execution_decision final.
        Lógica preservada del build_execution_layer() de ICARO V2.1.
        DO NOT TOUCH los thresholds.
        """
        if df.empty or len(df) < 10:
            return self._empty_signal()

        # Último snapshot del pipeline
        last = df.iloc[-1]

        regime_label    = last.get('regime_label', 'UNKNOWN')
        fragility       = float(last.get('fragility_score',    0))
        convexity       = float(last.get('convexity_score',    0))
        continuation    = float(last.get('continuation_score', 0))
        crash_prob      = float(last.get('crash_probability',  0))
        conv_window     = last.get('convexity_window', 'NONE')
        drawdown        = float(last.get('drawdown', 0))

        # ── KILLSWITCH GLOBAL ─────────────────────────────────
        killswitch = drawdown <= self.config['killswitch_dd']

        if killswitch:
            return {
                **self._empty_signal(),
                'regime_label':    regime_label,
                'fragility_score': fragility,
                'convexity_score': convexity,
                'crash_probability': crash_prob,
                'killswitch_global': True,
                'execution_decision': 'KILLSWITCH',
                'deployment_stage':   'NO_DEPLOYMENT',
                'signal_quality':     'MISSED_CRASH',
                'signal_quality_score': self.config['score_map']['MISSED_CRASH'],
                'live_action':        'RISK OFF — KILLSWITCH',
                'drawdown_from_high': round(drawdown, 4),
            }

        # ── GATE 1: HARD GATE — Condiciones extremas ──────────
        extreme_stress = fragility > 0.80 and crash_prob > 0.30
        if extreme_stress:
            return {
                **self._empty_signal(),
                'regime_label':      regime_label,
                'fragility_score':   fragility,
                'convexity_score':   convexity,
                'crash_probability': crash_prob,
                'killswitch_global': False,
                'execution_decision': 'NO_ACTION',
                'deployment_stage':   'NO_DEPLOYMENT',
                'signal_quality':     'FALSE_POSITIVE',
                'signal_quality_score': self.config['score_map']['FALSE_POSITIVE'],
                'live_action':        'RISK OFF',
                'drawdown_from_high': round(drawdown, 4),
            }

        # ── GATE 2: CONVEXITY SIGNAL ──────────────────────────
        probe_signal = (
            convexity >= 0.35 and
            fragility >= 0.20 and
            conv_window in ['MID', 'HIGH'] and
            not killswitch
        )

        full_signal = (
            convexity >= 0.60 and
            fragility >= 0.40 and
            conv_window == 'HIGH' and
            crash_prob < 0.20
        )

        convexity_signal = (
            convexity >= 0.70 and
            fragility >= 0.50 and
            conv_window == 'HIGH'
        )

        # ── DECISION TREE ─────────────────────────────────────
        if convexity_signal:
            execution_decision = 'EXECUTE'
            deployment_stage   = 'CONVEXITY_DEPLOY'
            deployment_action  = 'CONVEXITY_ACCELERATION'
            signal_quality     = 'TRUE_POSITIVE_HIGH_CONVICTION'
            live_action        = 'RISK ON — CONVEXITY'
        elif full_signal:
            execution_decision = 'EXECUTE'
            deployment_stage   = 'FULL_DEPLOY'
            deployment_action  = 'FULL_DEPLOYMENT'
            signal_quality     = 'TRUE_POSITIVE'
            live_action        = 'RISK ON — FULL'
        elif probe_signal:
            execution_decision = 'EXECUTE'
            deployment_stage   = 'PROBE'
            deployment_action  = 'PROBE_DEPLOYMENT'
            signal_quality     = 'EARLY_WARNING'
            live_action        = 'RISK ON — PROBE'
        else:
            execution_decision = 'NO_ACTION'
            deployment_stage   = 'NO_DEPLOYMENT'
            deployment_action  = 'NO_CONVEXITY_ACTION'
            signal_quality     = 'NO_SIGNAL_OK'
            live_action        = 'RISK ON' if regime_label == 'LOW_VOL_TREND' else 'NEUTRAL'

        signal_quality_score = self.config['score_map'].get(signal_quality, 0.75)

        # ── CAPITAL UTILIZATION ───────────────────────────────
        beta_map = {
            'PROBE':             self.config['probe_beta'],
            'FULL_DEPLOY':       self.config['full_deploy_beta'],
            'CONVEXITY_DEPLOY':  self.config['convexity_acceleration'],
            'NO_DEPLOYMENT':     0.0,
        }
        beta              = beta_map.get(deployment_stage, 0.0)
        capital_util      = min(beta, self.config['max_capital_utilization'])
        recommended_exp   = round(capital_util * 100, 1)

        # Probe success probability
        probe_success = round(
            0.40 * (1 - fragility) +
            0.35 * convexity       +
            0.25 * continuation,
            4
        )

        return {
            'regime_label':             regime_label,
            'fragility_score':          round(fragility, 4),
            'continuation_score':       round(continuation, 4),
            'crash_probability':        round(crash_prob, 4),
            'convexity_score':          round(convexity, 4),
            'convexity_window':         conv_window,
            'probe_success_probability': probe_success,
            'state':                    'STRESS' if fragility > 0.50 else 'NORMAL',
            'event_mode':               fragility > 0.70,
            'execution_decision':       execution_decision,
            'deployment_stage':         deployment_stage,
            'deployment_action':        deployment_action,
            'capital_utilization':      round(capital_util, 4),
            'killswitch_global':        False,
            'signal_quality':           signal_quality,
            'signal_quality_score':     signal_quality_score,
            'live_action':              live_action,
            'recommended_exposure_pct': recommended_exp,
            'drawdown_from_high':       round(float(drawdown), 4),
            'benchmark_close':          round(float(df.iloc[-1]['close']), 2),
            'vix_close':                round(float(df.iloc[-1]['vix_close']), 2),
        }

    # ── HELPERS ───────────────────────────────────────────────

    def _empty_signal(self) -> dict:
        return {
            'regime_label':             'UNKNOWN',
            'fragility_score':          None,
            'continuation_score':       None,
            'crash_probability':        None,
            'convexity_score':          None,
            'convexity_window':         None,
            'probe_success_probability': None,
            'state':                    'UNKNOWN',
            'event_mode':               False,
            'execution_decision':       'NO_ACTION',
            'deployment_stage':         'NO_DEPLOYMENT',
            'deployment_action':        'NO_CONVEXITY_ACTION',
            'capital_utilization':      0.0,
            'killswitch_global':        False,
            'signal_quality':           'NO_SIGNAL_OK',
            'signal_quality_score':     0.75,
            'live_action':              'UNKNOWN',
            'recommended_exposure_pct': 0.0,
            'drawdown_from_high':       0.0,
            'benchmark_close':          None,
            'vix_close':                None,
        }

    def _error_snapshot(self, reason: str) -> dict:
        snap = self._empty_signal()
        snap.update({
            'status':           'ERROR',
            'error':            reason,
            'timestamp':        datetime.now(timezone.utc).isoformat(),
            'engine_name':      'ICARO V2.1',
            'snapshot_version': 'v2.1.0',
        })
        return snap


# ══════════════════════════════════════════════════════════════
# RUNNER — PROCESO PRINCIPAL
# ══════════════════════════════════════════════════════════════

class IcaroRunner:
    """Orquesta el pipeline de ICARO y escribe snapshots al disco."""

    def __init__(self):
        self.provider = AlpacaDataProvider(
            api_key    = ICARO_CONFIG['alpaca_api_key'],
            api_secret = ICARO_CONFIG['alpaca_api_secret'],
        )
        self.pipeline = IcaroPipeline(self.provider, ICARO_CONFIG)
        self.running  = False
        self.thread   = None

    def start(self):
        """Inicia el runner en un thread separado."""
        if self.running:
            return
        self.running = True
        self.thread  = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print(f'[ICARO RUNNER] Iniciado — ciclos cada {ICARO_CONFIG["run_interval_minutes"]} minutos')

    def stop(self):
        self.running = False
        print('[ICARO RUNNER] Detenido')

    def run_once(self):
        """Ejecuta el pipeline una vez y escribe el snapshot."""
        snapshot = self.pipeline.run()
        self._write_snapshot(snapshot)
        return snapshot

    def _loop(self):
        interval = ICARO_CONFIG['run_interval_minutes'] * 60
        while self.running:
            try:
                now = datetime.now(timezone.utc)
                if now.weekday() >= 5:
                    print('[ICARO RUNNER] Fin de semana — esperando')
                    time.sleep(3600)
                    continue

                self.run_once()
                print(f'[ICARO RUNNER] Próximo ciclo en {ICARO_CONFIG["run_interval_minutes"]} minutos')
                time.sleep(interval)

            except Exception as e:
                print(f'[ICARO RUNNER] Error en loop: {e}')
                time.sleep(300)  # 5 minutos antes de reintentar

    def _write_snapshot(self, snapshot: dict):
        """Escribe el snapshot al disco de forma atómica."""
        try:
            # Escribir a archivo temporal primero, luego renombrar (atómico)
            tmp_file = SNAPSHOT_FILE.with_suffix('.tmp')
            with open(tmp_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, default=str)
            tmp_file.replace(SNAPSHOT_FILE)

            # Guardar copia histórica
            ts_str    = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            hist_file = SNAPSHOT_DIR / f'snapshot_{ts_str}.json'
            with open(hist_file, 'w', encoding='utf-8') as f:
                json.dump(snapshot, f, indent=2, default=str)

            print(f'[ICARO RUNNER] Snapshot escrito → {SNAPSHOT_FILE.name}')

        except Exception as e:
            print(f'[ICARO RUNNER] Error escribiendo snapshot: {e}')


# ══════════════════════════════════════════════════════════════
# ENTRY POINT
# py -3.11 icaro_runner.py
# ══════════════════════════════════════════════════════════════

if __name__ == '__main__':
    print("""
╔═══════════════════════════════════════════════════╗
║   ICARO V2.1 — Runner Local                       ║
║   Fuente: Alpaca API                              ║
║   Storage: icaro_storage/snapshots/               ║
╚═══════════════════════════════════════════════════╝
    """)

    runner = IcaroRunner()

    # Primera ejecución inmediata
    print('[ICARO RUNNER] Ejecutando ciclo inicial...')
    snapshot = runner.run_once()
    print(f'\n[ICARO RUNNER] Resultado inicial:')
    print(f'  Régimen:    {snapshot.get("regime_label")}')
    print(f'  Decisión:   {snapshot.get("execution_decision")}')
    print(f'  Fragility:  {snapshot.get("fragility_score")}')
    print(f'  Killswitch: {snapshot.get("killswitch_global")}')
    print(f'  Quality:    {snapshot.get("signal_quality_score")}')

    # Loop continuo
    runner.start()

    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        runner.stop()
        print('\n[ICARO RUNNER] Detenido por el usuario')