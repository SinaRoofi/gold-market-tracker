# main.py
"""
اسکریپت اصلی Gold Market Tracker
"""

import os
import sys
import logging
from datetime import datetime
import pytz
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELETHON_API_ID,
    TELETHON_API_HASH,
    TELEGRAM_SESSION,
    TIMEZONE,
    LOG_FORMAT,
    LOG_FILE,
    LOG_LEVEL,
    DEFAULT_GOLD_PRICE,
    DEFAULT_DOLLAR_PRICE
)
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
from utils.sheets_storage import save_to_sheets

# ════════════════════════════════════════════════════════════════
# تنظیمات Logging با زمان تهران
# ════════════════════════════════════════════════════════════════
class TehranFormatter(logging.Formatter):
    """Formatter برای تبدیل زمان لاگ به تهران"""
    def converter(self, timestamp):
        dt = datetime.fromtimestamp(timestamp, pytz.timezone(TIMEZONE))
        return dt.timetuple()

    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, pytz.timezone(TIMEZONE))
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

formatter = TehranFormatter(LOG_FORMAT)

file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)

logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
logger.addHandler(file_handler)
logger.addHandler(stream_handler)


async def main():
    """تابع اصلی برنامه"""
    try:
        logger.info("=" * 60)
        logger.info("🚀 شروع اجرای Gold Market Tracker")
        logger.info("=" * 60)

        tehran_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tehran_tz)

        if is_iranian_holiday(now):
            logger.info(f"🏖️ امروز {now.strftime('%Y-%m-%d')} تعطیل است.")
            return

        logger.info(f"🕐 زمان تهران: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELETHON_API_ID, 
                    TELETHON_API_HASH, TELEGRAM_SESSION]):
            logger.error("❌ یکی از متغیرهای محیطی تلگرام پیدا نشد!")
            return

        async with TelegramClient(StringSession(TELEGRAM_SESSION), 
                                 TELETHON_API_ID, 
                                 TELETHON_API_HASH) as client:

            logger.info("✅ اتصال به Telethon برقرار شد")

            # 1️⃣ دریافت قیمت طلای جهانی
            logger.info("🔆 دریافت قیمت طلای جهانی...")
            gold_today, gold_time = await fetch_gold_price_today(client)
            if not gold_today:
                gold_today = DEFAULT_GOLD_PRICE
                logger.warning(f"⚠️ قیمت طلا گرفته نشد → پیش‌فرض {DEFAULT_GOLD_PRICE}")
            else:
                logger.info(f"✅ قیمت طلا: ${gold_today:.2f}")

            gold_yesterday = get_gold_yesterday() or DEFAULT_GOLD_PRICE

            # 2️⃣ دریافت قیمت دلار
            logger.info("💵 دریافت قیمت‌های دلار...")
            dollar_prices = await fetch_dollar_prices(client)
            if not dollar_prices:
                dollar_prices = {'last_trade': DEFAULT_DOLLAR_PRICE, 'bid': 0, 'ask': 0}
                logger.warning(f"⚠️ قیمت دلار گرفته نشد → پیش‌فرض {DEFAULT_DOLLAR_PRICE}")
            else:
                last_trade = dollar_prices['last_trade']
                logger.info(f"✅ آخرین معامله دلار: {last_trade:,} تومان")

            last_trade = dollar_prices.get('last_trade', DEFAULT_DOLLAR_PRICE)

            # 3️⃣ دریافت قیمت بسته دیروز
            logger.info("📊 دریافت قیمت بسته شدن دیروز...")
            yesterday_close = await fetch_yesterday_close(client)
            if not yesterday_close or yesterday_close == 0:
                yesterday_close = last_trade
                logger.warning(f"⚠️ قیمت بسته دیروز پیدا نشد → استفاده از قیمت فعلی")
            else:
                logger.info(f"✅ قیمت بسته دیروز: {yesterday_close:,} تومان")

            # 4️⃣ دریافت داده‌های بازار
            logger.info("📡 دریافت داده‌های بازار از API...")
            market_data = await fetch_market_data()
            if not market_data:
                logger.error("❌ داده‌های بازار گرفته نشد")
                return
            logger.info("✅ داده‌های بازار دریافت شد")

            # 5️⃣ پردازش داده‌ها
            logger.info("⚙️ پردازش داده‌های بازار...")
            processed = process_market_data(
                market_data=market_data,
                gold_price=gold_today,
                last_trade=last_trade,
                yesterday_close=yesterday_close,
                gold_yesterday=gold_yesterday
            )
            if not processed:
                logger.error("❌ پردازش داده ناموفق")
                return

            Fund_df = processed['Fund_df']
            dfp = processed['dfp']
            logger.info(f"✅ پردازش کامل شد - {len(Fund_df)} صندوق")

            # 6️⃣ محاسبه میانگین‌های وزنی
            total_value = Fund_df["value"].sum() or 1
            fund_change_weighted = (
                (Fund_df["close_price_change_percent"] * Fund_df["value"]).sum() / total_value
            )
            fund_bubble_weighted = (
                (Fund_df["nominal_bubble"] * Fund_df["value"]).sum() / total_value
            )
            sarane_kharid_w = (
                (Fund_df["sarane_kharid"] * Fund_df["value"]).sum() / total_value
            )
            sarane_forosh_w = (
                (Fund_df["sarane_forosh"] * Fund_df["value"]).sum() / total_value
            )
            ekhtelaf_sarane_w = sarane_kharid_w - sarane_forosh_w

            dollar_change = (
                ((last_trade - yesterday_close) / yesterday_close) * 100 
                if yesterday_close else 0
            )

            if "شمش-طلا" in dfp.index:
                shams_change = dfp.loc["شمش-طلا", "close_price_change_percent"]
                shams_price = dfp.loc["شمش-طلا", "close_price"]
                shams_date = dfp.loc["شمش-طلا", "trade_date"]
            else:
                shams_change = 0
                shams_price = 0
                shams_date = None

            logger.info(f"📈 تغییر دلار: {dollar_change:+.2f}%")
            logger.info(f"📈 تغییر شمش: {shams_change:+.2f}%")
            logger.info(f"📈 تغییر صندوق‌ها: {fund_change_weighted:+.2f}%")
            logger.info(f"🎈 میانگین حباب: {fund_bubble_weighted:+.2f}%")

            # 7️⃣ ذخیره در Google Sheets
            logger.info("💾 ذخیره داده‌ها در Google Sheets...")
            save_to_sheets({
                'gold_price': gold_today,
                'dollar_price': last_trade,
                'shams_price': shams_price,
                'dollar_change': dollar_change,
                'shams_change': shams_change,
                'shams_date': shams_date,
                'fund_change_weighted': fund_change_weighted,
                'fund_bubble_weighted': fund_bubble_weighted,
                'sarane_kharid_w': sarane_kharid_w,
                'sarane_forosh_w': -sarane_forosh_w,
                'ekhtelaf_sarane_w': ekhtelaf_sarane_w,
            })

            # 8️⃣ ارسال به تلگرام
            logger.info("📤 ارسال به تلگرام...")
            success = send_to_telegram(
                bot_token=TELEGRAM_BOT_TOKEN,
                chat_id=TELEGRAM_CHAT_ID,
                data=processed,
                dollar_prices=dollar_prices,
                gold_price=gold_today,
                gold_yesterday=gold_yesterday,
                gold_time=gold_time,
                yesterday_close=yesterday_close
            )

            if success:
                logger.info("=" * 60)
                logger.info("✅ ارسال به تلگرام با موفقیت انجام شد")
                logger.info("=" * 60)
            else:
                logger.error("=" * 60)
                logger.error("❌ ارسال به تلگرام ناموفق")
                logger.error("=" * 60)

        logger.info("✅ اجرای موفق به پایان رسید")

    except KeyboardInterrupt:
        logger.info("\n⚠️ برنامه توسط کاربر متوقف شد")

    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ خطای کلی: {e}", exc_info=True)
        logger.error("=" * 60)
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 خداحافظ!")
    except Exception as e:
        logger.critical(f"💥 خطای بحرانی: {e}", exc_info=True)
        sys.exit(1)