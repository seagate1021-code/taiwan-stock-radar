
from pathlib import Path

import pandas as pd
import yaml


SIGNALS_PATH = Path("data/reports/stock_signals.csv")
OUTPUT_PATH = Path("data/reports/top_picks.csv")
CONFIG_PATH = Path("config/strategy.yaml")


def calculate_score(df):
    df = df.copy()

    # 1. FIRE 確認數
    df["score_fire"] = df["fire_confirmations"] * 20

    # 2. 成交量比率，最高加30分
    df["score_volume"] = (
        (df["volume_ratio"] - 1).clip(lower=0, upper=3)
        * 10
    )

    # 3. 接近20日最高收盤價，最高加20分
    # 距離高點越遠，得分越低
    df["score_near_high"] = (
        20 + df["near_high_pct"] * 4
    ).clip(lower=0, upper=20)

    # 4. RSI 60～75為較理想區間
    df["score_rsi"] = 0.0

    df.loc[
        df["rsi14"].between(60, 75),
        "score_rsi",
    ] = 20

    df.loc[
        df["rsi14"].between(55, 60, inclusive="left"),
        "score_rsi",
    ] = 10

    df.loc[
        df["rsi14"] > 75,
        "score_rsi",
    ] = 5

    # 5. HOT 過熱扣分
    df["score_hot"] = 0.0

    df.loc[
        df["hot_flag"] == "HOT",
        "score_hot",
    ] = -30

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

    ranked = calculate_score(fire)

    ranked = ranked.sort_values(
        [
            "total_score",
            "fire_confirmations",
            "volume_ratio",
            "stock_id",
        ],
        ascending=[False, False, False, True],
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
            ]
        ].to_string(index=False)
    )

    print("輸出檔案:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
