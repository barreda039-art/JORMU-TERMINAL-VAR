# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — RISK MANAGER
# Sizing institucional + validación pre-ejecución
# ═══════════════════════════════════════════════════════════

from icaro_bridge import icaro_bridge


class RiskManager:

    # Umbrales de score mínimo por activo
    MIN_SCORE = {
        'EURUSD': 62, 'GBPUSD': 65, 'USDJPY': 68,
        'SPX500': 70, 'NAS100': 70,
        'XAUUSD': 60, 'USOIL': 75,
    }

    # Tamaño mínimo de posición por activo en Capital.com
    MIN_SIZE = {
        'EURUSD': 1000, 'GBPUSD': 1000, 'USDJPY': 1000,
        'SPX500': 0.1,  'NAS100': 0.1,
        'XAUUSD': 0.1,  'USOIL': 0.1,
    }

    def __init__(self, capital_client, config: dict = None):
        self.client = capital_client
        self.config = config or {
            'risk_per_trade':    1.0,    # % del NAV por trade
            'max_positions':     10,
            'max_drawdown':      10.0,   # % máximo
            'max_daily_loss':    3.0,    # % pérdida diaria máxima
            'max_exposure':      80.0,   # % exposición máxima
            'max_single_pos':    5.0,    # % máximo por posición
            'circuit_breaker':   False,
            'icaro_reserve_pct': 20.0,   # % del NAV reservado para ICARO (configurable)
        }
        self.daily_pnl    = 0
        self.peak_nav     = 0

    def validate(self, signal: dict, nav: float, open_positions: list) -> dict:
        """
        Validación completa pre-ejecución
        Retorna {'approved': True/False, 'reason': '...', 'size': N}
        """
        asset = signal['asset']
        score = signal['total_score']

        # 0. ICARO Killswitch — gate de máxima prioridad
        if icaro_bridge.is_killswitch_active():
            return self._reject('ICARO Killswitch global activo — trading suspendido')

        # Calcular NAV disponible para estrategias generales (excluyendo reserva ICARO)
        icaro_reserve  = nav * (self.config['icaro_reserve_pct'] / 100)
        available_nav  = nav - icaro_reserve

        # Informar al bridge cuánto capital tiene ICARO
        icaro_bridge.update_capital(nav, self.config['icaro_reserve_pct'])

        # 1. Circuit breaker
        if self.config['circuit_breaker']:
            return self._reject('Circuit breaker activo — trading suspendido')

        # 2. Score mínimo por activo
        min_score = self.MIN_SCORE.get(asset, 65)
        if score < min_score:
            return self._reject(f'Score {score} < mínimo {min_score} para {asset}')

        # 3. Límite de posiciones
        if len(open_positions) >= self.config['max_positions']:
            return self._reject(f'Posiciones máximas alcanzadas ({self.config["max_positions"]})')

        # 4. No duplicar posición en mismo activo
        same_asset = [p for p in open_positions if p.get('epic') == asset or p.get('symbol') == asset]
        if same_asset:
            return self._reject(f'Ya existe posición abierta en {asset}')

        # 5. Drawdown máximo
        if self.peak_nav > 0:
            current_dd = ((nav - self.peak_nav) / self.peak_nav) * 100
            if current_dd <= -self.config['max_drawdown']:
                self.config['circuit_breaker'] = True
                return self._reject(f'Drawdown máximo alcanzado ({current_dd:.1f}%) — Circuit breaker activado')

        # 6. Pérdida diaria
        daily_pnl_pct = (self.daily_pnl / nav * 100) if nav > 0 else 0
        if daily_pnl_pct <= -self.config['max_daily_loss']:
            return self._reject(f'Pérdida diaria máxima alcanzada ({daily_pnl_pct:.1f}%)')

        # 7. Calcular sizing
        size = self._calculate_size(signal, nav, asset)
        if size is None:
            return self._reject('No se pudo calcular el tamaño de posición')

        return {
            'approved': True,
            'reason':   f'Validado — Score: {score} | Size: {size}',
            'size':     size,
            'risk_usd': round(nav * self.config['risk_per_trade'] / 100, 2),
        }

    def _calculate_size(self, signal, nav, asset) -> float:
        """
        Volatility-based position sizing
        Riesgo = 1% del NAV
        Size = Riesgo / (ATR × multiplicador SL)
        """
        try:
            risk_usd    = nav * (self.config['risk_per_trade'] / 100)
            atr         = signal.get('atr', 0)
            sl_distance = signal.get('sl_distance', atr * 1.5)

            if atr == 0 or sl_distance == 0:
                # Fallback: usar mínimo permitido
                return self.MIN_SIZE.get(asset, 0.1)

            # Ajuste por régimen macro
            size_mult = signal.get('size_multiplier', 1.0)
            risk_usd  = risk_usd * size_mult

            # Size basado en riesgo
            raw_size = risk_usd / sl_distance

            # Aplicar límites
            min_size = self.MIN_SIZE.get(asset, 0.1)
            max_size = (nav * self.config['max_single_pos'] / 100) / signal.get('entry_price', 1)

            size = max(min_size, min(raw_size, max_size))

            # Redondear según el activo
            if asset in ['EURUSD', 'GBPUSD', 'USDJPY']:
                size = round(size / 1000) * 1000  # Lotes de 1000
                size = max(size, 1000)
            else:
                size = round(size, 1)
                size = max(size, 0.1)

            return size

        except Exception as e:
            print(f'[RISK] Error calculando size: {e}')
            return None

    def update_daily_pnl(self, pnl_change: float):
        self.daily_pnl += pnl_change

    def reset_daily(self):
        self.daily_pnl = 0

    def update_peak_nav(self, nav: float):
        if nav > self.peak_nav:
            self.peak_nav = nav

    def set_icaro_reserve(self, reserve_pct: float):
        """Actualiza el % de reserva de ICARO — llamado desde el terminal."""
        self.config['icaro_reserve_pct'] = max(0.0, min(reserve_pct, 80.0))
        icaro_bridge.update_reserve_pct(self.config['icaro_reserve_pct'])
        print(f'[RISK] Reserva ICARO actualizada: {self.config["icaro_reserve_pct"]}%')

    def get_icaro_capital(self, nav: float) -> float:
        """Retorna el capital reservado para ICARO dado el NAV actual."""
        return round(nav * self.config['icaro_reserve_pct'] / 100, 2)

    def _reject(self, reason: str) -> dict:
        print(f'[RISK] Rechazado: {reason}')
        return {'approved': False, 'reason': reason, 'size': 0}

    def get_status(self) -> dict:
        return {
            'circuit_breaker':   self.config['circuit_breaker'],
            'daily_pnl':         self.daily_pnl,
            'peak_nav':          self.peak_nav,
            'config':            self.config,
            'icaro_reserve_pct': self.config.get('icaro_reserve_pct', 20.0),
            'icaro_killswitch':  icaro_bridge.is_killswitch_active(),
        }
