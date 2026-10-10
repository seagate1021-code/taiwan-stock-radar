
import requests
import pandas as pd


URL = "https://openapi.tdcc.com.tw/v1/opendata/1-5"


def main():
    response = requests.get(URL, timeout=90)
    response.raise_for_status()

    df = pd.DataFrame(response.json())

    df.columns = [
        str(col).replace("\ufeff", "").strip()
        for col in df.columns
    ]

    dates = sorted(
        df["資料日期"].dropna().astype(str).unique()
    )

    print("API 包含的不同日期數:", len(dates))
    print("API 包含的日期:", dates)

    if len(dates) >= 12:
        print("API 已包含至少12個不同日期")
    else:
        print("API 不足12週，需使用歷史查詢來源")


if __name__ == "__main__":
    main()
