
from pathlib import Path

import pandas as pd


PICKS_PATH = Path(
    "data/reports/combined_top_picks.csv"
)

HISTORY_PATH = Path(
    "data/history/combined_picks_history.csv"
)

COLUMNS = [
    "date",
    "stock_id",
    "stock_name",
    "close",
    "combined_rank",
    "fire_score",
    "tdcc_score",
    "combined_score",
    "breakout_status",
    "tdcc_trend",
    "tdcc_date",
]


def main():
    # 1. 讀取當日綜合選股結果
    picks = pd.read_csv(
        PICKS_PATH,
        dtype={"stock_id": str},
    )

    missing = [
        col for col in COLUMNS
        if col not in picks.columns
    ]

    if missing:
        raise ValueError(
            f"綜合選股報表缺少欄位: {missing}"
        )

    today = picks[COLUMNS].copy()

    # 2. 讀取既有歷史紀錄
    if HISTORY_PATH.exists():
        history = pd.read_csv(
            HISTORY_PATH,
            dtype={"stock_id": str},
        )

        missing_history = [
            col for col in COLUMNS
            if col not in history.columns
        ]

        if missing_history:
            raise ValueError(
                f"歷史紀錄缺少欄位: {missing_history}"
            )

        history = history[COLUMNS]

    else:
        history = pd.DataFrame(
            columns=COLUMNS
        )

    before_count = len(history)

    # 3. 合併新舊資料
    combined = pd.concat(
        [history, today],
        ignore_index=True,
    )

    # 4. 同一天同一股票只保存一筆
    # 重複執行時，以最新一次結果為準
    combined = combined.drop_duplicates(
        subset=["date", "stock_id"],
        keep="last",
    )

    # 5. 日期由舊到新，同日依排名排序
    combined = combined.sort_values(
        ["date", "combined_rank", "stock_id"],
        ascending=[True, True, True],
    )

    # 6. 寫入歷史紀錄
    HISTORY_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    combined.to_csv(
        HISTORY_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("本次選股數:", len(today))
    print("原有歷史紀錄:", before_count)
    print("更新後歷史紀錄:", len(combined))
    print("新增紀錄數:", len(combined) - before_count)

    print("\n本次選股名單:")

    print(
        today[
            [
                "date",
                "combined_rank",
                "stock_id",
                "stock_name",
                "close",
                "combined_score",
                "breakout_status",
            ]
        ].to_string(index=False)
    )

    print("\n輸出檔案:", HISTORY_PATH)


if __name__ == "__main__":
    main()
