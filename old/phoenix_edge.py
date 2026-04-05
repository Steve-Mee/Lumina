# AUTO DNA REWRITE 2026-03-24 06:56:43.874519
# Rewritten the phoenix edge function with optimized momentum, inverse volatility weighting, and leverage scaling to target Sharpe ratio >2.5

def calculate_phoenix_edge(df):
    import pandas as pd
    import numpy as np
    df = df.copy()
    df['returns'] = df['close'].pct_change()
    df['momentum'] = df['returns'].ewm(span=10).mean()
    df['volatility'] = df['returns'].rolling(window=20).std()
    df['edge'] = (df['momentum'] / (df['volatility'] + 1e-6)) * 5.0
    df['edge'] = df['edge'].clip(-0.1, 0.1)
    df['edge'] = df['edge'].fillna(0)
    return df['edge']
