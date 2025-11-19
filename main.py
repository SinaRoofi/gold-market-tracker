# main.py — نسخه Google Sheets

import os
import sys
import logging
from datetime import datetime
import pytz
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

from utils.data_fetcher import (
    fetch_gold_price_today,
    fetch_dollar_prices,
    fetch_yesterday_close,
    fetch_market_data
)
from utils.gold_cache import get_gold_yesterday
from utils.data_processor import process_market_data
from utils.telegram_sender import send_to_telegram
from utils.holidays import is_iranian_holiday
from utils.sheets_storage import save_to_sheets  # ← تغییر اصلی

# تنظیمات لاگ
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gold_tracker.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

async def main():
    try:
        logger.info("=" * 60)
        logger.info("شروع اجرای Gold Market Tracker با Google Sheets")
        logger.info("=" * 60)

        tehran_tz = pytz.timezone('Asia/Tehran')
        now = datetime.now(tehran_tz)
        
        if is_iranian_holiday(now):
            logger.info(f"امروز {now.strftime('%Y-%m-%d')} تعطیل است.")
            return

        logger.info(f"زمان تهران: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        # متغیرهای محیطی
        bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        chat_id = os.getenv('TELEGRAM_CHAT_ID')
        api_id = int(os.getenv('TELETHON_API_ID'))
        api_hash = os.getenv('TELETHON_API_HASH')
        session_str = os.getenv('TELEGRAM_SESSION')

        if not all([bot_token, chat_id, api_id, api_hash, session_str]):
            logger.error("یکی از متغیرهای محیطی تلگرام پیدا نشد!")
            return

        async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
            # ۱. قیمت طلای جهانی
            gold_today, gold_time = await fetch_gold_price_today(client)
            if not gold_today:
                gold_today = 3300.0
                logger.warning("قیمت طلا گرفته نشد → پیش‌فرض 3300")

            gold_yesterday = get_gold_yesterday() or 3300.0

            # ۲. قیمت دلار
            dollar_prices = await fetch_dollar_prices(client)
            if not dollar_prices:
                dollar_prices = {'last_trade': 650000}
            last_trade = dollar_prices['last_trade']

            # ۳. قیمت بسته دیروز
            yesterday_close = await fetch_yesterday_close(client)
            if not yesterday_close or yesterday_close == 0:
                yesterday_close = last_trade

            # ۴. داده‌های بازار
            market_data = await fetch_market_data()
            if not market_data:
                logger.error("داده‌های بازار گرفته نشد")
                return

            # ۵. پردازش داده‌ها
            processed = process_market_data(
                market_data=market_data,
                gold_price=gold_today,
                last_trade=last_trade,
                yesterday_close=yesterday_close,
                gold_yesterday=gold_yesterday
            )
            if not processed:
                logger.error("پردازش داده ناموفق")
                return

            Fund_df = processed['Fund_df']
            dfp = processed['dfp']

            # محاسبه میانگین‌های وزنی
            total_value = Fund_df["value"].sum() or 1
            fund_change_weighted = (Fund_df["close_price_change_percent"] * Fund_df["value"]).sum() / total_value
            sarane_kharid_w = (Fund_df["sarane_kharid"] * Fund_df["value"]).sum() / total_value
            sarane_forosh_w = (Fund_df["sarane_forosh"] * Fund_df["value"]).sum() / total_value
            ekhtelaf_sarane_w = sarane_kharid_w - sarane_forosh_w

            dollar_change = ((last_trade - yesterday_close) / yesterday_close) * 100 if yesterday_close else 0
            shams_change = dfp.loc["شمش-طلا", "close_price_change_percent"] if "شمش-طلا" in dfp.index else 0

            # ✅ ذخیره در Google Sheets
            save_to_sheets({
                'gold_price': gold_today,
                'dollar_change': dollar_change,
                'shams_change': shams_change,
                'fund_change_weighted': fund_change_weighted,
                'sarane_kharid_w': sarane_kharid_w,
                'sarane_forosh_w': -sarane_forosh_w,
                'ekhtelaf_sarane_w': ekhtelaf_sarane_w,
            })

            # ارسال به تلگرام
            success = send_to_telegram(
                bot_token=bot_token,
                chat_id=chat_id,
                data=processed,
                dollar_prices=dollar_prices,
                gold_price=gold_today,
                gold_yesterday=gold_yesterday,
                gold_time=gold_time,
                yesterday_close=yesterday_close
            )

            if success:
                logger.info("✅ ارسال به تلگرام با موفقیت انجام شد")
            else:
                logger.error("❌ ارسال به تلگرام ناموفق")

        logger.info("✅ اجرای موفق به پایان رسید")

    except Exception as e:
        logger.error(f"❌ خطای کلی: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
