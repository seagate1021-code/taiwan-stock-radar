
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

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

    
    import time

    payload = None

    for attempt in range(3):
        try:
            response = requests.get(
                URL,
                params=params,
                timeout=30,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                },
            )

            response.raise_for_status()
            payload = response.json()
            break

        except (
            requests.exceptions.RequestException,
            ValueError,
        ) as e:
            print(
                f"TWSE 請求失敗，第 {attempt + 1}/3 次："
                f"{type(e).__name__}: {e}"
            )

            if attempt == 2:
                raise

            time.sleep(5 * (attempt + 1))

    print("TWSE 回傳狀態:", payload.get("stat"))
    print("TWSE 回傳欄位:", list(payload.keys()))

    if payload.get("stat") != "OK":
        return pd.DataFrame()

    
    # 新版 TWSE JSON 使用 tables 陣列
    tables = payload.get("tables", [])

    fields = None
    rows = None

    for table in tables:
        if not isinstance(table, dict):
            continue

        candidate_fields = table.get("fields", [])
        candidate_rows = table.get("data", [])

        if (
            "證券代號" in candidate_fields
            and "證券名稱" in candidate_fields
            and "成交金額" in candidate_fields
            and "收盤價" in candidate_fields
            and candidate_rows
        ):
            fields = candidate_fields
            rows = candidate_rows
            break

    if fields is None or rows is None:
        raise ValueError(
            "TWSE tables 中找不到完整個股行情表"
        )

    df = pd.DataFrame(rows, columns=fields)
    
    required = [
        "證券代號",
        "證券名稱",
        "成交股數",
        "成交金額",
        "收盤價",
    ]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"缺少欄位: {col}")

   
    df = df[required].copy()

    df.columns = [
        "stock_id",
        "stock_name",
        "volume",
        "trade_value",
        "close",
    ]

    df["stock_id"] = df["stock_id"].astype(str)

    df = df[
        df["stock_id"].str.fullmatch(r"[1-9][0-9]{3}")
    ].copy()

    df["volume"] = df["volume"].map(to_number)
    df["trade_value"] = df["trade_value"].map(to_number)
    df["close"] = df["close"].map(to_number)

    df = df.dropna(
        subset=["close", "trade_value", "volume"]
    )

    df["date"] = target_date.isoformat()

    return df


def main():
    today = datetime.now(
        ZoneInfo("Asia/Taipei")
    ).date()

    for offset in range(10):
        target = today - timedelta(days=offset)
        print(f"嘗試取得: {target}")

        df = fetch_twse_daily(target)

        if not df.empty:
            output = Path("data/reports")
            output.mkdir(parents=True, exist_ok=True)

            path = output / "twse_latest.csv"

            df.to_csv(
                path,
                index=False,
                encoding="utf-8-sig",
            )

            print(f"資料日期: {target}")
            print(f"取得證券數量: {len(df)}")
            print(f"已儲存: {path}")

            print(df.head(10).to_string(index=False))
            return

    raise RuntimeError("最近 10 天找不到可用的 TWSE 資料")


if __name__ == "__main__":
    main()
