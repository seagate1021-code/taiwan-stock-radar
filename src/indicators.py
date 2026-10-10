
from pathlib import Path

import numpy as np
import pandas as pd
import yaml


HISTORY_PATH = Path("data/history/twse_daily.csv")
CONFIG_PATH = Path("config/strategy.yaml")
OUTPUT_PATH = Path("data/reports/technical_indicators.csv")


def calculate_rsi(close, period=14):
    """使用 Wilder 平滑法計算 RSI。"""
    delta = close.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)

    result = pd.Series(np.nan, index=close.index)

    if len(close) <= period:
        return result

    avg_gain = gains.iloc[1:period + 1].mean()
    avg_loss = losses.iloc[1:period + 1].mean()

    for i in range(period, len(close)):
        if i > period:
            avg_gain = (
                avg_gain * (period - 1) + gains.iloc[i]
            ) / period
            avg_loss = (
                avg_loss * (period - 1) + losses.iloc[i]
            ) / period

        if avg_loss == 0:
            rsi = 100.0 if avg_gain > 0 else 50.0
        else:
            rs = avg_gain / avg_loss
            rsi = 100 - 100 / (1 + rs)

        result.iloc[i] = rsi

    return result


def calculate_one_stock(group):
    group = group.sort_values("date").copy()

    close = group["close"]
    volume = group["volume"]

    group["ma10"] = close.rolling(10, min_periods=10).mean()
    group["ma20"] = close.rolling(20, min_periods=20).mean()

    group["rsi14"] = calculate_rsi(close)

    # 前20個交易日平均成交量，不包含當日
    group["avg_volume_20"] = (
        volume.shift(1)
        .rolling(20, min_periods=20)
        .mean()
    )

    group["volume_ratio"] = (
        volume / group["avg_volume_20"].replace(0, np.nan)
    )

    # 最近20日最高收盤價，不是盤中最高價
    group["high_close_20"] = close.rolling(
        20, min_periods=20
    ).max()

    # 前20個交易日最高收盤價，不包含當日
    group["previous_high_close_20"] = (
        close.shift(1)
        .rolling(20, min_periods=20)
        .max()
    )

    # 當日收盤價相對前20日高點的距離
    group["breakout_distance_pct"] = (
        (
            close / group["previous_high_close_20"]
            - 1
        ) * 100
    )

    group["near_high_pct"] = (
        (close / group["high_close_20"] - 1) * 100
    )

    group["price_vs_ma10_pct"] = (
        (close / group["ma10"] - 1) * 100
    )

    group["price_vs_ma20_pct"] = (
        (close / group["ma20"] - 1) * 100
    )

    group["daily_change_pct"] = close.pct_change() * 100

    return group


def main():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    min_history_days = int(
        config["history"]["min_history_days"]
    )

    df = pd.read_csv(
        HISTORY_PATH,
        dtype={"stock_id": str},
    )

    required = [
        "stock_id",
        "stock_name",
        "date",
        "close",
        "volume",
        "trade_value",
    ]

    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"缺少欄位: {missing}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")

    for col in ["close", "volume", "trade_value"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["stock_id", "date"])
    df = df.drop_duplicates(
        subset=["stock_id", "date"],
        keep="last",
    )

    df = df.sort_values(["stock_id", "date"])

    # 價格與成交量必須有效，才參與技術指標計算
    df = df[
        (df["close"] > 0)
        & (df["volume"].notna())
        & (df["volume"] >= 0)
    ].copy()

    df["history_days"] = (
        df.groupby("stock_id")["date"].transform("count")
    )

    eligible = df[
        df["history_days"] >= min_history_days
    ].copy()

    if eligible.empty:
        raise RuntimeError("沒有股票達到最低歷史資料天數")

    calculated = []

    for _, group in eligible.groupby("stock_id", sort=False):
        calculated.append(calculate_one_stock(group))

    result = pd.concat(calculated, ignore_index=True)

    latest_date = df["date"].max()

    latest = result[
        result["date"] == latest_date
    ].copy()

    
    indicator_columns = [
        "ma10",
        "ma20",
        "rsi14",
        "avg_volume_20",
        "volume_ratio",
        "high_close_20",
        "previous_high_close_20",
        "breakout_distance_pct",
        "near_high_pct",
        "price_vs_ma10_pct",
        "price_vs_ma20_pct",
        "daily_change_pct",
    ]
    
    latest = latest.dropna(subset=indicator_columns)

    columns = [
        "stock_id",
        "stock_name",
        "date",
        "close",
        "volume",
        "trade_value",
        "history_days",
    ] + indicator_columns

    latest = latest[columns].sort_values(
        "stock_id"
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    latest.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("最新行情日期:", latest_date.date())
    print("歷史資料達標股票數:", eligible["stock_id"].nunique())
    print("技術指標完整股票數:", len(latest))
    print("輸出檔案:", OUTPUT_PATH)
    print(latest.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
