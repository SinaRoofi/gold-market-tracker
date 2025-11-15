#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gold Market Tracker - اسکریپت اصلی
جمع‌آوری و ارسال داده‌های بازار طلا و ارز به تلگرام
"""

import os
import sys
import logging
from datetime import datetime
import pytz

# تنظیم logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('gold_tracker.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import ماژول‌های داخلی
from utils.data_fetcher import (
    fetch_gold_price,
    fetch_dollar_prices,
    fetch_yesterday_close,
    fetch_market_data
)
from utils.data_processor import process_market_data
from utils.telegram_sender import send_to_telegram
from utils.holidays import is_iranian_holiday


def main():
    """تابع اصلی برنامه"""
    try:
        logger.info("=" * 60)
        logger.info("شروع اجرای برنامه Gold Market Tracker")
        logger.info("=" * 60)
        
        # بررسی تعطیلی
        tehran_tz = pytz.timezone('Asia/Tehran')
        now = datetime.now(tehran_tz)
        
        if is_iranian_holiday(now):
            logger.info(f"امروز {now.strftime('%Y-%m-%d')} تعطیل است. برنامه اجرا نمی‌شود.")
            return
        
        logger.info(f"تاریخ و زمان: {now.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # دریافت متغیرهای محیطی
        telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        api_id = int(os.getenv('TELETHON_API_ID'))
        api_hash = os.getenv('TELETHON_API_HASH')
        phone = os.getenv('TELETHON_PHONE')
        
        if not all([telegram_bot_token, telegram_chat_id, api_id, api_hash, phone]):
            logger.error("متغیرهای محیطی کامل نیست!")
            return
        
        # 1. دریافت قیمت طلا
        logger.info("📊 دریافت قیمت اونس طلا...")
        gold_price, gold_time = fetch_gold_price(api_id, api_hash, phone)
        if not gold_price:
            logger.error("خطا در دریافت قیمت طلا")
            return
        logger.info(f"✅ قیمت طلا: ${gold_price:,.2f}")
        
        # 2. دریافت قیمت‌های دلار
        logger.info("💵 دریافت قیمت‌های دلار...")
        dollar_prices = fetch_dollar_prices(api_id, api_hash, phone)
        if not dollar_prices:
            logger.error("خطا در دریافت قیمت دلار")
            return
        logger.info(f"✅ آخرین معامله دلار: {dollar_prices['last_trade']:,} تومان")
        
        # 3. دریافت آخرین معامله دیروز
        logger.info("📈 دریافت قیمت بسته شده دیروز...")
        yesterday_close = fetch_yesterday_close(api_id, api_hash, phone)
        if yesterday_close:
            logger.info(f"✅ قیمت بسته دیروز: {yesterday_close:,} تومان")
        
        # 4. دریافت داده‌های بازار
        logger.info("🏦 دریافت داده‌های صندوق‌ها و بازار...")
        market_data = fetch_market_data()
        if not market_data:
            logger.error("خطا در دریافت داده‌های بازار")
            return
        logger.info("✅ داده‌های بازار دریافت شد")
        
        # 5. پردازش داده‌ها
        logger.info("⚙️ پردازش داده‌ها...")
        processed_data = process_market_data(
            market_data=market_data,
            gold_price=gold_price,
            last_trade=dollar_prices['last_trade'],
            yesterday_close=yesterday_close,
            gold_yesterday=4085.06  # می‌توانید این را از API بگیرید
        )
        logger.info("✅ پردازش داده‌ها تکمیل شد")
        
        # 6. ارسال به تلگرام
        logger.info("📤 ارسال به تلگرام...")
        success = send_to_telegram(
            bot_token=telegram_bot_token,
            chat_id=telegram_chat_id,
            data=processed_data,
            dollar_prices=dollar_prices,
            gold_price=gold_price,
            gold_time=gold_time,
            yesterday_close=yesterday_close
        )
        
        if success:
            logger.info("✅ ارسال به تلگرام موفقیت‌آمیز بود")
        else:
            logger.error("❌ خطا در ارسال به تلگرام")
        
        logger.info("=" * 60)
        logger.info("پایان اجرای برنامه")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"خطای غیرمنتظره: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    main()