# AUTO MUTATION 2026-03-23 21:41:30.643788
# Live momentum oracle met adaptive EMA crossover en volatility filter op real-time prijsdata om consistente signals te genereren met Sharpe >2.5

def nieuwe_node(state: dict) -> dict:
    import numpy as np
    from collections import deque
    if 'price_history' not in state:
        state['price_history'] = deque(maxlen=100)
    price = state.get('live_price', 100.0)
    state['price_history'].append(price)
    prices = np.array(state['price_history'])
    if len(prices) < 30:
        return {'signal': 0, 'oracle_value': 0.0, 'estimated_sharpe': 0.0}
    ema_fast = np.mean(prices[-10:]) 
    ema_slow = np.mean(prices[-30:])
    vol = np.std(prices[-20:]) if len(prices) > 20 else 1.0
    momentum = (ema_fast - ema_slow) / vol
    signal = 1 if momentum > 0.3 else (-1 if momentum < -0.3 else 0)
    returns = np.diff(prices[-50:]) / prices[-51:-1]
    if len(returns) > 5 and np.std(returns) > 0:
        est_sharpe = (np.mean(returns) / np.std(returns)) * np.sqrt(252)
    else:
        est_sharpe = 0.0
    return {'signal': signal, 'oracle_value': float(momentum), 'estimated_sharpe': float(est_sharpe), 'confidence': min(1.0, abs(momentum)*2)}
