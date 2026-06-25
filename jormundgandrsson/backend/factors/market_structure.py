# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — CAPA 2: ESTRUCTURA DE MERCADO
# HH/HL, LH/LL, tendencia, rangos — análisis de estructura pura
# ═══════════════════════════════════════════════════════════

class MarketStructure:

    def analyze(self, candles: list, asset: str) -> dict:
        """
        Analiza la estructura de mercado de un activo
        candles: lista de velas OHLCV [{open, high, low, close, volume}]
        Retorna score 0-25 y dirección estructural
        """
        if len(candles) < 20:
            return self._empty_result()

        try:
            highs  = [c['high']  for c in candles]
            lows   = [c['low']   for c in candles]
            closes = [c['close'] for c in candles]

            structure = self._identify_structure(highs, lows)
            trend     = self._identify_trend(closes)
            bos       = self._detect_break_of_structure(highs, lows, closes)
            choch     = self._detect_change_of_character(highs, lows, closes)

            score, direction = self._calculate_score(structure, trend, bos, choch)

            return {
                'score':     score,
                'direction': direction,   # BULLISH | BEARISH | NEUTRAL
                'structure': structure,   # HH_HL | LH_LL | RANGING
                'trend':     trend,
                'bos':       bos,         # Break of Structure detectado
                'choch':     choch,       # Change of Character detectado
                'details':   {
                    'last_high': highs[-1],
                    'last_low':  lows[-1],
                    'swing_high': max(highs[-10:]),
                    'swing_low':  min(lows[-10:]),
                }
            }

        except Exception as e:
            print(f'[STRUCTURE] Error en {asset}: {e}')
            return self._empty_result()

    def _identify_structure(self, highs: list, lows: list) -> str:
        """
        Identifica si el mercado está haciendo:
        HH_HL = Higher Highs + Higher Lows = tendencia alcista
        LH_LL = Lower Highs + Lower Lows = tendencia bajista
        RANGING = Sin estructura clara
        """
        # Tomamos los últimos 3 swing points
        n = len(highs)
        if n < 10:
            return 'RANGING'

        # Swing highs — máximos locales
        swing_highs = []
        swing_lows  = []

        for i in range(2, n - 2):
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                swing_highs.append(highs[i])
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                swing_lows.append(lows[i])

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            return 'RANGING'

        # Comparar últimos 2 swing highs y lows
        hh = swing_highs[-1] > swing_highs[-2]   # Higher High
        hl = swing_lows[-1]  > swing_lows[-2]    # Higher Low
        lh = swing_highs[-1] < swing_highs[-2]   # Lower High
        ll = swing_lows[-1]  < swing_lows[-2]    # Lower Low

        if hh and hl:
            return 'HH_HL'    # Estructura alcista
        elif lh and ll:
            return 'LH_LL'    # Estructura bajista
        else:
            return 'RANGING'  # Sin estructura clara

    def _identify_trend(self, closes: list) -> str:
        """Tendencia basada en medias simples de precio puro"""
        if len(closes) < 20:
            return 'NEUTRAL'

        # Media rápida vs lenta
        fast = sum(closes[-8:]) / 8
        slow = sum(closes[-20:]) / 20
        current = closes[-1]

        if fast > slow and current > fast:
            return 'BULLISH'
        elif fast < slow and current < fast:
            return 'BEARISH'
        else:
            return 'NEUTRAL'

    def _detect_break_of_structure(self, highs, lows, closes) -> dict:
        """
        BOS — Break of Structure
        Precio rompe un swing high/low previo con cierre confirmado
        Señal de continuación de tendencia
        """
        if len(closes) < 10:
            return {'detected': False, 'direction': None}

        recent_high = max(highs[-10:-1])
        recent_low  = min(lows[-10:-1])
        current_close = closes[-1]

        if current_close > recent_high:
            return {'detected': True, 'direction': 'BULLISH', 'level': recent_high}
        elif current_close < recent_low:
            return {'detected': True, 'direction': 'BEARISH', 'level': recent_low}

        return {'detected': False, 'direction': None, 'level': None}

    def _detect_change_of_character(self, highs, lows, closes) -> dict:
        """
        CHoCH — Change of Character
        Primer señal de reversión de tendencia
        En tendencia alcista: precio rompe debajo del último HL
        En tendencia bajista: precio rompe encima del último LH
        """
        if len(closes) < 15:
            return {'detected': False, 'direction': None}

        # Simplificado: cambio de carácter cuando precio cruza media intermedia
        mid_term = sum(closes[-12:]) / 12
        short_term = sum(closes[-4:]) / 4
        prev_short = sum(closes[-8:-4]) / 4

        # Cruce bajista de corto vs medio = posible CHoCH bajista
        if prev_short > mid_term and short_term < mid_term:
            return {'detected': True, 'direction': 'BEARISH'}
        # Cruce alcista
        elif prev_short < mid_term and short_term > mid_term:
            return {'detected': True, 'direction': 'BULLISH'}

        return {'detected': False, 'direction': None}

    def _calculate_score(self, structure, trend, bos, choch) -> tuple:
        """Calcula score 0-25 y dirección para esta capa"""
        score = 0
        directions = []

        # Estructura de mercado (0-10 puntos)
        if structure == 'HH_HL':
            score += 10
            directions.append('BULLISH')
        elif structure == 'LH_LL':
            score += 10
            directions.append('BEARISH')
        else:
            score += 3   # Rango — señal débil

        # Tendencia confirmada (0-8 puntos)
        if trend == 'BULLISH':
            score += 8
            directions.append('BULLISH')
        elif trend == 'BEARISH':
            score += 8
            directions.append('BEARISH')
        else:
            score += 2

        # BOS detectado (0-5 puntos)
        if bos['detected']:
            score += 5
            directions.append(bos['direction'])

        # CHoCH detectado — señal de reversión (0-2 puntos extra)
        if choch['detected']:
            score += 2
            directions.append(choch['direction'])

        # Dirección dominante
        if directions.count('BULLISH') > directions.count('BEARISH'):
            direction = 'BULLISH'
        elif directions.count('BEARISH') > directions.count('BULLISH'):
            direction = 'BEARISH'
        else:
            direction = 'NEUTRAL'

        return min(score, 25), direction

    def _empty_result(self):
        return {
            'score': 0, 'direction': 'NEUTRAL',
            'structure': 'UNKNOWN', 'trend': 'NEUTRAL',
            'bos': {'detected': False}, 'choch': {'detected': False},
            'details': {}
        }
