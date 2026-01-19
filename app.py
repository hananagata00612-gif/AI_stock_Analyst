import streamlit as st
import pandas_datareader.data as web
import pandas as pd
import feedparser
import plotly.graph_objects as go
import requests
from datetime import datetime

# ページ設定
st.set_page_config(page_title="Real Stock Analyst", layout="wide")
st.title("📈 米国株AI分析 (Stooq & Google版)")

# 有名銘柄リスト (Stooq用のシンボル)
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

# --- 関数: Googleニュース取得 (RSS) ---
@st.cache_data(ttl=600)
def get_google_news(ticker):
    """Google News RSSからニュースを取得"""
    # 検索クエリを作成 (例: NVDA stock)
    query = f"{ticker} stock"
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:5]: # 最新5件
            news_items.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.published
            })
        return news_items
    except Exception:
        return []

# --- 関数: 株価取得 (Stooq) ---
@st.cache_data(ttl=600)
def get_stock_price(ticker):
    """Stooqから株価データを取得"""
    try:
        # Stooqからデータを取得 (過去2年分)
        # Stooqは日付が新しい順で返ってくるので、sort_indexで古い順に並べ替える
        df = web.DataReader(ticker, 'stooq')
        df = df.sort_index() 
        # 直近2年分くらいに絞る
        df = df.tail(500)
        return df
    except Exception as e:
        return None

# --- 関数: 分析ロジック ---
def analyze_market(df, news_list):
    if df is None or len(df) < 50:
        return "データ不足", [], "gray"

    current_price = df['Close'].iloc[-1]
    sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
    
    # RSI計算
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current_rsi = rsi.iloc[-1] if not rsi.empty else 50

    score = 0
    reasons = []

    # トレンド判定
    if current_price > sma_50:
        score += 1
        reasons.append(f"📈 [トレンド] 上昇中 (現在 ${current_price:.2f} > 50日平均)")
    else:
        score -= 1
        reasons.append(f"📉 [トレンド] 下落中 (現在 ${current_price:.2f} < 50日平均)")

    # RSI判定
    if current_rsi < 30:
        score += 2
        reasons.append(f"🟢 [RSI] 売られすぎ ({current_rsi:.1f}) → 反発期待")
    elif current_rsi > 70:
        score -= 2
        reasons.append(f"🔴 [RSI] 買われすぎ ({current_rsi:.1f}) → 過熱感あり")
    else:
        reasons.append(f"⚖️ [RSI] 中立 ({current_rsi:.1f})")

    # ニュース判定 (Google Newsのタイトル分析)
    keywords_good = ['record', 'surge', 'jump', 'buy', 'beat', 'profit', 'high']
    keywords_bad = ['drop', 'fall', 'miss', 'loss', 'cut', 'fail', 'low']
    
    news_score = 0
    if news_list:
        for n in news_list:
            t = n['title'].lower()
            if any(w in t for w in keywords_good): news_score += 1
            if any(w in t for w in keywords_bad): news_score -= 1
    
    if news_score > 0:
        score += 1
        reasons.append("📰 [ニュース] ポジティブな報道が目立ちます")
    elif news_score < 0:
        score -= 1
        reasons.append("📰 [ニュース] ネガティブな報道が目立ちます")

    # 結論
    if score >= 2:
        judgment = "Strong Buy (強気買い)"
        color = "#ff4b4b"
    elif score == 1:
        judgment = "Buy (買い推奨)"
        color = "#ffa421"
    elif score <= -1:
        judgment = "Sell (売り推奨)"
        color = "#1c83e1"
    else:
        judgment = "Hold (様子見)"
        color = "gray"

    return judgment, reasons, color

# --- メイン処理 ---
with st.spinner('データを取得中 (Source: Stooq & Google)...'):
    df = get_stock_price(ticker)
    news_items = get_google_news(ticker)

    if df is not None and not df.empty:
        # 基本情報 (Stooqは株価のみ提供なので、時価総額などは表示不可)
        current_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]
        change = current_price - prev_price
        change_pct = (change / prev_price) * 100
        
        col1, col2 = st.columns(2)
        col1.metric("現在株価", f"${current_price:.2f}")
        col2.metric("前日比", f"{change:+.2f} ({change_pct:+.2f}%)")

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
        st.subheader("📈 株価チャート")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index,
                        open=df['Open'], high=df['High'],
                        low=df['Low'], close=df['Close'], name='Price'))
        st.plotly_chart(fig, use_container_width=True)

        # ニュース
        st.subheader("📰 Google ニュース")
        if news_items:
            for news in news_items:
                pub = news['published'][:16]
                st.markdown(f"**[{news['title']}]({news['link']})**")
                st.caption(f"📅 {pub}")
        else:
            st.info("ニュースが見つかりませんでした")

    else:
        st.error("データの取得に失敗しました。時間をおいて再試行してください。")
