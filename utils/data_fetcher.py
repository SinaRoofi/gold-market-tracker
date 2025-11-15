# data_fetcher.py
import re
import logging
import pytz
from datetime import datetime, timedelta
from telethon import TelegramClient
import requests

logger = logging.getLogger(__name__)

# ==============================================================================
# توابع کمکی استخراج قیمت‌ها (بر اساس کدهای ارسالی شما)
# ==============================================================================

def extract_prices_new(text):
    """استخراج قیمت‌های دلار (معامله/خرید/فروش) از متن پیام بر اساس الگوی کاربر."""
    prices = {"معامله": None, "خرید": None, "فروش": None}
    معامله_pattern = r"(\d{1,3}[,،]\d{3})\s*مـعامله\s*شد"
    معامله_match = re.search(معامله_pattern, text)
    if معامله_match:
        price_str = معامله_match.group(1).replace("،", "").replace(",", "")
        prices["معامله"] = int(price_str)

    خرید_pattern = r"(\d{1,3}[,،]\d{3})\s*خــرید"
    خرید_match = re.search(خرید_pattern, text)
    if خرید_match:
        price_str = خرید_match.group(1).replace("،", "").replace(",", "")
        prices["خرید"] = int(price_str)

    فروش_pattern = r"(\d{1,3}[,،]\d{3})\s*فروش"
    فروش_match = re.search(فروش_pattern, text)
    if فروش_match:
        price_str = فروش_match.group(1).replace("،", "").replace(",", "")
        prices["فروش"] = int(price_str)

    return prices

def extract_yesterday_close_price(text):
    """استخراج آخرین معامله فردایی از پیام پایان معاملات بر اساس الگوی کاربر"""
    patterns = [
        r"❌\s*([0-9,،]+)\s*آخرین[\s‌]*معامله[\s‌]*فردایی", 
        r"❌([0-9,،]+)\s*آخرین[\s‌]*معامله[\s‌]*فردایی", 
        r"([0-9,،]+)\s*آخرین[\s‌]*معامله[\s‌]*فردایی", 
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            price_str = match.group(1).replace("،", "").replace(",", "").strip()
            try:
                price = int(price_str)
                if 10000 <= price <= 1000000:
                    return price
            except:
                continue
    return None

def extract_gold_price(text):
    """استخراج قیمت اونس طلا بر اساس الگوی کاربر"""
    pattern = r"XAUUSD\s*➡\s*\*\*(\d+[.,]\d+)\*\*"
    match = re.search(pattern, text)

    if match:
        price_str = match.group(1).replace(",", ".")
        return float(price_str)
    return None


# ==============================================================================
# توابع واکشی داده اصلی
# ==============================================================================

async def fetch_gold_price_today(client: TelegramClient):
    """دریافت قیمت لحظه‌ای اونس طلای امروز (مطابق کد ارسالی شما)"""
    try:
        channel_username = "XAUUSD_ONE"
        tehran_tz = pytz.timezone("Asia/Tehran")

        # دریافت 5 پیام آخر
        messages = await client.get_messages(channel_username, limit=5)

        for message in messages:
            if message.text and "XAUUSD" in message.text:
                # استفاده از تابع استخراج شما
                price = extract_gold_price(message.text)
                
                if price:
                    msg_time_tehran = message.date.astimezone(tehran_tz)
                    return price, msg_time_tehran
                    
        return None, None
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت طلای امروز: {e}")
        return None, None

async def fetch_gold_price_yesterday(client: TelegramClient):
    """
    دریافت قیمت طلای دیروز با استفاده از offset_date
    """
    try:
        channel_username = "XAUUSD_ONE"
        tehran_tz = pytz.timezone("Asia/Tehran")
        
        latest_message = await client.get_messages(channel_username, limit=1)
        if not latest_message:
            logger.warning("⚠️ کانال طلا پیام جدیدی ندارد. 0 برگردانده می‌شود.")
            return 0
            
        today_ref_time = latest_message[0].date.astimezone(tehran_tz)
        
        yesterday = today_ref_time - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        messages = await client.get_messages(
            channel_username, 
            limit=1000, 
            offset_date=today_ref_time
        )
        
        yesterday_prices = []
        
        for message in messages:
            if message.text and "XAUUSD" in message.text:
                msg_time = message.date.astimezone(tehran_tz)
                
                if msg_time < yesterday_start:
                    break # توقف جستجو در صورت رسیدن به پیام‌های خیلی قدیمی
                
                price = extract_gold_price(message.text) # استفاده از تابع استخراج شما
                
                # اگر قیمت پیدا شد و تاریخ دیروز بود، اضافه می‌کنیم
                if price and msg_time.date() == yesterday_start.date():
                    yesterday_prices.append((price, msg_time))

        
        if yesterday_prices:
            # آخرین قیمت دیروز را برمی‌گرداند (جدیدترین زمان ثبت شده در بازه دیروز)
            yesterday_prices.sort(key=lambda x: x[1], reverse=True)
            return yesterday_prices[0][0]
        
        logger.warning("⚠️ قیمت بسته شدن طلای دیروز پیدا نشد. 0 برگردانده می‌شود.")
        return 0
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت طلای دیروز: {e}")
        return 0

async def fetch_dollar_prices(client: TelegramClient):
    """دریافت قیمت‌های دلار از کانال با منطق جستجوی دقیق‌تر (بر اساس کد کاربر)."""
    try:
        channel_username = "dollar_tehran3bze"
        tehran_tz = pytz.timezone("Asia/Tehran")

        def extract_prices(text):
            return extract_prices_new(text)

        messages = await client.get_messages(channel_username, limit=50)

        final_prices = {
            "last_trade": None, 
            "bid": None,         
            "ask": None,         
            "last_trade_time": None,
            "bid_time": None,
            "ask_time": None,
        }

        for message in messages:
            if message.text and "دلار فردایی تهران" in message.text:
                prices = extract_prices(message.text)
                msg_time_tehran = message.date.astimezone(tehran_tz)

                if prices["معامله"] and not final_prices["last_trade"]:
                    final_prices["last_trade"] = prices["معامله"]
                    final_prices["last_trade_time"] = msg_time_tehran

                if prices["خرید"] and not final_prices["bid"]:
                    final_prices["bid"] = prices["خرید"]
                    final_prices["bid_time"] = msg_time_tehran

                if prices["فروش"] and not final_prices["ask"]:
                    final_prices["ask"] = prices["فروش"]
                    final_prices["ask_time"] = msg_time_tehran

                if all([final_prices["last_trade"], final_prices["bid"], final_prices["ask"]]):
                    break
        
        if any([final_prices["last_trade"], final_prices["bid"], final_prices["ask"]]):
            return final_prices
        else:
            logger.warning("❌ هیچ قیمت دلاری پیدا نشد.")
            return None
            
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت دلار: {e}")
        return None

async def fetch_yesterday_close(client: TelegramClient):
    """جستجوی قیمت بسته شدن دلار دیروز با جستجوی دسته‌ای (بر اساس منطق کاربر)"""
    try:
        channel_username = "dollar_tehran3bze"
        tehran_tz = pytz.timezone("Asia/Tehran")

        batch_size = 100  
        offset_id = 0
        total_checked = 0
        max_messages = 10000 

        for batch_num in range(max_messages // batch_size):
            messages = await client.get_messages(
                channel_username, limit=batch_size, offset_id=offset_id
            )

            if not messages:
                logger.warning(f"⚠️ به انتهای پیام‌های کانال دلار رسیدیم. کل پیام بررسی شده: {total_checked}")
                break

            total_checked += len(messages)
            offset_id = messages[-1].id

            for message in messages:
                if message.text and "پایان معاملات" in message.text:
                    price = extract_yesterday_close_price(message.text)

                    if price:
                        return price 
                    else:
                        logger.warning(f"❌ پیام 'پایان معاملات' پیدا شد اما استخراج قیمت امکان پذیر نبود.")
                        return 0 

            if total_checked % 1000 == 0:
                logger.info(f"⏳ در حال جستجوی قیمت بسته شدن دلار... {total_checked} پیام بررسی شد.")

        logger.warning(f"❌ پیام 'پایان معاملات' تا عمق {max_messages} پیدا نشد.")
        return 0
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت بسته دیروز: {e}")
        return 0

async def fetch_market_data():
    """دریافت داده‌های بازار (بدون تغییر)"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url1 = "https://rahavard365.com/api/v2/gold/intrinsic-values"
        resp1 = requests.get(url1, headers=headers, timeout=30)
        data1 = resp1.json()

        url2 = "https://tradersarena.ir/data/industries-stocks-csv/gold-funds?_=1762346248071"
        resp2 = requests.get(url2, headers=headers, timeout=30)
        data2 = resp2.json()

        return {'rahavard_data': data1, 'traders_data': data2}
    except Exception as e:
        logger.error(f"خطا در دریافت داده‌های بازار: {e}")
        return None

