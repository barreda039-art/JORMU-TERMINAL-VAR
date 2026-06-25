# ═══════════════════════════════════════════════════════════
# JORMUNDGANDRSSON — Flask API Server v2 + Quant Engine
# ═══════════════════════════════════════════════════════════

from flask import Flask, jsonify, request
from flask_cors import CORS
from capital_client import CapitalClient
from icaro_bridge import icaro_bridge
import json, time

app = Flask(__name__)
CORS(app)

capital = CapitalClient()
price_cache = {}

def on_price(epic, data):
    price_cache[epic] = data

capital.on_price_update = on_price

# ══════════════════════════════════════════════════════════
# HEALTH
# ══════════════════════════════════════════════════════════
@app.route('/api/health', methods=['GET'])
def health():
    return jsonify({'ok': True, 'service': 'JORMUNDGANDRSSON Backend', 'version': '2.0'})

# ══════════════════════════════════════════════════════════
# AUTH
# ══════════════════════════════════════════════════════════
@app.route('/api/session/create', methods=['POST'])
def create_session():
    result = capital.create_session()
    if result.get('ok'):
        engine.risk.update_peak_nav(0)
    return jsonify(result)

@app.route('/api/session/status', methods=['GET'])
def session_status():
    return jsonify(capital.status())

@app.route('/api/session/ping', methods=['GET'])
def ping():
    return jsonify(capital.ping())

# ══════════════════════════════════════════════════════════
# CUENTA
# ══════════════════════════════════════════════════════════
@app.route('/api/account/balance', methods=['GET'])
def account_balance():
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión activa'}), 401
    return jsonify(capital.get_account_balance())

@app.route('/api/account/info', methods=['GET'])
def account_info():
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    return jsonify(capital.get_account_info())

# ══════════════════════════════════════════════════════════
# PRECIOS
# ══════════════════════════════════════════════════════════
@app.route('/api/market/price/<epic>', methods=['GET'])
def market_price(epic):
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    return jsonify(capital.get_price(epic))

@app.route('/api/market/prices', methods=['GET'])
def market_prices_live():
    return jsonify({'ok': True, 'prices': price_cache, 'count': len(price_cache)})

@app.route('/api/market/history/<epic>', methods=['GET'])
def market_history(epic):
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    resolution = request.args.get('resolution', 'HOUR')
    max_points = int(request.args.get('max', 100))
    return jsonify(capital.get_prices_history(epic, resolution, max_points))

@app.route('/api/market/search', methods=['GET'])
def market_search():
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    term = request.args.get('q', '')
    return jsonify(capital.get_markets(term))

# ══════════════════════════════════════════════════════════
# STREAMING
# ══════════════════════════════════════════════════════════
@app.route('/api/stream/start', methods=['POST'])
def stream_start():
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    body  = request.get_json() or {}
    epics = body.get('epics', [])
    if not epics:
        return jsonify({'ok': False, 'error': 'Debes pasar al menos 1 epic'}), 400
    result = capital.start_streaming(epics)
    return jsonify(result)

@app.route('/api/stream/stop', methods=['POST'])
def stream_stop():
    capital.stop_streaming()
    return jsonify({'ok': True})

@app.route('/api/stream/status', methods=['GET'])
def stream_status():
    return jsonify({'ok': True, 'active': capital.ws_active, 'instruments': list(price_cache.keys())})

# ══════════════════════════════════════════════════════════
# POSICIONES
# ══════════════════════════════════════════════════════════
@app.route('/api/positions', methods=['GET'])
def get_positions():
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    return jsonify(capital.get_positions())

@app.route('/api/positions/open', methods=['POST'])
def open_position():
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    body = request.get_json()
    if not body:
        return jsonify({'ok': False, 'error': 'Body requerido'}), 400
    epic      = body.get('epic')
    direction = body.get('direction')
    size      = body.get('size')
    if not all([epic, direction, size]):
        return jsonify({'ok': False, 'error': 'epic, direction y size son requeridos'}), 400
    if direction not in ['BUY', 'SELL']:
        return jsonify({'ok': False, 'error': 'direction debe ser BUY o SELL'}), 400
    risk_check = validate_risk(epic, direction, size)
    if not risk_check['ok']:
        return jsonify({'ok': False, 'error': 'RISK MANAGER: ' + risk_check['reason']}), 403
    result = capital.open_position(
        epic=epic, direction=direction, size=float(size),
        stop_distance=body.get('stopDistance'),
        limit_distance=body.get('limitDistance'),
    )
    return jsonify(result)

@app.route('/api/positions/close/<deal_id>', methods=['DELETE'])
def close_position(deal_id):
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    body      = request.get_json() or {}
    direction = body.get('direction')
    size      = body.get('size')
    if not direction or not size:
        return jsonify({'ok': False, 'error': 'direction y size requeridos'}), 400
    return jsonify(capital.close_position(deal_id, direction, float(size)))

@app.route('/api/positions/update/<deal_id>', methods=['PUT'])
def update_position(deal_id):
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    body = request.get_json() or {}
    return jsonify(capital.update_position(
        deal_id,
        stop_level=body.get('stopLevel'),
        limit_level=body.get('limitLevel'),
    ))

@app.route('/api/positions/confirm/<deal_reference>', methods=['GET'])
def confirm_deal(deal_reference):
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    return jsonify(capital.get_deal_confirmation(deal_reference))

# ══════════════════════════════════════════════════════════
# RISK MANAGER BÁSICO
# ══════════════════════════════════════════════════════════
RISK_CONFIG = {
    'max_positions':   10,
    'max_exposure':    80,
    'max_single_pos':  5,
    'circuit_breaker': False,
}

def validate_risk(epic, direction, size):
    if RISK_CONFIG['circuit_breaker']:
        return {'ok': False, 'reason': 'Circuit breaker activo'}
    pos_result = capital.get_positions()
    if not pos_result['ok']:
        return {'ok': False, 'reason': 'No se pudieron verificar posiciones'}
    if len(pos_result['positions']) >= RISK_CONFIG['max_positions']:
        return {'ok': False, 'reason': f'Límite de posiciones alcanzado ({RISK_CONFIG["max_positions"]})'}
    return {'ok': True}

@app.route('/api/risk/config', methods=['GET'])
def get_risk_config():
    return jsonify({'ok': True, 'config': RISK_CONFIG})

@app.route('/api/risk/config', methods=['PUT'])
def update_risk_config():
    body = request.get_json() or {}
    RISK_CONFIG.update({k: v for k, v in body.items() if k in RISK_CONFIG})
    return jsonify({'ok': True, 'config': RISK_CONFIG})

@app.route('/api/risk/circuit-breaker', methods=['POST'])
def toggle_circuit_breaker():
    body = request.get_json() or {}
    RISK_CONFIG['circuit_breaker'] = body.get('active', False)
    return jsonify({'ok': True, 'circuit_breaker': RISK_CONFIG['circuit_breaker']})

@app.route('/api/watchlists', methods=['GET'])
def get_watchlists():
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    return jsonify(capital.get_watchlists())

# ══════════════════════════════════════════════════════════
# QUANT ENGINE
# ══════════════════════════════════════════════════════════
from quant_engine import QuantEngine

engine = QuantEngine(capital)

def on_new_signal(signal):
    print(f'[SERVER] ◆ Nueva señal: {signal["asset"]} {signal["direction"]} Score:{signal["total_score"]}')

def on_auto_execute(signal):
    print(f'[SERVER] ★ Auto-ejecutado: {signal["asset"]} {signal["direction"]}')

engine.on_signal       = on_new_signal
engine.on_auto_execute = on_auto_execute

@app.route('/api/engine/start', methods=['POST'])
def engine_start():
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Conecta Capital.com primero'}), 401
    engine.start()
    return jsonify({'ok': True, 'message': 'Quant Engine iniciado — análisis cada 15 min'})

@app.route('/api/engine/stop', methods=['POST'])
def engine_stop():
    engine.stop()
    return jsonify({'ok': True, 'message': 'Quant Engine detenido'})

@app.route('/api/engine/status', methods=['GET'])
def engine_status():
    return jsonify({'ok': True, 'status': engine.get_status()})

@app.route('/api/engine/signals', methods=['GET'])
def engine_signals():
    return jsonify({'ok': True, 'signals': engine.get_signals()})

@app.route('/api/engine/signals/approve/<signal_id>', methods=['POST'])
def approve_signal(signal_id):
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Sin sesión'}), 401
    return jsonify(engine.approve_signal(signal_id))

@app.route('/api/engine/signals/reject/<signal_id>', methods=['POST'])
def reject_signal(signal_id):
    return jsonify(engine.reject_signal(signal_id))

@app.route('/api/engine/run-now', methods=['POST'])
def engine_run_now():
    """Fuerza análisis inmediato — útil para testing"""
    if not capital.connected:
        return jsonify({'ok': False, 'error': 'Conecta Capital.com primero'}), 401
    import threading
    t = threading.Thread(target=engine._run_analysis_cycle, daemon=True)
    t.start()
    return jsonify({'ok': True, 'message': 'Ciclo de análisis iniciado'})

@app.route('/api/engine/asset/pause/<asset>', methods=['POST'])
def pause_asset(asset):
    engine.pause_asset(asset)
    return jsonify({'ok': True, 'asset': asset, 'status': 'paused'})

@app.route('/api/engine/asset/resume/<asset>', methods=['POST'])
def resume_asset(asset):
    engine.resume_asset(asset)
    return jsonify({'ok': True, 'asset': asset, 'status': 'active'})

@app.route('/api/engine/strategy/<strategy_id>', methods=['PUT'])
def update_strategy_status(strategy_id):
    body   = request.get_json() or {}
    active = body.get('active', True)
    engine.set_strategy_active(strategy_id, active)
    return jsonify({'ok': True, 'strategy': strategy_id, 'active': active})

# ══════════════════════════════════════════════════════════
# ICARO ENGINE
# ══════════════════════════════════════════════════════════

@app.route('/api/icaro/status', methods=['GET'])
def icaro_status():
    nav = 0
    if capital.connected:
        balance_data = capital.get_account_balance()
        nav = balance_data.get('balance', 0) if balance_data.get('ok') else 0
    summary = icaro_bridge.get_status_summary()
    summary['icaro_capital'] = engine.risk.get_icaro_capital(nav)
    summary['nav']           = nav
    return jsonify({'ok': True, 'icaro': summary})

@app.route('/api/icaro/capital', methods=['GET', 'PUT'])
def icaro_capital():
    if request.method == 'GET':
        nav = 0
        if capital.connected:
            balance_data = capital.get_account_balance()
            nav = balance_data.get('balance', 0) if balance_data.get('ok') else 0
        reserve_pct   = engine.risk.config.get('icaro_reserve_pct', 20.0)
        icaro_cap     = engine.risk.get_icaro_capital(nav)
        return jsonify({
            'ok':            True,
            'nav':           nav,
            'reserve_pct':   reserve_pct,
            'icaro_capital': icaro_cap,
            'available_nav': nav - icaro_cap,
        })
    body        = request.get_json() or {}
    reserve_pct = body.get('reserve_pct')
    if reserve_pct is None:
        return jsonify({'ok': False, 'error': 'reserve_pct requerido'}), 400
    if not (0 <= reserve_pct <= 80):
        return jsonify({'ok': False, 'error': 'reserve_pct debe estar entre 0 y 80'}), 400
    engine.risk.set_icaro_reserve(reserve_pct)
    return jsonify({'ok': True, 'reserve_pct': reserve_pct})

# ══════════════════════════════════════════════════════════
# ERRORS
# ══════════════════════════════════════════════════════════
@app.errorhandler(404)
def not_found(e):
    return jsonify({'ok': False, 'error': 'Endpoint no encontrado'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'ok': False, 'error': 'Error interno del servidor'}), 500

# ══════════════════════════════════════════════════════════
if __name__ == '__main__':
    # Iniciar watcher de ICARO en background
    icaro_bridge.start_watching(interval_seconds=30)

    print("""
╔═══════════════════════════════════════════════════╗
║   JORMUNDGANDRSSON — Backend Server v2            ║
║   Puerto: 5000  |  Quant Engine: integrado        ║
║   Endpoints: /api/engine/start  /api/engine/stop  ║
╚═══════════════════════════════════════════════════╝
    """)
    app.run(host='0.0.0.0', port=5000, debug=False)
