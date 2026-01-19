import streamlit as st
import pandas as pd
import feedparser
import plotly.graph_objects as go
import requests
from datetime import datetime

# ページ設定
st.set_page_config(page_title="Real Stock Analyst", layout="wide")
st.title("📈 米国株AI分析 (Professional API版)")

# --- ★ここに取得したAPIキーを貼り付けてください ---
# 例: API_KEY = "abc123456789..."
API_KEY = "aaa2294ad1124462b54f453da3a8dc3b" 

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

# --- 関数: ニュース取得 (Google News RSS - これは安定) ---
@st.cache_data(ttl=600)
def get_google_news(ticker):
    query = f"{ticker} stock"
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    try:
        feed = feedparser.parse(rss_url)
        news_items = []
        for entry in feed.entries[:5]:
            news_items.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.published
            })
        return news_items
    except:
        return []

# --- 関数: 株価取得 (Twelve Data API - 正規ルート) ---
@st.cache_data(ttl=3600) # 1時間キャッシュして回数を節約
def get_stock_price(ticker, api_key):
    """Twelve Data APIから正規にデータを取得"""
    if "ここに" in api_key: # キーが未入力の場合
        return None, "NoKey"

    url = f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=1day&outputsize=365&apikey={api_key}"
    
    try:
        response = requests.get(url).json()
        
        if "values" not in response:
            return None, "Error"
            
        # データ整形
        df = pd.DataFrame(response['values'])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        # 数値型に変換
        cols = ['open', 'high', 'low', 'close']
        for c in cols:
            df[c] = pd.to_numeric(df[c])
            
        # 日付の古い順に並べ替え
        df = df.sort_index()
        
        # 列名をCapitalize (Open, High...)
        df.columns = [c.capitalize() for c in df.columns]
        
        return df, "Success"
    except Exception as e:
        return None, str(e)

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
        reasons.append(f"🟢 [RSI] 売られすぎ ({current_rsi:.0f}) → 買い好機")
    elif current_rsi > 70:
        score -= 2
        reasons.append(f"🔴 [RSI] 買われすぎ ({current_rsi:.0f}) → 過熱感あり")
    else:
        reasons.append(f"⚖️ [RSI] 中立 ({current_rsi:.0f})")

    # ニュース判定
    keywords_good = ['record', 'surge', 'jump', 'buy', 'beat', 'high', 'up', 'profit']
    keywords_bad = ['drop', 'fall', 'miss', 'loss', 'cut', 'low', 'down', 'fail']
    
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
with st.spinner('正規APIからデータを取得中...'):
    df, status = get_stock_price(ticker, API_KEY)
    news_items = get_google_news(ticker)

    if status == "NoKey":
        st.error("⚠️ APIキーが設定されていません")
        st.info("1. https://twelvedata.com/ で無料キーを取得\n2. app.pyの `API_KEY` の部分に貼り付けてください")
    
    elif df is not None and not df.empty:
        # 基本情報
        current_price = df['Close'].iloc[-1]
        prev_price = df['Close'].iloc[-2]
        change = current_price - prev_price
        pct = (change / prev_price) * 100
        
        col1, col2 = st.columns(2)
        col1.metric("株価", f"${current_price:.2f}")
        col2.metric("前日比", f"{change:+.2f} ({pct:+.2f}%)")
        st.caption("Data Source: Twelve Data API (Official)")

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
        st.error(f"データ取得エラー: {status}")
        st.write("APIの制限回数（1分間に8回）を超えた可能性があります。少し待ってからリロードしてください。")
