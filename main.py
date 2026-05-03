import requests
import time
import json
# Import hàm gửi tin nhắn từ file baocao_tele.py
from baocao_tele import send_telegram_message

# --- Cấu hình API (Giữ nguyên) ---
binance_url = "https://fapi.binance.com/fapi/v1/ticker/24hr"
binance_params = {"symbol": "BTCUSDT"}

okx_url = "https://www.okx.com/api/v5/market/ticker"
okx_params = {"instId": "BTC-USDT-SWAP"}

# --- Các hàm lấy giá (Giữ nguyên) ---

def get_binance_price():
    try:
        response = requests.get(binance_url, params=binance_params, timeout=0.5)
        response.raise_for_status()
        return float(response.json().get('lastPrice'))
    except Exception:
        return None

def get_okx_price():
    try:
        response = requests.get(okx_url, params=okx_params, timeout=0.5)
        response.raise_for_status()
        return float(response.json()['data'][0].get('last'))
    except Exception:
        return None

# --- Vòng lặp chính (Thêm logic báo cáo) ---

print("Bắt đầu theo dõi giá...")

# Biến để tránh spam tin nhắn
last_alert_time = 0
alert_cooldown = 2 # Chờ 120 giây (2 phút) giữa các lần báo cáo

while True:
    try:
        price_binance = get_binance_price()
        price_okx = get_okx_price()

        if price_binance is not None and price_okx is not None:
            # Logic 1: In ra khi giá khác nhau (giữ nguyên)
            if price_binance != price_okx:
                print(f"Lệch giá! Binance: {price_binance} | OKX: {price_okx}")

            # Logic 2: Gửi báo cáo Telegram khi chênh lệch >= 5$
            chenh_lech = abs(price_binance - price_okx)
            current_time = time.time()
            if chenh_lech >= 30 and (current_time - last_alert_time > alert_cooldown):
                message = (f"!!! CẢNH BÁO LỆCH GIÁ !!!\n\n"
                           f"Mức chênh lệch: {chenh_lech:.2f}$\n\n"
                           f"Binance: {price_binance}$\n"
                           f"OKX: {price_okx}$")
                send_telegram_message(message)
                last_alert_time = current_time # Cập nhật lại thời gian

        time.sleep(0.001)

    except KeyboardInterrupt:
        print("\nĐã dừng chương trình.")
        break
    except Exception as e:
        print(f"Lỗi không mong muốn: {e}")
        time.sleep(2)
