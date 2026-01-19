import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd

# ページ設定
st.set_page_config(page_title="AI Stock Analyst Pro", layout="wide")
st.title("📈 米国株 AI分析アプリ (Pro版)")

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

# ★ここが修正ポイント：データを10分間(600秒)保存して、アクセス制限を回避する
@st.cache_data(ttl=600)
def get_data(ticker):
    """株価とニュースを取得"""
    stock = yf.Ticker(ticker)
    # 期間を2年に設定
    hist = stock.history(period="2y")
    info = stock.info
    try:
        news = stock.news
    except:
        news = []
    return hist, info, news

def analyze_trend(df):
    """テクニカル分析ロジック"""
    if df is None or len(df) == 0:
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
    
    # トレンド判定
    if current_price > sma_50:
        score += 1
        reasons.append(f"📈 上昇トレンド (現在値 ${current_price:.0f} > 50日平均)")
    else:
        score -= 1
        reasons.append(f"📉 下落トレンド (現在値 ${current_price:.0f} < 50日平均)")
        
    # RSI判定
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
    # データを取得
    hist, info, news = get_data(ticker)
    
    if hist is not None and not hist.empty:
        
        # 1. 基本データ表示
        col1, col2, col3 = st.columns(3)
        col1.metric("株価", f"${info.get('currentPrice', 0)}")
        col2.metric("時価総額", f"${info.get('marketCap', 0)/10**9:.1f} B")
        col3.metric("PER", f"{info.get('trailingPE', 'N/A')}")
        
        # 2. AI判定
        judgment, reasons, color = analyze_trend(hist)
        st.markdown(f"### AI判定: <span style='color:{color}; font-size: 24px;'>{judgment}</span>", unsafe_allow_html=True)
        for r in reasons:
            st.write(f"- {r}")

        # 3. チャート
        st.subheader("チャート (過去2年)")
        st.line_chart(hist['Close'])
        
        # 4. ニュース表示
        st.subheader("📰 最新ニュース")
        if news:
            for item in news[:5]: # 最新5件を表示
                title = item.get('title', 'No Title')
                link = item.get('link', '#')
                publisher = item.get('publisher', 'Unknown')
                st.markdown(f"**[{title}]({link})**")
                st.caption(f"Source: {publisher}")
        else:
            st.info("現在、関連ニュースが見つかりませんでした。")
            
    else:
        st.error("データの取得に失敗しました。少し時間をおいてリロードしてください。")

except Exception as e:
    st.warning("アクセスが集中しています。数分待ってからリロードしてください。")
