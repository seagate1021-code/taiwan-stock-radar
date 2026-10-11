from pathlib import Path
from html import escape
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Taiwan Stock Radar", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

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
    "price_vs_ma20_pct": "相對 MA20 (%)", "hot_flag": "熱門標記", "tdcc_date": "籌碼日期",
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
    chart_style(fig, 365, True)
    fig.update_layout(legend=dict(orientation="h", y=1.12, x=0, font=dict(color="#e5efff")))
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
/* Taiwan Stock Radar v2.0 — design system */
.stApp {background:#081321;color:#e8f2ff}
.stApp, .stApp p, .stApp h1, .stApp h2, .stApp h3, .stApp label,
.stApp button, .stApp [data-testid="stMetric"] {
 font-family:"Microsoft JhengHei","PingFang TC","Noto Sans TC",Arial,sans-serif;
}
[data-testid="stHeader"] {background:#081321e8}
[data-testid="stSidebar"] {background:#0e2034;border-right:1px solid #25405d}
.block-container {max-width:1650px;padding-top:2.2rem;padding-bottom:3rem}
h1,h2,h3 {color:#f5f9ff!important;letter-spacing:.1px}
h1 {font-size:2rem!important} h2 {font-size:1.5rem!important} h3 {font-size:1.14rem!important}
[data-testid="stMetric"] {background:#13263e;border:1px solid #294662;border-radius:13px;padding:15px 17px;min-height:105px}
[data-testid="stMetricLabel"] {color:#9fb8d3}
[data-testid="stMetricValue"] {color:#f4f9ff;font-size:clamp(1.05rem,2vw,1.7rem);font-weight:730}
.stTabs [data-baseweb="tab-list"] {gap:16px;border-bottom:1px solid #29435e}
.stTabs [data-baseweb="tab"] {color:#b8cee4;padding:11px 12px}
.stTabs [aria-selected="true"] {color:#fff;border-bottom:3px solid #38bdf8}
[data-testid="stExpander"] {background:#102139;border:1px solid #2c4662;border-radius:12px}
[data-testid="stExpander"] summary {background:#142943!important;color:#eaf3ff!important;border-radius:10px}
[data-testid="stExpander"] summary p {color:#eaf3ff!important;font-weight:600}
[data-testid="stExpander"] [data-testid="stExpanderDetails"] {background:#102139}
[data-testid="stExpander"] svg {color:#d8e7fa}
[data-testid="stMarkdownContainer"] p {line-height:1.65}
[data-testid="stCaptionContainer"] p,.stApp small {color:#9fb4ca!important}
.stApp [data-testid="stRadio"] label p {color:#d8e8f8!important}
hr {border-color:#243d57}
[data-testid="stAlert"] {background:#143050!important;border:1px solid #2c5b83;border-radius:10px}
[data-testid="stAlert"] p {color:#e9f4ff!important}
.radar-eyebrow {color:#61c4f3;font-size:.76rem;font-weight:700;letter-spacing:1.7px;margin-bottom:5px}
.radar-hero {padding:19px 22px;border:1px solid #2b4867;border-radius:16px;background:linear-gradient(120deg,#122a45,#0e2035 70%);margin:8px 0 22px}
.radar-hero h2 {font-size:1.4rem!important;margin:0 0 7px}
.radar-muted {color:#a4bad1;font-size:.86rem}
.radar-section {font-size:.85rem;color:#69c9f6;font-weight:750;letter-spacing:1px;margin:23px 0 12px;padding-bottom:8px;border-bottom:1px solid #233d57}
.radar-panel {background:#102239;border:1px solid #28435f;border-radius:14px;padding:18px 20px;margin:7px 0 15px;min-height:120px}
.radar-panel-title {color:#b9d2ea;font-size:.82rem;font-weight:650;margin-bottom:9px}
.radar-panel-main {font-size:1.25rem;font-weight:750;color:#f3f9ff;line-height:1.5}
.radar-panel-note {color:#9fb5ce;font-size:.79rem;line-height:1.65;margin-top:7px}
.radar-green {color:#5de0b2}.radar-amber {color:#f6c16b}.radar-red {color:#ff9299}
.radar-verdict {background:linear-gradient(110deg,#16395c,#122d4a);border:1px solid #34658b;border-left:4px solid #49c4ee;border-radius:12px;padding:18px 20px;line-height:1.9;margin:10px 0}
.radar-table-scroll {overflow:auto;max-height:440px;border:1px solid #30465e;border-radius:12px;margin:8px 0 15px;background:#111f32}
.radar-table {border-collapse:separate;border-spacing:0;width:100%;min-width:560px;color:#e4eefc;font-size:13px}
.radar-table th {position:sticky;top:0;background:#1b304b;color:#edf5ff;font-weight:700;text-align:left;padding:12px;border-bottom:1px solid #38526d;white-space:nowrap}
.radar-table td {background:#111f32;color:#e3edf9;padding:11px 12px;border-bottom:1px solid #263950;white-space:nowrap}
.radar-table tbody tr:nth-child(even) td {background:#17283e}
.radar-table tbody tr:hover td {background:#223b56}
@media(max-width:900px) {.block-container{padding-left:1rem;padding-right:1rem}.radar-hero{padding:14px}.radar-panel{padding:14px}}
</style>
""", unsafe_allow_html=True)


def section(num_label, title):
    st.markdown(f'<div class="radar-section">{escape(num_label)} / {escape(title)}</div>', unsafe_allow_html=True)


def panel(title, main, note="", tone=""):
    st.markdown('<div class="radar-panel"><div class="radar-panel-title">'
                + escape(str(title)) + '</div><div class="radar-panel-main '
                + escape(tone) + '">' + escape(str(main)) + '</div>'
                + ('<div class="radar-panel-note">' + escape(str(note)) + '</div>' if note else '')
                + '</div>', unsafe_allow_html=True)


def safeval(row, key):
    return row.get(key) if row is not None else None


def sign_class(v):
    v = num(v)
    return 'radar-green' if pd.notna(v) and v > 0 else 'radar-red' if pd.notna(v) and v < 0 else ''

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
st.sidebar.caption("資料由 GitHub Actions 每日產生，非即時行情")
st.sidebar.caption("v2.0 測試版｜選股策略及資料管線維持不變")

st.markdown('<div class="radar-eyebrow">TAIWAN STOCK RADAR · RESEARCH TERMINAL</div>', unsafe_allow_html=True)
st.title("📈 Taiwan Stock Radar")
st.caption("台股智慧選股與個股決策｜FIRE 技術訊號 × TDCC 大戶籌碼")
if not prices.empty:
    st.caption(f"📅 股價資料更新至 {datefmt(prices['date'].max())}｜非即時行情")
else:
    st.warning("尚未讀取到歷史股價 CSV。")

tab1, tab2, tab3 = st.tabs(["🏆 每日精選", "📊 個股決策終端", "🗂️ 歷史研究紀錄"])

with tab1:
    section("01", "今日 FIRE × TDCC 精選")
    st.markdown('<div class="radar-hero"><h2>今日策略觀察清單</h2><div class="radar-muted">依原有 FIRE 與 TDCC 策略排序；分數代表選股優先順序，不代表預期報酬。</div></div>', unsafe_allow_html=True)
    if picks.empty:
        st.info("尚無每日精選資料。")
    else:
        ordered = picks.copy()
        if "combined_rank" in ordered.columns:
            ordered = ordered.assign(_rank=num(ordered["combined_rank"])).sort_values("_rank").drop(columns="_rank")
        best = ordered.iloc[0]
        a,b,c = st.columns(3)
        with a: panel("本日候選檔數", str(len(ordered)), "依當日 CSV 紀錄")
        with b: panel("排名第一", f"{best.get('stock_id','—')} {best.get('stock_name','')}", "綜合策略排名")
        with c: panel("最高綜合分數", fmt(best.get("combined_score")), "不是預測報酬率")
        section("02", "候選股票比較")
        display_table(ordered, ["combined_rank","stock_id","stock_name","close","fire_score","tdcc_score","combined_score","breakout_status","tdcc_trend"])
        if "date" in ordered.columns:
            st.caption(f"選股日期：{datefmt(ordered.iloc[0]['date'])}")
        st.caption("可從左側搜尋股票代號，切換至『個股決策終端』深入檢視。")

with tab2:
    pr = stock_rows(prices, stock_id)
    sr = latest(signals, stock_id)
    tr = latest(tdcc, stock_id)
    ir = latest(indicators, stock_id)
    wr = stock_rows(weekly, stock_id)
    name = "個股"
    for source in [sr, tr, pr.iloc[-1] if not pr.empty else None]:
        if source is not None and pd.notna(source.get("stock_name")):
            name = str(source.get("stock_name"))
            break
    close = pr.iloc[-1]["close"] if not pr.empty else None
    previous = pr.iloc[-2]["close"] if len(pr) >= 2 else None
    change = (float(close)/float(previous)-1)*100 if pd.notna(close) and pd.notna(previous) and previous > 0 else None
    fire = str(sr.get("signal", "—")).strip().upper() if sr is not None else "—"
    trend_raw = str(tr.get("trend", "")).strip().upper() if tr is not None else ""
    trend = TREND.get(trend_raw, "無資料")
    c4 = num(safeval(tr,"change_4w_pp"))
    c12 = num(safeval(tr,"change_12w_pp"))
    agreement = ("同向" if fire == "FIRE" and trend_raw == "ACCUMULATING" else
                 "分歧" if fire == "FIRE" and trend_raw == "DISTRIBUTING" else
                 "資料不足" if sr is None or tr is None else "待確認")
    st.markdown(f'<div class="radar-hero"><div class="radar-eyebrow">STOCK INTELLIGENCE / {escape(stock_id)}</div><h2>{escape(stock_id)}　{escape(name)}</h2><div class="radar-muted">股價：{datefmt(pr.iloc[-1]["date"]) if not pr.empty else "—"}　｜　FIRE：{datefmt(safeval(sr,"date"))}　｜　TDCC：{datefmt(safeval(tr,"date"))}</div></div>', unsafe_allow_html=True)

    section("01", "決策快照")
    c1,c2,c3,c4col = st.columns(4)
    with c1: panel("最新收盤價", fmt(close,2," 元"), f"較前一交易日 {change:+.2f}%" if change is not None else "無前日資料",sign_class(change))
    with c2: panel("FIRE 技術訊號", SIGNAL.get(fire,fire), "來源：歷史技術訊號")
    with c3: panel("TDCC 大戶方向", trend, "來源：TDCC 籌碼分析")
    with c4col: panel("技術 × 籌碼", agreement, "依兩項訊號規則交叉比對")

    if sr is None or tr is None:
        verdict = "技術或籌碼資料不足，暫無法完成雙訊號判讀。"
    else:
        verdict = ("FIRE 技術訊號成立；" if fire == "FIRE" else f"技術訊號為 {SIGNAL.get(fire,fire)}；") + f"TDCC 顯示{trend}。"
        if pd.notna(c4) and pd.notna(c12):
            verdict += f"近 4 週持股變化 {c4:+.2f} 個百分點，近 12 週 {c12:+.2f} 個百分點。"
            if c4 < 0 < c12: verdict += "中期略增、短期略減，留意籌碼轉折。"
            elif c12 < 0 < c4: verdict += "中期略減、短期回升，仍需持續觀察。"
    st.markdown('<div class="radar-verdict"><strong>綜合判讀</strong>　'+escape(verdict)+'</div>',unsafe_allow_html=True)
    st.caption("本判讀為透明規則式整理，不是 AI 股價預測或買賣建議；不同資料的更新日期可能不同。")

    section("02", "市場走勢與交叉證據")
    left,right = st.columns([1.7,1],gap="large")
    with left:
        st.markdown("#### 📈 股價與移動平均線")
        price_chart(pr)
    with right:
        st.markdown("#### 🔥 FIRE 技術動能")
        x,y = st.columns(2)
        with x: panel("RSI (14)",fmt(safeval(sr,"rsi14")),"相對強弱指標")
        with y: panel("成交量倍數",fmt(safeval(sr,"volume_ratio"),2," 倍"),"相對基準成交量")
        x,y = st.columns(2)
        with x: panel("相對 MA10",fmt(safeval(sr,"price_vs_ma10_pct"),2,"%"),"收盤價相對 10 日均線")
        with y: panel("相對 MA20",fmt(safeval(sr,"price_vs_ma20_pct"),2,"%"),"收盤價相對 20 日均線")
        st.caption(f"FIRE 排名分數 {fmt(safeval(sr,'rank_score'))}｜近期高點距離 {fmt(safeval(sr,'near_high_pct'),2,'%')}")
        st.caption(f"FIRE 確認條件 {fmt(safeval(sr,'fire_confirmations'),0)}｜SETUP 確認條件 {fmt(safeval(sr,'setup_confirmations'),0)}")
        st.markdown("#### 🏦 TDCC 籌碼結構")
        x,y = st.columns(2)
        with x: panel("大戶持股比例",fmt(safeval(tr,"big_holder_pct"),2,"%"),"最新可取得的 TDCC 資料")
        with y: panel("近 4 週變化",fmt(c4,2," pp"),"百分點變化",sign_class(c4))
        x,y = st.columns(2)
        with x: panel("近 12 週變化",fmt(c12,2," pp"),"百分點變化",sign_class(c12))
        with y: panel("分析週數",fmt(safeval(tr,"period_count"),0),"資料覆蓋")
    section("03", "大戶持股軌跡")
    if not wr.empty and {"date","big_holder_pct"}.issubset(wr.columns):
        wr["big_holder_pct"] = num(wr["big_holder_pct"])
        wr = wr.dropna(subset=["date","big_holder_pct"]).drop_duplicates("date",keep="last")
        if not wr.empty:
            tc = go.Figure(go.Scatter(x=wr["date"],y=wr["big_holder_pct"],mode="lines+markers",name="大戶持股比例",line=dict(color="#38bdf8",width=2.5),marker=dict(size=6),hovertemplate="%{x|%Y-%m-%d}<br>%{y:.2f}%<extra></extra>"))
            chart_style(tc,285)
            tc.update_yaxes(ticksuffix="%")
            st.plotly_chart(tc,use_container_width=True)
            st.caption(f"TDCC 週資料：{datefmt(wr['date'].min())} ～ {datefmt(wr['date'].max())}｜{len(wr)} 筆")
        else: st.info("目前沒有有效的 TDCC 每週資料。")
    else: st.info("目前沒有此股票的 TDCC 每週持股紀錄。")

    section("04", "技術指標與風險觀察")
    a,b,c,d = st.columns(4)
    with a: panel("10 日均線",fmt(safeval(ir,"ma10")),"最新技術指標")
    with b: panel("20 日均線",fmt(safeval(ir,"ma20")),"最新技術指標")
    with c: panel("RSI (14)",fmt(safeval(ir,"rsi14")),"最新技術指標")
    with d: panel("突破距離",fmt(safeval(ir,"breakout_distance_pct"),2,"%"),"依原有計算口徑")
    warnings = []
    rsi = num(safeval(sr,"rsi14"))
    if pd.notna(rsi) and rsi >= 70: warnings.append("RSI 達 70 以上，注意短線波動。")
    if pd.notna(c4) and c4 < 0: warnings.append("近 4 週大戶持股比例下降。")
    if change is not None and abs(change) >= 7: warnings.append("最近一個交易日股價波動較大。")
    if not warnings: warnings.append("目前未觸發本頁設定的簡易觀察條件；不代表沒有投資風險。")
    st.markdown('<div class="radar-verdict"><strong>風險觀察</strong>　'+escape(' '.join(warnings))+'</div>',unsafe_allow_html=True)
    st.caption("風險提示只依 RSI、持股變化及單日漲跌等可驗證條件產生，不是風險機率或價格預測。")

    section("05", "研究資料庫")
    st.caption("原始 CSV 資料完整保留，供追溯與驗證；以下表格可左右捲動。")
    with st.expander("📋 技術指標原始資料",expanded=False):
        display_table(stock_rows(indicators,stock_id),["date","close","ma10","ma20","rsi14","volume_ratio","breakout_distance_pct"])
    with st.expander("🔥 FIRE 歷史技術訊號",expanded=False):
        display_table(stock_rows(signals,stock_id),["date","close","signal","rsi14","volume_ratio","rank_score"])
    with st.expander("🏦 TDCC 籌碼分析明細",expanded=False):
        display_table(stock_rows(tdcc,stock_id),["date","big_holder_pct","change_4w_pp","change_12w_pp","trend"])
    with st.expander("📈 TDCC 每週持股紀錄",expanded=False):
        display_table(wr,["date","big_holder_pct"])

with tab3:
    section("01","歷史策略紀錄")
    st.markdown('<div class="radar-hero"><h2>歷史選股資料庫</h2><div class="radar-muted">回看每日 FIRE × TDCC 候選股票，資料與原始策略保持一致。</div></div>',unsafe_allow_html=True)
    if history.empty:
        st.info("尚未建立選股歷史紀錄。")
    else:
        h=history.copy()
        if "date" in h.columns: h=h.sort_values("date",ascending=False)
        a,b,c=st.columns(3)
        with a: panel("累計紀錄",f"{len(h):,} 筆")
        with b: panel("涵蓋日期",f"{h['date'].nunique()} 天" if "date" in h.columns else "—")
        with c: panel("最新紀錄",datefmt(h.iloc[0]["date"]) if "date" in h.columns else "—")
        section("02","選股歷史明細")
        display_table(h)

st.divider()
st.caption("Taiwan Stock Radar v2.0 測試版｜僅供研究參考，不構成投資建議。")
