import os
import json
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
from dotenv import load_dotenv
from sheet_utils import write_to_sheet

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
            return "Neutral"
        count = sum(1 for n in news[:10] if "bearish" in str(n).lower())
        if count >= 5:
            return "Bearish"
        elif count <= 2:
            return "Bullish"
        return "Neutral"
    except:
        return "Neutral"

def send_telegram(msg):
    token = os.getenv("TG_BOT_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload)
        print("✅ Telegram response:", r.text)
    except Exception as e:
        print("❌ Telegram failed:", str(e))

@app.route("/webhook", methods=["POST", "HEAD"])
def webhook():
    if request.method == "HEAD":
        return "", 200

    try:
        params = request.get_json()
        print("✅ JSON received:")
        print(json.dumps(params, indent=2))
    except Exception as e:
        print("❌ JSON decode error:", str(e))
        return jsonify(error="JSON decode error", detail=str(e)), 400

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
        return jsonify(error="Invalid parameter type", detail=str(e)), 400

    now_price, source = fetch_price(symbol)
    entry_price = now_price if now_price else tv_price
    if now_price is None:
        price_note = "❗Using TV price (price fetch failed)"
    elif abs(now_price - tv_price) / tv_price > 0.005:
        price_note = f"⚠️ Price deviation >0.5%, using live price ({source})"
    else:
        price_note = f"📡 Price source: {source}"

    ob_range = abs(ob_high - ob_low)
    risk_R = ob_range + 2 * atr
    print(f"📐 OB Range: {ob_range}, ATR: {atr}, R: {risk_R}")

    if risk_R == 0:
        return jsonify(error="R = 0", message="OB range and ATR both zero"), 400

    tp1 = round(entry_price + risk_R, 2) if side == "BUY" else round(entry_price - risk_R, 2)
    tp2 = round(entry_price + risk_R * 2.0, 2) if side == "BUY" else round(entry_price - risk_R * 2.0, 2)
    tp3 = round(entry_price + risk_R * 3, 2) if side == "BUY" else round(entry_price - risk_R * 3, 2)
    tp4 = round(entry_price + risk_R * 4, 2) if side == "BUY" else round(entry_price - risk_R * 4, 2)
    sl = round(entry_price - risk_R, 2) if side == "BUY" else round(entry_price + risk_R, 2)
    rr = round((tp4 - entry_price) / risk_R if side == "BUY" else (entry_price - tp4) / risk_R, 2)

    tw_time = datetime.utcnow() + timedelta(hours=8)
    session = "Asia" if 9 <= tw_time.hour < 17 else "Europe" if 15 <= tw_time.hour < 23 else "US" if (tw_time.hour >= 21 or tw_time.hour < 5) else "Other"

    valid = abs(m5_slope) >= 15 and abs(ma12_slope) >= 2
    print(f"📊 Slope check: M5={m5_slope}, MA12={ma12_slope} → {'PASS' if valid else 'FAIL'}")
    if not valid:
        return jsonify(error="Slope check failed", m5_slope=m5_slope, ma12_slope=ma12_slope), 200

    news = fetch_news_sentiment()
    msg = f"""🕒 <b>{tw_time.strftime('%Y-%m-%d %H:%M:%S')} ({session})</b>
🚀 <b>{'Long' if side == "BUY" else "Short"}</b>
📉 Symbol: {display_symbol}
💰 Entry: {entry_price:.2f}
{price_note}
🎯 TP: TP1 {tp1} / TP2 {tp2} / TP3 {tp3} / TP4 {tp4}
🛑 SL: {sl}
⚖️ RR: {rr}:1
📈 Trend: {side}
📊 Conditions: Slope + OB + MA filter
📰 Sentiment: {news}
🔖 GPT-CORE (V23-en)
"""
    send_telegram(msg)

    row_data = [
        tw_time.strftime("%Y-%m-%d %H:%M:%S"),
        display_symbol,
        side,
        price_note,
        round(entry_price, 2),
        sl, tp1, tp2, tp3, tp4,
        rr,
        "Slope + OB + MA filter",
        news,
        "",
        session
    ]
    write_to_sheet(row_data)

    print("✅ Broadcast + logging complete.")
    return jsonify(status="ok", message="Broadcast complete"), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
