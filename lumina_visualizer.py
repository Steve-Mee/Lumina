import json
from datetime import datetime, timedelta
from pathlib import Path
import os

import dash
from dash import dcc, html, Input, Output
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

print("=== LUMINA DASH v3.0 – DEFINITIEVE FIX MIXED TZ + RECENTE DATA ===")

LIVE_JSONL = Path("live_stream.jsonl")
STATE_FILE = Path("lumina_sim_state.json")
TIMEFRAMES = {"5min": "5min", "15min": "15min", "30min": "30min", "60min": "60min", "240min": "240min", "1440min": "1440min"}

app = dash.Dash(__name__, title="LUMINA Live Charts v3.0")

data_cache = pd.DataFrame()
last_mtime = 0

def load_latest_data():
    global data_cache, last_mtime
    if not LIVE_JSONL.exists():
        print("⚠️ live_stream.jsonl bestaat nog niet")
        return pd.DataFrame()

    current_mtime = os.path.getmtime(LIVE_JSONL)
    if current_mtime == last_mtime and not data_cache.empty:
        return data_cache.copy()

    with open(LIVE_JSONL, "r", encoding="utf-8") as f:
        lines = f.readlines()[-200000:]

    data = [json.loads(line) for line in lines]
    df = pd.DataFrame(data)
    
    # Forceer alles naar tz-naive timestamps
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors='coerce').dt.tz_localize(None)
    
    # Alleen de laatste 36 uur tonen (geen oude bars van 24 maart meer)
    cutoff = datetime.now() - timedelta(hours=36)
    df = df[df['timestamp'] >= cutoff]
    
    data_cache = df.sort_values("timestamp").reset_index(drop=True)
    last_mtime = current_mtime
    
    print(f"📊 Visualizer loaded {len(df)} rows (laatste 36u)")
    if len(df) > 0:
        print(f"   Tijdspanne: {df['timestamp'].min()} → {df['timestamp'].max()}")
    
    return data_cache.copy()

def resample_to_ohlc(df, timeframe):
    if len(df) < 10:
        return pd.DataFrame()
    df = df.set_index("timestamp")
    ohlc = df['last'].resample(timeframe).agg(['first', 'max', 'min', 'last'])
    ohlc.columns = ['open', 'high', 'low', 'close']
    volume = df['volume'].resample(timeframe).last() - df['volume'].resample(timeframe).first()
    ohlc['volume'] = volume
    ohlc['vwap'] = (df['last'] * df['volume']).resample(timeframe).sum() / df['volume'].resample(timeframe).sum()
    ohlc['ema200'] = ohlc['close'].ewm(span=200, adjust=False).mean()
    return ohlc.dropna().reset_index()

@app.callback(
    Output("main-graph", "figure"),
    Input("interval", "n_intervals"),
    Input("tabs", "value")
)
def update_chart(n, tab):
    df = load_latest_data()
    print(f"🔄 Update voor {tab} – {len(df)} total rows in data")

    if len(df) < 20:
        return go.Figure()

    timeframe = TIMEFRAMES[tab]
    candles = resample_to_ohlc(df, timeframe)
    print(f"   → Resampled to {len(candles)} {tab} candles")

    if len(candles) > 1200:
        candles = candles.iloc[-1200:].reset_index(drop=True)

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.03)

    fig.add_trace(go.Candlestick(x=candles['timestamp'], open=candles['open'], high=candles['high'],
                                 low=candles['low'], close=candles['close'], name=tab,
                                 increasing_line_color="#00FF88", decreasing_line_color="#FF3333",
                                 line_width=1.6, whiskerwidth=0.4), row=1, col=1)

    fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['vwap'], name="VWAP",
                             line=dict(color="#FFFF00", width=2.8)), row=1, col=1)
    fig.add_trace(go.Scatter(x=candles['timestamp'], y=candles['ema200'], name="EMA 200",
                             line=dict(color="#FFFFFF", width=1.9, dash="dash")), row=1, col=1)

    fig.add_trace(go.Bar(x=candles['timestamp'], y=candles['volume'], name="Volume",
                         marker_color="rgba(180,180,180,0.65)"), row=2, col=1)

    latest = df.iloc[-1]
    dream = latest.get("current_dream", {})
    signal = dream.get("signal", "HOLD")
    conf = dream.get("confidence", 0)
    color = "#00FF88" if signal in ["BUY", "LONG"] else "#FF3333" if signal in ["SELL", "SHORT"] else "#777777"

    fig.add_annotation(
        text=f"<b>LUMINA BOT:</b> {signal} ({conf}%)<br>"
             f"Price: {latest['last']:.2f} | Bid {latest.get('bid',0):.2f} | Ask {latest.get('ask',0):.2f}",
        xref="paper", yref="paper", x=0.02, y=0.96, showarrow=False,
        font=dict(size=15, color="white"), bgcolor=color, bordercolor="black",
        borderwidth=3, borderpad=9
    )

    fig.update_xaxes(type='date', tickformat="%H:%M", tickangle=45, tickfont=dict(size=11))
    fig.update_yaxes(fixedrange=False, autorange=True)

    fig.update_layout(
        title=f"{tab} – MES JUN26   |   Update: {datetime.now().strftime('%H:%M:%S')} | {len(candles)} candles",
        xaxis_rangeslider_visible=False,
        height=680,
        template="plotly_dark",
        margin=dict(l=50, r=50, t=70, b=50),
        legend=dict(orientation="h", y=1.02, x=1, xanchor="right")
    )
    return fig

@app.callback(Output("perf-graph", "figure"), Input("interval", "n_intervals"))
def update_performance(n):
    if not STATE_FILE.exists():
        return go.Figure()
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
        equity = state.get("equity_curve", [50000])
        pnl = state.get("pnl_history", [])
        fig = make_subplots(rows=2, cols=1, subplot_titles=("Equity Curve", "PnL per Trade"))
        fig.add_trace(go.Scatter(y=equity, mode="lines", name="Equity", line=dict(color="#00FF88")), row=1, col=1)
        fig.add_trace(go.Bar(y=pnl, name="PnL", marker_color="#FFFF00"), row=2, col=1)
        fig.update_layout(height=340, template="plotly_dark", title="LUMINA Performance Oracle")
        return fig
    except:
        return go.Figure()

app.layout = html.Div([
    html.H1("LUMINA Live Charts v3.0 – FULL HISTORICAL OVERVIEW", 
            style={"textAlign": "center", "color": "#00FF88", "fontSize": "26px", "marginBottom": "10px"}),
    dcc.Tabs(id="tabs", value="5min", children=[
        dcc.Tab(label=name, value=name) for name in TIMEFRAMES.keys()
    ] + [dcc.Tab(label="Performance", value="perf")]),
    dcc.Graph(id="main-graph", style={"height": "680px"}),
    dcc.Graph(id="perf-graph", style={"height": "340px"}),
    dcc.Interval(id="interval", interval=1000, n_intervals=0)
])

if __name__ == "__main__":
    print("🌐 LUMINA Dash v3.0 gestart op http://127.0.0.1:8050")
    import webbrowser
    webbrowser.open("http://127.0.0.1:8050")
    app.run(debug=False, port=8050, use_reloader=False)