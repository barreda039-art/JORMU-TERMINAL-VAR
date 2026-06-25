import requests

KEY    = 'PKQBQXEK2HQX5BLDF3FAISRASP'
SECRET = '9boiuYtJijkd5bvKkQgUja96BkrJvejSuUFBcEZigApQ'

url     = 'https://data.alpaca.markets/v2/stocks/SPY/bars'
params  = {'timeframe': '1Day', 'limit': 10, 'feed': 'iex'}
headers = {'APCA-API-KEY-ID': KEY, 'APCA-API-SECRET-KEY': SECRET}

r = requests.get(url, params=params, headers=headers, timeout=15)
print('Status:', r.status_code)
print('Response:', r.text[:800])
