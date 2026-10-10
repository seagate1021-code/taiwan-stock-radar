
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Taiwan Stock Radar",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 讀取 GitHub Actions 已產生的資料
HISTORY_PATH = Path("data/history/twse_daily.csv")
PICKS_PATH = Path("data/history/combined_top_picks.csv")
PICKS_HISTORY_PATH = Path("data/history/combined_picks_history.csv")
INDICATORS_PATH = Path("data/reports/technical_indicators.csv")
TDCC_PATH = Path("data/history/tdcc_analysis.csv")
TDCC_WEEKLY_PATH = Path("data/history/tdcc_weekly.csv")
SIGNALS_PATH = Path("data/history/stock_signals.csv")


@st.cache_data(ttl=300)
def read_csv(path):
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(
            path,
            dtype={"stock_id": str},
            encoding="utf-8-sig",
        )
    except (pd.errors.EmptyDataError, UnicodeError):
        return pd.DataFrame()


def prepare_prices(df):
    if df.empty:
        return df

    required = {"stock_id", "date", "close"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df = df.copy()
    df["stock_id"] = df["stock_id"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["close"] = pd.to_numeric(df["close"], errors="coerce")

    for column in ["open", "high", "low", "volume"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")

    df = df.dropna(subset=["date", "close"])
    df = df.sort_values("date").drop_duplicates(
        subset=["stock_id", "date"],
        keep="last",
    )
    return df


def format_number(value, digits=2):
    if pd.isna(value):
        return "—"
    try:
        return f"{float(value):,.{digits}f}"
    except (ValueError, TypeError):
        return str(value)


def show_price_chart(stock_prices):
    stock_prices = stock_prices.sort_values("date").copy()

    period = st.radio(
        "📅 股價圖時間區間",
        ["近 1 個月", "近 3 個月", "近 6 個月", "近 1 年", "全部"],
        index=2,
        horizontal=True,
        key="price_chart_period",
    )

    has_ohlc = all(
        column in stock_prices.columns
        for column in ["open", "high", "low", "close"]
    )

    if has_ohlc and stock_prices[
        ["open", "high", "low", "close"]
    ].notna().all(axis=1).any():
        chart_prices = stock_prices.dropna(
            subset=["open", "high", "low", "close"]
        )

        fig = go.Figure(
            data=[
                go.Candlestick(
                    x=chart_prices["date"],
                    open=chart_prices["open"],
                    high=chart_prices["high"],
                    low=chart_prices["low"],
                    close=chart_prices["close"],
                    name="K 線",
                    increasing_line_color="#ef5350",
                    decreasing_line_color="#26a69a",
                )
            ]
        )
        fig.update_layout(xaxis_rangeslider_visible=False)
    else:
        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=stock_prices["date"],
                y=stock_prices["close"],
                mode="lines",
                name="收盤價",
                line=dict(color="#7c9cff", width=2),
            )
        )

    for days, color in [
        (5, "#ffb74d"),
        (10, "#66bb6a"),
        (20, "#ef5350"),
    ]:
        if len(stock_prices) >= days:
            ma = stock_prices["close"].rolling(days).mean()
            fig.add_trace(
                go.Scatter(
                    x=stock_prices["date"],
                    y=ma,
                    mode="lines",
                    name=f"MA{days}",
                    line=dict(color=color, width=1.5),
                )
            )

    fig.update_layout(
        template="plotly_dark",
        height=440,
        margin=dict(l=10, r=10, t=20, b=10),
        paper_bgcolor="#101827",
        plot_bgcolor="#101827",
        xaxis_title="日期",
        yaxis_title="價格（元）",
        legend=dict(orientation="h", y=1.12),
    )

    st.plotly_chart(fig, use_container_width=True)


st.markdown(
    """
    
<style>
/* ===== 整體深色背景 ===== */
.stApp {
    background: linear-gradient(
        160deg,
        #080f1d 0%,
        #0b1527 55%,
        #0d1a2f 100%
    );
    color: #e8eefc;
}

/* ===== 側邊欄 ===== */
[data-testid="stSidebar"] {
    background: #0c1729;
    border-right: 1px solid #24334c;
}

[data-testid="stSidebar"] * {
    color: #e8eefc;
}

/* ===== 標題 ===== */
h1, h2, h3 {
    color: #eaf1ff;
    letter-spacing: 0.3px;
}

h1 {
    font-weight: 800;
}

h2, h3 {
    font-weight: 700;
}

/* ===== 指標卡片 ===== */
[data-testid="stMetric"] {
    background: linear-gradient(
        145deg,
        #14243b,
        #101c30
    );
    padding: 18px;
    border: 1px solid #2a3d58;
    border-radius: 14px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
}

[data-testid="stMetricLabel"] {
    color: #9fb4d2;
}

[data-testid="stMetricValue"] {
    color: #f1f6ff;
    font-weight: 700;
}

/* ===== 頁籤 ===== */
.stTabs [data-baseweb="tab-list"] {
    gap: 10px;
    border-bottom: 1px solid #263a55;
}

.stTabs [data-baseweb="tab"] {
    background: #132239;
    border: 1px solid #263a55;
    border-radius: 10px 10px 0 0;
    color: #c5d5ed;
    padding: 10px 18px;
}

.stTabs [aria-selected="true"] {
    background: #193451;
    color: #ffffff;
    border-bottom: 2px solid #38bdf8;
}

/* ===== 資料表格 ===== */
[data-testid="stDataFrame"] {
    border: 1px solid #2a3d58;
    border-radius: 12px;
    overflow: hidden;
}

/* ===== 輸入框 ===== */
.stTextInput input {
    background: #14243b;
    color: #f1f6ff;
    border: 1px solid #304764;
    border-radius: 9px;
}

/* ===== 展開區塊 ===== */
[data-testid="stExpander"] {
    background: #101d30;
    border: 1px solid #2a3d58;
    border-radius: 12px;
}

/* ===== 分隔線 ===== */
hr {
    border-color: #293b55;
}
</style>
    """,
    unsafe_allow_html=True,
)

st.title("📈 Taiwan Stock Radar")
st.caption("台股智慧選股與個股分析系統｜非即時行情")

prices = prepare_prices(read_csv(HISTORY_PATH))
picks = read_csv(PICKS_PATH)
picks_history = read_csv(PICKS_HISTORY_PATH)
indicators = read_csv(INDICATORS_PATH)
tdcc = read_csv(TDCC_PATH)
tdcc_weekly = read_csv(TDCC_WEEKLY_PATH)
signals = read_csv(SIGNALS_PATH)

if not picks.empty and "combined_rank" in picks.columns:
    picks["combined_rank"] = pd.to_numeric(
        picks["combined_rank"], errors="coerce"
    )
    picks = picks.sort_values("combined_rank")

if not prices.empty:
    latest_date = prices["date"].max().strftime("%Y-%m-%d")
    st.info(f"📅 歷史股價資料最新日期：{latest_date}")
else:
    st.warning("目前找不到歷史股價資料，請確認 GitHub 已儲存 CSV。")

st.sidebar.header("🔎 個股搜尋")
typed_stock_id = st.sidebar.text_input(
    "輸入股票代號",
    value="3416",
    placeholder="例如 2330、2317、3416",
).strip()

quick_options = ["自行輸入"]

if not picks.empty and "stock_id" in picks.columns:
    for _, item in picks.iterrows():
        sid = str(item["stock_id"]).strip()
        name = str(item.get("stock_name", ""))
        quick_options.append(f"{sid} {name}")

quick_pick = st.sidebar.selectbox(
    "或直接選擇今日精選股票",
    quick_options,
)

stock_id = (
    typed_stock_id
    if quick_pick == "自行輸入"
    else quick_pick.split(" ")[0]
)

st.sidebar.divider()
st.sidebar.caption("資料來源：GitHub Actions 每日更新的 CSV")
st.sidebar.caption("個股搜尋目前限於已收錄的股票資料。")

tab1, tab2, tab3 = st.tabs(
    ["🏆 每日智慧選股", "📊 個股技術分析", "🗂️ 歷史選股紀錄"]
)

with tab1:
    st.subheader("FIRE + TDCC 綜合前五名")

    if picks.empty:
        st.warning("找不到 combined_top_picks.csv。")
    else:
        display_columns = [
            "combined_rank",
            "stock_id",
            "stock_name",
            "close",
            "fire_score",
            "tdcc_score",
            "combined_score",
            "breakout_status",
            "tdcc_trend",
        ]
        available = [
            column for column in display_columns
            if column in picks.columns
        ]

        st.dataframe(
            picks[available],
            use_container_width=True,
            hide_index=True,
        )

        if "date" in picks.columns:
            st.caption(
                f"選股資料日期：{picks['date'].iloc[0]}"
            )

        st.caption(
            "綜合分數是選股策略評分，不代表預測報酬率。"
        )

with tab2:
    st.subheader(f"股票代號：{stock_id}")

    # ===== FIRE + TDCC 個股綜合分析 =====
    st.subheader("🎯 FIRE + TDCC 綜合分析")

    def latest_stock_row(df, code):
        if df.empty or "stock_id" not in df.columns:
            return None

        rows = df[
            df["stock_id"].astype(str).str.strip()
            == str(code).strip()
        ].copy()

        if rows.empty:
            return None

        if "date" in rows.columns:
            rows["date"] = pd.to_datetime(
                rows["date"], errors="coerce"
            )
            rows = rows.sort_values(
                "date", ascending=False
            )

        return rows.iloc[0]

    fire_row = latest_stock_row(signals, stock_id)
    tdcc_row = latest_stock_row(tdcc, stock_id)

    if fire_row is None and tdcc_row is None:
        st.info("目前沒有此股票的 FIRE 或 TDCC 分析資料。")
    else:
        fire_signal = "無資料"
        fire_score = "—"
        tdcc_direction = "無資料"

        if fire_row is not None:
            raw_signal = fire_row.get("signal")
            if pd.notna(raw_signal):
                fire_signal = str(raw_signal).strip()

            score = pd.to_numeric(
                fire_row.get("rank_score"),
                errors="coerce"
            )
            if pd.notna(score):
                fire_score = f"{score:.2f}"

        if tdcc_row is not None:
            raw_trend = tdcc_row.get("trend")
            trend = (
                str(raw_trend).strip().upper()
                if pd.notna(raw_trend)
                else ""
            )

            tdcc_direction = {
                "ACCUMULATING": "大戶增持",
                "DISTRIBUTING": "大戶減持",
                "NEUTRAL": "籌碼持平",
            }.get(trend, trend or "無資料")

        c1, c2, c3 = st.columns(3)

        c1.metric("FIRE 技術訊號", fire_signal)
        c2.metric("技術排名分數", fire_score)
        c3.metric("TDCC 籌碼方向", tdcc_direction)

        if fire_row is None or tdcc_row is None:
            interpretation = "資料不足，暫無法綜合判讀"
        elif (
            fire_signal.upper() == "FIRE"
            and tdcc_direction == "大戶增持"
        ):
            interpretation = "🔥 FIRE 訊號與大戶增持同向"
        elif (
            fire_signal.upper() == "FIRE"
            and tdcc_direction == "大戶減持"
        ):
            interpretation = "⚠️ FIRE 訊號與大戶籌碼分歧"
        elif tdcc_direction == "大戶增持":
            interpretation = "📈 大戶增持，技術訊號尚未達 FIRE"
        elif tdcc_direction == "大戶減持":
            interpretation = "📉 大戶減持，留意籌碼變化"
        else:
            interpretation = "技術與籌碼方向尚不明確"

        st.info(f"**綜合判讀：{interpretation}**")

        st.caption(
            "此為規則式技術與籌碼訊號整理，"
            "並非股價預測或買賣建議。"
        )

    st.divider()

    # ===== 個股 FIRE 技術訊號 =====
    st.subheader("🔥 FIRE 技術訊號分析")

    if signals.empty:
        st.info("目前尚無技術訊號資料。")
    elif not stock_id:
        st.info("請先輸入股票代號。")
    else:
        stock_signals = signals[
            signals["stock_id"].astype(str).str.strip()
            == str(stock_id).strip()
        ].copy()

        if stock_signals.empty:
            st.info("此股票目前沒有技術訊號資料。")
        else:
            stock_signals["date"] = pd.to_datetime(
                stock_signals["date"], errors="coerce"
            )
            stock_signals = stock_signals.sort_values(
                "date", ascending=False
            )

            latest = stock_signals.iloc[0]

            def signal_text(value):
                if pd.isna(value):
                    return "—"
                return str(value)

            def signal_number(value, digits=2):
                number = pd.to_numeric(value, errors="coerce")
                if pd.isna(number):
                    return "—"
                return f"{number:.{digits}f}"

            st.caption(
                f"股票：{signal_text(latest['stock_name'])} "
                f"({stock_id})｜"
                f"資料日期：{latest['date'].strftime('%Y-%m-%d')}"
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "最新訊號",
                signal_text(latest["signal"])
            )
            c2.metric(
                "選股排名分數",
                signal_number(latest["rank_score"])
            )
            c3.metric(
                "RSI (14)",
                signal_number(latest["rsi14"])
            )
            c4.metric(
                "成交量倍數",
                signal_number(latest["volume_ratio"]) + " 倍"
            )

            c5, c6, c7, c8 = st.columns(4)

            c5.metric(
                "接近近期高點",
                signal_number(latest["near_high_pct"]) + "%"
            )
            c6.metric(
                "相對 MA10",
                signal_number(latest["price_vs_ma10_pct"]) + "%"
            )
            c7.metric(
                "相對 MA20",
                signal_number(latest["price_vs_ma20_pct"]) + "%"
            )
            c8.metric(
                "熱門標記",
                signal_text(latest["hot_flag"])
            )

            st.write("**訊號確認條件**")
            st.write(
                "FIRE：",
                signal_text(latest["fire_confirmations"])
            )
            st.write(
                "SETUP：",
                signal_text(latest["setup_confirmations"])
            )

            with st.expander("查看此股票的歷史技術訊號"):
                st.dataframe(
                    stock_signals[
                        [
                            "date",
                            "close",
                            "signal",
                            "rsi14",
                            "volume_ratio",
                            "rank_score",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

    st.divider()

    # ===== TDCC 大戶籌碼分析 =====
    st.subheader("🏦 TDCC 大戶籌碼分析")

    if tdcc.empty:
        st.info("目前尚無 TDCC 分析資料。")
    else:
        stock_tdcc = tdcc[
            tdcc["stock_id"].astype(str).str.strip()
            == str(stock_id).strip()
        ].copy()

        if stock_tdcc.empty:
            st.info("此股票目前沒有 TDCC 籌碼分析資料。")
        else:
            stock_tdcc["date"] = pd.to_datetime(
                stock_tdcc["date"], errors="coerce"
            )
            stock_tdcc = stock_tdcc.sort_values(
                "date", ascending=False
            )

            latest_tdcc = stock_tdcc.iloc[0]

            def tdcc_number(value, digits=2):
                number = pd.to_numeric(value, errors="coerce")
                if pd.isna(number):
                    return "—"
                return f"{number:.{digits}f}"

            trend_value = str(latest_tdcc["trend"]).strip().upper()

            trend_labels = {
                "ACCUMULATING": "🟢 大戶增持",
                "DISTRIBUTING": "🔴 大戶減持",
                "NEUTRAL": "⚪ 籌碼持平",
            }

            trend_label = trend_labels.get(
                trend_value, trend_value
            )

            st.caption(
                "TDCC 最新資料日期："
                + latest_tdcc["date"].strftime("%Y-%m-%d")
            )

            c1, c2, c3, c4 = st.columns(4)

            c1.metric(
                "大戶持股比例",
                tdcc_number(latest_tdcc["big_holder_pct"]) + "%"
            )
            c2.metric(
                "近 4 週變化",
                tdcc_number(latest_tdcc["change_4w_pp"]) + " 百分點"
            )
            c3.metric(
                "近 12 週變化",
                tdcc_number(latest_tdcc["change_12w_pp"]) + " 百分點"
            )
            c4.metric(
                "籌碼趨勢",
                trend_label
            )

            # ===== TDCC 4 週 / 12 週籌碼變化比較 =====
            st.markdown("#### 📊 大戶籌碼變化比較")

            change_4w = pd.to_numeric(
                latest_tdcc["change_4w_pp"],
                errors="coerce"
            )
            change_12w = pd.to_numeric(
                latest_tdcc["change_12w_pp"],
                errors="coerce"
            )

            if pd.notna(change_4w) or pd.notna(change_12w):
                import plotly.graph_objects as go

                labels = []
                values = []
                colors = []

                for label, value in [
                    ("近 4 週", change_4w),
                    ("近 12 週", change_12w),
                ]:
                    if pd.notna(value):
                        labels.append(label)
                        values.append(float(value))
                        colors.append(
                            "#22C55E" if value >= 0 else "#EF4444"
                        )

                fig_change = go.Figure(
                    go.Bar(
                        x=labels,
                        y=values,
                        marker_color=colors,
                        text=[f"{v:+.2f}" for v in values],
                        textposition="outside",
                        hovertemplate=(
                            "%{x}<br>持股比例變化："
                            "%{y:+.2f} 百分點"
                            "<extra></extra>"
                        ),
                    )
                )

                fig_change.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="#0B1220",
                    plot_bgcolor="#0B1220",
                    font=dict(color="#E2E8F0"),
                    height=320,
                    margin=dict(l=30, r=20, t=30, b=30),
                    xaxis_title="比較期間",
                    yaxis_title="持股比例變化（百分點）",
                    showlegend=False,
                )

                fig_change.add_hline(
                    y=0,
                    line_color="#94A3B8",
                    line_width=1,
                )

                st.plotly_chart(
                    fig_change,
                    use_container_width=True,
                )
            else:
                st.info("目前沒有足夠資料比較籌碼變化。")

            st.caption(
                "分析期間筆數："
                + str(latest_tdcc["period_count"])
            )

           
            # ===== TDCC 每週大戶持股趨勢圖 =====
            st.markdown("#### 📈 TDCC 每週大戶持股趨勢")

            if tdcc_weekly.empty:
                st.info("目前尚無 TDCC 每週歷史資料。")
            else:
                weekly_stock = tdcc_weekly[
                    tdcc_weekly["stock_id"].astype(str).str.strip()
                    == str(stock_id).strip()
                ].copy()

                if weekly_stock.empty:
                    st.info("此股票目前沒有 TDCC 每週歷史資料。")
                else:
                    weekly_stock["date"] = pd.to_datetime(
                        weekly_stock["date"], errors="coerce"
                    )
                    weekly_stock["big_holder_pct"] = pd.to_numeric(
                        weekly_stock["big_holder_pct"],
                        errors="coerce"
                    )

                    weekly_stock = weekly_stock.dropna(
                        subset=["date", "big_holder_pct"]
                    )
                    weekly_stock = weekly_stock.sort_values("date")
                    weekly_stock = weekly_stock.drop_duplicates(
                        subset=["date"], keep="last"
                    )

                    if weekly_stock.empty:
                        st.info("目前沒有可繪製的 TDCC 歷史資料。")
                    else:
                        import plotly.graph_objects as go

                        fig_tdcc = go.Figure()

                        fig_tdcc.add_trace(
                            go.Scatter(
                                x=weekly_stock["date"],
                                y=weekly_stock["big_holder_pct"],
                                mode="lines+markers",
                                name="大戶持股比例",
                                line=dict(
                                    color="#38BDF8",
                                    width=3
                                ),
                                marker=dict(size=6),
                                hovertemplate=(
                                    "日期：%{x|%Y-%m-%d}"
                                    "<br>大戶持股：%{y:.2f}%"
                                    "<extra></extra>"
                                ),
                            )
                        )

                        fig_tdcc.update_layout(
                            template="plotly_dark",
                            paper_bgcolor="#0B1220",
                            plot_bgcolor="#0B1220",
                            font=dict(color="#E2E8F0"),
                            height=380,
                            margin=dict(
                                l=20, r=20, t=30, b=20
                            ),
                            xaxis=dict(
                                title="資料日期",
                                tickformat="%Y-%m-%d",
                                showgrid=True,
                                gridcolor="#243247",
                            ),
                            yaxis=dict(
                                title="大戶持股比例 (%)",
                                ticksuffix="%",
                                showgrid=True,
                                gridcolor="#243247",
                            ),
                            hovermode="x unified",
                        )

                        st.plotly_chart(
                            fig_tdcc,
                            use_container_width=True,
                        )

                        st.caption(
                            f"共 {len(weekly_stock)} 週資料｜"
                            f"期間："
                            f"{weekly_stock['date'].min():%Y-%m-%d}"
                            f" ～ "
                            f"{weekly_stock['date'].max():%Y-%m-%d}"
                        )


            with st.expander("查看 TDCC 分析資料"):
                st.dataframe(
                    stock_tdcc[
                        [
                            "date",
                            "big_holder_pct",
                            "change_4w_pp",
                            "change_12w_pp",
                            "trend",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

    st.divider()

    if prices.empty:
        st.warning("歷史股價資料尚未準備好。")
    else:
        stock_prices = prices[
            prices["stock_id"] == stock_id
        ].sort_values("date")

        if stock_prices.empty:
            st.warning(
                f"找不到 {stock_id} 的歷史股價。"
                "這不一定代表股票代號錯誤，"
                "可能是目前資料庫尚未收錄。"
            )
        else:
            latest = stock_prices.iloc[-1]
            latest_close = latest["close"]

            previous_close = (
                stock_prices.iloc[-2]["close"]
                if len(stock_prices) >= 2
                else None
            )

            change_pct = (
                (latest_close / previous_close - 1) * 100
                if previous_close is not None and previous_close > 0
                else None
            )

            c1, c2, c3 = st.columns(3)

            c1.metric(
                "最新收盤價",
                f"{latest_close:,.2f}",
                (
                    f"{change_pct:+.2f}%"
                    if change_pct is not None
                    else None
                ),
            )
            c2.metric(
                "歷史資料筆數",
                f"{len(stock_prices):,}",
            )
            c3.metric(
                "最新交易日期",
                latest["date"].strftime("%Y-%m-%d"),
            )

            st.markdown("### K 線與均線")
            show_price_chart(stock_prices)

            if "volume" in stock_prices.columns:
                st.markdown("### 成交量")
                volume_fig = go.Figure(
                    go.Bar(
                        x=stock_prices["date"],
                        y=stock_prices["volume"],
                        marker_color="#648bff",
                    )
                )
                volume_fig.update_layout(
                    template="plotly_dark",
                    height=230,
                    margin=dict(l=10, r=10, t=10, b=10),
                    paper_bgcolor="#101827",
                    plot_bgcolor="#101827",
                    xaxis_title="日期",
                    yaxis_title="成交量（原始資料單位）",
                )
                st.plotly_chart(
                    volume_fig,
                    use_container_width=True,
                )

    st.markdown("### 技術指標")

    if not indicators.empty and "stock_id" in indicators.columns:
        stock_indicators = indicators[
            indicators["stock_id"].astype(str) == stock_id
        ].copy()

        if not stock_indicators.empty:
            if "date" in stock_indicators.columns:
                stock_indicators = stock_indicators.sort_values("date")

            latest_indicator = stock_indicators.iloc[-1]

            indicator_columns = [
                "date",
                "close",
                "ma10",
                "ma20",
                "rsi14",
                "volume_ratio",
                "breakout_distance_pct",
            ]

            indicator_data = {
                column: latest_indicator[column]
                for column in indicator_columns
                if column in stock_indicators.columns
            }

            st.dataframe(
                pd.DataFrame(
                    [indicator_data]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("目前沒有這檔股票的技術指標紀錄。")
    else:
        st.info("技術指標報表尚未準備好。")

with tab3:
    st.subheader("每日綜合選股歷史紀錄")

    if picks_history.empty:
        st.info("尚未建立選股歷史紀錄。")
    else:
        history = picks_history.copy()

        if "date" in history.columns:
            history = history.sort_values(
                "date", ascending=False
            )

        st.dataframe(
            history,
            use_container_width=True,
            hide_index=True,
        )

        st.caption(
            f"目前已保存 {len(history)} 筆選股紀錄。"
        )

st.divider()
st.caption(
    "Taiwan Stock Radar｜資料僅供研究與參考，"
    "不構成投資建議。"
)
