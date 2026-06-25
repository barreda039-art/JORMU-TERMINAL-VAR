import requests
from datetime import datetime, timedelta, timezone

KEY    = 'PKQBQXEK2HQX5BLDF3FAISRASP'
SECRET = '9boiuYtJijkd5bvKkQgUja96BkrJvejSuUFBcEZigApQ'

end   = datetime.now(timezone.utc)
start = end - timedelta(days=600)  # 600 dias atras

url     = 'https://data.alpaca.markets/v2/stocks/SPY/bars'
params  = {
    'timeframe': '1Day',
    'limit':     300,
    'start':     start.strftime('%Y-%m-%dT%H:%M:%SZ'),
    'end':       end.strftime('%Y-%m-%dT%H:%M:%SZ'),
    'feed':      'iex',
}
headers = {'APCA-API-KEY-ID': KEY, 'APCA-API-SECRET-KEY': SECRET}

r = requests.get(url, params=params, headers=headers, timeout=15)
print('Status:', r.status_code)

data = r.json()
bars = data.get('bars', [])
print('Barras recibidas:', len(bars))
if bars:
    print('Primera barra:', bars[0])
    print('Ultima barra: ', bars[-1])
else:
    print('Respuesta completa:', r.text[:500])
