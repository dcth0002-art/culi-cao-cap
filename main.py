import asyncio
import ccxt.async_support as ccxt
import os
import time
from dotenv import load_dotenv
import telebot

# Load môi trường
load_dotenv()

# ================= CONFIG =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8536602142:AAEnCocktZ-MMGke0K9OVCbepaKooQ0z2BE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5919982628")

# Giữ nguyên logic spread của bạn
SPREAD_ENTRY = 0.0035   # 0.35% để vào lệnh
SPREAD_EXIT = 0.001     # 0.1% để chốt lời
SPREAD_STOP = 0.008     # 0.8% để cắt lỗ

UPDATE_INTERVAL = 600   # 10 phút gửi báo cáo Top Spread 1 lần
SCAN_INTERVAL = 5       # Quét lại toàn bộ thị trường sau mỗi 5 giây

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

def send_telegram(msg):
    try:
        bot.send_message(TELEGRAM_CHAT_ID, msg, parse_mode='Markdown')
    except Exception as e:
        print(f"Lỗi Telegram: {e}")

class ArbitrageBot:
    def __init__(self):
        # Bạn có thể thêm nhiều sàn vào đây cực dễ: 'bybit', 'gateio', 'mexc'...
        self.exchanges = {
            'binance': ccxt.binance({'enableRateLimit': True}),
            'okx': ccxt.okx({'enableRateLimit': True})
        }
        self.common_symbols = []
        self.positions = {}
        self.last_report_time = 0

    async def init_markets(self):
        """Tự động tìm các cặp tiền chung giữa các sàn"""
        print("🔍 Đang đồng bộ danh sách coin giữa các sàn...")
        for ex in self.exchanges.values():
            await ex.load_markets()
        
        # Chỉ lấy Spot /USDT chuẩn xuất hiện ở cả 2 sàn
        b_syms = [s for s in self.exchanges['binance'].symbols if '/USDT' in s and ':' not in s]
        o_syms = [s for s in self.exchanges['okx'].symbols if '/USDT' in s and ':' not in s]
        
        self.common_symbols = list(set(b_syms) & set(o_syms))
        # Khởi tạo trạng thái cho từng mã
        for s in self.common_symbols:
            self.positions[s] = {"open": False, "direction": None, "entry_spread": 0}
        
        print(f"✅ Đã tìm thấy {len(self.common_symbols)} cặp tiền chung.")

    async def fetch_spread(self, symbol):
        """Lấy giá từ 2 sàn cùng lúc và tính spread"""
        try:
            tasks = [
                self.exchanges['binance'].fetch_ticker(symbol),
                self.exchanges['okx'].fetch_ticker(symbol)
            ]
            tickers = await asyncio.gather(*tasks)
            binance, okx = tickers[0], tickers[1]
            
            # S1: Long Binance - Short OKX (OKX giá cao hơn)
            s1 = (okx['bid'] - binance['ask']) / binance['ask']
            # S2: Long OKX - Short Binance (Binance giá cao hơn)
            s2 = (binance['bid'] - okx['ask']) / okx['ask']
            
            return {'symbol': symbol, 's1': s1, 's2': s2, 'max_s': max(s1, s2)}
        except:
            return None

    async def run(self):
        await self.init_markets()
        send_telegram(f"🚀 *Bot Arbitrage Async ONLINE*\nĐang quét `{len(self.common_symbols)}` cặp tiền.")

        while True:
            try:
                # Quét hàng trăm mã cùng lúc (Async)
                tasks = [self.fetch_spread(s) for s in self.common_symbols]
                results = await asyncio.gather(*tasks)
                results = [r for r in results if r]

                # SẮP XẾP: Mã có độ lệch cao nhất nằm trên cùng -> Dễ tìm lệnh
                results.sort(key=lambda x: x['max_s'], reverse=True)
                
                report_lines = []
                for i, res in enumerate(results):
                    sym = res['symbol']
                    pos = self.positions[sym]
                    
                    # Logic Vào Lệnh
                    if not pos["open"]:
                        if res['s1'] > SPREAD_ENTRY:
                            pos.update({"open": True, "direction": "B_LONG_O_SHORT", "entry_spread": res['s1']})
                            send_telegram(f"🔥 *[VÀO LỆNH]* {sym}\nLONG Binance - SHORT OKX\nSpread: `{res['s1']*100:.3f}%`")
                        elif res['s2'] > SPREAD_ENTRY:
                            pos.update({"open": True, "direction": "O_LONG_B_SHORT", "entry_spread": res['s2']})
                            send_telegram(f"🔥 *[VÀO LỆNH]* {sym}\nLONG OKX - SHORT Binance\nSpread: `{res['s2']*100:.3f}%`")
                    
                    # Logic Chốt Lời / Cắt Lỗ
                    else:
                        curr_s = res['s1'] if pos['direction'] == "B_LONG_O_SHORT" else res['s2']
                        if curr_s < SPREAD_EXIT:
                            profit = (pos["entry_spread"] - curr_s) * 100
                            send_telegram(f"💰 *[CHỐT LỜI]* {sym}\nLợi nhuận: `{profit:.2f}%` (Spread còn {curr_s*100:.3f}%)")
                            pos["open"] = False
                        elif curr_s > SPREAD_STOP:
                            send_telegram(f"⚠️ *[CẮT LỖ]* {sym}\nSpread dãn quá lớn: `{curr_s*100:.2f}%`")
                            pos["open"] = False

                    # Gom Top 5 cho báo cáo định kỳ
                    if i < 5 or pos["open"]:
                        icon = "💎" if pos["open"] else "🔍"
                        report_lines.append(f"{icon} {sym}: `{res['max_s']*100:.3f}%`")

                # Gửi báo cáo Top Spread
                if time.time() - self.last_report_time > UPDATE_INTERVAL:
                    msg = "📊 *TOP CƠ HỘI (SPREAD GIẢM DẦN)*\n" + "\n".join(report_lines)
                    send_telegram(msg)
                    self.last_report_time = time.time()

                await asyncio.sleep(SCAN_INTERVAL)
            except Exception as e:
                print(f"Lỗi vòng lặp: {e}")
                await asyncio.sleep(10)

if __name__ == "__main__":
    bot_engine = ArbitrageBot()
    try:
        asyncio.run(bot_engine.run())
    except KeyboardInterrupt:
        pass
