# main.py
"""اسکریپت اصلی Gold Market Tracker"""

import os
import sys
import logging
from datetime import datetime
import pytz
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID,
    TELETHON_API_ID, TELETHON_API_HASH, TELEGRAM_SESSION,
    TIMEZONE, LOG_FORMAT, LOG_FILE, LOG_LEVEL,
    DEFAULT_GOLD_PRICE, DEFAULT_DOLLAR_PRICE, TELEGRAM_ALERT_CHAT_ID
)
from utils.data_fetcher import (
    fetch_gold_price_today, fetch_dollar_prices,
    fetch_market_data
)
from utils.data_processor import process_market_data
from utils.telegram_sender import send_to_telegram
from utils.holidays import is_iranian_holiday
from utils.sheets_storage import save_to_sheets, read_from_sheets
from utils.alerts import check_and_send_alerts

# ════════════════════════════════════════════════════════════════
# تنظیمات Logging
# ════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def get_gold_yesterday_from_sheet(today_date):
    """
    دریافت قیمت طلای آخرین روز کاری قبل از امروز
    
    Args:
        today_date: تاریخ امروز به فرمت YYYY-MM-DD
    
    Returns:
        tuple: (قیمت طلا، تاریخ پیدا شده، موفقیت)
    """
    try:
        from datetime import datetime, timedelta

        today = datetime.strptime(today_date, "%Y-%m-%d")

        logger.info(f"🔍 جستجوی آخرین قیمت طلای قبل از {today_date}")

        # خواندن 15 رکورد آخر (برای احتمال تعطیلات طولانی)
        rows = read_from_sheets(limit=80)

        if not rows:
            logger.warning("⚠️ هیچ رکوردی در شیت پیدا نشد")
            return None, None, False

        # جستجو از آخرین رکورد به قبل تا پیدا کردن اولین روز قبل از امروز
        # فرض: ستون اول (index 0) تاریخ است به فرمت YYYY-MM-DD
        for row in reversed(rows):
            if len(row) > 1 and row[0]:
                row_date_str = row[0][:10]  # اگر datetime باشه فقط تاریخ رو میگیریم
                row_date = datetime.strptime(row_date_str, "%Y-%m-%d")

                # باید قبل از امروز باشه
                if row_date < today:
                    if row[1]:  # ستون دوم قیمت اونس طلا
                        gold_price = float(row[1])
                        days_ago = (today - row_date).days
                        logger.info(f"✅ آخرین قیمت طلا: ${gold_price:.2f} (تاریخ {row_date_str} - {days_ago} روز پیش)")
                        return gold_price, row_date_str, True
                    else:
                        logger.warning(f"⚠️ تاریخ {row_date_str} پیدا شد ولی قیمت خالی است")
                        continue  # به دنبال رکورد قبلی میگردیم

        logger.warning(f"⚠️ هیچ رکورد معتبری قبل از {today_date} پیدا نشد")
        return None, None, False

    except Exception as e:
        logger.error(f"❌ خطا در خواندن قیمت طلای دیروز: {e}")
        return None, None, False


def get_dollar_yesterday_from_sheet(today_date):
    """
    دریافت قیمت دلار آخرین روز کاری قبل از امروز
    
    Args:
        today_date: تاریخ امروز به فرمت YYYY-MM-DD
    
    Returns:
        tuple: (قیمت دلار، تاریخ پیدا شده، موفقیت)
    """
    try:
        from datetime import datetime, timedelta

        today = datetime.strptime(today_date, "%Y-%m-%d")

        logger.info(f"🔍 جستجوی آخرین قیمت دلار قبل از {today_date}")

        # خواندن 80 رکورد آخر
        rows = read_from_sheets(limit=80)

        if not rows:
            logger.warning("⚠️ هیچ رکوردی در شیت پیدا نشد")
            return None, None, False

        # جستجو از آخرین رکورد به قبل
        for row in reversed(rows):
            if len(row) > 2 and row[0]:
                row_date_str = row[0][:10]  # تاریخ
                row_date = datetime.strptime(row_date_str, "%Y-%m-%d")

                # باید قبل از امروز باشه
                if row_date < today:
                    if row[2]:  # ستون سوم قیمت دلار
                        dollar_price = float(row[2])
                        days_ago = (today - row_date).days
                        logger.info(f"✅ آخرین قیمت دلار: {dollar_price:,.0f} تومان (تاریخ {row_date_str} - {days_ago} روز پیش)")
                        return dollar_price, row_date_str, True
                    else:
                        logger.warning(f"⚠️ تاریخ {row_date_str} پیدا شد ولی قیمت دلار خالی است")
                        continue

        logger.warning(f"⚠️ هیچ رکورد معتبری قبل از {today_date} پیدا نشد")
        return None, None, False

    except Exception as e:
        logger.error(f"❌ خطا در خواندن قیمت دلار دیروز: {e}")
        return None, None, False


async def main():
    """تابع اصلی برنامه"""
    try:
        logger.info("=" * 60)
        logger.info("🚀 شروع اجرای Gold Market Tracker")
        logger.info("=" * 60)

        # ═══════════════════════════════════════════════════════
        # بررسی زمان و تعطیلات
        # ═══════════════════════════════════════════════════════
        tehran_tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tehran_tz)

        if is_iranian_holiday(now):
            logger.info(f"🏖️ امروز {now.strftime('%Y-%m-%d')} تعطیل است.")
            return

        logger.info(f"🕐 زمان تهران: {now.strftime('%Y-%m-%d %H:%M:%S')}")

        # ═══════════════════════════════════════════════════════
        # بررسی متغیرهای محیطی
        # ═══════════════════════════════════════════════════════
        if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ALERT_CHAT_ID, TELETHON_API_ID, 
                    TELETHON_API_HASH, TELEGRAM_SESSION]):
            logger.error("❌ یکی از متغیرهای محیطی تلگرام پیدا نشد!")
            logger.error("لطفاً این متغیرها را تنظیم کنید:")
            logger.error("- TELEGRAM_BOT_TOKEN")
            logger.error("- TELEGRAM_CHAT_ID")
            logger.error("- TELETHON_API_ID")
            logger.error("- TELETHON_API_HASH")
            logger.error("- TELEGRAM_SESSION")
            logger.error("- TELEGRAM_ALERT_CHAT_ID")           
            return

        # ═══════════════════════════════════════════════════════
        # دریافت قیمت طلای آخرین روز کاری از شیت
        # ═══════════════════════════════════════════════════════
        logger.info("📊 دریافت قیمت طلای آخرین روز کاری از Google Sheets...")
        today_str = now.strftime("%Y-%m-%d")
        gold_yesterday, prev_date, found = get_gold_yesterday_from_sheet(today_str)

        if not found:
            logger.warning("⚠️ قیمت طلای قبلی پیدا نشد → تغییر صفر محاسبه می‌شود")
            gold_yesterday = None

        # ═══════════════════════════════════════════════════════
        # 🆕 دریافت قیمت دلار آخرین روز کاری از شیت
        # ═══════════════════════════════════════════════════════
        logger.info("📊 دریافت قیمت دلار آخرین روز کاری از Google Sheets...")
        dollar_yesterday, dollar_prev_date, dollar_found = get_dollar_yesterday_from_sheet(today_str)

        if not dollar_found:
            logger.warning("⚠️ قیمت دلار قبلی پیدا نشد → yesterday_close = قیمت فعلی")
            dollar_yesterday = None

        # ═══════════════════════════════════════════════════════
        # اتصال به Telethon و دریافت داده‌ها
        # ═══════════════════════════════════════════════════════
        async with TelegramClient(StringSession(TELEGRAM_SESSION), 
                                 TELETHON_API_ID, 
                                 TELETHON_API_HASH) as client:

            logger.info("✅ اتصال به Telethon برقرار شد")

            # ───────────────────────────────────────────────────
            # 1️⃣ دریافت قیمت طلای جهانی
            # ───────────────────────────────────────────────────
            logger.info("🔆 دریافت قیمت طلای جهانی...")
            gold_today, gold_time = await fetch_gold_price_today(client)

            # ✅ چک و fallback برای طلا
            if not gold_today or gold_today <= 0:
                gold_today = DEFAULT_GOLD_PRICE
                gold_time = None
                logger.warning(f"⚠️ قیمت طلا گرفته نشد → پیش‌فرض ${DEFAULT_GOLD_PRICE:.2f}")
            else:
                logger.info(f"✅ قیمت طلا: ${gold_today:.2f}")

            # ───────────────────────────────────────────────────
            # 2️⃣ دریافت قیمت دلار
            # ───────────────────────────────────────────────────
            logger.info("💵 دریافت قیمت‌های دلار...")
            dollar_prices = await fetch_dollar_prices(client)

            # ✅ چک دقیق: باید هم dollar_prices باشه و هم last_trade
            if not dollar_prices or not dollar_prices.get('last_trade'):
                last_trade = DEFAULT_DOLLAR_PRICE
                dollar_prices = {
                    'last_trade': DEFAULT_DOLLAR_PRICE, 
                    'bid': dollar_prices.get('bid', 0) if dollar_prices else 0,
                    'ask': dollar_prices.get('ask', 0) if dollar_prices else 0
                }
                logger.warning(f"⚠️ قیمت معامله دلار گرفته نشد → پیش‌فرض {DEFAULT_DOLLAR_PRICE:,}")
            else:
                last_trade = dollar_prices['last_trade']
                logger.info(f"✅ آخرین معامله دلار: {last_trade:,} تومان")

            # ───────────────────────────────────────────────────
            # 3️⃣ استفاده از قیمت دلار دیروز از Sheet
            # ───────────────────────────────────────────────────
            yesterday_close = dollar_yesterday if dollar_yesterday else last_trade

            if dollar_yesterday:
                logger.info(f"✅ قیمت دلار دیروز (از Sheet): {yesterday_close:,} تومان")
            else:
                logger.warning(f"⚠️ قیمت دلار دیروز پیدا نشد → استفاده از قیمت فعلی ({last_trade:,})")

            # ───────────────────────────────────────────────────
            # 4️⃣ دریافت داده‌های بازار
            # ───────────────────────────────────────────────────
            logger.info("📡 دریافت داده‌های بازار از API...")
            market_data = await fetch_market_data()

            if not market_data:
                logger.error("❌ داده‌های بازار گرفته نشد")
                return

            logger.info("✅ داده‌های بازار دریافت شد")

            # ───────────────────────────────────────────────────
            # 5️⃣ پردازش داده‌ها
            # ───────────────────────────────────────────────────
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

            # ───────────────────────────────────────────────────
            # 6️⃣ محاسبه میانگین‌های وزنی و ساده
            # ───────────────────────────────────────────────────
            total_value = Fund_df["value"].sum() or 1

            # میانگین وزنی (برای آخرین قیمت)
            fund_change_weighted = (
                (Fund_df["close_price_change_percent"] * Fund_df["value"]).sum() / total_value
            )
            fund_bubble_weighted = (
                (Fund_df["nominal_bubble"] * Fund_df["value"]).sum() / total_value
            )

            # ✅ میانگین ساده قیمت پایانی
            fund_final_price_avg = Fund_df["final_price_change"].mean()

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

            # محاسبه تغییر قیمت طلا
            if gold_yesterday:
                gold_change = ((gold_today - gold_yesterday) / gold_yesterday) * 100
                logger.info(f"📈 تغییر اونس طلا: {gold_change:+.2f}%")
            else:
                gold_change = 0
                logger.info("📈 تغییر اونس طلا: 0% (قیمت دیروز نبود)")

            # گرفتن اطلاعات شمش
            if "شمش-طلا" in dfp.index:
                shams_change = dfp.loc["شمش-طلا", "close_price_change_percent"]
                shams_price = dfp.loc["شمش-طلا", "close_price"]
                shams_date = dfp.loc["شمش-طلا", "trade_date"]
            else:
                shams_change = 0
                shams_price = 0
                shams_date = None

            logger.info(f"📈 تغییر دلار: {dollar_change:+.2f}%")
            logger.info(f"📈 تغییر اونس طلا: {gold_change:+.2f}%")
            logger.info(f"📈 تغییر شمش: {shams_change:+.2f}%")
            logger.info(f"📈 تغییر صندوق‌ها (وزنی): {fund_change_weighted:+.2f}%")
            logger.info(f"📈 قیمت پایانی (ساده): {fund_final_price_avg:+.2f}%")
            logger.info(f"🎈 میانگین حباب: {fund_bubble_weighted:+.2f}%")

            # ───────────────────────────────────────────────────
            # 7️⃣ ذخیره در Google Sheets
            # ───────────────────────────────────────────────────
            logger.info("💾 ذخیره داده‌ها در Google Sheets...")
            save_to_sheets({
                'gold_price': gold_today,
                'dollar_price': last_trade,
                'shams_price': shams_price,
                'dollar_change': dollar_change,
                'shams_change': shams_change,
                'shams_date': shams_date,
                'fund_change_weighted': fund_change_weighted,
                'fund_final_price_avg': fund_final_price_avg,
                'fund_bubble_weighted': fund_bubble_weighted,
                'sarane_kharid_w': sarane_kharid_w,
                'sarane_forosh_w': -sarane_forosh_w,
                'ekhtelaf_sarane_w': ekhtelaf_sarane_w,
            })

            # ───────────────────────────────────────────────────
            # 8️⃣ ارسال گزارش اصلی به تلگرام (اول این!)
            # ───────────────────────────────────────────────────
            logger.info("📤 ارسال گزارش اصلی به تلگرام...")
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
                logger.info("✅ ارسال گزارش اصلی موفق بود")
            else:
                logger.warning("⚠️ ارسال گزارش اصلی ناموفق")

            # ───────────────────────────────────────────────────
            # 9️⃣ بررسی و ارسال هشدارها (بعد از پیام اصلی!)
            # ───────────────────────────────────────────────────
            logger.info("🚨 بررسی شرایط هشدارها...")
            try:
                check_and_send_alerts(
                    bot_token=TELEGRAM_BOT_TOKEN,
                    chat_id=TELEGRAM_ALERT_CHAT_ID,
                    data=processed,
                    dollar_prices=dollar_prices,
                    gold_price=gold_today,
                    yesterday_close=yesterday_close,
                    gold_yesterday=gold_yesterday
                )
                logger.info("✅ بررسی هشدارها کامل شد")
            except Exception as e:
                logger.error(f"⚠️ خطا در سیستم هشدارها (ادامه می‌دهیم): {e}")

            # ───────────────────────────────────────────────────
            logger.info("=" * 60)
            logger.info("✅ اجرای کامل به پایان رسید")
            logger.info("=" * 60)

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