
from datetime import date, timedelta
from pathlib import Path
import time

import pandas as pd
import yaml

from twse import fetch_twse_daily


CONFIG_PATH = Path("config/strategy.yaml")
HISTORY_PATH = Path("data/history/twse_daily.csv")


def load_settings():
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    history = config["history"]

    return (
        date.fromisoformat(str(history["start_date"])),
        int(history["bootstrap_batch_size"]),
    )


def main():
    start_date, batch_size = load_settings()

    HISTORY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if HISTORY_PATH.exists():
        history = pd.read_csv(
            HISTORY_PATH,
            dtype={"stock_id": str},
        )
    else:
        history = pd.DataFrame()

    if not history.empty:
        existing_dates = set(
            history["date"].astype(str)
        )
    else:
        existing_dates = set()

    today = date.today()
    current = start_date

    new_data = []
    successful_days = 0

    while current <= today:
        day_text = current.isoformat()

        if day_text in existing_dates:
            current += timedelta(days=1)
            continue

        if current.weekday() >= 5:
            current += timedelta(days=1)
            continue

        print(f"下載歷史行情: {day_text}")

        try:
            df = fetch_twse_daily(current)

            if not df.empty:
                new_data.append(df)
                successful_days += 1
                print(f"取得 {len(df)} 筆資料")
            else:
                print("當日無行情資料")

        except Exception as e:
            print(f"下載失敗: {e}")
            raise

        if successful_days >= batch_size:
            break

        current += timedelta(days=1)
        time.sleep(3)

    if new_data:
        new_df = pd.concat(
            new_data,
            ignore_index=True,
        )

        history = pd.concat(
            [history, new_df],
            ignore_index=True,
        )

        history = history.drop_duplicates(
            subset=["date", "stock_id"],
            keep="last",
        )

        history = history.sort_values(
            ["date", "stock_id"]
        )

        history.to_csv(
            HISTORY_PATH,
            index=False,
            encoding="utf-8-sig",
        )

    print(f"本次新增交易日: {successful_days}")

    if not history.empty:
        print(
            "目前累積交易日:",
            history["date"].nunique(),
        )
        print(
            "目前累積資料筆數:",
            len(history),
        )


if __name__ == "__main__":
    main()
