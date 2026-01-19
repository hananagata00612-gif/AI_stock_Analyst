import streamlit as st
import pandas as pd
import feedparser
import plotly.graph_objects as go
import requests
import io
import yfinance as yf
from datetime import datetime

# ページ設定
st.set_page_config(page_title="Real Stock Analyst", layout="wide")
st.title("📈 米国株AI分析 (Browser Mask版)")

# 有名銘柄リスト
FAMOUS_STOCKS = {
    "NVIDIA": "NVDA",
    "Apple": "AAPL",
    "Microsoft": "MSFT",
    "Tesla": "TSLA",
    "Amazon": "AMZN",
    "Google": "GOOGL",
    "Meta": "META",
    "Eli Lilly": "LLY",
    "Pfizer": "PFE",
    "JPMorgan": "JPM"
}

st.sidebar.header("銘柄選択")
selected_name = st.sidebar.selectbox("分析対象", list(FAMOUS_STOCKS.keys()))
ticker = FAMOUS_STOCKS[selected_name]

# --- 共通設定: ブラウザ偽装用ヘッダー ---
FAKE_BROWSER_HEADER = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

# --- 関数: ニュース取得 ---
@st.cache_data(ttl=600)
def get_google_news(ticker):
    """Google News RSSから取得"""
    query = f"{ticker} stock"
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        response = requests.get(rss_url, headers=FAKE_BROWSER_HEADER, timeout=5)
        feed = feedparser.parse(response.content)
        news_items = []
        for entry in feed.entries[:5]:
            news_items.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.published
            })
        return news_items
    except Exception:
        return []

# --- 関数: 株価取得 (メイン: Stooq) ---
def get_data_from_stooq(ticker):
    """StooqからブラウザのふりをしてCSVをダウンロード"""
    url = f"https://stooq.com/q/d/l/?s={ticker}.us&i=d"
    try:
        # ここが重要！requestsを使ってヘッダー付きでアクセスする
        response = requests.get(url, headers=FAKE_BROWSER_HEADER, timeout=10)
        
        if response.status_code == 200:
            # 文字列データをメモリ上のファイルとして扱う
            csv_data = io.BytesIO(response.content)
            df = pd.read_csv(csv_data)
            
            # データ整形
            df['Date'] = pd.to_datetime(df['Date'])
            df.set_index('Date', inplace=True)
            df = df.sort_index()
            return df.tail(500)
        return None
    except Exception:
        return None

# --- 関数: 株価取得 (予備: Yahoo) ---
def get_data_from_yahoo(ticker):
    """Stooqがダメな時の保険"""
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y")
        return df
    except Exception:
        return None

# --- メインデータ取得関数 ---
@st.cache_data(ttl=600)
def get_stock_data(ticker):
    # 1. まずStooqを試す
    df = get_data_from_stooq(ticker)
    source = "Stooq"
    
    # 2. ダメならYahooを試す
    if df is None or df.empty:
        df = get_data_from_yahoo(ticker)
        source = "Yahoo Finance"
    
    return df, source

# --- 分析ロジック ---
def analyze_market(df, news_list):
    if df is None or len(df) < 50:
        return "データ不足", [], "gray"

    current_price = df['Close'].iloc[-1]
    sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1] if not rsi.empty else 50

    score = 0
    reasons = []

    # トレンド
    if current_price > sma_50:
        score += 1
        reasons.append(f"📈 [トレンド] 上昇中 (${current_price:.2f} > 50日平均)")
    else:
        score -= 1
        reasons.append(f"📉 [トレンド] 下落中 (${current_price:.2f} < 50日平均)")

    # RSI
    if current_rsi < 30:
        score += 2
        reasons.append(f"🟢 [RSI] 売られすぎ ({current_rsi:.0f}) → 反発期待")
    elif current_rsi > 70:
        score -= 2
        reasons.append(f"🔴 [RSI] 買われすぎ ({current_rsi:.0f}) → 過熱感あり")
    else:
        reasons.append(f"⚖️ [RSI] 中立 ({current_rsi:.0f})")

    # ニュース
    keywords_good = ['record', 'surge', 'jump', 'buy', 'beat', 'high', 'up']
    keywords_bad = ['drop', 'fall', 'miss', 'loss', 'cut', 'low', 'down']
    
    news_score = 0
    if news_list:
        for n in news_list:
            t = n['title'].lower()
            if any(w in t for w in keywords_good): news_score += 1
            if any(w in t for w in keywords_bad): news_score -= 1
    
    if news_score > 0:
        score += 1
        reasons.append("📰 [ニュース] 強気な報道が多い")
    elif news_score < 0:
        score -= 1
        reasons.append("📰 [ニュース] 弱気な報道が多い")

    # 判定
    if score >= 2:
        judgment = "Strong Buy"
        color = "#ff4b4b"
    elif score == 1:
        judgment = "Buy"
        color = "#ffa421"
    elif score <= -1:
        judgment = "Sell"
        color = "#1c83e1"
    else:
        judgment = "Hold"
        color = "gray"

    return judgment, reasons, color

# --- UI構築 ---
with st.spinner('データを取得しています...'):
    df, source = get_stock_data(ticker)
    news_items = get_google_news(ticker)

    if df is not None and not df.empty:
        # 基本情報
        current_price = df['Close'].iloc[-1]
        
        # 前日比
        if len(df) >= 2:
            prev_price = df['Close'].iloc[-2]
            change = current_price - prev_price
            pct = (change / prev_price) * 100
        else:
            change = 0
            pct = 0
        
        col1, col2 = st.columns(2)
        col1.metric("株価", f"${current_price:.2f}")
        col2.metric("前日比", f"{change:+.2f} ({pct:+.2f}%)")
        st.caption(f"Data Source: {source}") # どっちから取れたか表示

        # AI判定
        judgment, reasons, color = analyze_market(df, news_items)
        st.markdown(f"""
        <div style="border: 2px solid {color}; padding: 15px; border-radius: 10px; margin: 20px 0; text-align: center;">
            <h2 style="color: {color}; margin:0;">AI判定: {judgment}</h2>
        </div>
        """, unsafe_allow_html=True)
        
        for r in reasons:
            st.write(r)

        # チャート
        st.subheader("📈 チャート")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index,
                        open=df['Open'], high=df['High'],
                        low=df['Low'], close=df['Close'], name='Price'))
        st.plotly_chart(fig, use_container_width=True)

        # ニュース
        st.subheader("📰 Googleニュース")
        if news_items:
            for news in news_items:
                pub = news['published'][:16]
                st.markdown(f"**[{news['title']}]({news['link']})**")
                st.caption(f"📅 {pub}")
        else:
            st.info("ニュースなし")

    else:
        st.error(f"データの取得に失敗しました。({ticker})")
        st.write("対策: 数分待ってリロードするか、銘柄を変えてみてください。")
