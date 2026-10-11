from pathlib import Path
from html import escape
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Taiwan Stock Radar", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

HISTORY_PATH = Path("data/history/twse_daily.csv")
PICKS_PATH = Path("data/history/combined_top_picks.csv")
PICKS_HISTORY_PATH = Path("data/history/combined_picks_history.csv")
INDICATORS_PATH = Path("data/history/technical_indicators.csv")
TDCC_PATH = Path("data/history/tdcc_analysis.csv")
TDCC_WEEKLY_PATH = Path("data/history/tdcc_weekly.csv")
SIGNALS_PATH = Path("data/history/stock_signals.csv")

@st.cache_data(ttl=300)
def read_csv(path):
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype={"stock_id": str}, encoding="utf-8-sig")
    except (pd.errors.EmptyDataError, UnicodeError):
        return pd.DataFrame()

def num(value):
    return pd.to_numeric(value, errors="coerce")

def fmt(value, digits=2, suffix=""):
    v = num(value)
    return f"{float(v):,.{digits}f}{suffix}" if pd.notna(v) else "—"

def datefmt(value):
    d = pd.to_datetime(value, errors="coerce")
    return d.strftime("%Y-%m-%d") if pd.notna(d) else "—"

def stock_rows(df, code):
    if df.empty or "stock_id" not in df.columns:
        return pd.DataFrame()
    rows = df.loc[df["stock_id"].astype(str).str.strip() == str(code).strip()].copy()
    if "date" in rows.columns:
        rows["date"] = pd.to_datetime(rows["date"], errors="coerce")
        rows = rows.sort_values("date")
    return rows

def latest(df, code):
    rows = stock_rows(df, code)
    return rows.iloc[-1] if not rows.empty else None

TREND = {"ACCUMULATING": "大戶增持", "DISTRIBUTING": "大戶減持", "NEUTRAL": "籌碼持平"}
SIGNAL = {"BREAKOUT": "突破", "SETUP": "觀察中", "FIRE": "FIRE", "NONE": "無訊號"}
LABELS = {
    "date": "日期", "stock_id": "股票代號", "stock_name": "股票名稱",
    "combined_rank": "綜合排名", "close": "收盤價", "fire_score": "FIRE 分數",
    "tdcc_score": "TDCC 分數", "combined_score": "綜合分數",
    "breakout_status": "突破狀態", "tdcc_trend": "籌碼趨勢",
    "signal": "技術訊號", "rank_score": "排名分數",
    "rsi14": "RSI (14)", "volume_ratio": "成交量倍數",
    "ma10": "10 日均線", "ma20": "20 日均線",
    "breakout_distance_pct": "突破距離 (%)",
    "big_holder_pct": "大戶持股 (%)", "change_4w_pp": "近 4 週變化 (百分點)",
    "change_12w_pp": "近 12 週變化 (百分點)", "trend": "籌碼方向",
    "near_high_pct": "接近近期高點 (%)", "price_vs_ma10_pct": "相對 MA10 (%)",
    "price_vs_ma20_pct": "相對 MA20 (%)", "hot_flag": "熱門標記",
}
def display_table(df, columns=None):
    if df.empty:
        st.info("目前沒有可顯示的紀錄。")
        return
    d = df.copy()
    if columns:
        d = d[[c for c in columns if c in d.columns]]
    for c in d.columns:
        if c == "date":
            d[c] = pd.to_datetime(d[c], errors="coerce").dt.strftime("%Y-%m-%d").fillna("—")
        elif c in ("trend", "tdcc_trend"):
            d[c] = d[c].map(lambda v: TREND.get(str(v).upper(), str(v)) if pd.notna(v) else "—")
        elif c in ("signal", "breakout_status"):
            d[c] = d[c].map(lambda v: SIGNAL.get(str(v).upper(), str(v)) if pd.notna(v) else "—")
        elif c not in ("stock_id", "stock_name", "hot_flag") and pd.api.types.is_numeric_dtype(d[c]):
            d[c] = d[c].round(2)
    d = d.rename(columns=LABELS)
    # HTML 表格讓深色配色可控，避免 Streamlit dataframe 自帶亮色背景。
    headers = "".join(f"<th>{escape(str(c))}</th>" for c in d.columns)
    body = "".join(
        "<tr>" + "".join(
            f"<td>{escape('—' if pd.isna(v) else str(v))}</td>" for v in row
        ) + "</tr>" for row in d.itertuples(index=False, name=None)
    )
    st.markdown(
        '<div class="radar-table-scroll"><table class="radar-table"><thead><tr>'
        + headers + '</tr></thead><tbody>' + body + '</tbody></table></div>',
        unsafe_allow_html=True,
    )

def metric_row(items):
    cols = st.columns(len(items))
    for col, (name, value, *rest) in zip(cols, items):
        col.metric(name, value, help=rest[0] if rest else None)

def chart_style(fig, height=300, showlegend=False):
    fig.update_layout(
        template="plotly_dark", height=height, paper_bgcolor="#101b2d",
        plot_bgcolor="#101b2d", font=dict(color="#d9e6f7", family="Arial, sans-serif", size=12),
        margin=dict(l=12, r=12, t=22, b=16), showlegend=showlegend,
        xaxis=dict(title=None, gridcolor="#26384e", zeroline=False, tickfont=dict(color="#b5c8df")),
        yaxis=dict(title=None, gridcolor="#26384e", zeroline=False, tickfont=dict(color="#b5c8df")),
        hovermode="x unified",
    )
    return fig

def price_chart(rows):
    if rows.empty:
        st.info("目前沒有這檔股票的歷史股價。")
        return
    p = rows.copy()
    p["close"] = num(p["close"])
    p = p.dropna(subset=["date", "close"]).sort_values("date")
    if p.empty:
        st.info("目前沒有有效的收盤價資料。")
        return
    period = st.radio("股價圖時間區間", ["近 1 個月", "近 3 個月", "近 6 個月", "近 1 年", "全部"],
                      index=2, horizontal=True, key="v12_period")
    days = {"近 1 個月": 30, "近 3 個月": 90, "近 6 個月": 180, "近 1 年": 365}
    start = p["date"].max() - pd.Timedelta(days=days[period]) if period in days else None
    fig = go.Figure()
    ohlc = {"open", "high", "low", "close"}.issubset(p.columns)
    if ohlc and p[["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce").notna().all(axis=1).any():
        k = p.dropna(subset=["open", "high", "low", "close"])
        fig.add_trace(go.Candlestick(x=k["date"], open=k["open"], high=k["high"], low=k["low"],
                                     close=k["close"], name="K 線",
                                     increasing_line_color="#ef5350", decreasing_line_color="#2dd4bf"))
        fig.update_xaxes(rangeslider_visible=False)
    else:
        fig.add_trace(go.Scatter(x=p["date"], y=p["close"], name="收盤價",
                                 line=dict(color="#80a7ff", width=2.5)))
    for n, color in [(5, "#ffbd69"), (10, "#52d6a4"), (20, "#fa777b")]:
        if len(p) >= n:
            fig.add_trace(go.Scatter(x=p["date"], y=p["close"].rolling(n).mean(),
                                     name=f"MA{n}", line=dict(color=color, width=1.6)))
    chart_style(fig, 350, True)
    fig.update_layout(legend=dict(orientation="h", y=1.15, x=0, font=dict(color="#e5efff")))
    if start is not None:
        fig.update_xaxes(range=[start, p["date"].max()])
    st.plotly_chart(fig, use_container_width=True)
    if "volume" in p.columns:
        v = p.copy()
        v["volume"] = num(v["volume"])
        v = v.dropna(subset=["volume"])
        if not v.empty:
            prior = v["close"].shift(1)
            colors = ["#ef5350" if pd.notna(old) and new >= old else "#2dd4bf"
                      for new, old in zip(v["close"], prior)]
            vf = go.Figure(go.Bar(x=v["date"], y=v["volume"], marker_color=colors, name="成交量"))
            chart_style(vf, 155)
            vf.update_yaxes(tickformat="~s")
            if start is not None:
                vf.update_xaxes(range=[start, p["date"].max()])
            st.caption("每日成交量｜單位依原始 CSV 資料")
            st.plotly_chart(vf, use_container_width=True)

st.markdown("""
<style>
/* 僅設定內容文字，不覆寫 Streamlit Material Symbols 圖示字型。 */
.stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3,
.stApp label, .stApp button, .stApp [data-testid="stMetric"] {
  font-family: Arial, "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", sans-serif;
}
.stApp {background:linear-gradient(150deg,#081120,#0a1628 60%,#0c1b2e);color:#e8f1ff}
[data-testid="stSidebar"] {background:#0e1c2f;border-right:1px solid #283b52}
h1,h2,h3 {color:#f2f7ff;letter-spacing:.2px}
h1 {font-size:2rem!important} h2 {font-size:1.5rem!important} h3 {font-size:1.18rem!important}
[data-testid="stMetric"] {background:#13233a;border:1px solid #2b405c;
 border-radius:13px;padding:15px 17px;min-height:112px}
[data-testid="stMetricLabel"] {color:#b6c9e2}
[data-testid="stMetricValue"] {color:#f4f8ff;font-size:clamp(1.15rem,2.3vw,2rem);font-weight:750}
.stTabs [data-baseweb="tab-list"] {gap:12px;border-bottom:1px solid #30455d}
.stTabs [data-baseweb="tab"] {color:#d3e2f6;padding:10px 15px}
.stTabs [aria-selected="true"] {color:#fff;border-bottom:2px solid #60a5fa}
[data-testid="stExpander"] {background:#122138;border:1px solid #2b405c;border-radius:10px}
[data-testid="stExpander"] summary {background:#14253b!important;color:#eaf3ff!important;border-radius:9px}
[data-testid="stExpander"] summary p {color:#eaf3ff!important;font-weight:600}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {background:#101e32}
[data-testid="stExpander"] svg {color:#d8e7fa}
[data-testid="stDataFrame"] {border:1px solid #30455d;border-radius:10px;overflow:hidden}
[data-testid="stMarkdownContainer"] p {line-height:1.65}
div[data-testid="stVerticalBlock"] {gap:.7rem}
hr {border-color:#263950}
[data-testid="stAlert"] {border-radius:10px;background:#132944!important;border:1px solid #28537d}
[data-testid="stAlert"] p, [data-testid="stAlert"] strong {color:#eaf5ff!important}
[data-testid="stCaptionContainer"] p, .stApp small {color:#b8cbe1!important}
.stApp [data-testid="stRadio"] label p {color:#d7e7fb!important}
.radar-table-scroll {overflow:auto;max-height:430px;border:1px solid #30465e;border-radius:10px;margin:8px 0 15px;background:#111f32}
.radar-table {border-collapse:separate;border-spacing:0;width:100%;min-width:560px;color:#e4eefc;font-size:13px}
.radar-table th {position:sticky;top:0;background:#1b304b;color:#edf5ff;font-weight:700;text-align:left;padding:12px;border-bottom:1px solid #38526d;white-space:nowrap}
.radar-table td {background:#111f32;color:#e3edf9;padding:11px 12px;border-bottom:1px solid #263950;white-space:nowrap}
.radar-table tbody tr:nth-child(even) td {background:#17283e}
.radar-table tbody tr:hover td {background:#223b56}
</style>
""", unsafe_allow_html=True)

prices = read_csv(HISTORY_PATH)
if not prices.empty and {"stock_id", "date", "close"}.issubset(prices.columns):
    prices["stock_id"] = prices["stock_id"].astype(str).str.strip()
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")
    for c in ["close", "open", "high", "low", "volume"]:
        if c in prices.columns:
            prices[c] = num(prices[c])
    prices = prices.dropna(subset=["date", "close"]).sort_values("date").drop_duplicates(["stock_id", "date"], keep="last")
else:
    prices = pd.DataFrame()
picks = read_csv(PICKS_PATH)
history = read_csv(PICKS_HISTORY_PATH)
indicators = read_csv(INDICATORS_PATH)
tdcc = read_csv(TDCC_PATH)
weekly = read_csv(TDCC_WEEKLY_PATH)
signals = read_csv(SIGNALS_PATH)

st.sidebar.title("🔎 股票搜尋")
typed = st.sidebar.text_input("股票代號", value="3416", placeholder="例如 2330").strip()
choices = ["自行輸入"]
if not picks.empty and "stock_id" in picks.columns:
    for _, r in picks.iterrows():
        choices.append(f"{str(r['stock_id']).strip()} {str(r.get('stock_name', ''))}")
chosen = st.sidebar.selectbox("今日精選股票", choices)
stock_id = typed if chosen == "自行輸入" else chosen.split()[0]
st.sidebar.divider()
st.sidebar.caption("GitHub Actions 每日產生資料｜非即時行情")
st.sidebar.caption("v1.2 測試版｜原始選股策略未變更")

st.title("📈 Taiwan Stock Radar")
st.caption("台股智慧選股與個股分析｜FIRE 技術訊號 × TDCC 籌碼")
if not prices.empty:
    st.caption(f"📅 歷史股價最新日期：{datefmt(prices['date'].max())}")
else:
    st.warning("尚未讀取到歷史股價 CSV。")

tab1, tab2, tab3 = st.tabs(["🏆 每日智慧選股", "📊 個股決策儀表板", "🗂️ 歷史選股紀錄"])

with tab1:
    st.subheader("🏆 FIRE + TDCC 每日精選")
    st.caption("綜合分數是選股策略排名，不代表未來報酬率。")
    if picks.empty:
        st.info("尚無每日精選資料。")
    else:
        if "combined_rank" in picks.columns:
            picks = picks.assign(_rank=num(picks["combined_rank"])).sort_values("_rank").drop(columns="_rank")
        cols = ["combined_rank", "stock_id", "stock_name", "close", "fire_score", "tdcc_score",
                "combined_score", "breakout_status", "tdcc_trend"]
        display_table(picks, cols)
        if "date" in picks.columns:
            st.caption(f"選股日期：{datefmt(picks.iloc[0]['date'])}")

with tab2:
    pr = stock_rows(prices, stock_id)
    sr = latest(signals, stock_id)
    tr = latest(tdcc, stock_id)
    ir = latest(indicators, stock_id)
    name = "個股"
    for source in [sr, tr, pr.iloc[-1] if not pr.empty else None]:
        if source is not None and pd.notna(source.get("stock_name")):
            name = str(source.get("stock_name"))
            break
    st.subheader(f"{stock_id} {name}")
    st.caption("依照最新可取得的 CSV 數據顯示，各指標日期可能不同。")

    st.markdown("### 01｜投資決策總覽")
    close = pr.iloc[-1]["close"] if not pr.empty else None
    previous = pr.iloc[-2]["close"] if len(pr) >= 2 else None
    change = (float(close) / float(previous) - 1) * 100 if pd.notna(close) and pd.notna(previous) and previous > 0 else None
    fire = str(sr.get("signal", "—")).strip().upper() if sr is not None else "—"
    trend_raw = str(tr.get("trend", "")).strip().upper() if tr is not None else ""
    trend = TREND.get(trend_raw, "無資料")
    agreement = ("同向" if fire == "FIRE" and trend_raw == "ACCUMULATING"
                 else "分歧" if fire == "FIRE" and trend_raw == "DISTRIBUTING"
                 else "資料不足" if sr is None or tr is None else "尚未同向確認")
    metric_row([("最新收盤價", fmt(close, 2, " 元")), ("FIRE 訊號", SIGNAL.get(fire, fire)),
                ("TDCC 方向", trend), ("技術 × 籌碼", agreement)])
    st.caption(f"最新股價日期：{datefmt(pr.iloc[-1]['date']) if not pr.empty else '—'}"
               + (f"｜較前一交易日 {change:+.2f}%" if change is not None else ""))

    c4 = num(tr.get("change_4w_pp")) if tr is not None else float("nan")
    c12 = num(tr.get("change_12w_pp")) if tr is not None else float("nan")
    if sr is None or tr is None:
        verdict = "技術或籌碼資料不足，暫無法完成雙訊號判讀。"
    else:
        verdict = ("FIRE 技術訊號成立；" if fire == "FIRE" else f"目前技術訊號為 {SIGNAL.get(fire, fire)}；")
        verdict += f"TDCC 顯示{trend}。"
        if pd.notna(c4) and pd.notna(c12):
            verdict += (f"近 4 週持股變化 {c4:+.2f} 個百分點，"
                        f"近 12 週 {c12:+.2f} 個百分點。")
            if c4 < 0 < c12:
                verdict += "中期略增、短期略減，留意籌碼轉折。"
            elif c12 < 0 < c4:
                verdict += "中期略減、短期回升，仍需持續觀察。"
    st.info("**綜合判讀｜** " + verdict)
    st.caption("此為規則式資料整理，不是 AI 價格預測，也不構成買賣建議。")

    st.divider()
    st.markdown("### 02｜趨勢與分析證據")
    left, right = st.columns([1.75, 1], gap="large")
    with left:
        st.markdown("#### 股價趨勢與均線")
        price_chart(pr)
    with right:
        st.markdown("#### FIRE 技術動能")
        if sr is None:
            st.info("此股票沒有 FIRE 訊號資料。")
        else:
            metric_row([("RSI (14)", fmt(sr.get("rsi14"))),
                        ("成交量倍數", fmt(sr.get("volume_ratio"), 2, " 倍"))])
            metric_row([("相對 MA10", fmt(sr.get("price_vs_ma10_pct"), 2, "%")),
                        ("相對 MA20", fmt(sr.get("price_vs_ma20_pct"), 2, "%"))])
            st.caption(f"排名分數：{fmt(sr.get('rank_score'))}｜接近近期高點：{fmt(sr.get('near_high_pct'), 2, '%')}")
            st.caption(f"FIRE 確認條件：{fmt(sr.get('fire_confirmations'), 0)}"
                       f"｜SETUP 確認條件：{fmt(sr.get('setup_confirmations'), 0)}")
        st.markdown("#### TDCC 籌碼摘要")
        if tr is None:
            st.info("此股票沒有 TDCC 分析資料。")
        else:
            metric_row([("大戶持股", fmt(tr.get("big_holder_pct"), 2, "%")),
                        ("近 4 週", fmt(c4, 2, " pp"))])
            metric_row([("近 12 週", fmt(c12, 2, " pp")),
                        ("分析週數", fmt(tr.get("period_count"), 0))])
            st.caption("pp 表示百分點；正值為持股比例增加，負值為減少。")
    st.markdown("#### TDCC 大戶持股趨勢")
    wr = stock_rows(weekly, stock_id)
    if not wr.empty and {"date", "big_holder_pct"}.issubset(wr.columns):
        wr["big_holder_pct"] = num(wr["big_holder_pct"])
        wr = wr.dropna(subset=["date", "big_holder_pct"]).drop_duplicates("date", keep="last")
        if not wr.empty:
            tc = go.Figure(go.Scatter(x=wr["date"], y=wr["big_holder_pct"],
                                      mode="lines+markers", name="大戶持股比例",
                                      line=dict(color="#38bdf8", width=2.5), marker=dict(size=5),
                                      hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}%<extra></extra>"))
            chart_style(tc, 250)
            tc.update_yaxes(ticksuffix="%")
            st.plotly_chart(tc, use_container_width=True)
            st.caption(f"TDCC 週資料：{datefmt(wr['date'].min())} ～ {datefmt(wr['date'].max())}｜{len(wr)} 筆")
        else:
            st.info("沒有有效的 TDCC 週資料。")
    else:
        st.info("目前沒有此股票的 TDCC 每週持股紀錄。")

    st.divider()
    st.markdown("### 03｜深入研究與資料明細")
    if ir is not None:
        st.caption(f"最新技術指標日期：{datefmt(ir.get('date'))}")
        metric_row([("10 日均線", fmt(ir.get("ma10"))), ("20 日均線", fmt(ir.get("ma20"))),
                    ("RSI (14)", fmt(ir.get("rsi14"))), ("突破距離", fmt(ir.get("breakout_distance_pct"), 2, "%"))])
    else:
        st.info("此股票目前沒有技術指標報表。")
    with st.expander("📋 查看技術指標原始資料", expanded=False):
        display_table(stock_rows(indicators, stock_id),
                      ["date", "close", "ma10", "ma20", "rsi14", "volume_ratio", "breakout_distance_pct"])
    with st.expander("🔥 查看 FIRE 歷史技術訊號", expanded=False):
        display_table(stock_rows(signals, stock_id),
                      ["date", "close", "signal", "rsi14", "volume_ratio", "rank_score"])
    with st.expander("🏦 查看 TDCC 籌碼分析明細", expanded=False):
        display_table(stock_rows(tdcc, stock_id),
                      ["date", "big_holder_pct", "change_4w_pp", "change_12w_pp", "trend"])
    with st.expander("📈 查看 TDCC 每週持股紀錄", expanded=False):
        display_table(wr, ["date", "big_holder_pct"])

with tab3:
    st.subheader("🗂️ 每日綜合選股歷史紀錄")
    if history.empty:
        st.info("尚未建立選股歷史紀錄。")
    else:
        if "date" in history.columns:
            history = history.sort_values("date", ascending=False)
        display_table(history)
        st.caption(f"已保存 {len(history)} 筆選股紀錄。")

st.divider()
st.caption("Taiwan Stock Radar v1.2 測試版｜資料僅供研究參考，不構成投資建議。")
