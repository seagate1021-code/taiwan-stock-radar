
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
import time

import pandas as pd
import requests


# 櫃買中心上櫃股票每日收盤行情
URL = "https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes"


def to_number(value):
    try:
        text = str(value).replace(",", "").strip()

        if text in ("", "--", "---", "除權息", "nan"):
            return None

        return float(text)

    except (ValueError, TypeError):
        return None


def fetch_tpex_daily(target_date):
    # 櫃買中心使用民國年日期
    roc_date = (
        f"{target_date.year - 1911}/"
        f"{target_date.month:02d}/"
        f"{target_date.day:02d}"
    )

    params = {
        "date": roc_date,
        "id": "",
        "response": "json",
    }

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
        ) as exc:
            print(
                f"TPEx 請求失敗，第 {attempt + 1}/3 次："
                f"{type(exc).__name__}: {exc}"
            )

            if attempt == 2:
                raise

            time.sleep(5 * (attempt + 1))

    # 相容不同版本的 JSON 欄位名稱
    tables = payload.get("tables", [])

    if not tables:
        tables = [payload]

    fields = None
    rows = None

    for table in tables:
        if not isinstance(table, dict):
            continue

        candidate_fields = (
            table.get("fields")
            or table.get("Columns")
            or table.get("columns")
            or []
        )

        candidate_rows = (
            table.get("data")
            or table.get("aaData")
            or []
        )

        if candidate_fields and candidate_rows:
            fields = candidate_fields
            rows = candidate_rows
            break

    if fields is None or rows is None:
        print("TPEx 當日無可用行情資料")
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=fields)

    # 對應櫃買中心欄位名稱
    column_aliases = {
        "代號": "stock_id",
        "證券代號": "stock_id",
        "股票代號": "stock_id",
        "名稱": "stock_name",
        "證券名稱": "stock_name",
        "股票名稱": "stock_name",
        "收盤": "close",
        "收盤價": "close",
        "成交股數": "volume",
        "成交量": "volume",
        "成交金額(元)": "trade_value",
        "成交金額": "trade_value",
    }

    df.columns = [
        column_aliases.get(
            str(col).strip(),
            str(col).strip(),
        )
        for col in df.columns
    ]

    required = [
        "stock_id",
        "stock_name",
        "volume",
        "trade_value",
        "close",
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(
            f"TPEx 行情缺少欄位: {missing}；"
            f"實際欄位: {list(df.columns)}"
        )

    df = df[required].copy()

    df["stock_id"] = (
        df["stock_id"]
        .astype(str)
        .str.strip()
    )

    # 只保留一般四碼股票代號
    df = df[
        df["stock_id"].str.fullmatch(
            r"[1-9][0-9]{3}"
        )
    ].copy()

    for col in [
        "volume",
        "trade_value",
        "close",
    ]:
        df[col] = df[col].map(to_number)

    df = df.dropna(
        subset=[
            "volume",
            "trade_value",
            "close",
        ]
    )

    df = df[
        (df["close"] > 0)
        & (df["volume"] >= 0)
        & (df["trade_value"] >= 0)
    ].copy()

    df["date"] = target_date.isoformat()

    return df


def main():
    today = datetime.now(
        ZoneInfo("Asia/Taipei")
    ).date()

    for offset in range(10):
        target = today - timedelta(days=offset)

        print(f"嘗試取得上櫃行情: {target}")

        df = fetch_tpex_daily(target)

        if not df.empty:
            output = Path("data/reports")
            output.mkdir(
                parents=True,
                exist_ok=True,
            )

            path = output / "tpex_latest.csv"

            df.to_csv(
                path,
                index=False,
                encoding="utf-8-sig",
            )

            print(f"資料日期: {target}")
            print(f"取得上櫃股票數量: {len(df)}")
            print(f"已儲存: {path}")
            print(
                df.head(10).to_string(
                    index=False
                )
            )

            return

    raise RuntimeError(
        "最近 10 天找不到可用的 TPEx 行情"
    )


if __name__ == "__main__":
    main()
