import requests
import time
import os
from dotenv import load_dotenv

# Load môi trường từ Railway hoặc file .env
load_dotenv()

# ================= CONFIG =================
# Ưu tiên lấy từ biến môi trường của Railway, nếu không có thì dùng giá trị mặc định của bạn
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8536602142:AAEnCocktZ-MMGke0K9OVCbepaKooQ0z2BE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5919982628")

SPREAD_ENTRY = 0.0035   # 0.35%
SPREAD_EXIT = 0.001     # 0.1%
SPREAD_STOP = 0.007     # 0.7%

UPDATE_INTERVAL = 600   # 10 phút (Railway worker chạy 24/7 nên để interval này để tránh spam)

# ================= COINS =================
symbols = [
    "BTCUSDT", "ETHUSDT", "DOGEUSDT", "SOLUSDT",
    "XRPUSDT", "BCHUSDT", "LTCUSDT", "JTOUSDT", "KAITOUSDT", "PIUSDT"
]

# OKX mapping
okx_symbols = {
    "BTCUSDT": "BTC-USDT",
    "ETHUSDT": "ETH-USDT",
    "DOGEUSDT": "DOGE-USDT",
    "SOLUSDT": "SOL-USDT",
    "XRPUSDT": "XRP-USDT",
    "BCHUSDT": "BCH-USDT",
    "LTCUSDT": "LTC-USDT",
    "JTOUSDT": "JTO-USDT",
    "KAITOUSDT": "KAITO-USDT",
    "PIUSDT": "PI-USDT"
}

# ================= STATE =================
# Trong thực tế Railway có thể restart, nếu muốn lưu trạng thái lệnh cần Database.
# Tạm thời giữ nguyên lưu trong RAM.
positions = {}
last_update_time = 0

for s in symbols:
    positions[s] = {
        "open": False,
        "entry_spread": 0
    }

# ================= TELEGRAM =================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": msg
        }, timeout=10)
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")

# ================= GET PRICE =================
def get_binance_price(symbol):
    url = f"https://api.binance.com/api/v3/ticker/bookTicker?symbol={symbol}"
    resp = requests.get(url, timeout=10)
    data = resp.json()
    if "askPrice" not in data:
        raise Exception(f"Binance không có cặp {symbol}")
    return float(data["askPrice"]), float(data["bidPrice"])

def get_okx_price(symbol):
    url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}"
    resp = requests.get(url, timeout=10)
    data = resp.json()
    if "data" not in data or len(data["data"]) == 0:
        raise Exception(f"OKX không có cặp {symbol}")
    return float(data["data"][0]["askPx"]), float(data["data"][0]["bidPx"])

# ================= BOT LOOP =================
def bot_loop():
    global last_update_time

    while True:
        try:
            status_text = "📊 CẬP NHẬT BOT (24/7)\n----------------------\n"
            has_valid_data = False

            for sym in symbols:
                try:
                    b_ask, b_bid = get_binance_price(sym)
                    o_ask, o_bid = get_okx_price(okx_symbols[sym])

                    spread = (o_bid - b_ask) / b_ask
                    pos = positions[sym]

                    status_text += f"{sym}: {spread*100:.2f}% | {'ĐANG GIỮ' if pos['open'] else 'NONE'}\n"
                    has_valid_data = True

                    # ===== ENTRY =====
                    if not pos["open"] and spread > SPREAD_ENTRY:
                        pos["open"] = True
                        pos["entry_spread"] = spread

                        send_telegram(
                            f"🚀 [VÀO LỆNH] {sym}\n"
                            f"Spread: {spread*100:.3f}%\n"
                            f"LONG Binance: {b_ask}\n"
                            f"SHORT OKX: {o_bid}"
                        )

                    # ===== EXIT =====
                    elif pos["open"]:
                        if spread < SPREAD_EXIT:
                            profit = (pos["entry_spread"] - spread) * 1000
                            send_telegram(
                                f"💰 [CHỐT LỜI] {sym}\n"
                                f"Lợi nhuận: {profit:.2f}$"
                            )
                            pos["open"] = False

                        elif spread > SPREAD_STOP:
                            loss = (spread - pos["entry_spread"]) * 1000
                            send_telegram(
                                f"⚠️ [CẮT LỖ] {sym}\n"
                                f"Lỗ: {loss:.2f}$"
                            )
                            pos["open"] = False

                except Exception:
                    # Bỏ qua các đồng chưa list hoặc lỗi API lẻ
                    continue

            # ===== GỬI CẬP NHẬT ĐỊNH KỲ =====
            current_time = time.time()
            if has_valid_data and (current_time - last_update_time > UPDATE_INTERVAL):
                send_telegram(status_text)
                last_update_time = current_time

            time.sleep(5) # Tránh spam API quá nhanh

        except Exception as e:
            print(f"Lỗi vòng lặp chính: {e}")
            time.sleep(10)

# ================= RUN =================
if __name__ == "__main__":
    print("Bot đang khởi động...")
    send_telegram("🤖 Bot multi-coin 24/7 đã ONLINE trên Railway")
    bot_loop()
