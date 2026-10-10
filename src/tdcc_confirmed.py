
from pathlib import Path

import pandas as pd


INPUT_PATH = Path("data/reports/top_picks_tdcc.csv")
OUTPUT_PATH = Path("data/reports/tdcc_confirmed.csv")


def main():
    df = pd.read_csv(
        INPUT_PATH,
        dtype={"stock_id": str},
    )

    required = [
        "rank",
        "stock_id",
        "stock_name",
        "breakout_status",
        "big_holder_pct",
        "change_12w_pp",
        "tdcc_trend",
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(f"缺少欄位: {missing}")

    # 同時符合突破與大戶增持
    confirmed = df[
        (df["breakout_status"] == "BREAKOUT")
        & (df["tdcc_trend"] == "ACCUMULATING")
    ].copy()

    # 保留原本 FIRE 排名
    confirmed = confirmed.sort_values("rank")

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    confirmed.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("原始 FIRE 精選股票數:", len(df))
    print("突破且大戶增持股票數:", len(confirmed))

    print("\nFIRE + TDCC 雙重確認名單:")

    if confirmed.empty:
        print("目前沒有符合條件的股票")
    else:
        display_columns = [
            "rank",
            "stock_id",
            "stock_name",
            "breakout_status",
            "big_holder_pct",
            "change_12w_pp",
            "tdcc_trend",
        ]

        print(
            confirmed[display_columns].to_string(
                index=False
            )
        )


if __name__ == "__main__":
    main()
