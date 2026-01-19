import streamlit as st
import pandas as pd
import feedparser
import plotly.graph_objects as go
import requests
from datetime import datetime

# --- 1. ページ設定 (読み込み速度アップのため最優先) ---
st.set_page_config(
    page_title="Stock AI Pro", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. 白飛び完全防止 (CSSで背景色を固定) ---
st.markdown("""
    <style>
        .stApp {
            background-color: #0e1117;
            color: #ffffff;
        }
        section[data-testid="stSidebar"] {
            background-color: #262730;
        }
    </style>
""", unsafe_allow_html=True)

st.title("📈 米国株AI分析 (Speed & Stable)")

# --- ★APIキー設定 ---
API_KEY = "aaa2294ad1124462b54f453da3a8dc3b" 

# 銘柄リスト
FAMOUS_STOCKS = {
    "NVIDIA": "NVDA", "Apple": "AAPL", "Microsoft": "MSFT",
    "Tesla": "TSLA", "Amazon": "AMZN", "Google": "GOOGL",
    "Meta": "META", "Eli Lilly": "LLY", "Pfizer": "PFE",
    "JPMorgan": "JPM"
}

st.sidebar.header("銘柄選択")
# index=0 にすることで、リロード時に一番上の銘柄に戻るのを防ぐ工夫も可能ですが今回はシンプルに
selected_name = st.sidebar.selectbox("分析対象", list(FAMOUS_STOCKS.keys()))
ticker = FAMOUS_STOCKS[selected_name]

# --- 関数: ニュース取得 (タイムアウト設定でフリーズ回避) ---
@st.cache_data(ttl=600)
def get_google_news(ticker):
    query = f"{ticker} stock"
    rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # ★重要: timeout=3 (3秒で返事がなければ諦めて次へ進む)
        response = requests.get(rss_url, headers=headers, timeout=3)
        feed = feedparser.parse(response.content)
        
        news_items = []
        if feed.entries:
            for entry in feed.entries[:5]:
                news_items.append({
                    'title': entry.title,
                    'link': entry.link,
                    'published': entry.published
                })
        return news_items
    except Exception:
        return [] # エラーが出ても空リストを返してアプリを止めない

# --- 関数: 株価取得 (エラーハンドリング強化) ---
@st.cache_data(ttl=3600)
def get_stock_price(ticker, api_key):
    if "ここに" in api_key:
        return None, "KeyError"

    url = f"https://api.twelvedata.com/time_series?symbol={ticker}&interval=1day&outputsize=365&apikey={api_key}"
    
    try:
        # ★重要: ここもtimeout設定
        response = requests.get(url, timeout=5).json()
        
        if "values" not in response:
            # API制限(1分間に8回)に引っかかった場合など
            return None, "ApiLimit"
            
        df = pd.DataFrame(response['values'])
        df['datetime'] = pd.to_datetime(df['datetime'])
        df.set_index('datetime', inplace=True)
        
        cols = ['open', 'high', 'low', 'close']
        for c in cols:
            df[c] = pd.to_numeric(df[c])
        df = df.sort_index()
        df.columns = [c.capitalize() for c in df.columns]
        
        return df, "Success"
    except Exception:
        return None, "ConnectionError"

# --- 分析ロジック ---
def analyze_market(df, news_list):
    if df is None or len(df) < 20:
        return "データ不足", [], "gray"

    current = df['Close'].iloc[-1]
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
    if current > sma_50:
        score += 1
        reasons.append(f"📈 [トレンド] 上昇中 (${current:.2f} > 50日平均)")
    else:
        score -= 1
        reasons.append(f"📉 [トレンド] 下落中 (${current:.2f} < 50日平均)")

    # RSI
    if current_rsi < 30:
        score += 2
        reasons.append(f"🟢 [RSI] 売られすぎ ({current_rsi:.0f}) → 反発期待")
    elif current_rsi > 70:
        score -= 2
        reasons.append(f"🔴 [RSI] 買われすぎ ({current_rsi:.0f}) → 利確推奨")
    else:
        reasons.append(f"⚖️ [RSI] 中立 ({current_rsi:.0f})")

    # ニュース
    keywords_good = ['surge', 'jump', 'record', 'buy', 'beat', 'profit', 'high']
    keywords_bad = ['drop', 'fall', 'miss', 'loss', 'cut', 'low', 'fail']
    
    news_score = 0
    if news_list:
        for n in news_list:
            t = n['title'].lower()
            if any(w in t for w in keywords_good): news_score += 1
            if any(w in t for w in keywords_bad): news_score -= 1
    
    if news_score > 0:
        score += 1
        reasons.append("📰 [ニュース] ポジティブ報道優勢")
    elif news_score < 0:
        score -= 1
        reasons.append("📰 [ニュース] ネガティブ報道優勢")

    if score >= 2:
        judgment, color = "Strong Buy", "#ff4b4b"
    elif score == 1:
        judgment, color = "Buy", "#ffa421"
    elif score <= -1:
        judgment, color = "Sell", "#1c83e1"
    else:
        judgment, color = "Hold", "gray"

    return judgment, reasons, color

# --- メイン処理 ---
# ★スピナー（読み込み中のぐるぐる）を軽くする
with st.spinner('Loading...'):
    df, status = get_stock_price(ticker, API_KEY)
    # ニュース取得は失敗しても株価表示を止めないように独立させる
    news_items = get_google_news(ticker)

    if status == "KeyError":
        st.error("⚠️ APIキーを設定してください")
    elif status == "ApiLimit":
        st.warning("⚠️ API制限（1分間に8回）のためデータを取得できませんでした。少し待ってから別の銘柄を選んでください。")
    elif status != "Success" or df is None:
        st.error("データ取得エラー。リロードしてください。")
    else:
        # 基本情報
        current = df['Close'].iloc[-1]
        prev = df['Close'].iloc[-2]
        change = current - prev
        pct = (change / prev) * 100
        
        col1, col2 = st.columns(2)
        col1.metric("株価", f"${current:.2f}")
        col2.metric("前日比", f"{change:+.2f} ({pct:+.2f}%)")

        # AI判定
        judgment, reasons, color = analyze_market(df, news_items)
        st.markdown(f"""
        <div style="border: 2px solid {color}; padding: 15px; border-radius: 10px; margin: 20px 0; text-align: center; background-color: rgba(255,255,255,0.05);">
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
        fig.update_layout(height=400, margin=dict(l=20, r=20, t=20, b=20))
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
