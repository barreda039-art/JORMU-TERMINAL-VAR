# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — Capital.com API Client v5
# Fix: parser OHLCV usa bid/ask en vez de mid
# ═══════════════════════════════════════════════════════════

import os, json, time, threading
import requests, websocket
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

import urllib3
urllib3.disable_warnings()

class CapitalClient:

    def __init__(self):
        env = os.getenv('CAPITAL_ENV', 'demo')
        if env == 'live':
            self.base_url = 'https://api-capital.backend-capital.com/api/v1'
            self.ws_url   = 'wss://api-streaming-capital.backend-capital.com/connect'
        else:
            self.base_url = 'https://demo-api-capital.backend-capital.com/api/v1'
            self.ws_url   = 'wss://api-streaming-capital.backend-capital.com/connect'

        self.api_key    = os.getenv('CAPITAL_API_KEY',      '2ckU7cepBbJ0OV2b')
        self.password   = os.getenv('CAPITAL_API_PASSWORD', 'Lomito1945***')
        self.identifier = os.getenv('CAPITAL_IDENTIFIER',   'rolls.artesanal@gmail.com')
        self.env        = env

        self.cst         = None
        self.x_security  = None
        self.session_exp = 0

        self.ws         = None
        self.ws_thread  = None
        self.ws_active  = False
        self.prices     = {}
        self.on_price_update = None
        self.connected  = False

        self.session = requests.Session()
        self.session.verify = False

    def _mid(self, price_dict):
        """Calcula mid price desde bid/ask de Capital.com"""
        if not price_dict:
            return None
        bid = price_dict.get('bid', 0) or 0
        ask = price_dict.get('ask') or price_dict.get('offer') or 0
        if bid and ask:
            return round((bid + ask) / 2, 6)
        return bid or ask or None

    def create_session(self):
        url = f'{self.base_url}/session'
        headers = {
            'X-CAP-API-KEY': self.api_key,
            'Content-Type':  'application/json',
        }
        payload = {
            'identifier':        self.identifier,
            'password':          self.password,
            'encryptedPassword': False,
        }
        try:
            r = self.session.post(url, headers=headers, json=payload, timeout=15)
            if r.status_code == 200:
                self.cst         = r.headers.get('CST')
                self.x_security  = r.headers.get('X-SECURITY-TOKEN')
                self.session_exp = time.time() + 600
                self.connected   = True
                print(f'[CAPITAL] Sesión creada — ENV: {self.env.upper()}')
                return {'ok': True, 'env': self.env}
            else:
                print(f'[CAPITAL] Error {r.status_code}: {r.text}')
                return {'ok': False, 'error': r.text, 'status': r.status_code}
        except Exception as e:
            print(f'[CAPITAL] Excepción: {e}')
            return {'ok': False, 'error': str(e)}

    def _refresh_if_needed(self):
        if time.time() > self.session_exp - 60:
            self.create_session()

    def _headers(self):
        return {
            'X-CAP-API-KEY':    self.api_key,
            'CST':              self.cst or '',
            'X-SECURITY-TOKEN': self.x_security or '',
            'Content-Type':     'application/json',
        }

    def get_account_info(self):
        self._refresh_if_needed()
        try:
            r = self.session.get(f'{self.base_url}/accounts', headers=self._headers(), timeout=10)
            return {'ok': True, 'data': r.json()} if r.status_code == 200 else {'ok': False, 'error': r.text}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def get_account_balance(self):
        info = self.get_account_info()
        if not info['ok']:
            return info
        accounts = info['data'].get('accounts', [])
        if accounts:
            acc     = accounts[0]
            balance = acc.get('balance', {})
            return {
                'ok':          True,
                'balance':     balance.get('balance', 0),
                'available':   balance.get('available', 0),
                'profit':      balance.get('profitLoss', 0),
                'deposit':     balance.get('deposit', 0),
                'currency':    acc.get('preferred', 'USD'),
                'accountId':   acc.get('accountId', ''),
                'accountName': acc.get('accountName', ''),
            }
        return {'ok': False, 'error': 'No accounts found'}

    def get_markets(self, search_term=''):
        self._refresh_if_needed()
        try:
            params = {'searchTerm': search_term} if search_term else {}
            r = self.session.get(f'{self.base_url}/markets', headers=self._headers(), params=params, timeout=10)
            return {'ok': True, 'data': r.json()} if r.status_code == 200 else {'ok': False, 'error': r.text}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def get_price(self, epic):
        self._refresh_if_needed()
        try:
            r = self.session.get(f'{self.base_url}/markets/{epic}', headers=self._headers(), timeout=10)
            if r.status_code == 200:
                data = r.json()
                snap = data.get('snapshot', {})
                bid  = snap.get('bid', 0)
                ask  = snap.get('offer', 0)
                return {
                    'ok':    True,
                    'epic':  epic,
                    'bid':   bid,
                    'ask':   ask,
                    'mid':   round((bid + ask) / 2, 6) if bid and ask else bid or ask,
                    'high':  snap.get('high'),
                    'low':   snap.get('low'),
                    'change':snap.get('percentageChange'),
                    'status':snap.get('marketStatus'),
                }
            return {'ok': False, 'error': r.text}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def get_prices_history(self, epic, resolution='HOUR', max_points=100):
        """
        Obtiene velas históricas OHLCV
        Capital.com devuelve bid/ask por separado — calculamos mid
        """
        self._refresh_if_needed()
        try:
            r = self.session.get(
                f'{self.base_url}/prices/{epic}',
                headers=self._headers(),
                params={'resolution': resolution, 'max': max_points},
                timeout=20
            )
            if r.status_code == 200:
                candles = []
                for p in r.json().get('prices', []):
                    open_  = self._mid(p.get('openPrice',  {}))
                    high_  = self._mid(p.get('highPrice',  {}))
                    low_   = self._mid(p.get('lowPrice',   {}))
                    close_ = self._mid(p.get('closePrice', {}))

                    # Solo incluir velas con datos completos
                    if all([open_, high_, low_, close_]):
                        candles.append({
                            'time':   p.get('snapshotTime'),
                            'open':   open_,
                            'high':   high_,
                            'low':    low_,
                            'close':  close_,
                            'volume': p.get('lastTradedVolume', 0),
                        })

                print(f'[CAPITAL] {epic} {resolution}: {len(candles)} velas OK')
                return {'ok': True, 'epic': epic, 'candles': candles}
            return {'ok': False, 'error': r.text}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def get_positions(self):
        self._refresh_if_needed()
        try:
            r = self.session.get(f'{self.base_url}/positions', headers=self._headers(), timeout=10)
            if r.status_code == 200:
                positions = []
                for p in r.json().get('positions', []):
                    pos    = p.get('position', {})
                    market = p.get('market', {})
                    positions.append({
                        'dealId':    pos.get('dealId'),
                        'epic':      market.get('epic'),
                        'name':      market.get('instrumentName'),
                        'direction': pos.get('direction'),
                        'size':      pos.get('size'),
                        'level':     pos.get('level'),
                        'bid':       market.get('bid'),
                        'ask':       market.get('offer'),
                        'pnl':       pos.get('upl'),
                        'stopLevel': pos.get('stopLevel'),
                        'limitLevel':pos.get('limitLevel'),
                        'currency':  pos.get('currency'),
                        'createdAt': pos.get('createdDateUTC'),
                    })
                return {'ok': True, 'positions': positions}
            return {'ok': False, 'error': r.text}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def open_position(self, epic, direction, size, stop_distance=None, limit_distance=None):
        self._refresh_if_needed()
        payload = {
            'epic': epic, 'direction': direction, 'size': size,
            'guaranteedStop': False, 'trailingStop': False,
        }
        if stop_distance:  payload['stopDistance']  = stop_distance
        if limit_distance: payload['limitDistance'] = limit_distance
        try:
            r = self.session.post(f'{self.base_url}/positions', headers=self._headers(), json=payload, timeout=10)
            return {'ok': True, 'dealReference': r.json().get('dealReference')} if r.status_code == 200 else {'ok': False, 'error': r.text}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def close_position(self, deal_id, direction, size):
        self._refresh_if_needed()
        try:
            r = self.session.delete(
                f'{self.base_url}/positions/{deal_id}',
                headers=self._headers(),
                json={'direction': direction, 'size': size}, timeout=10
            )
            return {'ok': True, 'data': r.json()} if r.status_code == 200 else {'ok': False, 'error': r.text}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def update_position(self, deal_id, stop_level=None, limit_level=None):
        self._refresh_if_needed()
        payload = {}
        if stop_level:  payload['stopLevel']  = stop_level
        if limit_level: payload['limitLevel'] = limit_level
        try:
            r = self.session.put(f'{self.base_url}/positions/{deal_id}', headers=self._headers(), json=payload, timeout=10)
            return {'ok': True} if r.status_code == 200 else {'ok': False, 'error': r.text}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def get_deal_confirmation(self, deal_reference):
        self._refresh_if_needed()
        try:
            r = self.session.get(f'{self.base_url}/confirms/{deal_reference}', headers=self._headers(), timeout=10)
            return {'ok': True, 'data': r.json()} if r.status_code == 200 else {'ok': False, 'error': r.text}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def start_streaming(self, epics: list):
        if self.ws_active:
            self.stop_streaming()

        def on_open(ws):
            print(f'[WS] Conectado — suscribiendo a {len(epics)} instrumentos')
            ws.send(json.dumps({
                'destination': 'marketData.subscribe',
                'correlationId': '1',
                'cst': self.cst,
                'securityToken': self.x_security,
                'payload': {'epics': epics}
            }))

        def on_message(ws, message):
            try:
                data    = json.loads(message)
                payload = data.get('payload', {})
                epic    = payload.get('epic', '')
                bid     = payload.get('bid')
                ask     = payload.get('ofr') or payload.get('ask')
                if epic and bid:
                    self.prices[epic] = {
                        'epic': epic, 'bid': bid, 'ask': ask,
                        'mid': round((bid + (ask or bid)) / 2, 6),
                        'time': datetime.utcnow().isoformat(),
                    }
                    if self.on_price_update:
                        self.on_price_update(epic, self.prices[epic])
            except Exception as e:
                print(f'[WS] Error: {e}')

        def on_error(ws, error): print(f'[WS] Error: {error}')
        def on_close(ws, c, m):
            self.ws_active = False
            print('[WS] Cerrado')

        self.ws = websocket.WebSocketApp(
            self.ws_url,
            on_open=on_open, on_message=on_message,
            on_error=on_error, on_close=on_close
        )
        self.ws_active = True
        self.ws_thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs={'ping_interval': 30}, daemon=True
        )
        self.ws_thread.start()
        print('[WS] Streaming iniciado')
        return {'ok': True, 'epics': epics}

    def stop_streaming(self):
        if self.ws: self.ws.close()
        self.ws_active = False

    def get_cached_prices(self): return self.prices

    def get_watchlists(self):
        self._refresh_if_needed()
        try:
            r = self.session.get(f'{self.base_url}/watchlists', headers=self._headers(), timeout=10)
            return {'ok': True, 'data': r.json()} if r.status_code == 200 else {'ok': False, 'error': r.text}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def ping(self):
        try:
            r = self.session.get(f'{self.base_url}/ping', headers=self._headers(), timeout=5)
            return {'ok': r.status_code == 200}
        except Exception as e:
            return {'ok': False, 'error': str(e)}

    def status(self):
        return {
            'connected':     self.connected,
            'env':           self.env,
            'ws_active':     self.ws_active,
            'cached_prices': len(self.prices),
            'session_valid': time.time() < self.session_exp,
            'base_url':      self.base_url,
        }
