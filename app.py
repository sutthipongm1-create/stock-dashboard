import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
from datetime import date, timedelta

# 1. ตั้งค่าหน้าเว็บ
st.set_page_config(page_title="Stock & Market Dashboard", layout="wide")
st.title("📈 Pro Trader Dashboard (หุ้น, ทองคำ, น้ำมัน)")

# ==========================================
# 🌟 ฟังก์ชันดึงข้อมูล (Cache ไว้เพื่อความเร็ว)
# ==========================================
@st.cache_data(ttl=300)
def get_market_data(tickers):
    try:
        df = yf.download(tickers, period="1d", progress=False)
        if not df.empty and isinstance(df.columns, pd.MultiIndex):
            closes = df['Close'].iloc[-1]
            opens = df['Open'].iloc[0]
            pct_change = ((closes - opens) / opens) * 100
            return pct_change[pct_change > 0].sort_values(ascending=False).head(5)
    except: pass
    return pd.Series(dtype=float)

@st.cache_data(ttl=300)
def get_commodity_prices():
    # GC=F (ทองคำ), CL=F (น้ำมันดิบ WTI)
    com_tickers = ['GC=F', 'CL=F']
    prices = {}
    try:
        df = yf.download(com_tickers, period="1d", progress=False)
        if not df.empty:
            for t in com_tickers:
                try:
                    if isinstance(df.columns, pd.MultiIndex):
                        prices[t] = df['Close'][t].iloc[-1]
                    else:
                        prices[t] = df[t].iloc[-1]
                except: pass
    except: pass
    return prices

@st.cache_data(ttl=600)
def get_recommended_thai_stocks():
    thai_tickers = ['PTT.BK', 'AOT.BK', 'CPALL.BK', 'ADVANC.BK', 'PTTEP.BK', 'BDMS.BK', 'GULF.BK', 'SCC.BK', 'KBANK.BK', 'SCB.BK']
    try:
        df = yf.download(thai_tickers, period="3mo", progress=False)
        recs = {}
        for ticker in thai_tickers:
            try:
                s = df['Close'][ticker].dropna() if isinstance(df.columns, pd.MultiIndex) else df[ticker].dropna()
                if len(s) > 14:
                    delta = s.diff()
                    gain = delta.clip(lower=0).ewm(com=13, adjust=False).mean()
                    loss = -delta.clip(upper=0).ewm(com=13, adjust=False).mean()
                    rsi = 100 - (100 / (1 + gain / loss))
                    recs[ticker] = rsi.iloc[-1]
            except: continue
        return sorted(recs.items(), key=lambda x: x[1])[:5]
    except: return []

# ==========================================
# 2. Sidebar (แถบด้านข้าง)
# ==========================================
st.sidebar.header("🌍 สินทรัพย์โกลบอล")
com_prices = get_commodity_prices()
if 'GC=F' in com_prices:
    st.sidebar.markdown(f"🥇 **ทองคำ (Gold)**: ${com_prices['GC=F']:.2f}/oz")
if 'CL=F' in com_prices:
    st.sidebar.markdown(f"🛢️ **น้ำมัน (WTI)**: ${com_prices['CL=F']:.2f}/bbl")

st.sidebar.markdown("---")
st.sidebar.header("🔥 หุ้นมาแรง & น่าสะสม")

rec_thai = get_recommended_thai_stocks()
rec_list = []
st.sidebar.subheader("⭐ หุ้นไทยน่าสะสม (RSI ต่ำ)")
for t, r in rec_thai:
    st.sidebar.write(f"{t.replace('.BK','')}: RSI {r:.1f}")
    rec_list.append(t)

st.sidebar.markdown("---")

# ส่วนที่ใช้ "กดเลือก" หุ้น หรือ สินทรัพย์
options = ["--- พิมพ์ชื่อหุ้นเอง ---", "GC=F (ทองคำ)", "CL=F (น้ำมัน WTI)"] + rec_list + ['PTT.BK', 'AOT.BK', 'CPALL.BK', 'AAPL', 'TSLA']
selected = st.sidebar.selectbox("คลิกเลือกสินทรัพย์ที่ต้องการวิเคราะห์", options)

if selected == "--- พิมพ์ชื่อหุ้นเอง ---":
    ticker_input = st.sidebar.text_input("ระบุชื่อหุ้น (เช่น PTT, AAPL)", "PTT")
else:
    # ตัดคำอธิบายภาษาไทยออกเวลาดึงข้อมูล
    ticker_input = selected.split(" ")[0] 

if not ticker_input.endswith(".BK") and "." not in ticker_input and ticker_input.upper() not in ["GC=F", "CL=F", "AAPL", "TSLA"]:
    ticker_symbol = ticker_input.upper() + ".BK"
else:
    ticker_symbol = ticker_input.upper()

# ==========================================
# 3. ส่วนแสดงกราฟ (Main Area พร้อม Technical Analysis)
# ==========================================
st.header(f"📊 วิเคราะห์เทคนิค: {ticker_symbol}")

try:
    data = yf.download(ticker_symbol, period="1y")
    if not data.empty:
        # 🌟 คำนวณ Technical Indicators
        # ตรวจสอบโครงสร้าง yfinance ใหม่
        close_col = data['Close'].iloc[:, 0] if isinstance(data.columns, pd.MultiIndex) else data['Close']
        open_col = data['Open'].iloc[:, 0] if isinstance(data.columns, pd.MultiIndex) else data['Open']
        high_col = data['High'].iloc[:, 0] if isinstance(data.columns, pd.MultiIndex) else data['High']
        low_col = data['Low'].iloc[:, 0] if isinstance(data.columns, pd.MultiIndex) else data['Low']
        vol_col = data['Volume'].iloc[:, 0] if isinstance(data.columns, pd.MultiIndex) else data['Volume']

        # 1. Bollinger Bands & SMA
        data['SMA20'] = close_col.rolling(window=20).mean()
        data['STD20'] = close_col.rolling(window=20).std()
        data['BB_Upper'] = data['SMA20'] + (data['STD20'] * 2)
        data['BB_Lower'] = data['SMA20'] - (data['STD20'] * 2)

        # 2. MACD
        data['EMA12'] = close_col.ewm(span=12, adjust=False).mean()
        data['EMA26'] = close_col.ewm(span=26, adjust=False).mean()
        data['MACD'] = data['EMA12'] - data['EMA26']
        data['Signal'] = data['MACD'].ewm(span=9, adjust=False).mean()
        data['MACD_Hist'] = data['MACD'] - data['Signal']

        # 🌟 วาดกราฟ 3 ชั้น (ราคา, Volume, MACD)
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                            vertical_spacing=0.03, row_heights=[0.6, 0.2, 0.2],
                            subplot_titles=("ราคา & Bollinger Bands", "Volume", "MACD"))

        # ชั้นที่ 1: ราคาและ Bollinger Bands
        fig.add_trace(go.Candlestick(x=data.index, open=open_col, high=high_col, low=low_col, close=close_col, name='Price'), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_Upper'], line=dict(color='gray', width=1, dash='dot'), name='Upper Band'), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['BB_Lower'], line=dict(color='gray', width=1, dash='dot'), name='Lower Band'), row=1, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['SMA20'], line=dict(color='blue', width=1.5), name='SMA 20'), row=1, col=1)

        # ชั้นที่ 2: Volume
        colors = ['green' if close_col.iloc[i] >= open_col.iloc[i] else 'red' for i in range(len(data))]
        fig.add_trace(go.Bar(x=data.index, y=vol_col, marker_color=colors, name='Volume'), row=2, col=1)

        # ชั้นที่ 3: MACD
        fig.add_trace(go.Scatter(x=data.index, y=data['MACD'], line=dict(color='blue', width=1.5), name='MACD'), row=3, col=1)
        fig.add_trace(go.Scatter(x=data.index, y=data['Signal'], line=dict(color='orange', width=1.5), name='Signal'), row=3, col=1)
        fig.add_trace(go.Bar(x=data.index, y=data['MACD_Hist'], marker_color='gray', name='Histogram'), row=3, col=1)

        fig.update_layout(height=800, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.error("ไม่พบข้อมูลสินทรัพย์นี้")
except Exception as e:
    st.error(f"Error rendering chart: {e}")

# ==========================================
# 4. กราฟ Real-time 
# ==========================================
st.markdown("---")
st.subheader("⏱️ ราคา Real-time (1 นาที)")
rt_placeholder = st.empty()

while True:
    try:
        rt_data = yf.download(ticker_symbol, period="1d", interval="1m", progress=False)
        if not rt_data.empty:
            with rt_placeholder.container():
                # จัดการ yfinance multi-index
                rt_close = rt_data['Close'].iloc[:, 0] if isinstance(rt_data.columns, pd.MultiIndex) else rt_data['Close']
                rt_open = rt_data['Open'].iloc[:, 0] if isinstance(rt_data.columns, pd.MultiIndex) else rt_data['Open']
                rt_high = rt_data['High'].iloc[:, 0] if isinstance(rt_data.columns, pd.MultiIndex) else rt_data['High']
                rt_low = rt_data['Low'].iloc[:, 0] if isinstance(rt_data.columns, pd.MultiIndex) else rt_data['Low']
                
                last_price = rt_close.iloc[-1]
                st.metric("ราคาล่าสุด", f"{last_price:.2f}")
                
                fig_rt = go.Figure(data=[go.Candlestick(x=rt_data.index, open=rt_open, high=rt_high, low=rt_low, close=rt_close)])
                fig_rt.update_layout(height=300, xaxis_rangeslider_visible=False, margin=dict(t=0,b=0,l=0,r=0))
                st.plotly_chart(fig_rt, use_container_width=True, key=f"rt_{time.time()}")
    except: pass
    time.sleep(60)