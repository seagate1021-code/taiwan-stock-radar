
import io

import pandas as pd
import requests


URL = (
    "https://raw.githubusercontent.com/"
    "wirelessr/tdcc-opendata-archive/"
    "main/snapshots/2026/2026-10-02.csv"
)


def main():
    print("開始測試 TDCC 歷史備份")

    response = requests.get(URL, timeout=60)
    print("HTTP 狀態碼:", response.status_code)
    response.raise_for_status()

    df = pd.read_csv(
        io.BytesIO(response.content),
        dtype={"證券代號": str},
        encoding="utf-8-sig",
    )

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
        raise ValueError(f"缺少必要欄位: {missing}")

    dates = sorted(
        df["資料日期"].astype(str).unique()
    )

    print("資料筆數:", len(df))
    print("資料日期:", dates)
    print("持股分級:", sorted(
        pd.to_numeric(
            df["持股分級"], errors="coerce"
        ).dropna().unique().tolist()
    ))

    if dates != ["20261002"]:
        raise ValueError("歷史快照日期不符合預期")

    print("歷史快照驗證成功")


if __name__ == "__main__":
    main()
