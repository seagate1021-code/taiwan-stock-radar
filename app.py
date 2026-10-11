from pathlib import Path
from html import escape
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

st.set_page_config(page_title="Taiwan Stock Radar | Investment Workspace", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

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
        plot_bgcolor="#101b2d", font=dict(color="#d9e6f7", family="Microsoft JhengHei, PingFang TC, Noto Sans TC, sans-serif", size=12),
        margin=dict(l=12, r=12, t=22, b=16), showlegend=showlegend,
        xaxis=dict(title=None, gridcolor="#26384e", zeroline=False, tickfont=dict(color="#b5c8df")),
        yaxis=dict(title=None, gridcolor="#26384e", zeroline=False, tickfont=dict(color="#b5c8df")),
        hovermode="x unified",
    )
    return fig

def price_chart(rows):
    """完整歷史計算指標、共用時間軸的專業技術分析組合圖。"""
    if rows.empty or not {"date", "close"}.issubset(rows.columns):
        st.info("目前沒有這檔股票的歷史股價。")
        return
    p = rows.copy()
    p["date"] = pd.to_datetime(p["date"], errors="coerce")
    p["close"] = pd.to_numeric(p["close"], errors="coerce")
    p = (p.dropna(subset=["date", "close"])
           .sort_values("date").drop_duplicates("date", keep="last"))
    if p.empty:
        st.info("目前沒有有效的收盤價資料。")
        return

    period = st.radio("技術分析時間區間", ["近 1 個月", "近 3 個月", "近 6 個月", "近 1 年", "全部"],
                      index=2, horizontal=True, key="v4_period")
    days = {"近 1 個月": 30, "近 3 個月": 90, "近 6 個月": 180, "近 1 年": 365}
    start = p["date"].max() - pd.Timedelta(days=days[period]) if period in days else p["date"].min()
    end = p["date"].max() + pd.Timedelta(days=2)

    # 指標以完整歷史計算，再截取選定期間，避免移動平均線與 RSI 在區間起點重算。
    for n in (5, 10, 20):
        p[f"ma{n}"] = p["close"].rolling(n, min_periods=n).mean()
    # 布林通道：20 日簡單移動平均 ± 2 倍母體標準差。
    bb_std = p["close"].rolling(20, min_periods=20).std(ddof=0)
    p["bb_upper"] = p["ma20"] + 2 * bb_std
    p["bb_lower"] = p["ma20"] - 2 * bb_std
    delta = p["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    p["rsi14_chart"] = 100 - 100 / (1 + rs)
    p.loc[(avg_loss == 0) & (avg_gain > 0), "rsi14_chart"] = 100
    p.loc[(avg_gain == 0) & (avg_loss > 0), "rsi14_chart"] = 0
    p.loc[(avg_gain == 0) & (avg_loss == 0), "rsi14_chart"] = 50

    visible = p.loc[p["date"] >= start].copy()
    has_volume = "volume" in p.columns and pd.to_numeric(visible["volume"], errors="coerce").notna().any()
    if has_volume:
        p["volume"] = pd.to_numeric(p["volume"], errors="coerce")
        visible = p.loc[p["date"] >= start].copy()
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.69, 0.13, 0.18], vertical_spacing=0.028)
    ohlc = {"open", "high", "low", "close"}.issubset(p.columns)
    if ohlc:
        for field in ("open", "high", "low"):
            visible[field] = pd.to_numeric(visible[field], errors="coerce")
        candles = visible.dropna(subset=["open", "high", "low", "close"])
    else:
        candles = pd.DataFrame()
    if not candles.empty and len(candles) == len(visible):
        fig.add_trace(go.Candlestick(x=candles["date"], open=candles["open"],
            high=candles["high"], low=candles["low"], close=candles["close"],
            name="K 線", increasing_line_color="#f87171", decreasing_line_color="#2dd4bf"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=visible["date"], y=visible["close"], name="收盤價",
            mode="lines", line=dict(color="#83b4ff", width=3.0)), row=1, col=1)
    for n, color in ((5, "#ffbd69"), (10, "#52d6a4"), (20, "#fa777b")):
        fig.add_trace(go.Scatter(x=visible["date"], y=visible[f"ma{n}"], name=f"MA{n}",
            mode="lines", line=dict(color=color, width=1.35),
            hovertemplate=f"%{{x|%Y-%m-%d}}<br>MA{n}：%{{y:,.2f}}<extra></extra>"), row=1, col=1)

    # 布林通道：降低填色透明度；上、下軌同屬一組圖例，主圖以價格為視覺重心。
    fig.add_trace(go.Scatter(
        x=visible["date"], y=visible["bb_lower"], name="布林通道",
        legendgroup="boll", showlegend=True, mode="lines",
        line=dict(color="#7d91b2", width=1.1, dash="dot"),
        hovertemplate="%{x|%Y-%m-%d}<br>布林下軌：%{y:,.2f}<extra></extra>"
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=visible["date"], y=visible["bb_upper"], name="布林上軌",
        legendgroup="boll", showlegend=False, mode="lines",
        line=dict(color="#7d91b2", width=1.1, dash="dot"),
        fill="tonexty", fillcolor="rgba(125,145,178,0.045)",
        hovertemplate="%{x|%Y-%m-%d}<br>布林上軌：%{y:,.2f}<extra></extra>"
    ), row=1, col=1)

    if has_volume:
        prev_close = p["close"].shift(1).reindex(visible.index)
        bar_colors = ["#f87171" if pd.notna(prev) and current >= prev else "#2dd4bf"
                      for current, prev in zip(visible["close"], prev_close)]
        fig.add_trace(go.Bar(x=visible["date"], y=visible["volume"], name="成交量",
            marker_color=bar_colors, showlegend=False,
            hovertemplate="%{x|%Y-%m-%d}<br>成交量：%{y:,.0f}<extra></extra>"), row=2, col=1)
    else:
        fig.add_annotation(x=0.5, y=0.29, xref="paper", yref="paper", text="無成交量資料",
                           showarrow=False, font=dict(color="#9cb0c8", size=12))

    fig.add_trace(go.Scatter(x=visible["date"], y=visible["rsi14_chart"],
        name="RSI (14)", mode="lines", line=dict(color="#b39aff", width=2.2),
        hovertemplate="%{x|%Y-%m-%d}<br>RSI (14)：%{y:.2f}<extra></extra>"), row=3, col=1)
    for level, color in ((70, "#fb7185"), (50, "#94a3b8"), (30, "#34d399")):
        fig.add_hline(y=level, row=3, col=1, line_color=color, line_width=1,
                      line_dash="dash", opacity=0.8)
        fig.add_annotation(x=1, y=level, xref="x3 domain", yref="y3",
                           text=str(level), xanchor="right", yanchor="bottom",
                           showarrow=False, font=dict(color=color, size=11), bgcolor="#101b2d")

    fig.update_layout(template="plotly_dark", height=770, autosize=True,
        paper_bgcolor="#101b2d", plot_bgcolor="#101b2d",
        font=dict(color="#d9e6f7", family="Microsoft JhengHei, PingFang TC, Noto Sans TC, sans-serif", size=12),
        margin=dict(l=16, r=22, t=72, b=32), hovermode="x unified",
        legend=dict(orientation="h", y=1.06, x=0, font=dict(color="#e5efff", size=12),
                     bgcolor="rgba(16,27,45,0)", traceorder="normal"),
        bargap=0.16, dragmode="pan")
    fig.update_xaxes(showgrid=True, gridcolor="#26384e", zeroline=False,
                     tickfont=dict(color="#b5c8df"), range=[start, end],
                     rangeslider_visible=False)
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)
    fig.update_xaxes(tickformat="%Y-%m-%d", nticks=7, row=3, col=1)
    fig.update_yaxes(showgrid=True, gridcolor="#26384e", zeroline=False,
                     tickfont=dict(color="#b5c8df"))
    fig.update_yaxes(tickformat="~s", nticks=4, row=2, col=1)
    fig.update_yaxes(range=[0, 100], dtick=20, row=3, col=1)
    fig.update_traces(hoverlabel=dict(bgcolor="#192e47", font_color="#eef6ff"))
    st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False, "scrollZoom": False})
    st.caption("主圖：收盤價、MA5／MA10／MA20、布林通道（20 日均線 ± 2 倍標準差）｜下方：成交量及 RSI(14)。"
               "共用日期軸；BOLL 前 19 筆及 RSI 前 14 筆歷史資料不顯示數值。")

st.markdown("""
<style>
:root {color-scheme:dark}
html, body, .stApp {background:#070e19!important;color:#e7eef8!important}
.stApp, .stApp * {font-family:"Microsoft JhengHei","PingFang TC","Noto Sans TC",system-ui,sans-serif!important}
[data-testid="stHeader"] {background:#070e19!important;height:2.1rem!important}
[data-testid="stSidebar"], [data-testid="collapsedControl"] {display:none!important}
.block-container {max-width:1660px!important;padding:2.3rem 2.4rem 4rem!important}
#MainMenu, footer {visibility:hidden}
.workspace-brand {display:flex;align-items:center;gap:12px;color:#f4f7fc;font-weight:850;font-size:1.13rem;letter-spacing:1.2px;padding:0 0 18px;border-bottom:1px solid #26344a;margin-bottom:20px}
.brand-mark {display:inline-flex;align-items:center;justify-content:center;width:37px;height:37px;border-radius:10px;background:#17416b;color:#74d2ff;font-size:1.5rem}
.brand-edition {color:#7189a5;font-size:.72rem;font-weight:650;letter-spacing:1.7px}
.workspace-subtitle {margin:3px 0 5px;color:#9aafc6;font-size:.83rem;letter-spacing:.2px}
.workspace-subtitle span {color:#5bb6e9}
.stApp [data-testid="stTextInput"] label p,.stApp [data-testid="stSelectbox"] label p {font-size:.7rem!important;font-weight:800!important;color:#83a4c8!important;letter-spacing:1px!important}
.stApp input,.stApp [data-baseweb="select"]>div {background:#111f32!important;border:1px solid #2a435e!important;color:#eaf4ff!important;border-radius:8px!important;min-height:43px!important}
.stTabs [data-baseweb="tab-list"] {background:#0d1828!important;border:1px solid #273950!important;border-radius:11px!important;padding:5px!important;gap:6px!important;margin:16px 0 20px!important}
.stTabs [data-baseweb="tab"] {padding:11px 22px!important;color:#9cb1ca!important;border-radius:7px!important;font-size:.92rem!important;font-weight:750!important}
.stTabs [aria-selected="true"] {background:#1d3d5d!important;color:#fff!important;border-bottom:none!important}
.instrument-header {display:flex;align-items:center;justify-content:space-between;gap:22px;background:linear-gradient(115deg,#12243b,#0d1b2d);border:1px solid #2d4661;border-radius:13px;padding:25px 30px;margin:10px 0 24px}
.instrument-overline {color:#59c8f7;font-size:.7rem;letter-spacing:1.6px;font-weight:800}
.instrument-title {font-size:2.25rem;font-weight:850;line-height:1.6;color:#fff}
.instrument-title span {font-size:1.42rem;font-weight:700;color:#c9d9ed;margin-left:12px}
.instrument-date {font-size:.77rem;color:#94aac3;letter-spacing:.25px}
.instrument-price {text-align:right;white-space:nowrap}
.price-caption {color:#8ca6c2;font-size:.67rem;font-weight:800;letter-spacing:1.3px}
.price-number {font-size:2.65rem;line-height:1.35;color:#f8fbff;font-weight:850;font-variant-numeric:tabular-nums}
.price-delta {font-size:.85rem;color:#9db4cb}
.radar-green {color:#3cdbad!important}.radar-red {color:#ff8290!important}
.radar-section {font-size:.72rem;color:#77bde7;font-weight:850;letter-spacing:1.45px;margin:29px 0 14px;padding-bottom:10px;border-bottom:1px solid #25374c}
.chart-head {display:flex;justify-content:space-between;align-items:center;gap:14px;margin:5px 0 7px}
.chart-head-main {font-size:1.08rem;color:#f4f8ff;font-weight:800;letter-spacing:.6px}
.chart-head-sub {color:#8ca7c1;font-size:.72rem;font-weight:650}
[data-testid="stPlotlyChart"] {border:1px solid #2a3b52;border-radius:12px;overflow:hidden;background:#0d192a!important}
.stApp [data-testid="stRadio"] {background:#0d192a;border-radius:8px;padding:6px 10px;margin:5px 0 12px}
.stApp [data-testid="stRadio"] label p {color:#c7d9ed!important;font-size:.78rem!important}
.radar-panel {background:#101e31;border:1px solid #2b4058;border-radius:10px;padding:17px 19px;margin:4px 0 12px;min-height:112px}
.radar-panel-title {color:#8ca8c5;font-size:.76rem;font-weight:700;margin-bottom:10px}
.radar-panel-main {color:#f5f9ff;font-size:1.52rem;font-weight:850;line-height:1.4;font-variant-numeric:tabular-nums}
.radar-panel-note {color:#8099b4;font-size:.73rem;margin-top:7px;line-height:1.5}
.radar-verdict {background:#102840;border:1px solid #305774;border-left:4px solid #4ac4ef;border-radius:9px;padding:17px 20px;margin:12px 0;color:#dbeaf9;line-height:1.9;font-size:.92rem}
.radar-hero {padding:23px 26px;border:1px solid #2a415b;border-radius:12px;background:linear-gradient(115deg,#122b46,#0c1b2e);margin:9px 0 20px}
.radar-hero h2 {font-size:1.4rem!important;margin:0 0 7px!important}
.radar-muted {color:#a2b8d0;font-size:.84rem}
.radar-table-scroll {overflow:auto;max-height:490px;border:1px solid #2b4058;border-radius:10px;background:#101c2d;margin:9px 0 17px}
.radar-table {border-collapse:separate;border-spacing:0;width:100%;min-width:600px;color:#e2edfb;font-size:13px}
.radar-table th {position:sticky;top:0;background:#20364f;color:#eaf5ff;text-align:left;padding:12px;border-bottom:1px solid #38526d;white-space:nowrap}
.radar-table td {background:#101c2d;padding:11px 12px;border-bottom:1px solid #26384b;white-space:nowrap}
.radar-table tbody tr:nth-child(even) td {background:#15263b}
.radar-table tbody tr:hover td {background:#213b57}
[data-testid="stExpander"] {background:#101e31;border:1px solid #2a405a;border-radius:10px}
[data-testid="stExpander"] summary {color:#eaf3ff!important}
[data-testid="stCaptionContainer"] p,.stApp small {color:#829bb6!important;font-size:.77rem!important}
[data-testid="stMarkdownContainer"] p {line-height:1.65}
.stApp h1,.stApp h2,.stApp h3,.stApp h4 {color:#eef6ff!important}
[data-testid="stAlert"] {background:#142a40!important;border:1px solid #325575!important;border-radius:9px}
hr {border-color:#25374c}
@media(max-width:900px) {.block-container{padding:1.5rem .9rem 3rem!important}.instrument-header{padding:17px;flex-direction:column;align-items:flex-start}.instrument-price{text-align:left}.instrument-title{font-size:1.7rem}.price-number{font-size:2rem}.brand-edition{display:none}.chart-head{flex-direction:column;align-items:flex-start}}
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

# V4 workspace navigation: search and navigation are visible, no hidden sidebar dependency.
st.markdown('<div class="workspace-brand"><span class="brand-mark">◈</span><span>TAIWAN STOCK RADAR</span><span class="brand-edition">/ INVESTMENT WORKSPACE</span></div>', unsafe_allow_html=True)
head_left, head_right = st.columns([1.05, 2.4], gap="large")
with head_left:
    typed = st.text_input("股票代號 / STOCK SEARCH", value="2330", placeholder="輸入代號，例如 2330")
with head_right:
    choices = ["自行輸入"]
    if not picks.empty and "stock_id" in picks.columns:
        for _, r in picks.iterrows():
            choices.append(f"{str(r['stock_id']).strip()} {str(r.get('stock_name', ''))}")
    chosen = st.selectbox("快速切換 / TODAY'S WATCHLIST", choices)
stock_id = typed.strip() if chosen == "自行輸入" else chosen.split()[0]
st.markdown('<div class="workspace-subtitle">市場研究工作台 <span>／</span> FIRE 技術訊號 <span>×</span> TDCC 大戶籌碼 <span>／</span> 每日批次資料 · 非即時行情</div>', unsafe_allow_html=True)
if not prices.empty:
    st.caption(f"股價資料更新至 {datefmt(prices['date'].max())}｜來源：GitHub Actions 每日資料")
else:
    st.warning("尚未讀取到歷史股價 CSV。")
tab2, tab1, tab3 = st.tabs(["◈  個股工作台", "▦  每日選股", "▤  歷史研究"])

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
    st.markdown(f'<div class="instrument-header"><div><div class="instrument-overline">EQUITY / TWSE · {escape(stock_id)}</div><div class="instrument-title">{escape(stock_id)} <span>{escape(name)}</span></div><div class="instrument-date">PRICE {datefmt(pr.iloc[-1]["date"]) if not pr.empty else "—"}　·　FIRE {datefmt(safeval(sr,"date"))}　·　TDCC {datefmt(safeval(tr,"date"))}</div></div><div class="instrument-price"><div class="price-caption">LAST CLOSE · TWD</div><div class="price-number">{fmt(close)}</div><div class="price-delta {sign_class(change)}">{f"{change:+.2f}%" if change is not None else "—"} / 前一交易日</div></div></div>', unsafe_allow_html=True)

    section("01", "PRICE ACTION / 核心技術圖表")
    st.markdown('<div class="chart-head"><span class="chart-head-main">PRICE INTELLIGENCE</span><span class="chart-head-sub">MA 5 / 10 / 20　·　BOLL 20 / 2　·　VOL　·　RSI 14</span></div>', unsafe_allow_html=True)
    price_chart(pr)

    section("02", "SIGNAL SNAPSHOT / 決策快照")
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

    section("03", "RESEARCH PANELS / 交叉證據")
    evidence_left, evidence_right = st.columns(2, gap="large")
    with evidence_left:
        st.markdown("#### 🔥 FIRE 技術動能")
        a, b = st.columns(2)
        with a: panel("RSI (14)", fmt(safeval(sr,"rsi14")), "相對強弱指標")
        with b: panel("成交量倍數", fmt(safeval(sr,"volume_ratio"),2," 倍"), "相對基準成交量")
        a, b = st.columns(2)
        with a: panel("相對 MA10",fmt(safeval(sr,"price_vs_ma10_pct"),2,"%"),"收盤價相對 10 日均線")
        with b: panel("相對 MA20",fmt(safeval(sr,"price_vs_ma20_pct"),2,"%"),"收盤價相對 20 日均線")
        st.caption(f"FIRE 排名分數：{fmt(safeval(sr,'rank_score'))}｜近期高點距離：{fmt(safeval(sr,'near_high_pct'),2,'%')}")
        st.caption(f"FIRE 確認條件：{fmt(safeval(sr,'fire_confirmations'),0)}｜SETUP 確認條件：{fmt(safeval(sr,'setup_confirmations'),0)}")
    with evidence_right:
        st.markdown("#### 🏦 TDCC 大戶籌碼")
        a, b = st.columns(2)
        with a: panel("大戶持股比例",fmt(safeval(tr,"big_holder_pct"),2,"%"),"最新 TDCC 資料")
        with b: panel("近 4 週變化",fmt(c4,2," pp"),"百分點變化",sign_class(c4))
        a, b = st.columns(2)
        with a: panel("近 12 週變化",fmt(c12,2," pp"),"百分點變化",sign_class(c12))
        with b: panel("分析週數",fmt(safeval(tr,"period_count"),0),"資料覆蓋")
        st.caption(f"技術 × 籌碼交叉判讀：{agreement}｜籌碼方向：{trend}")

    section("04", "籌碼歷史 / HOLDER TREND")
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

    section("05", "風險雷達 / RISK MONITOR")
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

    section("06", "資料研究室 / RESEARCH DATA")
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
st.caption("Taiwan Stock Radar v4.0 Investment Workspace 測試版｜僅供研究參考，不構成投資建議。")
