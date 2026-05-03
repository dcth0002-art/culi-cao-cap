import asyncio

async def thuc_hien_dong_lenh_real(bot, sym, pos, send_telegram):
    try:
        ex_b = bot.exec_binance
        ex_o = bot.exec_okx

        sym_b = sym
        sym_o = pos.get('sym_o_futures')

        # 1. Truy vấn vị thế thực tế bằng hàm fetch_positions (số nhiều)
        # Chúng ta truyền mảng [symbol] để lọc lấy đúng đồng đó
        tasks_pos = [
            ex_b.fetch_positions([sym_b]),
            ex_o.fetch_positions([sym_o])
        ]
        res_pos = await asyncio.gather(*tasks_pos)

        # Kết quả trả về là một danh sách, ta lấy phần tử đầu tiên
        pos_b_list = res_pos[0]
        pos_o_list = res_pos[1]

        pos_b = pos_b_list[0] if len(pos_b_list) > 0 else None
        pos_o = pos_o_list[0] if len(pos_o_list) > 0 else None

        close_tasks = []

        # 2. Xử lý đóng vị thế trên Binance
        if pos_b:
            # CCXT trả về khối lượng trong 'contracts' hoặc 'contractSize' * 'contracts'
            # Ở Binance USDT-M, 'contracts' chính là số lượng coin
            qty_b = float(pos_b.get('contracts', 0))
            if qty_b != 0:
                side_b = 'sell' if pos_b['side'] == 'long' else 'buy'
                close_tasks.append(ex_b.create_market_order(
                    symbol=sym_b,
                    side=side_b,
                    amount=abs(qty_b),
                    params={'reduceOnly': True}
                ))

        # 3. Xử lý đóng vị thế trên OKX
        if pos_o:
            qty_o = float(pos_o.get('contracts', 0))
            if qty_o != 0:
                side_o = 'sell' if pos_o['side'] == 'long' else 'buy'
                close_tasks.append(ex_o.create_market_order(
                    symbol=sym_o,
                    side=side_o,
                    amount=abs(qty_o),
                    params={'posSide': pos_o['side'], 'reduceOnly': True}
                ))

        if close_tasks:
            await asyncio.gather(*close_tasks)
            send_telegram(f"🏁 *[REAL]* Đã quét sạch và ĐÓNG TOÀN BỘ vị thế `{sym}` thành công!")
        else:
            send_telegram(f"⚠️ *[REAL]* Không tìm thấy vị thế mở của `{sym}` để đóng.")

        # Dọn dẹp trạng thái
        pos.update({"open": False, "status": "idle", "real_qty_b": None, "real_qty_o": None})
        bot.active_trade = None

    except Exception as e:
        send_telegram(f"❌ *LỖI ĐÓNG LỆNH KHẨN CẤP:* {str(e)}\n⚠️ Kiểm tra sàn ngay!")
        pos['status'] = 'open'

def xu_ly_dong_lenh(bot, sym, pos, res, SPREAD_EXIT, SPREAD_STOP, MARGIN_PER_TRADE, LEVERAGE, FEE_CLOSE, send_telegram):
    if pos["open"] and sym == bot.active_trade:
        if pos.get('status') in ['opening', 'closing']:
            return

        curr_s = res['s1'] if pos['direction'] == "B_LONG_O_SHORT" else res['s2']

        if curr_s < SPREAD_EXIT or curr_s > SPREAD_STOP:
            pos['status'] = 'closing'

            volume = MARGIN_PER_TRADE * LEVERAGE
            bot.balance += (pos["entry_spread"] - curr_s) * volume - FEE_CLOSE

            asyncio.create_task(thuc_hien_dong_lenh_real(bot, sym, pos, send_telegram))
            send_telegram(f"⏳ *[REAL]* Spread đạt `{curr_s*100:.3f}%` -> Đang đóng khẩn cấp `{sym}`...")
