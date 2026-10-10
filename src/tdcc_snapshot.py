
from pathlib import Path

import pandas as pd
import requests


URL = "https://openapi.tdcc.com.tw/v1/opendata/1-5"
OUTPUT_PATH = Path("data/history/tdcc_weekly.csv")


def main():
    print("開始下載 TDCC 股權分散資料")

    response = requests.get(
        URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "TaiwanStockRadar/1.0",
        },
        timeout=90,
    )
    response.raise_for_status()

    data = response.json()

    if not isinstance(data, list) or not data:
        raise ValueError("TDCC API 沒有回傳有效清單")

    df = pd.DataFrame(data)

    # 清除欄位名稱前面的 BOM
    df.columns = [
        str(col).replace("\ufeff", "").strip()
        for col in df.columns
    ]

    required = [
        "資料日期",
        "證券代號",
        "持股分級",
        "股數",
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(f"TDCC 缺少欄位: {missing}")

    df["stock_id"] = (
        df["證券代號"]
        .astype(str)
        .str.strip()
    )

    df["date"] = pd.to_datetime(
        df["資料日期"].astype(str),
        format="%Y%m%d",
        errors="coerce",
    )

    df["level"] = pd.to_numeric(
        df["持股分級"],
        errors="coerce",
    )

    df["shares"] = pd.to_numeric(
        df["股數"],
        errors="coerce",
    )

    # 暫時只追蹤四碼普通股票代號
    df = df[
        df["stock_id"].str.fullmatch(r"\d{4}")
    ].copy()

    df = df.dropna(
        subset=["date", "level", "shares"]
    )

    # 第15級：超過1000張
    big = df[df["level"] == 15][
        ["date", "stock_id", "shares"]
    ].rename(
        columns={"shares": "big_holder_shares"}
    )

    # 第17級：合計
    total = df[df["level"] == 17][
        ["date", "stock_id", "shares"]
    ].rename(
        columns={"shares": "total_shares"}
    )

    # 僅保留同時有第15、17級的股票
    result = big.merge(
        total,
        on=["date", "stock_id"],
        how="inner",
        validate="one_to_one",
    )

    result = result[
        result["total_shares"] > 0
    ].copy()

    result["big_holder_pct"] = (
        result["big_holder_shares"]
        / result["total_shares"]
        * 100
    )

    result["date"] = (
        result["date"].dt.strftime("%Y-%m-%d")
    )

    # 保留以前累積的資料
    if OUTPUT_PATH.exists():
        old = pd.read_csv(
            OUTPUT_PATH,
            dtype={"stock_id": str},
        )

        result = pd.concat(
            [old, result],
            ignore_index=True,
        )

    result = result.drop_duplicates(
        subset=["date", "stock_id"],
        keep="last",
    )

    result = result.sort_values(
        ["date", "stock_id"]
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

    print("TDCC 累積週次:", result["date"].nunique())
    print("TDCC 累積資料筆數:", len(result))
    print("最新資料日期:", result["date"].max())
    print("結果檔案:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
