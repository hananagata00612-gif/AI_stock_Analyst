import streamlit as st
import yfinance as yf
import pandas as pd
import feedparser
import plotly.graph_objects as go
import requests
import requests_cache # これでYahooに何度も聞きに行かないようにする
from datetime import datetime

# ページ設定
st.set_page_config(page_title="Real Stock Analyst", layout="wide")
st.title("📈 実戦用 米国株AI分析 (Anti-Block版)")

# 有名銘柄リスト
FAMOUS_STOCKS = {
    "NVIDIA (AI半導体)": "NVDA",
    "Apple (iPhone)": "AAPL",
    "Microsoft (Windows/AI)": "MSFT",
    "Tesla (EV)": "TSLA",
    "Amazon (EC/Cloud)": "AMZN",
    "Google (検索)": "GOOGL",
    "Meta (SNS)": "META",
    "Eli Lilly (製薬)": "LLY",
    "Pfizer (製薬)": "PFE",
    "JPMorgan (金融)": "JPM"
}

st.sidebar.header("銘柄選択")
selected_name = st.sidebar.selectbox("分析対象", list(FAMOUS_STOCKS.keys()))
ticker = FAMOUS_STOCKS[selected_name]

# --- ★重要: ブロック対策用セッション作成 ---
# キャッシュ有効化（データをsqliteファイルに保存して再利用）
session = requests_cache.CachedSession('yfinance.cache')
session.headers['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'

# --- 関数: ニュース取得 (RSS) ---
@st.cache_data(ttl=600)
def get_rss_news(ticker):
    """Yahoo Finance RSS取得"""
    rss_url = f'https://finance.yahoo.com/rss/headline?s={ticker}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(rss_url, headers=headers, timeout=5)
        feed = feedparser.parse(response.content)
        news_items = []
        for entry in feed.entries[:5]:
            news_items.append({
                'title': entry.title,
                'link': entry.link,
                'published': entry.published,
            })
        return news_items
    except Exception:
        return []

# --- 関数: 株価取得 (セッション使用) ---
@st.cache_data(ttl=600)
def get_stock_price(ticker):
    try:
        # ★ここで対策済みセッションを渡す
        stock = yf.Ticker(ticker, session=session)
        
        # 期間を少し短くして負荷を下げる
        hist = stock.history(period="1y")
        
        # infoが取れない場合のエラー回避
        try:
            info = stock.info
        except:
            # 最低限の情報だけ手動で作る（ブロックされた時の保険）
            info = {
                'currentPrice': hist['Close'].iloc[-1] if not hist.empty else 0,
                'marketCap': 0,
                'trailingPE': 0
            }
            
        return hist, info
    except Exception as e:
        return None, None

# --- 関数: 分析ロジック ---
def analyze_market(df, news_list):
    if df is None or len(df) < 50:
        return "データ不足", [], "gray"

    current_price = df['Close'].iloc[-1]
    sma_50 = df['Close'].rolling(window=50).mean().iloc[-1]
    
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
        reasons.append(f"📈 [トレンド] 上昇中 (現在 ${current_price:.0f} > 50日平均)")
    else:
        score -= 1
        reasons.append(f"📉 [トレンド] 下落中 (現在 ${current_price:.0f} < 50日平均)")

    # RSI
    if current_rsi < 30:
        score += 2
        reasons.append(f"🟢 [RSI] 売られすぎ ({current_rsi:.0f}) → 買い好機")
    elif current_rsi > 70:
        score -= 2
        reasons.append(f"🔴 [RSI] 買われすぎ ({current_rsi:.0f}) → 利確推奨")
    else:
        reasons.append(f"⚖️ [RSI] 中立 ({current_rsi:.0f})")

    # ニュース判定
    keywords_good = ['record', 'jump', 'soar', 'buy', 'beat', 'profit', 'upgrade']
    keywords_bad = ['drop', 'fall', 'miss', 'loss', 'cut', 'fail', 'downgrade']
    
    news_score = 0
    if news_list:
        for n in news_list:
            t = n['title'].lower()
            if any(w in t for w in keywords_good): news_score += 1
            if any(w in t for w in keywords_bad): news_score -= 1
    
    if news_score > 0:
        score += 1
        reasons.append("📰 [ニュース] 強気なヘッドラインが多いです")
    elif news_score < 0:
        score -= 1
        reasons.append("📰 [ニュース] 弱気なヘッドラインが多いです")

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
st.markdown("##### ※Yahoo Financeへの接続を最適化中...")

hist, info = get_stock_price(ticker)
news_items = get_rss_news(ticker)

if hist is not None and not hist.empty:
    # 基本情報
    col1, col2, col3 = st.columns(3)
    price = info.get('currentPrice', hist['Close'].iloc[-1])
    market_cap = info.get('marketCap', 0)
    
    col1.metric("株価", f"${price:.2f}")
    if market_cap > 0:
        col2.metric("時価総額", f"${market_cap/10**9:.1f} B")
    else:
        col2.metric("時価総額", "-") # 取得できなかった場合
        
    col3.metric("PER", f"{info.get('trailingPE', '-')}")

    # AI判定
    judgment, reasons, color = analyze_market(hist, news_items)
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
    fig.add_trace(go.Candlestick(x=hist.index,
                    open=hist['Open'], high=hist['High'],
                    low=hist['Low'], close=hist['Close'], name='Price'))
    st.plotly_chart(fig, use_container_width=True)

    # ニュース
    st.subheader("📰 最新ニュース")
    if news_items:
        for news in news_items:
            pub = news['published'][:16] 
            st.markdown(f"**[{news['title']}]({news['link']})**")
            st.caption(f"📅 {pub}")
    else:
        st.info("ニュースなし")
else:
    st.error("⚠️ Yahoo Financeからブロックされました。数分待ってからリロードするか、別の銘柄を試してください。")
