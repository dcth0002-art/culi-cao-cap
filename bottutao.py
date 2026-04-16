import requests
import json
import hmac
import base64
import time
import os

# --- LẤY THÔNG TIN TỪ BIẾN MÔI TRƯỜNG ---
API_KEY = os.getenv("API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")
PASSPHRASE = os.getenv("PASSPHRASE")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
# -----------------------------------------

# --- CẤU HÌNH CÁC CẶP GIAO DỊCH ---
# <<< THAY ĐỔI: Thêm hoặc xóa các cặp tiền bạn muốn giao dịch ở đây
COIN_PAIRS_TO_TRADE = ["JTO-USDT", "BTC-USDT", "ETH-USDT", "KAITO-USDT", "PI-USDT", "DOGE-USDT", "SOL-USDT", "OKB-USDT", "XRP-USDT", "BCH-USDT", "LTC-USDT"] 
# ------------------------------------

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
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("Vui lòng cung cấp TELEGRAM_BOT_TOKEN và TELEGRAM_CHAT_ID.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
    try:
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Lỗi khi gửi tin nhắn Telegram: {response.text}")
    except Exception as e:
        print(f"Lỗi kết nối đến Telegram: {e}")

# <<< THAY ĐỔI: Hàm được làm linh hoạt hơn để lấy giá cho bất kỳ coin nào
def get_price(instId):
    """Lấy giá của một cặp tiền cụ thể (ví dụ: 'JTO-USDT')."""
    request_path = f'/api/v5/market/ticker?instId={instId}'
    url = f"https://www.okx.com{request_path}"
    try:
        headers = get_auth_headers('GET', request_path)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if "data" in data and len(data["data"]) > 0:
            return float(data["data"][0]["last"])
    except Exception as e:
        print(f"Lỗi khi lấy giá {instId}: {e}")
    return None

def reset_trading_cycle():
    """Reset lại các biến cho chu kỳ giao dịch mới."""
    return {"total_invested": 0.0, "total_coin_bought": 0.0, "initial_price": 0.0, "dca_level": 0, "in_position": False}

if __name__ == "__main__":
    if not all([API_KEY, SECRET_KEY, PASSPHRASE]):
        print("VUI LÒNG CUNG CẤP ĐỦ BIẾN MÔI TRƯỜNG: API_KEY, SECRET_KEY, PASSPHRASE.")
    else:
        # --- CẤU HÌNH GIAO DỊCH ---
        BUY_AMOUNT_USD = 10.0
        DCA_PERCENTAGE = 0.03 # 3%
        TAKE_PROFIT_PERCENTAGE = 0.02 # 2%

        # <<< THAY ĐỔI: Tạo một dictionary để lưu trạng thái cho mỗi coin
        trade_states = {coin: reset_trading_cycle() for coin in COIN_PAIRS_TO_TRADE}
        
        print("Bot giao dịch đa coin DEMO đã khởi động...")
        send_telegram_message(f"🚀 *Bot giao dịch đa coin DEMO đã khởi động (trên Railway)* 🚀\n\nTheo dõi: {', '.join(COIN_PAIRS_TO_TRADE)}")

        try:
            while True:
                # <<< THAY ĐỔI: Vòng lặp mới để duyệt qua từng coin
                for coin_pair in COIN_PAIRS_TO_TRADE:
                    current_price = get_price(coin_pair)
                    if not current_price:
                        print(f"Không lấy được giá {coin_pair}, bỏ qua.")
                        continue # Bỏ qua coin này và tiếp tục với coin tiếp theo

                    trade_state = trade_states[coin_pair] # Lấy trạng thái của coin hiện tại
                    coin_name = coin_pair.split('-')[0] # Lấy tên coin (ví dụ: JTO)

                    # ----- LOGIC BẮT ĐẦU CHU KỲ MỚI -----
                    if not trade_state["in_position"]:
                        coin_to_buy = BUY_AMOUNT_USD / current_price
                        trade_state["total_invested"] = BUY_AMOUNT_USD
                        trade_state["total_coin_bought"] = coin_to_buy
                        trade_state["initial_price"] = current_price
                        trade_state["in_position"] = True

                        message = (
                            f"🟢 *LỆNH MUA MỚI ({coin_pair})*\n\n"
                            f"Mua **{coin_to_buy:.4f} {coin_name}** với giá **${current_price:,.4f}**.\n\n"
                            f"Tổng đầu tư: **${trade_state['total_invested']:.2f}**"
                        )
                        print(message)
                        send_telegram_message(message)

                    # ----- LOGIC KHI ĐANG TRONG 1 CHU KỲ -----
                    else:
                        # 1. KIỂM TRA CHỐT LỜI
                        current_value = trade_state["total_coin_bought"] * current_price
                        profit_target = trade_state["total_invested"] * (1 + TAKE_PROFIT_PERCENTAGE)

                        if current_value >= profit_target:
                            profit = current_value - trade_state['total_invested']
                            message = (
                                f"💰 *CHỐT LỜI THÀNH CÔNG ({coin_pair})!*\n\n"
                                f"Bán **{trade_state['total_coin_bought']:.4f} {coin_name}** tại giá **${current_price:,.4f}**.\n\n"
                                f"Tổng đầu tư: `${trade_state['total_invested']:.2f}`\n"
                                f"Tổng thu về: `${current_value:.2f}`\n"
                                f"Lợi nhuận: **+${profit:.2f}**\n\n"
                                f"--- Bắt đầu chu kỳ mới cho {coin_pair} ---"
                            )
                            print(message)
                            send_telegram_message(message)
                            trade_states[coin_pair] = reset_trading_cycle() # Reset chỉ coin này
                            continue

                        # 2. KIỂM TRA MUA THÊM (DCA)
                        next_dca_level = trade_state["dca_level"] + 1
                        dca_trigger_price = trade_state["initial_price"] * (1 - (next_dca_level * DCA_PERCENTAGE))

                        if current_price <= dca_trigger_price:
                            coin_to_buy = BUY_AMOUNT_USD / current_price
                            trade_state["total_invested"] += BUY_AMOUNT_USD
                            trade_state["total_coin_bought"] += coin_to_buy
                            trade_state["dca_level"] = next_dca_level
                            avg_price = trade_state["total_invested"] / trade_state["total_coin_bought"]

                            message = (
                                f"🔵 *LỆNH MUA THÊM (DCA {trade_state['dca_level']} - {coin_pair})*\n\n"
                                f"Giá giảm xuống **${current_price:,.4f}**.\n"
                                f"Mua thêm **{coin_to_buy:.4f} {coin_name}**.\n\n"
                                f"Tổng đầu tư: **${trade_state['total_invested']:.2f}**\n"
                                f"Giá trung bình mới: **${avg_price:,.4f}**"
                            )
                            print(message)
                            send_telegram_message(message)
                    
                    # Cập nhật lại trạng thái cho coin này trong dictionary chính
                    trade_states[coin_pair] = trade_state
                    print(f"[{coin_pair}] Giá: ${current_price:,.4f} | Đầu tư: ${trade_state['total_invested']:.2f} | Sở hữu: {trade_state['total_coin_bought']:.4f}")

                print("\n--- Hoàn thành chu kỳ kiểm tra tất cả các coin. Tạm nghỉ 15 giây. ---\n")
                time.sleep(15)

        except KeyboardInterrupt:
            print("\nĐã dừng bot.")
            send_telegram_message("🔴 *Bot đã dừng hoạt động.*")
