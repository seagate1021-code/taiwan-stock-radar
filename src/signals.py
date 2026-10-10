
from pathlib import Path

import pandas as pd
import yaml


CONFIG_PATH = Path("config/strategy.yaml")
INDICATORS_PATH = Path(
    "data/reports/technical_indicators.csv"
)
OUTPUT_PATH = Path("data/reports/stock_signals.csv")


def main():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    df = pd.read_csv(
        INDICATORS_PATH,
        dtype={"stock_id": str},
    )

    # 基本條件：沿用已建立的選股結果
    basic = pd.read_csv(
        "data/reports/basic_screen.csv",
        dtype={"stock_id": str},
    )

    df = df[
        df["stock_id"].isin(basic["stock_id"])
    ].copy()

    if df.empty:
        raise RuntimeError("沒有符合基本條件的股票")

    fire = cfg["fire"]
    hot = cfg["hot"]
    pullback = cfg["pullback"]
    setup = cfg["setup"]

    # FIRE 初版：5 項確認條件
    df["fire_c1"] = df["close"] > df["ma10"]
    df["fire_c2"] = df["ma10"] > df["ma20"]
    df["fire_c3"] = (
        df["volume_ratio"] >= fire["min_volume_ratio"]
    )
    df["fire_c4"] = (
        df["near_high_pct"] >= fire["near_high_pct"]
    )
    df["fire_c5"] = df["rsi14"] >= 60

    fire_cols = [
        "fire_c1",
        "fire_c2",
        "fire_c3",
        "fire_c4",
        "fire_c5",
    ]

    df["fire_confirmations"] = (
        df[fire_cols].sum(axis=1)
    )

    df["is_fire"] = (
        df["fire_confirmations"]
        >= fire["min_confirmations"]
    )

    # HOT：過熱標記，符合任一條件即標記
    df["is_hot"] = (
        (df["rsi14"] >= hot["rsi"])
        | (
            df["price_vs_ma20_pct"]
            >= hot["price_vs_ma20_pct"]
        )
        | (
            df["daily_change_pct"]
            >= hot["daily_change_pct"]
        )
    )

    # PULLBACK：量縮、RSI 回落、接近均線
    df["is_pullback"] = (
        df["rsi14"].between(
            pullback["rsi_min"],
            pullback["rsi_max"],
        )
        & (
            df["volume_ratio"]
            <= pullback["max_volume_ratio"]
        )
        & df["price_vs_ma10_pct"].between(
            pullback["ma10_min"],
            pullback["ma10_max"],
        )
        & df["price_vs_ma20_pct"].between(
            pullback["ma20_min"],
            pullback["ma20_max"],
        )
    )

    # SETUP 初版：4 項確認條件
    df["setup_c1"] = df["close"] >= df["ma20"]
    df["setup_c2"] = df["ma10"] >= df["ma20"]
    df["setup_c3"] = df["rsi14"] >= 50
    df["setup_c4"] = (
        df["daily_change_pct"]
        >= setup["min_daily_change_pct"]
    )

    setup_cols = [
        "setup_c1",
        "setup_c2",
        "setup_c3",
        "setup_c4",
    ]

    df["setup_confirmations"] = (
        df[setup_cols].sum(axis=1)
    )

    df["is_setup"] = (
        df["setup_confirmations"]
        >= setup["min_confirmations"]
    )

    # 主分類優先順序：FIRE > PULLBACK > SETUP
    df["signal"] = "NONE"

    df.loc[df["is_setup"], "signal"] = "SETUP"
    df.loc[df["is_pullback"], "signal"] = "PULLBACK"
    df.loc[df["is_fire"], "signal"] = "FIRE"

    # 過熱是獨立標記，不覆蓋主分類
    df["hot_flag"] = df["is_hot"].map(
        {True: "HOT", False: ""}
    )

    # 初版排序：確認數優先，其次成交量比率
    df["rank_score"] = (
        df["fire_confirmations"] * 10
        + df["setup_confirmations"] * 3
        + df["volume_ratio"].clip(upper=5)
    )

    selected = df[
        df["signal"] != "NONE"
    ].copy()

    selected = selected.sort_values(
        ["rank_score", "volume_ratio"],
        ascending=False,
    )

    columns = [
        "stock_id",
        "stock_name",
        "date",
        "close",
        "signal",
        "hot_flag",
        "rsi14",
        "volume_ratio",
        "near_high_pct",
        "price_vs_ma10_pct",
        "price_vs_ma20_pct",
        "fire_confirmations",
        "setup_confirmations",
        "rank_score",
    ]

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    selected[columns].to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("基本條件股票數:", len(df))
    print("FIRE 數量:", df["is_fire"].sum())
    print("PULLBACK 數量:", df["is_pullback"].sum())
    print("SETUP 數量:", df["is_setup"].sum())
    print("HOT 標記數量:", df["is_hot"].sum())
    print("輸出訊號股票數:", len(selected))
    print("結果檔案:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
