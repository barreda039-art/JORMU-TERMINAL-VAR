# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — CAPA 3: ZONAS INSTITUCIONALES
# Order Blocks, Fair Value Gaps, Liquidity Pools
# El corazón del sistema — donde está el dinero institucional
# ═══════════════════════════════════════════════════════════

class InstitutionalZones:

    # Parámetros por activo
    ASSET_PARAMS = {
        'EURUSD': {'impulse_atr': 1.5, 'ob_lookback': 30, 'fvg_min_pct': 0.0003},
        'GBPUSD': {'impulse_atr': 1.5, 'ob_lookback': 30, 'fvg_min_pct': 0.0004},
        'USDJPY': {'impulse_atr': 1.5, 'ob_lookback': 30, 'fvg_min_pct': 0.04},
        'SPX500': {'impulse_atr': 1.8, 'ob_lookback': 20, 'fvg_min_pct': 0.002},
        'NAS100': {'impulse_atr': 1.8, 'ob_lookback': 20, 'fvg_min_pct': 0.003},
        'XAUUSD': {'impulse_atr': 1.3, 'ob_lookback': 35, 'fvg_min_pct': 0.001},
        'USOIL':  {'impulse_atr': 2.0, 'ob_lookback': 25, 'fvg_min_pct': 0.002},
    }

    def analyze(self, candles: list, asset: str, structure_direction: str) -> dict:
        """
        Detecta zonas institucionales en las velas
        Retorna score 0-45 y zonas identificadas
        """
        if len(candles) < 20:
            return self._empty_result()

        try:
            params = self.ASSET_PARAMS.get(asset, self.ASSET_PARAMS['EURUSD'])
            atr    = self._calculate_atr(candles, 14)

            # Detectar cada tipo de zona
            order_blocks = self._detect_order_blocks(candles, atr, params, structure_direction)
            fvgs         = self._detect_fair_value_gaps(candles, params)
            liquidity    = self._detect_liquidity_pools(candles)

            # Precio actual
            current_price = candles[-1]['close']

            # Verificar si el precio está EN una zona válida
            ob_signal  = self._price_at_zone(current_price, order_blocks, atr)
            fvg_signal = self._price_at_fvg(current_price, fvgs)
            liq_signal = self._liquidity_swept(current_price, liquidity, candles[-1])

            score, direction = self._calculate_score(ob_signal, fvg_signal, liq_signal)

            return {
                'score':         score,
                'direction':     direction,
                'order_blocks':  order_blocks,
                'fvgs':          fvgs,
                'liquidity':     liquidity,
                'ob_signal':     ob_signal,
                'fvg_signal':    fvg_signal,
                'liq_signal':    liq_signal,
                'atr':           atr,
                'current_price': current_price,
            }

        except Exception as e:
            print(f'[ZONES] Error en {asset}: {e}')
            return self._empty_result()

    # ── ORDER BLOCKS ──────────────────────────────────────────
    def _detect_order_blocks(self, candles, atr, params, structure_direction) -> list:
        """
        Detecta Order Blocks válidos
        OB Bullish: última vela bajista antes de impulso alcista fuerte
        OB Bearish: última vela alcista antes de impulso bajista fuerte
        """
        obs = []
        n   = len(candles)
        lookback = min(params['ob_lookback'], n - 3)

        for i in range(2, lookback):
            idx = n - 1 - i  # Índice desde el final
            if idx < 1:
                continue

            candle     = candles[idx]
            next_move  = self._measure_impulse(candles, idx + 1, 3)

            body_size  = abs(candle['close'] - candle['open'])
            is_bearish = candle['close'] < candle['open']
            is_bullish = candle['close'] > candle['open']

            # OB Bullish — vela bajista seguida de impulso alcista fuerte
            if is_bearish and next_move > atr * params['impulse_atr']:
                # Validación de volumen (si disponible)
                avg_vol = self._avg_volume(candles, idx, 10)
                vol_confirm = candle.get('volume', avg_vol) >= avg_vol * 0.8

                if vol_confirm:
                    ob = {
                        'type':    'BULLISH',
                        'top':     max(candle['open'], candle['close']),
                        'bottom':  min(candle['open'], candle['close']),
                        'high':    candle['high'],
                        'low':     candle['low'],
                        'index':   idx,
                        'tested':  self._was_tested(candles, idx, 'BULLISH'),
                        'impulse': next_move / atr,
                        'fresh':   i <= 10,  # OB reciente = más válido
                    }
                    if not ob['tested']:  # Solo OBs no testeados
                        obs.append(ob)

            # OB Bearish — vela alcista seguida de impulso bajista fuerte
            elif is_bullish and next_move < -(atr * params['impulse_atr']):
                avg_vol = self._avg_volume(candles, idx, 10)
                vol_confirm = candle.get('volume', avg_vol) >= avg_vol * 0.8

                if vol_confirm:
                    ob = {
                        'type':    'BEARISH',
                        'top':     max(candle['open'], candle['close']),
                        'bottom':  min(candle['open'], candle['close']),
                        'high':    candle['high'],
                        'low':     candle['low'],
                        'index':   idx,
                        'tested':  self._was_tested(candles, idx, 'BEARISH'),
                        'impulse': abs(next_move) / atr,
                        'fresh':   i <= 10,
                    }
                    if not ob['tested']:
                        obs.append(ob)

        # Filtrar por alineación con estructura
        if structure_direction == 'BULLISH':
            obs = [ob for ob in obs if ob['type'] == 'BULLISH']
        elif structure_direction == 'BEARISH':
            obs = [ob for ob in obs if ob['type'] == 'BEARISH']

        # Ordenar por frescura e impulso
        obs.sort(key=lambda x: (x['fresh'], x['impulse']), reverse=True)
        return obs[:5]  # Top 5 OBs más relevantes

    def _measure_impulse(self, candles, start_idx, periods) -> float:
        """Mide el movimiento total en X velas desde un punto"""
        if start_idx >= len(candles):
            return 0
        end_idx = min(start_idx + periods, len(candles))
        if end_idx <= start_idx:
            return 0
        return candles[end_idx - 1]['close'] - candles[start_idx]['open']

    def _was_tested(self, candles, ob_idx, ob_type) -> bool:
        """Verifica si el OB ya fue testeado (precio volvió a la zona)"""
        ob_candle = candles[ob_idx]
        ob_top    = max(ob_candle['open'], ob_candle['close'])
        ob_bottom = min(ob_candle['open'], ob_candle['close'])

        for i in range(ob_idx + 3, len(candles)):
            c = candles[i]
            if ob_type == 'BULLISH':
                if c['low'] <= ob_top and c['low'] >= ob_bottom:
                    return True
            else:
                if c['high'] >= ob_bottom and c['high'] <= ob_top:
                    return True
        return False

    def _avg_volume(self, candles, idx, periods) -> float:
        start = max(0, idx - periods)
        vols  = [c.get('volume', 1) for c in candles[start:idx]]
        return sum(vols) / len(vols) if vols else 1

    # ── FAIR VALUE GAPS ───────────────────────────────────────
    def _detect_fair_value_gaps(self, candles, params) -> list:
        """
        FVG: Gap entre high de vela 1 y low de vela 3
        (o low de vela 1 y high de vela 3 para FVG bajista)
        El precio tiende a volver a llenar el gap
        """
        fvgs = []
        n    = len(candles)

        for i in range(2, min(40, n)):
            idx = n - 1 - i
            if idx < 2:
                continue

            c1, c2, c3 = candles[idx], candles[idx+1], candles[idx+2]

            # FVG Bullish — gap alcista (precio sube rápido dejando espacio)
            if c1['high'] < c3['low']:
                gap_size = c3['low'] - c1['high']
                mid_price = (c1['high'] + c3['low']) / 2
                if gap_size >= mid_price * params['fvg_min_pct']:
                    filled = self._fvg_filled(candles, idx + 3, c1['high'], c3['low'], 'BULLISH')
                    if not filled:
                        fvgs.append({
                            'type':   'BULLISH',
                            'top':    c3['low'],
                            'bottom': c1['high'],
                            'size':   gap_size,
                            'index':  idx,
                            'filled': False,
                            'fresh':  i <= 15,
                        })

            # FVG Bearish — gap bajista
            elif c1['low'] > c3['high']:
                gap_size = c1['low'] - c3['high']
                mid_price = (c1['low'] + c3['high']) / 2
                if gap_size >= mid_price * params['fvg_min_pct']:
                    filled = self._fvg_filled(candles, idx + 3, c3['high'], c1['low'], 'BEARISH')
                    if not filled:
                        fvgs.append({
                            'type':   'BEARISH',
                            'top':    c1['low'],
                            'bottom': c3['high'],
                            'size':   gap_size,
                            'index':  idx,
                            'filled': False,
                            'fresh':  i <= 15,
                        })

        fvgs.sort(key=lambda x: x['fresh'], reverse=True)
        return fvgs[:5]

    def _fvg_filled(self, candles, start_idx, bottom, top, fvg_type) -> bool:
        """Verifica si el FVG ya fue llenado"""
        for i in range(start_idx, len(candles)):
            c = candles[i]
            if fvg_type == 'BULLISH' and c['low'] <= bottom:
                return True
            if fvg_type == 'BEARISH' and c['high'] >= top:
                return True
        return False

    # ── LIQUIDITY POOLS ───────────────────────────────────────
    def _detect_liquidity_pools(self, candles) -> dict:
        """
        Detecta dónde están los stops del retail
        Encima de máximos recientes = stops de shorts (buy stops)
        Debajo de mínimos recientes = stops de longs (sell stops)
        """
        n = len(candles)
        if n < 20:
            return {}

        # Máximos y mínimos significativos de diferentes períodos
        high_5  = max(c['high'] for c in candles[-5:])
        high_20 = max(c['high'] for c in candles[-20:])
        low_5   = min(c['low']  for c in candles[-5:])
        low_20  = min(c['low']  for c in candles[-20:])

        current = candles[-1]['close']
        last    = candles[-1]

        # ¿La liquidez ya fue cazada? (sweep)
        buy_stop_swept  = last['high'] > high_5  and last['close'] < high_5   # Wicked above, closed below
        sell_stop_swept = last['low']  < low_5   and last['close'] > low_5    # Wicked below, closed above

        return {
            'buy_stops': {
                'near':  high_5,
                'far':   high_20,
                'swept': buy_stop_swept,
                'distance_near': abs(current - high_5) / current * 100,
            },
            'sell_stops': {
                'near':  low_5,
                'far':   low_20,
                'swept': sell_stop_swept,
                'distance_near': abs(current - low_5) / current * 100,
            },
        }

    # ── VERIFICAR SI PRECIO ESTÁ EN ZONA ─────────────────────
    def _price_at_zone(self, price, order_blocks, atr) -> dict:
        """Verifica si el precio actual está dentro de un OB válido"""
        for ob in order_blocks:
            tolerance = atr * 0.3
            if ob['bottom'] - tolerance <= price <= ob['top'] + tolerance:
                return {
                    'active':    True,
                    'type':      ob['type'],
                    'ob':        ob,
                    'strength':  ob['impulse'],
                    'fresh':     ob['fresh'],
                }
        return {'active': False}

    def _price_at_fvg(self, price, fvgs) -> dict:
        """Verifica si el precio está llenando un FVG"""
        for fvg in fvgs:
            if fvg['bottom'] <= price <= fvg['top']:
                return {
                    'active': True,
                    'type':   fvg['type'],
                    'fvg':    fvg,
                    'fresh':  fvg['fresh'],
                }
        return {'active': False}

    def _liquidity_swept(self, price, liquidity, last_candle) -> dict:
        """Verifica si la liquidez fue recientemente cazada — señal fuerte"""
        if not liquidity:
            return {'swept': False}

        buy_swept  = liquidity['buy_stops']['swept']
        sell_swept = liquidity['sell_stops']['swept']

        if buy_swept:
            return {'swept': True, 'direction': 'BEARISH', 'level': liquidity['buy_stops']['near']}
        elif sell_swept:
            return {'swept': True, 'direction': 'BULLISH', 'level': liquidity['sell_stops']['near']}

        return {'swept': False}

    # ── SCORE ─────────────────────────────────────────────────
    def _calculate_score(self, ob_signal, fvg_signal, liq_signal) -> tuple:
        """Calcula score 0-45 para esta capa"""
        score      = 0
        directions = []

        # Order Block activo (0-20 puntos)
        if ob_signal.get('active'):
            base = 15
            if ob_signal.get('fresh'):    base += 3
            if ob_signal.get('strength', 0) > 2.0: base += 2
            score += min(base, 20)
            directions.append(ob_signal['type'])

        # FVG activo (0-15 puntos)
        if fvg_signal.get('active'):
            base = 10
            if fvg_signal.get('fresh'): base += 5
            score += min(base, 15)
            directions.append(fvg_signal['type'])

        # Liquidez cazada (0-10 puntos) — señal muy fuerte
        if liq_signal.get('swept'):
            score += 10
            directions.append(liq_signal['direction'])

        # Dirección dominante
        bull = directions.count('BULLISH')
        bear = directions.count('BEARISH')
        direction = 'BULLISH' if bull > bear else ('BEARISH' if bear > bull else 'NEUTRAL')

        return min(score, 45), direction

    # ── ATR ───────────────────────────────────────────────────
    def _calculate_atr(self, candles, period=14) -> float:
        """Average True Range — medida de volatilidad"""
        if len(candles) < period + 1:
            if candles:
                return (candles[-1]['high'] - candles[-1]['low'])
            return 0.001

        trs = []
        for i in range(1, len(candles)):
            high  = candles[i]['high']
            low   = candles[i]['low']
            prev  = candles[i-1]['close']
            tr    = max(high - low, abs(high - prev), abs(low - prev))
            trs.append(tr)

        return sum(trs[-period:]) / period

    def _empty_result(self):
        return {
            'score': 0, 'direction': 'NEUTRAL',
            'order_blocks': [], 'fvgs': [], 'liquidity': {},
            'ob_signal': {'active': False},
            'fvg_signal': {'active': False},
            'liq_signal': {'swept': False},
            'atr': 0, 'current_price': 0,
        }
