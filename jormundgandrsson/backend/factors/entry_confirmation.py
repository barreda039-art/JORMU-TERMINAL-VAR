# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — CAPA 4: CONFIRMACIÓN DE ENTRADA
# Rechazo de precio, volumen, spread — el timing exacto
# ═══════════════════════════════════════════════════════════

class EntryConfirmation:

    # Spreads máximos permitidos por activo (en % del precio)
    MAX_SPREAD_PCT = {
        'EURUSD': 0.0002,   # 2 pips
        'GBPUSD': 0.0003,   # 3 pips
        'USDJPY': 0.025,    # 2.5 pips
        'SPX500': 0.05,     # 5 puntos %
        'NAS100': 0.08,     # 8 puntos %
        'XAUUSD': 0.003,    # 30 cents %
        'USOIL':  0.04,     # 4 cents %
    }

    def analyze(self, candles: list, asset: str, live_price: dict, direction: str) -> dict:
        """
        Confirma si hay una entrada válida en el precio actual
        Retorna score 0-30 y señal de entrada
        """
        if len(candles) < 5 or not live_price:
            return self._empty_result()

        try:
            atr = self._calculate_atr(candles, 14)

            rejection    = self._detect_rejection_candle(candles[-1], direction, atr)
            volume_conf  = self._confirm_volume(candles)
            spread_ok    = self._check_spread(live_price, asset)
            momentum_ok  = self._confirm_momentum(candles, direction)

            score, signal = self._calculate_score(rejection, volume_conf, spread_ok, momentum_ok, direction)

            # Calcular niveles de SL y TP
            sl, tp = self._calculate_levels(candles, live_price, direction, atr, asset)

            return {
                'score':       score,
                'signal':      signal,      # ENTER | WAIT | SKIP
                'direction':   direction,
                'rejection':   rejection,
                'volume_conf': volume_conf,
                'spread_ok':   spread_ok,
                'momentum_ok': momentum_ok,
                'entry_price': live_price.get('ask') if direction == 'BULLISH' else live_price.get('bid'),
                'sl':          sl,
                'tp':          tp,
                'atr':         atr,
                'rr':          round(abs((tp - live_price.get('mid', 0)) / (live_price.get('mid', 1) - sl)), 2) if sl and tp else 0,
            }

        except Exception as e:
            print(f'[ENTRY] Error en {asset}: {e}')
            return self._empty_result()

    def _detect_rejection_candle(self, candle, direction, atr) -> dict:
        """
        Detecta vela de rechazo (pin bar / engulfing)
        en la dirección correcta
        """
        if not candle or atr == 0:
            return {'detected': False, 'strength': 0}

        body     = abs(candle['close'] - candle['open'])
        total    = candle['high'] - candle['low']
        upper_w  = candle['high']  - max(candle['open'], candle['close'])
        lower_w  = min(candle['open'], candle['close']) - candle['low']
        is_bull  = candle['close'] > candle['open']

        if total == 0:
            return {'detected': False, 'strength': 0}

        body_ratio  = body / total
        wick_ratio  = (upper_w if direction == 'BEARISH' else lower_w) / total

        # Pin bar — mecha larga en dirección contraria, cuerpo pequeño
        is_pin = wick_ratio > 0.55 and body_ratio < 0.35

        # Engulfing — vela grande que "engulle" a la anterior
        is_engulfing = body > atr * 0.6 and (
            (direction == 'BULLISH' and is_bull) or
            (direction == 'BEARISH' and not is_bull)
        )

        # Vela de momentum — cierre fuerte en dirección
        strong_close = (
            (direction == 'BULLISH' and candle['close'] > (candle['high'] + candle['low']) / 2 * 1.002) or
            (direction == 'BEARISH' and candle['close'] < (candle['high'] + candle['low']) / 2 * 0.998)
        )

        detected = is_pin or is_engulfing or strong_close
        strength = 0
        if is_pin:       strength += 3
        if is_engulfing: strength += 3
        if strong_close: strength += 2

        return {
            'detected':    detected,
            'strength':    strength,
            'is_pin':      is_pin,
            'is_engulfing':is_engulfing,
            'strong_close':strong_close,
        }

    def _confirm_volume(self, candles) -> dict:
        """Volumen de la última vela vs promedio"""
        if len(candles) < 10:
            return {'confirmed': True, 'ratio': 1.0}

        vols = [c.get('volume', 0) for c in candles[-11:-1]]
        avg  = sum(vols) / len(vols) if vols else 1
        current_vol = candles[-1].get('volume', avg)

        ratio = current_vol / avg if avg > 0 else 1.0

        return {
            'confirmed': ratio >= 0.8,   # Al menos 80% del volumen promedio
            'ratio':     round(ratio, 2),
            'above_avg': ratio > 1.2,
        }

    def _check_spread(self, live_price, asset) -> dict:
        """Verifica que el spread sea opereable"""
        bid = live_price.get('bid', 0)
        ask = live_price.get('ask', 0)
        mid = live_price.get('mid', 1)

        if bid == 0 or ask == 0 or mid == 0:
            return {'ok': True, 'spread_pct': 0}

        spread     = ask - bid
        spread_pct = spread / mid
        max_spread = self.MAX_SPREAD_PCT.get(asset, 0.001)

        return {
            'ok':         spread_pct <= max_spread * 2,
            'spread_pct': round(spread_pct * 100, 4),
            'spread_raw': round(spread, 5),
            'normal':     spread_pct <= max_spread,
        }

    def _confirm_momentum(self, candles, direction) -> dict:
        """Momentum de corto plazo alineado con la dirección"""
        if len(candles) < 6:
            return {'confirmed': True}

        # Las últimas 3 velas deben mostrar momentum
        last3 = candles[-3:]
        bull_candles = sum(1 for c in last3 if c['close'] > c['open'])
        bear_candles = sum(1 for c in last3 if c['close'] < c['open'])

        if direction == 'BULLISH':
            confirmed = bull_candles >= 2
        else:
            confirmed = bear_candles >= 2

        return {
            'confirmed':   confirmed,
            'bull_count':  bull_candles,
            'bear_count':  bear_candles,
        }

    def _calculate_levels(self, candles, live_price, direction, atr, asset) -> tuple:
        """
        Calcula SL y TP basados en estructura + ATR
        SL: debajo/encima del OB con margen ATR
        TP: próximo pool de liquidez
        """
        atr_mult = {
            'EURUSD': 1.5, 'GBPUSD': 1.8, 'USDJPY': 1.5,
            'SPX500': 1.2, 'NAS100': 1.2,
            'XAUUSD': 2.0, 'USOIL': 2.5,
        }.get(asset, 1.5)

        tp_mult = atr_mult * 2.0  # R:R mínimo 2:1

        price = live_price.get('mid', candles[-1]['close'])

        if direction == 'BULLISH':
            sl = round(price - (atr * atr_mult), 5)
            tp = round(price + (atr * tp_mult), 5)
        else:
            sl = round(price + (atr * atr_mult), 5)
            tp = round(price - (atr * tp_mult), 5)

        return sl, tp

    def _calculate_score(self, rejection, volume_conf, spread_ok, momentum_ok, direction) -> tuple:
        """Score 0-30 para esta capa"""
        score = 0

        # Vela de rechazo (0-15 puntos)
        if rejection['detected']:
            score += 8 + rejection.get('strength', 0)

        # Volumen confirmado (0-10 puntos)
        if volume_conf['confirmed']:
            score += 6
        if volume_conf.get('above_avg'):
            score += 4

        # Spread opereable (0-5 puntos)
        if spread_ok['ok']:
            score += 3
        if spread_ok.get('normal'):
            score += 2

        # Momentum alineado (0-5 puntos)
        if momentum_ok['confirmed']:
            score += 5

        score = min(score, 30)

        # Señal final
        if score >= 20 and rejection['detected'] and spread_ok['ok']:
            signal = 'ENTER'
        elif score >= 12:
            signal = 'WAIT'
        else:
            signal = 'SKIP'

        return score, signal

    def _calculate_atr(self, candles, period=14) -> float:
        if len(candles) < 2:
            return 0.001
        trs = []
        for i in range(1, len(candles)):
            tr = max(
                candles[i]['high'] - candles[i]['low'],
                abs(candles[i]['high'] - candles[i-1]['close']),
                abs(candles[i]['low']  - candles[i-1]['close']),
            )
            trs.append(tr)
        return sum(trs[-period:]) / min(period, len(trs))

    def _empty_result(self):
        return {
            'score': 0, 'signal': 'SKIP', 'direction': 'NEUTRAL',
            'rejection': {'detected': False}, 'volume_conf': {'confirmed': False},
            'spread_ok': {'ok': False}, 'momentum_ok': {'confirmed': False},
            'entry_price': None, 'sl': None, 'tp': None, 'atr': 0, 'rr': 0,
        }
