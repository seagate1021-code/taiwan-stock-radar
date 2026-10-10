
from pathlib import Path

import pandas as pd
import yaml


SIGNALS_PATH = Path("data/reports/stock_signals.csv")
OUTPUT_PATH = Path("data/reports/top_picks.csv")
CONFIG_PATH = Path("config/strategy.yaml")



def calculate_score(df, ranking):
    df = df.copy()

    # 1. FIRE 確認數評分
    df["score_fire"] = (
        df["fire_confirmations"]
        * ranking["fire_confirmation_points"]
    )

    # 2. 成交量評分
    df["score_volume"] = (
        (df["volume_ratio"] - 1).clip(lower=0)
        * ranking["volume_ratio_points"]
    ).clip(upper=ranking["volume_score_cap"])

    # 3. 接近高點評分
    df["score_near_high"] = (
        ranking["near_high_max_points"]
        + df["near_high_pct"]
        * ranking["near_high_points_per_pct"]
    ).clip(
        lower=0,
        upper=ranking["near_high_max_points"],
    )

    # 4. RSI 評分
    df["score_rsi"] = 0.0

    ideal_min = ranking["rsi_ideal_min"]
    ideal_max = ranking["rsi_ideal_max"]
    moderate_min = ranking["rsi_moderate_min"]

    df.loc[
        df["rsi14"].between(ideal_min, ideal_max),
        "score_rsi",
    ] = ranking["rsi_ideal_points"]

    df.loc[
        (df["rsi14"] >= moderate_min)
        & (df["rsi14"] < ideal_min),
        "score_rsi",
    ] = ranking["rsi_moderate_points"]

    df.loc[
        df["rsi14"] > ideal_max,
        "score_rsi",
    ] = ranking["rsi_high_points"]

    # 5. HOT 過熱扣分
    df["score_hot"] = 0.0

    df.loc[
        df["hot_flag"] == "HOT",
        "score_hot",
    ] = -ranking["hot_penalty"]

    # 6. 總分
    df["total_score"] = (
        df["score_fire"]
        + df["score_volume"]
        + df["score_near_high"]
        + df["score_rsi"]
        + df["score_hot"]
    )

    return df

def main():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    min_picks = int(cfg["selection"]["min_picks"])
    max_picks = int(cfg["selection"]["max_picks"])

    if not 1 <= min_picks <= max_picks:
        raise ValueError("選股數量設定不正確")

    signals = pd.read_csv(
        SIGNALS_PATH,
        dtype={"stock_id": str},
    )

    # 只選 FIRE 主分類
    fire = signals[
        signals["signal"] == "FIRE"
    ].copy()

    print("FIRE 候選股票數:", len(fire))

    if fire.empty:
        print("今日沒有 FIRE 候選股票")
        OUTPUT_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        fire.to_csv(
            OUTPUT_PATH,
            index=False,
            encoding="utf-8-sig",
        )
        return

    fire["hot_flag"] = fire["hot_flag"].fillna("")

    # 讀取最新技術指標中的突破基準
    indicators = pd.read_csv(
        "data/reports/technical_indicators.csv",
        dtype={"stock_id": str},
    )

    required = [
        "stock_id",
        "date",
        "previous_high_close_20",
        "breakout_distance_pct",
    ]

    missing = [
        col for col in required
        if col not in indicators.columns
    ]

    if missing:
        raise ValueError(
            f"技術指標缺少突破欄位: {missing}"
        )

    fire = fire.merge(
        indicators[required],
        on=["stock_id", "date"],
        how="left",
        validate="one_to_one",
    )

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

    
    ranked = calculate_score(fire, cfg["ranking"])

    # 依照原本的 FIRE 觸發參數
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

    # 先判斷接近突破，再判斷真正突破
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

    # 突破優先，其次接近突破
    ranked["breakout_priority"] = (
        ranked["breakout_status"].map(
            {
                "BREAKOUT": 2,
                "NEAR_BREAKOUT": 1,
                "FIRE": 0,
            }
        )
    )


    
    ranked = ranked.sort_values(
        [
            "breakout_priority",
            "total_score",
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


    # 不足最低檔數時，保留實際結果，不硬湊
    picks = ranked.head(max_picks).copy()

    picks.insert(
        0,
        "rank",
        range(1, len(picks) + 1),
    )

    columns = [
        "rank",
        "stock_id",
        "stock_name",
        "date",
        "close",
        "signal",
        "hot_flag",
        "fire_confirmations",
        "rsi14",
        "volume_ratio",
        "near_high_pct",
        "breakout_status",
        "previous_high_close_20",
        "breakout_distance_pct",
        "score_fire",
        "score_volume",
        "score_near_high",
        "score_rsi",
        "score_hot",
        "total_score",
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

    print("精選股票數:", len(picks))

    if len(picks) < min_picks:
        print(
            "提醒：符合條件的股票不足最低選股數，"
            "不會強行補入不符合條件的股票"
        )

    print("每日強勢突破精選名單:")
    print(
        picks[
            [
                "rank",
                "stock_id",
                "stock_name",
                "close",
                "fire_confirmations",
                "volume_ratio",
                "rsi14",
                "total_score",
                "breakout_status",
                "breakout_distance_pct",
            ]
        ].to_string(index=False)
    )

    print("輸出檔案:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
