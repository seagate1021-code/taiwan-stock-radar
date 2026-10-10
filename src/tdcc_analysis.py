
from pathlib import Path

import pandas as pd
import yaml


INPUT_PATH = Path("data/history/tdcc_weekly.csv")
OUTPUT_PATH = Path("data/reports/tdcc_analysis.csv")
CONFIG_PATH = Path("config/strategy.yaml")


def main():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    target = int(cfg["tdcc"]["target_period_count"])
    noise = float(cfg["tdcc"]["noise_pp"])

    df = pd.read_csv(
        INPUT_PATH,
        dtype={"stock_id": str},
    )

    required = ["date", "stock_id", "big_holder_pct"]
    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(f"缺少欄位: {missing}")

    df["date"] = pd.to_datetime(
        df["date"], errors="coerce"
    )
    df["big_holder_pct"] = pd.to_numeric(
        df["big_holder_pct"], errors="coerce"
    )

    df = df.dropna(subset=required)
    df = df.drop_duplicates(
        subset=["date", "stock_id"],
        keep="last",
    )

    # 只分析資料庫最新的12個週次
    dates = sorted(df["date"].unique())[-target:]
    df = df[df["date"].isin(dates)].copy()

    if len(dates) < target:
        print(
            f"警告：目前只有 {len(dates)} 週，"
            f"目標是 {target} 週"
        )

    # 依股票逐一計算
    records = []

    for stock_id, group in df.groupby("stock_id"):
        group = group.sort_values("date")

        # 必須在全部目標週次都有資料
        if len(group) != target:
            continue

        if list(group["date"]) != list(dates):
            continue

        values = group["big_holder_pct"].to_numpy()

        latest_pct = float(values[-1])

        # 4週前 = 最新一期往前4個週次
        change_4w = float(
            values[-1] - values[-5]
        ) if target >= 5 else None

        # 12週觀察窗口：最新一期減最早一期
        change_12w = float(
            values[-1] - values[0]
        )

        if change_12w > noise:
            trend = "ACCUMULATING"
        elif change_12w < -noise:
            trend = "DISTRIBUTING"
        else:
            trend = "STABLE"

        records.append({
            "stock_id": stock_id,
            "date": group["date"].iloc[-1].strftime(
                "%Y-%m-%d"
            ),
            "period_count": len(group),
            "big_holder_pct": latest_pct,
            "change_4w_pp": change_4w,
            "change_12w_pp": change_12w,
            "trend": trend,
        })

    columns = [
        "stock_id",
        "date",
        "period_count",
        "big_holder_pct",
        "change_4w_pp",
        "change_12w_pp",
        "trend",
    ]

    result = pd.DataFrame(records, columns=columns)

    if not result.empty:
        result = result.sort_values(
            ["change_12w_pp", "stock_id"],
            ascending=[False, True],
        )

    OUTPUT_PATH.parent.mkdir(
        parents=True, exist_ok=True
    )
    result.to_csv(
        OUTPUT_PATH,
        index=False,
        encoding="utf-8-sig",
    )

    print("資料庫累積週次:", len(dates))
    print("完整12週股票數:", len(result))

    if not result.empty:
        print("大戶持股增加:", (
            result["trend"] == "ACCUMULATING"
        ).sum())
        print("大戶持股減少:", (
            result["trend"] == "DISTRIBUTING"
        ).sum())
        print("大戶持股持平:", (
            result["trend"] == "STABLE"
        ).sum())

        print("\n大戶增持前10名:")
        print(result.head(10).to_string(index=False))


if __name__ == "__main__":
    main()
