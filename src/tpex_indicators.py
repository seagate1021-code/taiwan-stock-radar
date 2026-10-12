
"""
TPEx 上櫃股票技術指標

讀取：
    data/history/tpex_daily.csv

輸出：
    data/reports/tpex_technical_indicators.csv

沿用上市版 indicators.py 的計算公式，
但不修改任何上市資料或 G1 績效。
"""

from pathlib import Path

import pandas as pd
import yaml

from indicators import calculate_one_stock


HISTORY_PATH = Path("data/history/tpex_daily.csv")
CONFIG_PATH = Path("config/strategy.yaml")
OUTPUT_PATH = Path(
    "data/reports/tpex_technical_indicators.csv"
)

REQUIRED_COLUMNS = [
    "stock_id",
    "stock_name",
    "date",
    "close",
    "volume",
    "trade_value",
]

INDICATOR_COLUMNS = [
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


def main():
    if not HISTORY_PATH.is_file():
        raise FileNotFoundError(
            f"找不到上櫃歷史資料：{HISTORY_PATH}"
        )

    with CONFIG_PATH.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    min_history_days = int(
        config["history"]["min_history_days"]
    )

    df = pd.read_csv(
        HISTORY_PATH,
        dtype={"stock_id": str},
        encoding="utf-8-sig",
    )

    missing = [
        column
        for column in REQUIRED_COLUMNS
        if column not in df.columns
    ]

    if missing:
        raise ValueError(
            f"上櫃歷史資料缺少欄位：{missing}"
        )

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    for column in [
        "close",
        "volume",
        "trade_value",
    ]:
        df[column] = pd.to_numeric(
            df[column],
            errors="coerce",
        )

    df = df.dropna(
        subset=["stock_id", "date"]
    )

    df = df.drop_duplicates(
        subset=["stock_id", "date"],
        keep="last",
    )

    df = df.sort_values(
        ["stock_id", "date"]
    )

    df = df[
        (df["close"] > 0)
        & df["volume"].notna()
        & (df["volume"] >= 0)
    ].copy()

    if df.empty:
        raise RuntimeError(
            "上櫃歷史資料沒有有效行情"
        )

    df["history_days"] = (
        df.groupby("stock_id")["date"]
        .transform("count")
    )

    eligible = df[
        df["history_days"] >= min_history_days
    ].copy()

    if eligible.empty:
        raise RuntimeError(
            "沒有上櫃股票達到最低歷史天數"
        )

    calculated = []

    for _, group in eligible.groupby(
        "stock_id",
        sort=False,
    ):
        calculated.append(
            calculate_one_stock(group)
        )

    result = pd.concat(
        calculated,
        ignore_index=True,
    )

    latest_date = df["date"].max()

    latest = result[
        result["date"] == latest_date
    ].copy()

    latest = latest.dropna(
        subset=INDICATOR_COLUMNS
    )

    columns = (
        REQUIRED_COLUMNS
        + ["history_days"]
        + INDICATOR_COLUMNS
    )

    latest = latest[columns].sort_values(
        "stock_id"
    )

    if latest.empty:
        raise RuntimeError(
            "最新交易日沒有完整的上櫃技術指標"
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

    print("=" * 50)
    print("TPEx 上櫃技術指標計算完成")
    print("最新行情日期:", latest_date.date())
    print(
        "歷史資料達標股票數:",
        eligible["stock_id"].nunique(),
    )
    print("技術指標完整股票數:", len(latest))
    print("輸出檔案:", OUTPUT_PATH)
    print("=" * 50)

    print(
        latest.head(10).to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
