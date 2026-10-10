
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests


URL = "https://www.twse.com.tw/exchangeReport/MI_INDEX"


def to_number(value):
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None


def fetch_twse_daily(target_date):
    params = {
        "response": "json",
        "date": target_date.strftime("%Y%m%d"),
        "type": "ALLBUT0999",
    }

    response = requests.get(
        URL,
        params=params,
        timeout=30,
        headers={"User-Agent": "TaiwanStockRadar/1.0"},
    )
    response.raise_for_status()

    payload = response.json()

    if payload.get("stat") != "OK":
        return pd.DataFrame()

    fields = payload.get("fields9")
    rows = payload.get("data9")

    if not fields or not rows:
        raise ValueError("TWSE 回應缺少每日個股行情表")

    df = pd.DataFrame(rows, columns=fields)

    required = [
        "證券代號", "證券名稱",
        "成交金額", "收盤價",
    ]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"缺少欄位: {col}")

    df = df[required].copy()

    df.columns = [
        "stock_id", "stock_name",
        "trade_value", "close",
    ]

    df["stock_id"] = df["stock_id"].astype(str)

    # 暫時只保留四位數證券代號
    df = df[
        df["stock_id"].str.fullmatch(r"[1-9][0-9]{3}")
    ].copy()

    df["trade_value"] = df["trade_value"].map(to_number)
    df["close"] = df["close"].map(to_number)

    df = df.dropna(subset=["close", "trade_value"])
    df["date"] = target_date.isoformat()

    return df


def main():
    # 以台灣日期為準
    from zoneinfo import ZoneInfo
    from datetime import datetime

    today = datetime.now(ZoneInfo("Asia/Taipei")).date()

    # 向前尋找最近有資料的交易日
    for offset in range(10):
        target = today - timedelta(days=offset)
        print(f"嘗試取得: {target}")

        df = fetch_twse_daily(target)

        if not df.empty:
            output = Path("data/reports")
            output.mkdir(parents=True, exist_ok=True)

            path = output / "twse_latest.csv"
            df.to_csv(path, index=False, encoding="utf-8-sig")

            print(f"資料日期: {target}")
            print(f"取得證券數量: {len(df)}")
            print(f"已儲存: {path}")
            print(df.head(10).to_string(index=False))
            return

    raise RuntimeError("最近 10 天找不到可用的 TWSE 資料")


if __name__ == "__main__":
    main()
