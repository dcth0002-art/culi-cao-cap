# Bạn cần cài đặt thư viện requests trước khi chạy mã này
# Mở terminal và chạy lệnh: pip install requests

import requests

# --- CẤU HÌNH BOT TELEGRAM ---
# THAY THẾ CÁC GIÁ TRỊ DƯỚI ĐÂY
TELEGRAM_BOT_TOKEN = "8536602142:AAEnCocktZ-MMGke0K9OVCbepaKooQ0z2BE"  # Thay bằng Token của bot bạn
TELEGRAM_CHAT_ID = "5919982628"      # Thay bằng Chat ID của bạn hoặc group

def send_telegram_message(message):
    """Hàm này chỉ làm một nhiệm vụ: Gửi tin nhắn đến Telegram."""
    if not TELEGRAM_BOT_TOKEN or "YOUR_BOT_TOKEN" in TELEGRAM_BOT_TOKEN:
        print("Lỗi: Vui lòng cấu hình TELEGRAM_BOT_TOKEN trong file baocao_tele.py")
        return

    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    params = {'chat_id': TELEGRAM_CHAT_ID, 'text': message}
    try:
        response = requests.post(api_url, params=params, timeout=5)
        print(">>> báo cáo lệch giá")
    except Exception as e:
        print(f">>> Lỗi khi gửi tin nhắn Telegram: {e}")

# File này giờ chỉ chứa hàm, không tự chạy nữa.
