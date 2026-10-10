
from pathlib import Path

import pandas as pd
import yaml


INPUT_PATH = Path("data/reports/top_picks_tdcc.csv")
OUTPUT_PATH = Path("data/reports/combined_ranking.csv")
CONFIG_PATH = Path("config/strategy.yaml")


def main():
    # 讀取設定
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    scoring = cfg["tdcc"]["scoring"]

    # 讀取 FIRE + TDCC 資料
    df = pd.read_csv(
        INPUT_PATH,
        dtype={"stock_id": str},
    )

    required = [
        "rank",
        "stock_id",
        "stock_name",
        "total_score",
        "breakout_status",
        "tdcc_trend",
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(f"缺少必要欄位: {missing}")

    # TDCC 趨勢與加減分對照
    points = {
        "ACCUMULATING": scoring["accumulating_points"],
        "DISTRIBUTING": scoring["distributing_points"],
        "STABLE": scoring["stable_points"],
        "NO_DATA": scoring["no_data_points"],
    }

    # 保留原始 FIRE 分數
    df["fire_score"] = pd.to_numeric(
        df["total_score"],
        errors="raise",
    )

    # 計算 TDCC 分數
    df["tdcc_score"] = (
        df["tdcc_trend"]
        .fillna("NO_DATA")
        .map(points)
    )

    if df["tdcc_score"].isna().any():
        unknown = df.loc[
            df["tdcc_score"].isna(),
            "tdcc_trend",
        ].unique()

        raise ValueError(
            f"未知的 TDCC 趨勢分類: {unknown}"
        )

    # 計算綜合分數
    df["combined_score"] = (
        df["fire_score"] + df["tdcc_score"]
    )

    # 依綜合分數重新排序
    df = df.sort_values(
        ["combined_score", "fire_score", "stock_id"],
        ascending=[False, False, True],
    ).copy()

    df["combined_rank"] = range(1, len(df) + 1)

    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    df.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    display_columns = [
        "combined_rank",
        "rank",
        "stock_id",
        "stock_name",
        "fire_score",
        "tdcc_score",
        "combined_score",
        "tdcc_trend",
    ]

    print("原始 FIRE 精選股票數:", len(df))
    print("\nFIRE + TDCC 綜合排名:")
    print(
        df[display_columns].to_string(
            index=False
        )
    )

    print("\n輸出檔案:", OUTPUT_PATH)


if __name__ == "__main__":
    main()
