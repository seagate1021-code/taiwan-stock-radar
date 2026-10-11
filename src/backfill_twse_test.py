
from datetime import date, timedelta
from pathlib import Path
import time

import pandas as pd

from twse import fetch_twse_daily


# ===== 回補設定 =====

START_DATE = date(2025, 10, 1)

# 不抓未來日期
END_DATE = date.today()

# 每次最多成功下載幾個交易日
BATCH_SIZE = 50

# 每次查詢後暫停秒數
REQUEST_DELAY = 3

# 獨立測試資料夾，不覆蓋正式資料
OUTPUT_PATH = Path(
    "data/backfill_test/twse_daily_backfill.csv"
)


def load_existing():
    if not OUTPUT_PATH.exists():
        return pd.DataFrame()

    df = pd.read_csv(
        OUTPUT_PATH,
        dtype={"stock_id": str},
    )

    if not df.empty:
        required = {"date", "stock_id"}
        missing = required - set(df.columns)

        if missing:
            raise ValueError(
                f"測試歷史資料缺少欄位: {sorted(missing)}"
            )

    return df


def save_history(df):
    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df = df.drop_duplicates(
        subset=["date", "stock_id"],
        keep="last",
    )

    df = df.sort_values(
        ["date", "stock_id"]
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )


def main():
    history = load_existing()

    if history.empty:
        existing_dates = set()
    else:
        existing_dates = set(
            history["date"].astype(str)
        )

    current = START_DATE
    successful_days = 0
    checked_days = 0
    new_data = []

    print("開始回補日期:", START_DATE)
    print("結束日期:", END_DATE)
    print("單次成功交易日上限:", BATCH_SIZE)
    print("測試輸出檔案:", OUTPUT_PATH)
    print()

    while current <= END_DATE:
        day_text = current.isoformat()

        # 跳過週末
        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        # 已經下載過的日期不重複下載
        if day_text in existing_dates:
            current += timedelta(days=1)
            continue

        print(f"查詢日期: {day_text}")
        checked_days += 1

        try:
            df = fetch_twse_daily(current)

        except Exception as exc:
            print(
                f"查詢失敗，停止本次回補: "
                f"{type(exc).__name__}: {exc}"
            )
            break

        if df.empty:
            print("沒有行情資料，略過")

        else:
            new_data.append(df)
            existing_dates.add(day_text)
            successful_days += 1

            print(
                f"成功取得 {len(df)} 筆股票資料"
            )

        # 每次請求後稍作等待
        time.sleep(REQUEST_DELAY)

        if successful_days >= BATCH_SIZE:
            print("已達本次下載上限")
            break

        current += timedelta(days=1)

    # 即使中途有錯誤，也保留本次已成功下載的資料
    if new_data:
        new_df = pd.concat(
            new_data,
            ignore_index=True,
        )

        combined = pd.concat(
            [history, new_df],
            ignore_index=True,
        )

        save_history(combined)
        history = combined.drop_duplicates(
            subset=["date", "stock_id"],
            keep="last",
        )

    print()
    print("===== 回補結果 =====")
    print("本次查詢日期數:", checked_days)
    print("本次成功交易日:", successful_days)

    if not history.empty:
        print(
            "測試資料累積交易日:",
            history["date"].nunique(),
        )
        print(
            "測試資料累積筆數:",
            len(history),
        )
        print(
            "最早日期:",
            history["date"].min(),
        )
        print(
            "最新日期:",
            history["date"].max(),
        )

    else:
        print("目前尚未取得測試資料")

    print("輸出位置:", OUTPUT_PATH)
    print()
    print("正式歷史資料未修改")


if __name__ == "__main__":
    main()
