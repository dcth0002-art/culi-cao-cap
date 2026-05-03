import asyncio
import os
import ccxt.async_support as ccxt
from dotenv import load_dotenv

load_dotenv()

BINANCE_API_KEY = os.getenv("BINANCE_API_KEY")
BINANCE_SECRET = os.getenv("BINANCE_SECRET")
OKX_API_KEY = os.getenv("OKX_API_KEY")
OKX_SECRET = os.getenv("OKX_SECRET")
OKX_PASSWORD = os.getenv("OKX_PASSWORD")

def xu_ly_loai_bo_coin(bot):
    """Đọc file exclude.txt và xóa coin khỏi danh sách quét của main"""
    if hasattr(bot, '_exclude_done'):
        return
    
    file_path = os.path.join(os.path.dirname(__file__), 'exclude.txt')
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                exclude_list = [line.strip() for line in f if line.strip()]
            
            removed = []
            for sym in exclude_list:
                if sym in bot.common_symbols:
                    bot.common_symbols.remove(sym)
                    removed.append(sym)
            
            if removed:
                print(f"🚫 [HỆ THỐNG] Đã loại bỏ {len(removed)} đồng từ exclude.txt: {removed}")
        except Exception as e:
            print(f"⚠️ Lỗi đọc file exclude.txt: {e}")
    
    bot._exclude_done = True

async def get_exec_exchanges(bot):
    if not hasattr(bot, 'exec_binance'):
        bot.exec_binance = ccxt.binance({
            'apiKey': BINANCE_API_KEY,
            'secret': BINANCE_SECRET,
            'enableRateLimit': True,
            'options': {'defaultType': 'future'}
        })
        bot.exec_okx = ccxt.okx({
            'apiKey': OKX_API_KEY,
            'secret': OKX_SECRET,
            'password': OKX_PASSWORD,
            'enableRateLimit': True
        })
        await asyncio.gather(bot.exec_binance.load_markets(), bot.exec_okx.load_markets())
    return bot.exec_binance, bot.exec_okx

async def thuc_hien_vao_lenh_real(bot, sym, direction, margin, leverage, pos, send_telegram):
    try:
        ex_b, ex_o = await get_exec_exchanges(bot)
        sym_b, sym_o = sym, f"{sym}:USDT"
        
        if sym_o not in ex_o.markets:
            alt = sym.replace("/", "-") + "-SWAP"
            if alt in ex_o.markets: sym_o = alt
            else: raise Exception(f"OKX không hỗ trợ Futures cho {sym}")

        try:
            await asyncio.gather(
                ex_b.set_leverage(leverage, sym_b),
                ex_o.set_leverage(leverage, sym_o)
            )
        except: pass

        tickers = await asyncio.gather(ex_b.fetch_ticker(sym_b), ex_o.fetch_ticker(sym_o))
        p_b, p_o = tickers[0]['last'], tickers[1]['last']
        amount_b = float(ex_b.amount_to_precision(sym_b, (margin * leverage) / p_b))
        amount_o = float(ex_o.amount_to_precision(sym_o, (margin * leverage) / p_o))

        pos.update({'real_qty_b': amount_b, 'real_qty_o': amount_o, 'sym_o_futures': sym_o})

        if direction == "B_LONG_O_SHORT":
            tasks = [ex_b.create_market_buy_order(sym_b, amount_b),
                     ex_o.create_market_sell_order(sym_o, amount_o, {'posSide': 'short'})]
        else:
            tasks = [ex_o.create_market_buy_order(sym_o, amount_o, {'posSide': 'long'}),
                     ex_b.create_market_sell_order(sym_b, amount_b)]

        await asyncio.gather(*tasks)
        pos['status'] = 'open'
        send_telegram(f"✅ *[REAL]* Đã vào lệnh `{sym}` thành công!")

    except Exception as e:
        send_telegram(f"❌ *LỖI VÀO LỆNH `{sym}`:* {str(e)}")
        pos.update({"open": False, "status": "idle", "real_qty_b": None, "real_qty_o": None})
        bot.active_trade = None
        if sym in bot.common_symbols:
            bot.common_symbols.remove(sym)

def xu_ly_vao_lenh(bot, sym, pos, res, MARGIN_PER_TRADE, SPREAD_ENTRY, FEE_OPEN, send_telegram):
    # Tự động thực hiện loại bỏ coin từ exclude.txt khi bot bắt đầu quét
    xu_ly_loai_bo_coin(bot)

    if not pos["open"] and bot.active_trade is None:
        direction = None
        if res['s1'] > SPREAD_ENTRY: direction = "B_LONG_O_SHORT"
        elif res['s2'] > SPREAD_ENTRY: direction = "O_LONG_B_SHORT"

        if direction:
            bot.active_trade = sym
            pos.update({"open": True, "direction": direction, "entry_spread": res['s1'] if direction == "B_LONG_O_SHORT" else res['s2'], "status": "opening"})
            bot.balance -= FEE_OPEN
            asyncio.create_task(thuc_hien_vao_lenh_real(bot, sym, direction, MARGIN_PER_TRADE, 10, pos, send_telegram))
            send_telegram(f"🚀 *[REAL]* Đang mở vị thế `{sym}`...")
