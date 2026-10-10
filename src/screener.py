
from pathlib import Path

import pandas as pd
import yaml


CONFIG_PATH = Path("config/strategy.yaml")
HISTORY_PATH = Path("data/history/twse_daily.csv")
OUTPUT_PATH = Path("data/reports/basic_screen.csv")


def main():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    min_price = float(config["basic"]["min_price"])
    min_trade_value = float(
        config["basic"]["min_avg_trade_value_20"]
    )
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
        "trade_value",
        "close",
        "date",
    ]

    for column in required:
        if column not in df.columns:
            raise ValueError(f"缺少必要欄位: {column}")

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    df["close"] = pd.to_numeric(
        df["close"],
        errors="coerce",
    )

    df["trade_value"] = pd.to_numeric(
        df["trade_value"],
        errors="coerce",
    )

    df = df.dropna(
        subset=[
            "date",
            "close",
            "trade_value",
        ]
    )

    df = df.sort_values(
        ["stock_id", "date"]
    )

    # 同一檔股票、同一日期只保留一筆
    df = df.drop_duplicates(
        subset=["stock_id", "date"],
        keep="last",
    )

    latest_date = df["date"].max()

    # 計算每檔股票的有效歷史天數
    df["history_days"] = (
        df.groupby("stock_id")["date"]
        .transform("count")
    )

    # 計算20日平均成交金額
    df["avg_trade_value_20"] = (
        df.groupby("stock_id")["trade_value"]
        .transform(
            lambda s: s.rolling(
                window=20,
                min_periods=20,
            ).mean()
        )
    )

    # 只使用全市場最新交易日的股票資料
    latest = df[
        df["date"] == latest_date
    ].copy()

    selected = latest[
        (latest["history_days"] >= min_history_days)
        & (latest["close"] >= min_price)
        & (
            latest["avg_trade_value_20"]
            >= min_trade_value
        )
    ].copy()

    selected = selected.sort_values(
        "avg_trade_value_20",
        ascending=False,
    )

    selected = selected[
        [
            "stock_id",
            "stock_name",
            "date",
            "close",
            "avg_trade_value_20",
            "history_days",
        ]
    ]

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    selected.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("最新資料日期:", latest_date.date())
    print("當日有行情的股票數:", len(latest))
    print("符合基本條件的股票數:", len(selected))
    print("結果檔案:", OUTPUT_PATH)

    print(
        selected.head(20).to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()
