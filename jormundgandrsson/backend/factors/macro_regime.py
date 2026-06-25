# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — CAPA 1: RÉGIMEN MACRO
# Determina el contexto global antes de analizar cualquier chart
# ═══════════════════════════════════════════════════════════

class MacroRegime:

    def __init__(self, capital_client):
        self.client = capital_client
        try:
            from icaro_bridge import icaro_bridge as _bridge
            self._icaro = _bridge
        except ImportError:
            self._icaro = None

        # Epics de Capital.com para instrumentos macro
        self.MACRO_EPICS = {
            'DXY':   'CS.D.DOLALIDX.TODAY.IP',
            'GOLD':  'CS.D.GOLD.TODAY.IP',
            'OIL':   'CS.D.CRUDE.TODAY.IP',
            'SPX':   'IX.D.SPTRD.DAILY.IP',
            'VIX':   'CS.D.USAVIX.TODAY.IP',
        }

        # Estado del régimen
        self.regime = {
            'mode':        'UNKNOWN',   # RISK_ON | RISK_OFF | NEUTRAL
            'dxy_trend':   'NEUTRAL',   # UP | DOWN | NEUTRAL
            'vix_level':   'NORMAL',    # LOW | NORMAL | HIGH | EXTREME
            'vix_value':   0,
            'bias': {
                'EURUSD': 'NEUTRAL',
                'GBPUSD': 'NEUTRAL',
                'USDJPY': 'NEUTRAL',
                'SPX500': 'NEUTRAL',
                'NAS100': 'NEUTRAL',
                'XAUUSD': 'NEUTRAL',
                'USOIL':  'NEUTRAL',
            },
            'size_multiplier': 1.0,
            'pass': True,
            'reason': '',
        }

    def analyze(self, prices: dict) -> dict:
        """
        Analiza el régimen macro usando precios en tiempo real
        prices: dict con precios actuales de Capital.com
        """
        try:
            self._analyze_vix(prices)
            self._analyze_dxy(prices)
            self._determine_regime()
            self._set_directional_bias()
            self._set_size_multiplier()
            self._enrich_with_icaro()   # ← enriquecimiento con ICARO (no bloquea)
            return self.regime

        except Exception as e:
            print(f'[MACRO] Error en análisis: {e}')
            self.regime['pass'] = True  # No bloquear por error de datos
            return self.regime

    def _analyze_vix(self, prices):
        """Determina nivel de miedo/riesgo del mercado"""
        vix = prices.get('VIX', {}).get('mid', 18)
        self.regime['vix_value'] = vix

        if vix < 15:
            self.regime['vix_level'] = 'LOW'       # Complacencia — cuidado con reversiones
        elif vix < 20:
            self.regime['vix_level'] = 'NORMAL'    # Condiciones normales
        elif vix < 30:
            self.regime['vix_level'] = 'HIGH'      # Miedo — reducir sizing
        else:
            self.regime['vix_level'] = 'EXTREME'   # Pánico — suspender índices

    def _analyze_dxy(self, prices):
        """Determina tendencia del dólar — afecta todos los pares"""
        # Usamos Gold como proxy inverso del DXY si no tenemos DXY directo
        gold = prices.get('XAUUSD', {}).get('mid', 2300)
        gold_prev = prices.get('XAUUSD', {}).get('prev', gold)

        if gold_prev > 0:
            gold_change = (gold - gold_prev) / gold_prev * 100
            # Gold sube = DXY baja (correlación inversa ~-0.75)
            if gold_change > 0.3:
                self.regime['dxy_trend'] = 'DOWN'
            elif gold_change < -0.3:
                self.regime['dxy_trend'] = 'UP'
            else:
                self.regime['dxy_trend'] = 'NEUTRAL'

    def _determine_regime(self):
        """Determina el régimen global del mercado"""
        vix = self.regime['vix_level']
        dxy = self.regime['dxy_trend']

        if vix == 'EXTREME':
            self.regime['mode'] = 'RISK_OFF'
            self.regime['pass'] = True  # Seguimos operando pero con restricciones
            self.regime['reason'] = f'VIX extremo ({self.regime["vix_value"]:.1f}) — solo safe havens'

        elif vix == 'HIGH':
            self.regime['mode'] = 'RISK_OFF'
            self.regime['pass'] = True
            self.regime['reason'] = f'VIX alto ({self.regime["vix_value"]:.1f}) — sizing reducido'

        elif vix in ['NORMAL', 'LOW'] and dxy == 'DOWN':
            self.regime['mode'] = 'RISK_ON'
            self.regime['pass'] = True
            self.regime['reason'] = 'Risk-on: VIX normal + DXY débil'

        elif vix in ['NORMAL', 'LOW'] and dxy == 'UP':
            self.regime['mode'] = 'RISK_ON'
            self.regime['pass'] = True
            self.regime['reason'] = 'Risk-on: VIX normal + DXY fuerte'

        else:
            self.regime['mode'] = 'NEUTRAL'
            self.regime['pass'] = True
            self.regime['reason'] = 'Régimen neutral'

    def _set_directional_bias(self):
        """Define sesgo direccional por activo basado en régimen"""
        mode = self.regime['mode']
        dxy  = self.regime['dxy_trend']
        vix  = self.regime['vix_level']

        bias = self.regime['bias']

        # FOREX — correlación directa con DXY
        if dxy == 'UP':
            bias['EURUSD'] = 'SHORT'   # USD fuerte → EUR débil
            bias['GBPUSD'] = 'SHORT'
            bias['USDJPY'] = 'LONG'    # USD fuerte → JPY débil
        elif dxy == 'DOWN':
            bias['EURUSD'] = 'LONG'
            bias['GBPUSD'] = 'LONG'
            bias['USDJPY'] = 'SHORT'
        else:
            bias['EURUSD'] = 'NEUTRAL'
            bias['GBPUSD'] = 'NEUTRAL'
            bias['USDJPY'] = 'NEUTRAL'

        # ÍNDICES — risk-on/off
        if mode == 'RISK_ON':
            bias['SPX500'] = 'LONG'
            bias['NAS100'] = 'LONG'
        elif mode == 'RISK_OFF' or vix in ['HIGH', 'EXTREME']:
            bias['SPX500'] = 'SHORT'
            bias['NAS100'] = 'SHORT'
        else:
            bias['SPX500'] = 'NEUTRAL'
            bias['NAS100'] = 'NEUTRAL'

        # GOLD — safe haven, correlación inversa DXY
        if vix in ['HIGH', 'EXTREME'] or dxy == 'DOWN':
            bias['XAUUSD'] = 'LONG'
        elif dxy == 'UP' and vix == 'LOW':
            bias['XAUUSD'] = 'SHORT'
        else:
            bias['XAUUSD'] = 'NEUTRAL'

        # OIL — sigue risk-on/off y DXY
        if mode == 'RISK_ON' and dxy != 'UP':
            bias['USOIL'] = 'LONG'
        elif mode == 'RISK_OFF':
            bias['USOIL'] = 'SHORT'
        else:
            bias['USOIL'] = 'NEUTRAL'

    def _set_size_multiplier(self):
        """Ajusta el multiplicador de sizing según condiciones"""
        vix = self.regime['vix_level']
        if vix == 'EXTREME':
            self.regime['size_multiplier'] = 0.25   # 25% del sizing normal
        elif vix == 'HIGH':
            self.regime['size_multiplier'] = 0.50   # 50% del sizing normal
        elif vix == 'LOW':
            self.regime['size_multiplier'] = 0.80   # Complacencia = precaución
        else:
            self.regime['size_multiplier'] = 1.0    # Normal

    def _enrich_with_icaro(self):
        """
        Enriquece el régimen con datos de ICARO si está disponible.
        No bloquea ni falla si ICARO está offline — el régimen sigue
        funcionando con su lógica propia.
        """
        if self._icaro is None or not self._icaro.is_alive():
            self.regime['icaro_available']  = False
            self.regime['icaro_regime']     = None
            self.regime['icaro_fragility']  = None
            self.regime['icaro_crash_prob'] = None
            return

        try:
            ctx = self._icaro.get_regime()

            self.regime['icaro_available']  = True
            self.regime['icaro_regime']     = ctx.get('regime_label')
            self.regime['icaro_fragility']  = ctx.get('fragility_score')
            self.regime['icaro_crash_prob'] = ctx.get('crash_probability')

            # Si ICARO detecta HIGH_VOL_STRESS y el sistema está en NEUTRAL,
            # reducir size_multiplier como capa adicional de protección.
            if (ctx.get('regime_label') == 'HIGH_VOL_STRESS' and
                    self.regime['mode'] == 'NEUTRAL'):
                self.regime['size_multiplier'] = min(
                    self.regime['size_multiplier'], 0.50
                )
                self.regime['reason'] += ' | ICARO: HIGH_VOL_STRESS detectado'

        except Exception as e:
            self.regime['icaro_available'] = False
            print(f'[MACRO] ICARO enrich error (no crítico): {e}')

    def is_active_session(self, asset: str) -> dict:
        """
        Determina si es buena hora para operar un activo dado
        Retorna info de sesión para ajustar parámetros
        """
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        hour = now.hour

        sessions = {
            'LONDON':   (7, 16),    # 7AM-4PM GMT
            'NEW_YORK': (13, 22),   # 1PM-10PM GMT
            'ASIAN':    (23, 7),    # 11PM-7AM GMT (wrap around)
            'OVERLAP':  (13, 16),   # Londres-NY overlap — máxima liquidez
        }

        # Determinar sesión activa
        in_london   = sessions['LONDON'][0]  <= hour < sessions['LONDON'][1]
        in_ny       = sessions['NEW_YORK'][0] <= hour < sessions['NEW_YORK'][1]
        in_overlap  = sessions['OVERLAP'][0] <= hour < sessions['OVERLAP'][1]
        in_asian    = hour >= 23 or hour < 7

        # Scoring de sesión por activo
        session_quality = {
            'EURUSD': 1.2 if in_overlap else (1.0 if in_london else 0.6),
            'GBPUSD': 1.2 if in_overlap else (1.0 if in_london else 0.5),
            'USDJPY': 1.2 if in_overlap else (0.9 if in_asian else 0.7),
            'SPX500': 1.3 if in_ny and not in_overlap else (0.8 if in_overlap else 0.2),
            'NAS100': 1.3 if in_ny and not in_overlap else (0.8 if in_overlap else 0.2),
            'XAUUSD': 1.1 if in_overlap else (1.0 if in_london or in_ny else 0.7),
            'USOIL':  1.2 if in_ny else (0.8 if in_london else 0.5),
        }

        quality = session_quality.get(asset, 0.7)

        return {
            'quality':    quality,
            'london':     in_london,
            'new_york':   in_ny,
            'overlap':    in_overlap,
            'asian':      in_asian,
            'tradeable':  quality >= 0.6,   # No operar en sesiones de muy baja liquidez
        }
