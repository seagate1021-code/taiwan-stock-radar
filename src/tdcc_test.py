
import requests


URL = "https://openapi.tdcc.com.tw/v1/opendata/1-5"


def main():
    print("開始測試 TDCC 官方 API")

    response = requests.get(
        URL,
        headers={
            "Accept": "application/json",
            "User-Agent": "TaiwanStockRadar/1.0",
        },
        timeout=60,
    )

    print("HTTP 狀態碼:", response.status_code)
    response.raise_for_status()

    data = response.json()

    print("回傳資料型態:", type(data).__name__)

    if isinstance(data, list):
        print("資料筆數:", len(data))

        if data:
            print("第一筆資料:", data[0])

    elif isinstance(data, dict):
        print("回傳欄位:", list(data.keys()))

        for key, value in data.items():
            if isinstance(value, list):
                print("資料清單欄位:", key)
                print("資料筆數:", len(value))

                if value:
                    print("第一筆資料:", value[0])
                break

    else:
        raise ValueError("TDCC 回傳格式不符合預期")


if __name__ == "__main__":
    main()
