
from pathlib import Path

import pandas as pd
import yaml

# 直接使用原本 FIRE 評分函式
from top_picks import calculate_score


SIGNALS_PATH = Path("data/reports/stock_signals.csv")
INDICATORS_PATH = Path(
    "data/reports/technical_indicators.csv"
)
TDCC_PATH = Path("data/reports/tdcc_analysis.csv")
CONFIG_PATH = Path("config/strategy.yaml")
OUTPUT_PATH = Path(
    "data/reports/combined_top_picks.csv"
)


def main():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    max_picks = int(cfg["selection"]["max_picks"])
    min_picks = int(cfg["selection"]["min_picks"])

    # 1. 讀取全部 FIRE 候選股
    signals = pd.read_csv(
        SIGNALS_PATH,
        dtype={"stock_id": str},
    )

    fire = signals[
        signals["signal"] == "FIRE"
    ].copy()

    print("全部 FIRE 候選股數:", len(fire))

    if fire.empty:
        OUTPUT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        pd.DataFrame().to_csv(
            OUTPUT_PATH,
            index=False,
            encoding="utf-8-sig",
        )
        print("今日沒有 FIRE 候選股")
        return

    # 2. 合併突破所需的技術指標
    indicators = pd.read_csv(
        INDICATORS_PATH,
        dtype={"stock_id": str},
    )

    indicator_cols = [
        "stock_id",
        "date",
        "previous_high_close_20",
        "breakout_distance_pct",
    ]

    fire = fire.merge(
        indicators[indicator_cols],
        on=["stock_id", "date"],
        how="left",
        validate="one_to_one",
    )

    # 3. 沿用原本 FIRE 評分
    fire["hot_flag"] = fire["hot_flag"].fillna("")

    numeric_cols = [
        "fire_confirmations",
        "volume_ratio",
        "near_high_pct",
        "rsi14",
    ]

    for col in numeric_cols:
        fire[col] = pd.to_numeric(
            fire[col],
            errors="coerce",
        )

    fire = fire.dropna(subset=numeric_cols)

    ranked = calculate_score(
        fire,
        cfg["ranking"],
    )

    ranked["fire_score"] = ranked["total_score"]

    # 4. 計算 BREAKOUT 確認標籤
    trigger_volume = float(
        cfg["fire"]["trigger_volume_ratio"]
    )

    trigger_near_high = float(
        cfg["fire"]["trigger_near_high_pct"]
    )

    ranked["breakout_distance_pct"] = pd.to_numeric(
        ranked["breakout_distance_pct"],
        errors="coerce",
    )

    ranked["breakout_status"] = "FIRE"

    near_breakout = (
        (ranked["volume_ratio"] >= trigger_volume)
        & (
            ranked["breakout_distance_pct"]
            >= trigger_near_high
        )
    )

    confirmed_breakout = (
        near_breakout
        & (ranked["breakout_distance_pct"] > 0)
    )

    ranked.loc[
        near_breakout,
        "breakout_status",
    ] = "NEAR_BREAKOUT"

    ranked.loc[
        confirmed_breakout,
        "breakout_status",
    ] = "BREAKOUT"

    # 5. 讀取 TDCC 12 週大戶趨勢
    tdcc = pd.read_csv(
        TDCC_PATH,
        dtype={"stock_id": str},
    )

    tdcc_cols = [
        "stock_id",
        "date",
        "big_holder_pct",
        "change_4w_pp",
        "change_12w_pp",
        "trend",
    ]

    missing = [
        col for col in tdcc_cols
        if col not in tdcc.columns
    ]

    if missing:
        raise ValueError(
            f"TDCC 分析缺少欄位: {missing}"
        )

    # 避免重複股票造成合併後筆數增加
    if tdcc["stock_id"].duplicated().any():
        raise ValueError("TDCC 分析出現重複股票代號")

    tdcc = tdcc[tdcc_cols].rename(
        columns={
            "date": "tdcc_date",
            "trend": "tdcc_trend",
        }
    )

    ranked = ranked.merge(
        tdcc,
        on="stock_id",
        how="left",
        validate="many_to_one",
    )

    # 防止使用晚於股價日期的 TDCC 資料
    price_dates = pd.to_datetime(
        ranked["date"],
        errors="coerce",
    )

    tdcc_dates = pd.to_datetime(
        ranked["tdcc_date"],
        errors="coerce",
    )

    future_tdcc = (
        tdcc_dates.notna()
        & price_dates.notna()
        & (tdcc_dates > price_dates)
    )

    tdcc_data_cols = [
        "tdcc_date",
        "big_holder_pct",
        "change_4w_pp",
        "change_12w_pp",
        "tdcc_trend",
    ]

    ranked.loc[
        future_tdcc,
        tdcc_data_cols,
    ] = pd.NA

    # 6. TDCC 加減分
    scoring = cfg["tdcc"]["scoring"]

    points = {
        "ACCUMULATING": scoring["accumulating_points"],
        "DISTRIBUTING": scoring["distributing_points"],
        "STABLE": scoring["stable_points"],
    }

    ranked["tdcc_score"] = (
        ranked["tdcc_trend"].map(points)
    )

    unknown_trend = (
        ranked["tdcc_trend"].notna()
        & ranked["tdcc_score"].isna()
    )

    if unknown_trend.any():
        raise ValueError("出現未知的 TDCC 趨勢分類")

    ranked["tdcc_score"] = (
        ranked["tdcc_score"].fillna(
            scoring["no_data_points"]
        )
    )

    # 7. 計算綜合分數
    ranked["combined_score"] = (
        ranked["fire_score"]
        + ranked["tdcc_score"]
    )

    # A 主策略：綜合分數優先
    # B BREAKOUT：只當標籤，不當篩選條件
    ranked = ranked.sort_values(
        [
            "combined_score",
            "fire_score",
            "fire_confirmations",
            "volume_ratio",
            "stock_id",
        ],
        ascending=[
            False,
            False,
            False,
            False,
            True,
        ],
    )

    picks = ranked.head(max_picks).copy()

    picks.insert(
        0,
        "combined_rank",
        range(1, len(picks) + 1),
    )

    # 8. 輸出報表
    columns = [
        "combined_rank",
        "stock_id",
        "stock_name",
        "date",
        "close",
        "fire_score",
        "tdcc_score",
        "combined_score",
        "breakout_status",
        "tdcc_trend",
        "big_holder_pct",
        "change_4w_pp",
        "change_12w_pp",
        "tdcc_date",
        "fire_confirmations",
        "volume_ratio",
        "rsi14",
        "hot_flag",
    ]

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    picks[columns].to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("綜合精選股票數:", len(picks))

    if len(picks) < min_picks:
        print("提醒：符合條件股票不足最低選股數")

    print("\n全部 FIRE + TDCC 綜合前五名:")

    print(
        picks[
            [
                "combined_rank",
                "stock_id",
                "stock_name",
                "fire_score",
                "tdcc_score",
                "combined_score",
                "breakout_status",
                "tdcc_trend",
            ]
        ].to_string(index=False)
    )

    print("\n輸出檔案:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
