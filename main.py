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
    fetch_gold_price_yesterday,
    fetch_dollar_prices,
    fetch_yesterday_close,
    fetch_market_data
)
from utils.data_processor import process_market_data
from utils.telegram_sender import send_to_telegram
from utils.holidays import is_iranian_holiday

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
        logger.info("🚀 شروع اجرای Gold Market Tracker")
        logger.info("=" * 60)

        # بررسی تعطیلی
        tehran_tz = pytz.timezone('Asia/Tehran')
        now = datetime.now(tehran_tz)
        if is_iranian_holiday(now):
            logger.info(f"📅 امروز {now.strftime('%Y-%m-%d')} تعطیل است. برنامه اجرا نمی‌شود.")
            return

        logger.info(f"📅 تاریخ: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        # دریافت متغیرهای محیطی
        telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        api_id = int(os.getenv('TELETHON_API_ID'))
        api_hash = os.getenv('TELETHON_API_HASH')
        session_str = os.getenv('TELEGRAM_SESSION')

        if not all([telegram_bot_token, telegram_chat_id, api_id, api_hash, session_str]):
            logger.error("❌ متغیرهای محیطی کامل نیست!")
            return

        async with TelegramClient(StringSession(session_str), api_id, api_hash) as client:
            # 1. دریافت قیمت طلای امروز
            logger.info("📊 دریافت قیمت اونس طلای امروز...")
            gold_today, gold_today_time = await fetch_gold_price_today(client)
            if not gold_today:
                logger.error("❌ خطا در دریافت قیمت طلای امروز")
                return
            logger.info(f"✅ قیمت طلای امروز: ${gold_today:,.2f}")

            # 2. دریافت قیمت طلای دیروز
            logger.info("📊 دریافت قیمت اونس طلای دیروز...")
            gold_yesterday = await fetch_gold_price_yesterday(client)
            if gold_yesterday:
                logger.info(f"✅ قیمت طلای دیروز: ${gold_yesterday:,.2f}")
            else:
                logger.warning("⚠️ نتوانستیم قیمت دیروز را بگیریم، از مقدار پیش‌فرض استفاده می‌کنیم")
                gold_yesterday = 4085.06

            # 3. دریافت قیمت‌های دلار
            logger.info("💵 دریافت قیمت‌های دلار...")
            dollar_prices = await fetch_dollar_prices(client)
            if not dollar_prices:
                logger.error("❌ خطا در دریافت قیمت دلار")
                return
            logger.info(f"✅ آخرین معامله دلار: {dollar_prices['last_trade']:,} تومان")

            # 4. دریافت آخرین معامله دیروز
            logger.info("📈 دریافت قیمت بسته دیروز...")
            yesterday_close = await fetch_yesterday_close(client)
            if yesterday_close:
                logger.info(f"✅ قیمت بسته دیروز: {yesterday_close:,} تومان")

            # 5. دریافت داده‌های بازار
            logger.info("🏦 دریافت داده‌های صندوق‌ها...")
            market_data = await fetch_market_data()
            if not market_data:
                logger.error("❌ خطا در دریافت داده‌های بازار")
                return
            logger.info("✅ داده‌های بازار دریافت شد")

            # 6. پردازش داده‌ها
            logger.info("⚙️ پردازش داده‌ها...")
            processed_data = process_market_data(
                market_data=market_data,
                gold_price=gold_today,
                last_trade=dollar_prices['last_trade'],
                yesterday_close=yesterday_close,
                gold_yesterday=gold_yesterday
            )
            logger.info("✅ پردازش تکمیل شد")

            # 7. ارسال به تلگرام
            logger.info("📤 ارسال به تلگرام...")
            success = await send_to_telegram(
                client=client,
                bot_token=telegram_bot_token,
                chat_id=telegram_chat_id,
                data=processed_data,
                dollar_prices=dollar_prices,
                gold_price=gold_today,
                gold_yesterday=gold_yesterday,
                gold_time=gold_today_time,
                yesterday_close=yesterday_close
            )

            if success:
                logger.info("✅ ارسال موفقیت‌آمیز بود!")
            else:
                logger.error("❌ خطا در ارسال")

        logger.info("=" * 60)
        logger.info("✅ پایان اجرا")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    asyncio.run(main())
