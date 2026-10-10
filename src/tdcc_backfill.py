
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests


ARCHIVE_BASE = (
    "https://raw.githubusercontent.com/"
    "wirelessr/tdcc-opendata-archive/"
    "main/snapshots"
)

OUTPUT_PATH = Path("data/history/tdcc_weekly.csv")

TARGET_WEEKS = 12
MAX_REQUESTS = 11


def normalize_snapshot(df, expected_date):
    df = df.copy()

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

    if any(col not in df.columns for col in required):
        raise ValueError("歷史資料缺少必要欄位")

    actual_dates = pd.to_datetime(
        df["資料日期"].astype(str),
        format="%Y%m%d",
        errors="coerce",
    ).dt.strftime("%Y-%m-%d").dropna().unique()

    if len(actual_dates) != 1:
        raise ValueError("歷史資料包含異常日期")

    if actual_dates[0] != expected_date:
        raise ValueError(
            f"日期不一致: {actual_dates[0]}"
        )

    df["stock_id"] = (
        df["證券代號"].astype(str).str.strip()
    )

    df = df[
        df["stock_id"].str.fullmatch(r"\d{4}")
    ].copy()

    df["level"] = pd.to_numeric(
        df["持股分級"], errors="coerce"
    )

    df["shares"] = pd.to_numeric(
        df["股數"], errors="coerce"
    )

    big = df[df["level"] == 15][
        ["stock_id", "shares"]
    ].rename(
        columns={"shares": "big_holder_shares"}
    )

    total = df[df["level"] == 17][
        ["stock_id", "shares"]
    ].rename(
        columns={"shares": "total_shares"}
    )

    result = big.merge(
        total,
        on="stock_id",
        how="inner",
        validate="one_to_one",
    )

    result = result[
        (result["total_shares"] > 0)
        & (result["big_holder_shares"] >= 0)
        & (
            result["big_holder_shares"]
            <= result["total_shares"]
        )
    ].copy()

    if result.empty:
        raise ValueError("沒有有效的大戶持股資料")

    result["date"] = expected_date

    result["big_holder_pct"] = (
        result["big_holder_shares"]
        / result["total_shares"]
        * 100
    )

    return result[
        [
            "date",
            "stock_id",
            "big_holder_shares",
            "total_shares",
            "big_holder_pct",
        ]
    ]


def main():
    if not OUTPUT_PATH.exists():
        raise FileNotFoundError(
            f"找不到現有歷史資料: {OUTPUT_PATH}"
        )

    history = pd.read_csv(
        OUTPUT_PATH,
        dtype={"stock_id": str},
    )

    history["date"] = pd.to_datetime(
        history["date"]
    ).dt.strftime("%Y-%m-%d")

    existing_dates = set(history["date"].unique())

    # 以現有最新資料日期為基準，往前尋找
    latest = date.fromisoformat(max(existing_dates))

    # 從最新日期前一天開始，避免覆蓋官方資料
    cursor = latest - timedelta(days=1)

    downloaded = []
    requests_used = 0

    while (
        len(existing_dates) < TARGET_WEEKS
        and requests_used < MAX_REQUESTS
    ):
        candidate = cursor.isoformat()
        cursor -= timedelta(days=1)

        # 只測試星期四與星期五
        weekday = date.fromisoformat(candidate).weekday()

        if weekday not in (3, 4):
            continue

        if candidate in existing_dates:
            continue

        year = candidate[:4]

        url = (
            f"{ARCHIVE_BASE}/{year}/{candidate}.csv"
        )

        requests_used += 1
        print(f"測試歷史日期: {candidate}")

        try:
            response = requests.get(
                url,
                timeout=60,
            )

            if response.status_code == 404:
                print("  找不到此日期，跳過")
                continue

            response.raise_for_status()

            raw = pd.read_csv(
                BytesIO(response.content),
                dtype={"證券代號": str},
                encoding="utf-8-sig",
            )

            snapshot = normalize_snapshot(
                raw,
                candidate,
            )

            downloaded.append(snapshot)
            existing_dates.add(candidate)

            print(
                f"  成功，股票筆數: {len(snapshot)}"
            )

        except (
            requests.RequestException,
            ValueError,
            pd.errors.ParserError,
        ) as exc:
            print(f"  跳過異常資料: {exc}")

    if downloaded:
        history = pd.concat(
            [history, *downloaded],
            ignore_index=True,
        )

        history = history.drop_duplicates(
            subset=["date", "stock_id"],
            keep="first",
        )

        history = history.sort_values(
            ["date", "stock_id"]
        )

        history.to_csv(
            OUTPUT_PATH,
            index=False,
            encoding="utf-8-sig",
        )

    print("本次歷史請求數:", requests_used)
    print("本次新增週次:", len(downloaded))
    print("目前累積週次:", history["date"].nunique())
    print("目前累積資料筆數:", len(history))
    print("已保存日期:", sorted(history["date"].unique()))


if __name__ == "__main__":
    main()
