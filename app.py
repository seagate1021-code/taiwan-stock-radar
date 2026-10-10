
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
PICKS_PATH = Path("data/reports/combined_top_picks.csv")
PICKS_HISTORY_PATH = Path("data/history/combined_picks_history.csv")
INDICATORS_PATH = Path("data/reports/technical_indicators.csv")
TDCC_PATH = Path("data/reports/tdcc_analysis.csv")


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
    .stApp {
        background-color: #080f1d;
        color: #e8eefc;
    }
    [data-testid="stMetric"] {
        background: #111d30;
        padding: 15px;
        border: 1px solid #23334d;
        border-radius: 12px;
    }
    h1, h2, h3 {
        color: #eaf1ff;
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

    st.markdown("### FIRE + TDCC 綜合分析")

    if not picks.empty and "stock_id" in picks.columns:
        matched = picks[
            picks["stock_id"].astype(str) == stock_id
        ]

        if not matched.empty:
            item = matched.iloc[0]
            c1, c2, c3 = st.columns(3)

            c1.metric(
                "FIRE 分數",
                format_number(item.get("fire_score")),
            )
            c2.metric(
                "TDCC 分數",
                format_number(item.get("tdcc_score"), 0),
            )
            c3.metric(
                "綜合分數",
                format_number(item.get("combined_score")),
            )

            st.success(
                "突破狀態："
                + str(item.get("breakout_status", "—"))
                + "｜大戶趨勢："
                + str(item.get("tdcc_trend", "—"))
            )
        else:
            st.info(
                "這檔股票不在本次綜合前五名。"
                "不代表它沒有 FIRE 訊號。"
            )

    if not tdcc.empty and "stock_id" in tdcc.columns:
        matched_tdcc = tdcc[
            tdcc["stock_id"].astype(str) == stock_id
        ]

        if not matched_tdcc.empty:
            st.markdown("### TDCC 大戶籌碼資料")
            st.dataframe(
                matched_tdcc.tail(1),
                use_container_width=True,
                hide_index=True,
            )

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
