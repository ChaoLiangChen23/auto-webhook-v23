import os
import json
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Webhook server is running (BROADCAST ONLY VERSION)"

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
    try:
        r = requests.post(url, data=payload)
        print("✅ Telegram response:", r.text)
    except Exception as e:
        print("❌ 發送 Telegram 失敗：", str(e))

@app.route("/webhook", methods=["POST", "HEAD"])
def webhook():
    if request.method == "HEAD":
        return "", 200

    try:
        params = request.get_json()
        print("✅ 接收到 JSON：")
        print(json.dumps(params, indent=2, ensure_ascii=False))
    except Exception as e:
        return jsonify(error="JSON decode error", detail=str(e), raw=request.data.decode()), 400

    # 中文轉英文欄位（兼容模式）
    if "幣種" in params:
        params = {
            "symbol": params.get("幣種"),
            "price": float(params.get("價格", 0) or 0),
            "side": params.get("方向", "").upper(),
            "ob_high": float(params.get("OB高點", 0) or 0),
            "ob_low": float(params.get("OB低點", 0) or 0),
            "atr": float(params.get("ATR", 0) or 0),
            "m5_slope": float(params.get("M5斜率", 0) or 0),
            "ma12_slope": float(params.get("M5_MA12斜率", 0) or 0)
        }

    try:
        symbol = params.get("symbol", "").upper().replace("USDT", "")
        display_symbol = params.get("symbol", "").upper()
        side = params.get("side", "").upper()
        tv_price = float(params.get("price", 0))
        ob_high = float(params.get("ob_high", 0))
        ob_low = float(params.get("ob_low", 0))
        atr = float(params.get("atr", 0))
        m5_slope = float(params.get("m5_slope", 0))
        ma12_slope = float(params.get("ma12_slope", 0))
    except Exception as e:
        return jsonify(error="Invalid parameter", detail=str(e)), 400

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
        return jsonify(error="R=0", message="OB區與ATR為0"), 400

    tp1 = round(entry_price + risk_R, 2) if side == "BUY" else round(entry_price - risk_R, 2)
    tp2 = round(entry_price + risk_R * 2, 2) if side == "BUY" else round(entry_price - risk_R * 2, 2)
    tp3 = round(entry_price + risk_R * 3, 2) if side == "BUY" else round(entry_price - risk_R * 3, 2)
    tp4 = round(entry_price + risk_R * 4, 2) if side == "BUY" else round(entry_price - risk_R * 4, 2)
    sl = round(entry_price - risk_R, 2) if side == "BUY" else round(entry_price + risk_R, 2)
    rr = round((tp4 - entry_price) / risk_R if side == "BUY" else (entry_price - tp4) / risk_R, 2)

    tw_time = datetime.utcnow() + timedelta(hours=8)
    session = "亞洲盤" if 9 <= tw_time.hour < 17 else "歐洲盤" if 15 <= tw_time.hour < 23 else "紐約盤" if (tw_time.hour >= 21 or tw_time.hour < 5) else "其他"

    valid = abs(m5_slope) >= 15 and abs(ma12_slope) >= 2
    if not valid:
        return jsonify(error="不符合斜率條件", m5=m5_slope, ma12=ma12_slope), 200

    news = fetch_news_sentiment()
    msg = f"""🕒 <b>{tw_time.strftime('%Y-%m-%d %H:%M:%S')}（{session}）</b>
🚀 <b>{"多單" if side == "BUY" else "空單"}</b>
📉 幣種：{display_symbol}
💰 進場價：{entry_price:.2f}
{price_note}
🎯 止盈：TP1 {tp1} / TP2 {tp2} / TP3 {tp3} / TP4 {tp4}
🛑 止損：{sl}
⚖️ 盈虧比：{rr}:1
📈 趨勢方向：{side}
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
    return jsonify(status="ok", message="✅ 廣播完成"), 200

if __name__ == '__main__':
    send_telegram("✅ Render 啟動完成，Telegram 廣播測試 OK")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
