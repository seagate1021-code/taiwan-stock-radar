
from datetime import date
from pathlib import Path
import time

import pandas as pd

from twse import fetch_twse_daily


HISTORY_PATH = Path("data/history/twse_daily.csv")
BATCH_SIZE = 10


def main():
    if not HISTORY_PATH.exists():
        raise FileNotFoundError("找不到歷史行情 CSV")

    history = pd.read_csv(
        HISTORY_PATH,
        dtype={"stock_id": str},
    )

    if "volume" not in history.columns:
        history["volume"] = float("nan")

    history["date"] = history["date"].astype(str)

    missing = history[
        history["volume"].isna()
    ]

    dates = sorted(
        missing["date"].unique()
    )

    print("待補成交量日期數:", len(dates))

    updated_days = 0

    for day_text in dates[:BATCH_SIZE]:
        target = date.fromisoformat(day_text)

        print("回補成交量:", day_text)

        try:
            daily = fetch_twse_daily(target)

            if daily.empty:
                print("當日無資料，跳過")
                continue

            if "volume" not in daily.columns:
                raise ValueError("TWSE 資料缺少 volume")

            volumes = daily[
                ["stock_id", "volume"]
            ].drop_duplicates("stock_id")

            day_mask = history["date"] == day_text

            matched = history.loc[
                day_mask, "stock_id"
            ].map(
                volumes.set_index("stock_id")["volume"]
            )

            history.loc[
                day_mask, "volume"
            ] = history.loc[
                day_mask, "volume"
            ].fillna(matched)

            updated_days += 1

            print(
                "成功補入筆數:",
                matched.notna().sum(),
            )

        except Exception as e:
            print("回補失敗:", e)
            raise

        time.sleep(3)

    history.to_csv(
        HISTORY_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    remaining = history[
        history["volume"].isna()
    ]["date"].nunique()

    print("本次處理日期數:", updated_days)
    print("仍有缺少成交量的日期數:", remaining)


if __name__ == "__main__":
    main()
