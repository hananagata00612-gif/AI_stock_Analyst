import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# ページ設定
st.set_page_config(page_title="AI Stock Analyst Pro", layout="wide")
st.title("📈 米国株 AI分析アプリ (News付)")

# 有名銘柄リスト
FAMOUS_STOCKS = {
    "NVIDIA (AI半導体)": "NVDA",
    "Apple (iPhone)": "AAPL",
    "Microsoft (Windows/AI)": "MSFT",
    "Tesla (EV)": "TSLA",
    "Amazon (EC/Cloud)": "AMZN",
    "Google (検索)": "GOOGL",
    "Meta (SNS)": "META",
    "Eli Lilly (製薬/肥満症薬)": "LLY",
    "Pfizer (製薬)": "PFE"
}

st.sidebar.header("銘柄選択")
selected_name = st.sidebar.selectbox("企業を選択", list(FAMOUS_STOCKS.keys()))
ticker = FAMOUS_STOCKS[selected_name]

# --- 関数定義 ---

def get_data(ticker):
    """株価とニュースを取得"""
    stock = yf.Ticker(ticker)
    hist = stock.history(period="2y")
    info = stock.info
    news = stock.news  # yfinanceの標準機能でニュースを取得
    return hist, info, news

def analyze_trend(df):
    """テクニカル分析ロジック"""
    if len(df) == 0:
        return "判定不能", [], "gray"
    
    # 指標計算
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    current_price = df['Close'].iloc[-1]
    sma_50 = df['SMA_50'].iloc[-1]
    
    # RSI計算
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1]
    
    # 判定ロジック
    score = 0
    reasons = []
    
    # トレンド
    if current_price > sma_50:
        score += 1
        reasons.append(f"📈 上昇トレンド (現在値 ${current_price:.0f} > 50日平均)")
    else:
        score -= 1
        reasons.append(f"📉 下落トレンド (現在値 ${current_price:.0f} < 50日平均)")
        
    # RSI
    if current_rsi < 30:
        score += 2
        reasons.append(f"🟢 売られすぎ (RSI {current_rsi:.0f}) → 反発期待")
    elif current_rsi > 70:
        score -= 2
        reasons.append(f"🔴 買われすぎ (RSI {current_rsi:.0f}) → 過熱感あり")
    else:
        reasons.append(f"⚖️ RSI中立 (RSI {current_rsi:.0f})")

    # 結論
    judgment = "Hold (様子見)"
    color = "gray"
    if score >= 1:
        judgment = "Buy (買い検討)"
        color = "red"
    elif score <= -1:
        judgment = "Sell (売り検討)"
        color = "blue"
        
    return judgment, reasons, color

# --- メイン処理 ---
try:
    hist, info, news = get_data(ticker)
    
    if hist is not None and not hist.
