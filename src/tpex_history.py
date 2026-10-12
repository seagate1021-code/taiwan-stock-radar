
"""
TPEx 上櫃股票歷史行情建立工具

輸出：
    data/history/tpex_daily.csv

安全原則：
    1. 不修改 TWSE 上市歷史資料
    2. 不修改 G1 歷史選股與績效
    3. 獨立下載並驗證上櫃歷史行情
"""

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import time

import pandas as pd

from tpex import fetch_tpex_daily


OUTPUT_PATH = Path("data/history/tpex_daily.csv")

# 首次建立時，往前抓取約 240 個日曆日
BACKFILL_DAYS = 240

# 每次請求之間暫停，避免對官方網站造成過多負擔
REQUEST_INTERVAL_SECONDS = 1.0

REQUIRED_COLUMNS = [
    "date",
    "stock_id",
    "stock_name",
    "volume",
    "trade_value",
    "close",
]


def read_existing_history():
    """讀取已存在的上櫃歷史資料。"""

    if not OUTPUT_PATH.exists():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    df = pd.read_csv(
        OUTPUT_PATH,
        dtype={"stock_id": str, "date": str},
        encoding="utf-8-sig",
    )

    missing = [
        col for col in REQUIRED_COLUMNS
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"既有上櫃歷史檔案缺少欄位: {missing}"
        )

    return df[REQUIRED_COLUMNS].copy()


def normalize_history(df):
    """整理資料型別並移除重複紀錄。"""

    if df.empty:
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    result = df[REQUIRED_COLUMNS].copy()

    result["date"] = pd.to_datetime(
        result["date"],
        errors="coerce",
    ).dt.strftime("%Y-%m-%d")

    result["stock_id"] = (
        result["stock_id"]
        .astype(str)
        .str.strip()
    )

    result["stock_name"] = (
        result["stock_name"]
        .astype(str)
        .str.strip()
    )

    for column in ["volume", "trade_value", "close"]:
        result[column] = pd.to_numeric(
            result[column],
            errors="coerce",
        )

    result = result.dropna(
        subset=[
            "date",
            "stock_id",
            "volume",
            "trade_value",
            "close",
        ]
    )

    result = result[
        result["stock_id"].str.fullmatch(
            r"[1-9][0-9]{3}"
        )
    ]

    result = result[
        (result["close"] > 0)
        & (result["volume"] >= 0)
        & (result["trade_value"] >= 0)
    ]

    result = result.drop_duplicates(
        subset=["date", "stock_id"],
        keep="last",
    )

    return result.sort_values(
        ["date", "stock_id"]
    ).reset_index(drop=True)


def save_history(df):
    """先寫入暫存檔，完成後再替換上櫃歷史檔。"""

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = OUTPUT_PATH.with_suffix(
        ".csv.tmp"
    )

    df.to_csv(
        temporary_path,
        index=False,
        encoding="utf-8-sig",
    )

    temporary_path.replace(OUTPUT_PATH)


def main():
    today = datetime.now(
        ZoneInfo("Asia/Taipei")
    ).date()

    existing = normalize_history(
        read_existing_history()
    )

    existing_dates = set(existing["date"])

    print("=" * 50)
    print("TPEx 上櫃歷史行情獨立建立工具")
    print(f"今天日期: {today}")
    print(f"既有資料筆數: {len(existing)}")
    print(f"既有交易日數: {len(existing_dates)}")
    print("=" * 50)

    collected = []

    # 包含今天；若當日行情尚未公布，API 無資料時會略過
        for offset in range(0, BACKFILL_DAYS + 1):
        target_date = today - timedelta(days=offset)

        if target_date.weekday() >= 5:
            continue

        date_string = target_date.isoformat()

        if date_string in existing_dates:
            continue

        print(f"下載上櫃行情: {date_string}")

        try:
            daily = fetch_tpex_daily(target_date)

            if daily.empty:
                print("  無資料，略過")
                continue

            missing = [
                col for col in REQUIRED_COLUMNS
                if col not in daily.columns
            ]

            if missing:
                raise ValueError(
                    f"下載資料缺少欄位: {missing}"
                )

            collected.append(
                daily[REQUIRED_COLUMNS].copy()
            )

            print(
                f"  成功取得 {len(daily)} 筆"
            )

        except Exception as exc:
            # 保留錯誤紀錄，不因單一天失敗而丟失其他日期
            print(
                f"  下載失敗: "
                f"{type(exc).__name__}: {exc}"
            )

        time.sleep(REQUEST_INTERVAL_SECONDS)

    if collected:
        combined = pd.concat(
            [existing, *collected],
            ignore_index=True,
        )
    else:
        combined = existing

    combined = normalize_history(combined)

    if combined.empty:
        raise RuntimeError(
            "沒有取得任何上櫃歷史行情，"
            "因此不建立空白 CSV。"
        )

    # 避免本次大量下載失敗卻被誤判為完整資料
    trading_days = combined["date"].nunique()

    print("=" * 50)
    print(f"總資料筆數: {len(combined)}")
    print(f"總交易日數: {trading_days}")
    print(
        f"股票代號數量: "
        f"{combined['stock_id'].nunique()}"
    )
    print(
        f"資料日期範圍: "
        f"{combined['date'].min()} ~ "
        f"{combined['date'].max()}"
    )

    if trading_days < 120:
        raise RuntimeError(
            f"目前只有 {trading_days} 個交易日，"
            "不足 120 日；暫不儲存歷史 CSV。"
        )

    save_history(combined)

    print(f"已儲存: {OUTPUT_PATH}")
    print("TPEx 上櫃歷史資料建立完成")
    print("=" * 50)


if __name__ == "__main__":
    main()
