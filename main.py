import requests
import time
import os
from dotenv import load_dotenv

# Load môi trường
load_dotenv()

# ================= CONFIG =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8536602142:AAEnCocktZ-MMGke0K9OVCbepaKooQ0z2BE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5919982628")

SPREAD_ENTRY = 0.0035   # 0.35% để vào lệnh
SPREAD_EXIT = 0.001     # 0.1% để chốt lời
SPREAD_STOP = 0.008     # 0.8% để cắt lỗ

UPDATE_INTERVAL = 600   # 10 phút gửi báo cáo 1 lần

# ================= COINS =================
symbols = [
    "BTCUSDT", "ETHUSDT", "DOGEUSDT", "SOLUSDT",
    "XRPUSDT", "BCHUSDT", "LTCUSDT", "JTOUSDT", "KAITOUSDT", "PIUSDT"
]

okx_symbols = {s: s.replace("USDT", "-USDT") for s in symbols}

# ================= STATE =================
positions = {}
last_update_time = 0

for s in symbols:
    positions[s] = {
        "open": False,
        "direction": None, 
        "entry_spread": 0
    }

# ================= TELEGRAM =================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg}, timeout=10)
    except:
        pass

# ================= GET PRICE =================
def get_prices(sym):
    # Binance
    url_b = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={sym}"
    res_b = requests.get(url_b, timeout=5).json()
    b_ask, b_bid = float(res_b["askPrice"]), float(res_b["bidPrice"])
    
    # OKX
    url_o = f"https://www.okx.com/api/v5/market/ticker?instId={okx_symbols[sym]}"
    res_o = requests.get(url_o, timeout=5).json()["data"][0]
    o_ask, o_bid = float(res_o["askPx"]), float(res_o["bidPx"])
    
    return b_ask, b_bid, o_ask, o_bid

# ================= BOT LOOP =================
def bot_loop():
    global last_update_time
    while True:
        try:
            status_text = "🔄 CẬP NHẬT 2 CHIỀU (24/7)\n----------------------\n"
            
            for sym in symbols:
                try:
                    b_ask, b_bid, o_ask, o_bid = get_prices(sym)
                    pos = positions[sym]

                    # Spread 1: Long Binance - Short OKX (Khi OKX giá cao hơn)
                    spread_1 = (o_bid - b_ask) / b_ask
                    # Spread 2: Long OKX - Short Binance (Khi Binance giá cao hơn)
                    spread_2 = (b_bid - o_ask) / o_ask

                    if not pos["open"]:
                        if spread_1 > SPREAD_ENTRY:
                            pos.update({"open": True, "direction": "B_LONG_O_SHORT", "entry_spread": spread_1})
                            send_telegram(f"🚀 [VÀO LỆNH 1] {sym}\nDirection: LONG Binance - SHORT OKX\nSpread: {spread_1*100:.3f}%")
                        
                        elif spread_2 > SPREAD_ENTRY:
                            pos.update({"open": True, "direction": "O_LONG_B_SHORT", "entry_spread": spread_2})
                            send_telegram(f"🚀 [VÀO LỆNH 2] {sym}\nDirection: LONG OKX - SHORT Binance\nSpread: {spread_2*100:.3f}%")
                        
                        current_max = max(spread_1, spread_2)
                        status_text += f"{sym}: {current_max*100:.2f}% | NONE\n"

                    else:
                        current_spread = spread_1 if pos["direction"] == "B_LONG_O_SHORT" else spread_2
                        
                        if current_spread < SPREAD_EXIT:
                            profit = (pos["entry_spread"] - current_spread) * 1000
                            send_telegram(f"💰 [CHỐT LỜI] {sym}\nDirection: {pos['direction']}\nLợi nhuận: {profit:.2f}$")
                            pos["open"] = False
                        
                        elif current_spread > SPREAD_STOP:
                            loss = (current_spread - pos["entry_spread"]) * 1000
                            send_telegram(f"⚠️ [CẮT LỖ] {sym}\nLỗ: {loss:.2f}$")
                            pos["open"] = False
                            
                        status_text += f"{sym}: {current_spread*100:.2f}% | HOLDING\n"

                except: continue

            if time.time() - last_update_time > UPDATE_INTERVAL:
                send_telegram(status_text)
                last_update_time = time.time()
            time.sleep(5)
        except Exception as e:
            time.sleep(10)

if __name__ == "__main__":
    send_telegram("🤖 Bot 2 chiều đã ONLINE trên Railway")
    bot_loop()
