import os
import json
import requests
from flask import Flask, request
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Webhook server is running."

def fetch_price(symbol):
    try:
        r = requests.get(f"https://api-swap.bingx.com/api/v1/market/marketOrder?symbol={symbol}_USDT")
        return float(r.json()['data']['price']), "BingX"
    except:
        pass
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol.upper()}USDT")
        return float(r.json()['price']), "Binance"
    except:
        pass
    try:
        r = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={symbol.lower()}&vs_currencies=usdt")
        return float(r.json()[symbol.lower()]["usdt"]), "CoinGecko"
    except:
        return None, "Error"

def fetch_news_sentiment():
    token = os.getenv("CRYPTOPANIC_API_KEY")
    try:
        r = requests.get(f"https://cryptopanic.com/api/v1/posts/?auth_token={token}&public=true")
        news = r.json().get("results", [])
        if not news:
            return "中立"
        count = sum(1 for n in news[:10] if "bearish" in str(n).lower())
        if count >= 5:
            return "偏空"
        elif count <= 2:
            return "偏多"
        return "中立"
    except:
        return "中立"

def send_telegram(msg):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    requests.post(url, data=payload)

@app.route("/webhook", methods=["POST", "HEAD"])
def webhook():
    if request.method == "HEAD":
        return "", 200

    try:
        params = request.get_json()
        print("✅ 接收到 TradingView 傳來的 JSON：")
        print(json.dumps(params, indent=2, ensure_ascii=False))
    except Exception as e:
        print("❌ JSON 解析失敗：", str(e))
        return f"JSON格式錯誤: {str(e)}", 400

    raw_symbol = params.get("幣種", "").upper()
    if "USDT" in raw_symbol:
        symbol = raw_symbol.replace("USDT", "")
    elif raw_symbol.startswith("X:"):
        symbol = raw_symbol.split(":")[1]
    else:
        symbol = raw_symbol
    display_symbol = raw_symbol
    direction = params.get("方向", "").upper()

    try:
        tv_price = float(params.get("價格", 0))
        ob_high = float(params.get("OB高點", 0))
        ob_low = float(params.get("OB低點", 0))
        atr = float(params.get("ATR", 0))
        m5_slope = float(params.get("M5斜率", 0))
        ma12_slope = float(params.get("M5_MA12斜率", 0))
    except:
        return "❌ 資料格式錯誤", 400

    now_price, source = fetch_price(symbol)
    entry_price = now_price if now_price else tv_price
    if now_price is None:
        price_note = "❗現價來源錯誤，使用TV價格"
    elif abs(now_price - tv_price) / tv_price > 0.005:
        price_note = f"⚠️價格偏差 >0.5%，改用現價（{source}）"
    else:
        price_note = f"📡 價格來源：{source}"

    ob_range = abs(ob_high - ob_low)
    risk_R = ob_range + 2 * atr
    if risk_R == 0:
        return "❌ R 為 0，無法計算", 400

    tp1 = round(entry_price + risk_R, 2) if direction == "BUY" else round(entry_price - risk_R, 2)
    tp2 = round(entry_price + risk_R * 2.0, 2) if direction == "BUY" else round(entry_price - risk_R * 2.0, 2)
    tp3 = round(entry_price + risk_R * 3, 2) if direction == "BUY" else round(entry_price - risk_R * 3, 2)
    tp4 = round(entry_price + risk_R * 4, 2) if direction == "BUY" else round(entry_price - risk_R * 4, 2)
    sl = round(entry_price - risk_R, 2) if direction == "BUY" else round(entry_price + risk_R, 2)
    rr = round((tp4 - entry_price) / risk_R if direction == "BUY" else (entry_price - tp4) / risk_R, 2)

    tw_time = datetime.utcnow() + timedelta(hours=8)
    session = "亞洲盤" if 9 <= tw_time.hour < 17 else "歐洲盤" if 15 <= tw_time.hour < 23 else "紐約盤" if (tw_time.hour >= 21 or tw_time.hour < 5) else "其他"

    valid = abs(m5_slope) >= 15 and abs(ma12_slope) >= 2
    if not valid:
        return "⛔ 不符合條件", 200

    news = fetch_news_sentiment()
    msg = f"""🕒 <b>{tw_time.strftime('%Y-%m-%d %H:%M:%S')}（{session}）</b>
🚀 <b>{"多單" if direction == "BUY" else "空單"}</b>
📉 幣種：{display_symbol}
💰 進場價：{entry_price:.2f}
{price_note}
🎯 止盈：TP1 {tp1} / TP2 {tp2} / TP3 {tp3} / TP4 {tp4}
🛑 止損：{sl}
⚖️ 盈虧比：{rr}:1
📈 趨勢方向：{direction}
📊 勝率條件：≥70%
🧠 技術依據：
- M5 實體穿越 MA12
- M5 MA12 斜率 ≥ ±2°
- M1 MA5 斜率 ≥ ±15°
- OB 觸發 + R = OB差 + 2×ATR
- H1 價格與 MA365 趨勢同向
📰 新聞情緒：{news}
🔖 GPT-CORE (V23)
"""
    send_telegram(msg)
    return "✅ 訊號已廣播", 200

import os  # ← 確保這行在檔案最上方或這邊加入

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

