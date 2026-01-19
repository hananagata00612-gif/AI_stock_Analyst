import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from duckduckgo_search import DDGS
import pandas as pd

# ページ設定
st.set_page_config(page_title="AI Stock Analyst Pro", layout="wide")

# タイトル
st.title("📈 米国株 自動分析アプリ (Local AI版)")

# --- 有名銘柄リスト ---
FAMOUS_STOCKS = {
    "NVIDIA (AI半導体)": "NVDA",
    "Apple (iPhone)": "AAPL",
    "Microsoft (Windows/AI)": "MSFT",
    "Tesla (EV)": "TSLA",
    "Amazon (EC/Cloud)": "AMZN",
    "Google (検索)": "GOOGL",
    "Meta (SNS)": "META",
    "Eli Lilly (製薬/肥満症薬)": "LLY",
    "Pfizer (製薬)": "PFE",
    "JPMorgan (金融)": "JPM",
    "Coca-Cola (飲料)": "KO",
    "McDonald's (飲食)": "MCD"
}

# --- サイドバー設定 ---
st.sidebar.header("銘柄選択")
selected_name = st.sidebar.selectbox("分析したい企業を選んでください", list(FAMOUS_STOCKS.keys()))
ticker = FAMOUS_STOCKS[selected_name]

st.sidebar.markdown("---")
st.sidebar.write(f"選択中: **{ticker}**")

# --- 関数定義 ---

def get_stock_data(ticker):
    """株価データを取得する"""
    stock = yf.Ticker(ticker)
    # テクニカル分析用に少し長め(2年分)にとる
    hist = stock.history(period="2y")
    return stock, hist

def calculate_technical_indicators(df):
    """
    テクニカル指標を計算して、売買判断を行うアルゴリズム
    """
    if len(df) < 50:
        return "データ不足", "判定不能"

    # 1. 移動平均線 (トレンドを見る)
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()

    # 2. RSI (買われすぎ・売られすぎを見る)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 最新の値を取得
    current_price = df['Close'].iloc[-1]
    sma_50 = df['SMA_50'].iloc[-1]
    sma_200 = df['SMA_200'].iloc[-1]
    rsi = df['RSI'].iloc[-1]

    # --- 独自の売買ロジック ---
    score = 0
    reasons = []

    # トレンド判定
    if current_price > sma_50:
        score += 1
        reasons.append(f"📈 株価が短期トレンド(50日線 ${sma_50:.2f})を上回っています（上昇傾向）")
    else:
        score -= 1
        reasons.append(f"📉 株価が短期トレンド(50日線 ${sma_50:.2f})を下回っています（下落傾向）")

    if sma_50 > sma_200:
        score += 1
        reasons.append("🌟 長期的に上昇トレンドが続いています（ゴールデンクロス状態に近い）")

    # RSI判定
    if rsi < 30:
        score += 2
        reasons.append(f"🟢 RSIが{rsi:.1f}で「売られすぎ」水準です。反発のチャンスかもしれません。")
    elif rsi > 70:
        score -= 2
        reasons.append(f"🔴 RSIが{rsi:.1f}で「買われすぎ」水準です。過熱感があります。")
    else:
        reasons.append(f"⚖️ RSIは{rsi:.1f}で中立的な水準です。")

    # 総合判定
    if score >= 2:
        judgment = "Strong Buy (買い推奨)"
        color = "red" # 海外では赤がプラス、緑がマイナスのことが多いが、わかりやすく赤を目立たせる
    elif score == 1:
        judgment = "Buy (打診買い検討)"
        color = "orange"
    elif score == 0:
        judgment = "Hold (様子見)"
        color = "gray"
    elif score == -1:
        judgment = "Sell (売り検討)"
        color = "blue"
    else:
        judgment = "Strong Sell (強く売り推奨)"
        color = "blue"

    return judgment, reasons, color

def get_news(ticker):
    """DuckDuckGoで最新ニュースを取得する"""
    query = f"{ticker} stock news finance"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
        return results
    except:
        return []

# --- メイン処理 ---

if ticker:
    try:
        # 1. データ取得
        stock, hist = get_stock_data(ticker)
        info = stock.info
        
        # 2. 企業情報の表示
        st.subheader(f"{selected_name} の分析結果")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("現在値", f"${info.get('currentPrice', 'N/A')}")
        col2.metric("時価総額", f"${info.get('marketCap', 0) / 1000000000:.1f} B") # Billion単位
        col3.metric("PER", f"{info.get('trailingPE', 'N/A')}")
        col4.metric("配当利回り", f"{info.get('dividendYield', 0) * 100:.2f}%" if info.get('dividendYield') else "なし")

        # 3. テクニカル分析と判定（ここが自作AI部分）
        judgment, reasons, color = calculate_technical_indicators(hist)

        st.markdown("### 🤖 アルゴリズム投資判断")
        st.markdown(f"""
        <div style="padding: 20px; border-radius: 10px; background-color: rgba(255, 255, 255, 0.1); border: 2px solid {color}; text-align: center;">
            <h2 style="color: {color}; margin: 0;">{judgment}</h2>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("#### 📊 判断の根拠:")
        for r in reasons:
            st.write(f"- {r}")

        # 4. チャート表示
        st.subheader("📈 株価チャート (ローソク足)")
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=hist.index,
                        open=hist['Open'], high=hist['High'],
                        low=hist['Low'], close=hist['Close'], name='Price'))
        
        # 移動平均線を追加
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'].rolling(window=50).mean(), line=dict(color='orange', width=1), name='50日平均'))
        fig.add_trace(go.Scatter(x=hist.index, y=hist['Close'].rolling(window=200).mean(), line=dict(color='blue', width=1), name='200日平均'))

        fig.update_layout(xaxis_rangeslider_visible=False, height=500)
        st.plotly_chart(fig, use_container_width=True)

        # 5. ニュース表示
        st.subheader("📰 最新ニュース")
        news_list = get_news(ticker)
        if news_list:
            for news in news_list:
                st.markdown(f"**[{news['title']}]({news['href']})**")
                st.caption(news['body'][:120] + "...")
        else:
            st.info("ニュースが見つかりませんでした。")

    except Exception as e:
        st.error(f"データの取得中にエラーが発生しました: {e}")