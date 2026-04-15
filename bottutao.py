import requests
import json
import hmac
import base64
import time
import os # Thêm thư viện os

# --- LẤY THÔNG TIN TỪ BIẾN MÔI TRƯỜNG ---
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
PASSPHRASE = os.getenv("PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# -----------------------------------------

def get_auth_headers(method, request_path, body=''):
    timestamp = str(time.time())
    message = timestamp + method + request_path + body
    mac = hmac.new(bytes(SECRET_KEY, 'utf-8'), bytes(message, 'utf-8'), digestmod='sha256')
    d = mac.digest()
    sign = base64.b64encode(d)
    return {
        'Content-Type': 'application/json',
        'OK-ACCESS-KEY': API_KEY,
        'OK-ACCESS-SIGN': sign,
        'OK-ACCESS-TIMESTAMP': timestamp,
        'OK-ACCESS-PASSPHRASE': PASSPHRASE,
    }

def send_telegram_message(message):
    """Gửi tin nhắn đến một chat cụ thể trên Telegram."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Vui lòng cung cấp TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Lỗi khi gửi tin nhắn Telegram: {response.text}")
    except Exception as e:
        print(f"Lỗi kết nối đến Telegram: {e}")

def get_jto_price():
    """Lấy giá JTO/USDT hiện tại và trả về giá trị."""
    method = 'GET'
    request_path = '/api/v5/market/ticker?instId=JTO-USDT'
    url = f"https://www.okx.com{request_path}"
    try:
        headers = get_auth_headers(method, request_path)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if "data" in data and len(data["data"]) > 0:
            last_price = float(data["data"][0]["last"])
            return last_price
    except Exception as e:
        print(f"Lỗi khi lấy giá: {e}")
    return None

def reset_trading_cycle():
    """Reset lại các biến cho chu kỳ giao dịch mới."""
    return {
        "total_invested": 0.0,
        "total_jto_bought": 0.0,
        "initial_price": 0.0,
        "dca_level": 0,
        "in_position": False
    }

if __name__ == "__main__":
    if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
        print("VUI LÒNG CUNG CẤP ĐỦ BIẾN MÔI TRƯỜNG: API_KEY, SECRET_KEY, PASSPHRASE.")
    else:
        # Khởi tạo trạng thái giao dịch
        trade_state = reset_trading_cycle()
        BUY_AMOUNT_USD = 10.0
        DCA_PERCENTAGE = 0.03 # 3%
        TAKE_PROFIT_PERCENTAGE = 0.02 # 2%

        print("Bot giao dịch DEMO đã khởi động...")
        send_telegram_message("🚀 *Bot giao dịch DEMO đã khởi động (trên Railway)* 🚀\n\nTheo dõi JTO/USDT...")

        try:
            while True:
                current_price = get_jto_price()
                if not current_price:
                    print("Không lấy được giá, thử lại sau 15 giây.")
                    time.sleep(15)
                    continue

                # ----- LOGIC BẮT ĐẦU CHU KỲ MỚI -----
                if not trade_state["in_position"]:
                    # Thực hiện lệnh mua đầu tiên
                    jto_to_buy = BUY_AMOUNT_USD / current_price
                    trade_state["total_invested"] = BUY_AMOUNT_USD
                    trade_state["total_jto_bought"] = jto_to_buy
                    trade_state["initial_price"] = current_price
                    trade_state["in_position"] = True

                    message = (
                        f"🟢 *LỆNH MUA MỚI (VÀO LỆNH)*\n\n"
                        f"Mua **{jto_to_buy:.4f} JTO** với giá **${current_price:,.4f}**.\n\n"
                        f"Tổng đầu tư: **${trade_state['total_invested']:.2f}**"
                    )
                    print(message)
                    send_telegram_message(message)

                # ----- LOGIC KHI ĐANG TRONG 1 CHU KỲ -----
                else:
                    # 1. KIỂM TRA CHỐT LỜI
                    current_value = trade_state["total_jto_bought"] * current_price
                    profit_target = trade_state["total_invested"] * (1 + TAKE_PROFIT_PERCENTAGE)

                    if current_value >= profit_target:
                        profit = current_value - trade_state['total_invested']
                        message = (
                            f"💰 *CHỐT LỜI THÀNH CÔNG!*\n\n"
                            f"Bán **{trade_state['total_jto_bought']:.4f} JTO** tại giá **${current_price:,.4f}**.\n\n"
                            f"Tổng đầu tư: `${trade_state['total_invested']:.2f}`\n"
                            f"Tổng thu về: `${current_value:.2f}`\n"
                            f"Lợi nhuận: **+${profit:.2f}**\n\n"
                            f"--- Bắt đầu chu kỳ mới ---"
                        )
                        print(message)
                        send_telegram_message(message)
                        trade_state = reset_trading_cycle()
                        time.sleep(5) 
                        continue

                    # 2. KIỂM TRA MUA THÊM (DCA)
                    next_dca_level = trade_state["dca_level"] + 1
                    dca_trigger_price = trade_state["initial_price"] * (1 - (next_dca_level * DCA_PERCENTAGE))

                    if current_price <= dca_trigger_price:
                        jto_to_buy = BUY_AMOUNT_USD / current_price
                        trade_state["total_invested"] += BUY_AMOUNT_USD
                        trade_state["total_jto_bought"] += jto_to_buy
                        trade_state["dca_level"] = next_dca_level
                        
                        avg_price = trade_state["total_invested"] / trade_state["total_jto_bought"]

                        message = (
                            f"🔵 *LỆNH MUA THÊM (DCA {trade_state['dca_level']})*\n\n"
                            f"Giá giảm xuống **${current_price:,.4f}**.\n"
                            f"Mua thêm **{jto_to_buy:.4f} JTO**.\n\n"
                            f"Tổng đầu tư: **${trade_state['total_invested']:.2f}**\n"
                            f"Giá trung bình mới: **${avg_price:,.4f}**"
                        )
                        print(message)
                        send_telegram_message(message)

                print(f"Giá hiện tại: ${current_price:,.4f} | Tổng đầu tư: ${trade_state['total_invested']:.2f} | JTO: {trade_state['total_jto_bought']:.4f}")
                time.sleep(15)

        except KeyboardInterrupt:
            print("\nĐã dừng bot.")
            send_telegram_message("🔴 *Bot đã dừng hoạt động.*")
