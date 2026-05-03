import asyncio
import ccxt.async_support as ccxt
import os
import time
from dotenv import load_dotenv
import telebot
import requests

# Import logic demo từ các file ngoài
from molenhdemo import xu_ly_vao_lenh
from donglenhdemo import xu_ly_dong_lenh

# Load môi trường
load_dotenv()

# ================= CONFIG DEMO =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8536602142:AAEnCocktZ-MMGke0K9OVCbepaKooQ0z2BE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5919982628")

# API Keys để đặt lệnh
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET = os.getenv("BINANCE_SECRET")
OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_SECRET = os.getenv("OKX_SECRET")
OKX_PASSWORD = os.getenv("OKX_PASSWORD")

# Cấu hình tài chính Demo
INITIAL_TOTAL_CAPITAL = 31.0  # Tổng vốn 2 sàn (100$ mỗi sàn)
LEVERAGE = 10                  # Đòn bẩy 10x
MARGIN_PER_TRADE = 5.0       # Ký quỹ mỗi sàn cho 1 lệnh (100$ x 2 sàn = 200$)
FEE_OPEN = 0.1                 # Tổng phí mở lệnh (0.5$ * 2 sàn)
FEE_CLOSE = 0.1                # Tổng phí đóng lệnh (0.5$ * 2 sàn)

# Logic spread
SPREAD_ENTRY = 0.0100
SPREAD_EXIT = 0.0002     
SPREAD_STOP = 1.008

UPDATE_INTERVAL = 600   # 10 phút báo cáo Top Spread 1 lần
SCAN_INTERVAL = 1

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

def get_public_ip():
    try:
        ip = requests.get("https://api.ipify.org", timeout=5).text
        print(f"🌐 IP hiện tại: {ip}")
        return ip
    except Exception as e:
        print(f"Lỗi lấy IP: {e}")
        return None

def send_telegram(msg):
    try:
        bot.send_message(TELEGRAM_CHAT_ID, msg, parse_mode='Markdown')
    except Exception as e:
        print(f"Lỗi Telegram: {e}")

class ArbitrageBotDemo:
    def __init__(self):
        self.exchanges = {
            'binance': ccxt.binance({'enableRateLimit': True}),
            'okx': ccxt.okx({'enableRateLimit': True})
        }
        self.common_symbols = []
        self.positions = {}
        self.last_report_time = 0
        
        # Biến Demo
        self.balance = INITIAL_TOTAL_CAPITAL
        self.total_pnl = 0.0
        self.active_trade = None  # Theo dõi mã đang trây

    async def init_markets(self):
        print("🔍 Đang đồng bộ danh sách coin giữa các sàn...")
        for ex in self.exchanges.values():
            await ex.load_markets()
        
        b_syms = [s for s in self.exchanges['binance'].symbols if '/USDT' in s and ':' not in s]
        o_syms = [s for s in self.exchanges['okx'].symbols if '/USDT' in s and ':' not in s]
        
        self.common_symbols = list(set(b_syms) & set(o_syms))
        for s in self.common_symbols:
            self.positions[s] = {"open": False, "direction": None, "entry_spread": 0}
        
        print(f"✅ Đã tìm thấy {len(self.common_symbols)} cặp tiền. Sẵn sàng!")

    async def fetch_spread(self, symbol):
        try:
            tasks = [self.exchanges['binance'].fetch_ticker(symbol), self.exchanges['okx'].fetch_ticker(symbol)]
            tickers = await asyncio.gather(*tasks)
            binance, okx = tickers[0], tickers[1]
            s1 = (okx['bid'] - binance['ask']) / binance['ask'] # OKX cao hơn
            s2 = (binance['bid'] - okx['ask']) / okx['ask'] # Binance cao hơn
            return {'symbol': symbol, 's1': s1, 's2': s2, 'max_s': max(s1, s2)}
        except: return None

    async def run(self):
        ip = get_public_ip()

        if ip:
            send_telegram(f"🌐 IP hiện tại: `{ip}`")

        await self.init_markets()
        send_telegram(f"🧪 *BẮT ĐẦU CHẾ ĐỘ TRÂY *\n💰 Vốn ban đầu: `{INITIAL_TOTAL_CAPITAL}$` ($5/sàn)\n⚙️ Đòn bẩy: `{LEVERAGE}x` | Phí: `$0.1` mỗi vòng.")

        while True:
            try:
                tasks = [self.fetch_spread(s) for s in self.common_symbols]
                results = await asyncio.gather(*tasks)
                results = [r for r in results if r]
                results.sort(key=lambda x: x['max_s'], reverse=True)
                
                status_lines = []
                for i, res in enumerate(results):
                    sym = res['symbol']
                    pos = self.positions[sym]
                    
                    # Gọi logic từ các file demo
                    xu_ly_vao_lenh(self, sym, pos, res, MARGIN_PER_TRADE, SPREAD_ENTRY, FEE_OPEN, send_telegram)
                    xu_ly_dong_lenh(self, sym, pos, res, SPREAD_EXIT, SPREAD_STOP, MARGIN_PER_TRADE, LEVERAGE, FEE_CLOSE, send_telegram)

                    if i < 5 or pos["open"]:
                        icon = "💎" if pos["open"] else "🔍"
                        status_lines.append(f"{icon} {sym}: `{res['max_s']*100:.3f}%`")

                # Báo cáo định kỳ
                if time.time() - self.last_report_time > UPDATE_INTERVAL:
                    report = (f"📊 *BÁO CÁO TÀI KHOẢN DEMO*\n"
                              f"🏦 Vốn hiện tại: `${self.balance:.2f}`\n"
                              f"📈 Tổng PnL: `${self.total_pnl:.2f}`\n"
                              f"📍 Trạng thái: `{'Trây ' + self.active_trade if self.active_trade else 'Đang săn kèo'}`\n\n"
                              f"*Top 5 Spread:*\n" + "\n".join(status_lines[:5]))
                    send_telegram(report)
                    self.last_report_time = time.time()

                await asyncio.sleep(SCAN_INTERVAL)
            except Exception as e:
                print(f"Lỗi: {e}")
                await asyncio.sleep(10)

if __name__ == "__main__":
    bot_engine = ArbitrageBotDemo()
    try:
        asyncio.run(bot_engine.run())
    except KeyboardInterrupt:
        pass
