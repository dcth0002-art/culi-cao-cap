import asyncio
import ccxt.async_support as ccxt
import os
import time
from dotenv import load_dotenv
import telebot

# Load môi trường
load_dotenv()

# ================= CONFIG DEMO =================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8536602142:AAEnCocktZ-MMGke0K9OVCbepaKooQ0z2BE")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "5919982628")

# Cấu hình tài chính Demo
INITIAL_TOTAL_CAPITAL = 200.0  # Tổng vốn 2 sàn (100$ mỗi sàn)
LEVERAGE = 10                  # Đòn bẩy 10x
MARGIN_PER_TRADE = 100.0       # Ký quỹ mỗi sàn cho 1 lệnh (100$ x 2 sàn = 200$)
FEE_OPEN = 1.0                 # Tổng phí mở lệnh (0.5$ * 2 sàn)
FEE_CLOSE = 1.0                # Tổng phí đóng lệnh (0.5$ * 2 sàn)

# Logic spread
SPREAD_ENTRY = 0.0035   
SPREAD_EXIT = 0.001     
SPREAD_STOP = 0.008     

UPDATE_INTERVAL = 600   # 10 phút báo cáo Top Spread 1 lần
SCAN_INTERVAL = 5       

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

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
        
        print(f"✅ Đã tìm thấy {len(self.common_symbols)} cặp tiền. Sẵn sàng Demo!")

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
        await self.init_markets()
        send_telegram(f"🧪 *BẮT ĐẦU CHẾ ĐỘ TRÂY DEMO*\n💰 Vốn ban đầu: `{INITIAL_TOTAL_CAPITAL}$` ($100/sàn)\n⚙️ Đòn bẩy: `{LEVERAGE}x` | Phí: `$2.0` mỗi vòng.")

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
                    
                    # 1. LOGIC VÀO LỆNH
                    if not pos["open"] and self.active_trade is None:
                        # Kiểm tra đủ vốn (Phải đủ 200$ để vào 1 lệnh arbitrage)
                        if self.balance >= (MARGIN_PER_TRADE * 2):
                            direction = None
                            if res['s1'] > SPREAD_ENTRY: direction = "B_LONG_O_SHORT"
                            elif res['s2'] > SPREAD_ENTRY: direction = "O_LONG_B_SHORT"
                            
                            if direction:
                                entry_s = res['s1'] if direction == "B_LONG_O_SHORT" else res['s2']
                                self.active_trade = sym
                                pos.update({"open": True, "direction": direction, "entry_spread": entry_s})
                                # Trừ phí vào lệnh
                                self.balance -= FEE_OPEN
                                send_telegram(f"🚀 *[DEMO - VÀO LỆNH]* `{sym}`\n↕️ `{direction}`\n📊 Spread: `{entry_s*100:.3f}%`\n💸 Phí mở: `$1.0` | Vốn còn: `${self.balance:.2f}`")
                        else:
                            # Không đủ vốn, chỉ in log console
                            pass

                    # 2. LOGIC ĐÓNG LỆNH (Chỉ xét mã đang mở)
                    elif pos["open"] and sym == self.active_trade:
                        curr_s = res['s1'] if pos['direction'] == "B_LONG_O_SHORT" else res['s2']
                        
                        is_tp = curr_s < SPREAD_EXIT
                        is_sl = curr_s > SPREAD_STOP
                        
                        if is_tp or is_sl:
                            # Tính PnL = (Spread vào - Spread ra) * Volume (Volume = Margin * Leverage)
                            volume = MARGIN_PER_TRADE * LEVERAGE
                            gross_pnl = (pos["entry_spread"] - curr_s) * volume
                            net_pnl = gross_pnl - FEE_CLOSE
                            
                            self.balance += net_pnl
                            self.total_pnl += net_pnl
                            
                            res_msg = "CHỐT LỜI ✅" if is_tp else "CẮT LỖ ❌"
                            send_telegram(f"{'💰' if net_pnl > 0 else '📉'} *[DEMO - ĐÓNG LỆNH]* `{sym}`\n📝 Lý do: `{res_msg}`\n📈 Lãi ròng: `{net_pnl:.2f}$` (Đã trừ phí)\n🏦 Vốn hiện tại: `${self.balance:.2f}`\n📊 Tổng lãi/lỗ: `${self.total_pnl:.2f}`")
                            
                            pos["open"] = False
                            self.active_trade = None

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
