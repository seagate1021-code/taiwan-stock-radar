
from pathlib import Path

import pandas as pd


PICKS_PATH = Path("data/reports/top_picks.csv")
TDCC_PATH = Path("data/reports/tdcc_analysis.csv")
OUTPUT_PATH = Path("data/reports/top_picks_tdcc.csv")


def main():
    picks = pd.read_csv(
        PICKS_PATH,
        dtype={"stock_id": str},
    )

    tdcc = pd.read_csv(
        TDCC_PATH,
        dtype={"stock_id": str},
    )

    columns = [
        "stock_id",
        "date",
        "period_count",
        "big_holder_pct",
        "change_4w_pp",
        "change_12w_pp",
        "trend",
    ]

    missing = [c for c in columns if c not in tdcc.columns]
    if missing:
        raise ValueError(f"TDCC 缺少欄位: {missing}")

    if tdcc["stock_id"].duplicated().any():
        raise ValueError("TDCC 股票代號出現重複")

    result = picks.merge(
        tdcc[columns],
        on="stock_id",
        how="left",
        validate="one_to_one",
    )

        result = result.rename(
        columns={
            "date_x": "price_date",
            "date_y": "tdcc_date",
            "trend": "tdcc_trend",
        }
    )

    result["price_date"] = pd.to_datetime(
        result["price_date"]
    )
    result["tdcc_date"] = pd.to_datetime(
        result["tdcc_date"]
    )

    future_data = (
        result["tdcc_date"] > result["price_date"]
    )

    if future_data.any():
        print("警告：部分TDCC資料日期晚於股價日期")
        result.loc[
            future_data,
            [
                "period_count",
                "big_holder_pct",
                "change_4w_pp",
                "change_12w_pp",
                "tdcc_trend",
            ],
        ] = pd.NA

    result["tdcc_trend"] = (
        result["tdcc_trend"].fillna("NO_DATA")
    )

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    result.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    display_columns = [
        "rank",
        "stock_id",
        "stock_name",
        "breakout_status",
        "big_holder_pct",
        "change_12w_pp",
        "tdcc_trend",
    ]

    print("FIRE 精選股票數:", len(result))
    print(
        "有完整TDCC資料:",
        (result["tdcc_trend"] != "NO_DATA").sum(),
    )

    print("\nFIRE 前五名與 TDCC 大戶趨勢:")
    print(
        result[display_columns].to_string(
            index=False
        )
    )

    print("\n輸出檔案:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
