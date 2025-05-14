import requests

def ping_bingx():
    url = "https://open-api.bingx.com/openApi/quote/v1/ticker?symbol=BTC-USDT"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            price = data.get("data", {}).get("lastPrice")
            print(f"[Ping 成功] 現價：{price}")
        else:
            print(f"[Ping 失敗] 狀態碼：{response.status_code}")
    except Exception as e:
        print(f"[錯誤] 無法連線 BingX：{e}")

if __name__ == "__main__":
    ping_bingx()
