# data_fetcher.py
import re
import logging
import pytz
from datetime import datetime, timedelta
from telethon import TelegramClient

logger = logging.getLogger(__name__)

async def fetch_gold_price_today(client: TelegramClient):
    """دریافت قیمت طلای امروز"""
    try:
        channel_username = "XAUUSD_ONE"
        tehran_tz = pytz.timezone("Asia/Tehran")

        messages = await client.get_messages(channel_username, limit=5)

        for message in messages:
            if message.text and "XAUUSD" in message.text:
                pattern = r"XAUUSD\s*➡\s*\*\*([\d.,]+)\*\*"
                match = re.search(pattern, message.text)
                if match:
                    price_str = match.group(1).replace(",", ".")
                    price = float(price_str)
                    msg_time_tehran = message.date.astimezone(tehran_tz)
                    return price, msg_time_tehran
        return None, None
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت طلای امروز: {e}")
        return None, None

async def fetch_gold_price_yesterday(client: TelegramClient):
    """دریافت قیمت طلای دیروز با جستجوی گسترده‌تر بر اساس تاریخ"""
    try:
        channel_username = "XAUUSD_ONE"
        tehran_tz = pytz.timezone("Asia/Tehran")
        now = datetime.now(tehran_tz)
        
        # تعیین بازه زمانی دیروز
        yesterday = now - timedelta(days=1)
        yesterday_start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)

        # جستجوی پیام‌ها: limit=30000 و offset_date=now برای جستجوی پیام‌های قبل از لحظه فعلی
        messages = await client.get_messages(
            channel_username, 
            limit=30000, 
            offset_date=now 
        )
        
        yesterday_prices = []

        for message in messages:
            if message.text and "XAUUSD" in message.text:
                msg_time = message.date.astimezone(tehran_tz)
                
                # بررسی می‌کنیم که آیا پیام دقیقاً در بازه دیروز است یا خیر
                if yesterday_start <= msg_time <= yesterday_end:
                    pattern = r"XAUUSD\s*➡\s*\*\*([\d.,]+)\*\*"
                    match = re.search(pattern, message.text)
                    if match:
                        price_str = match.group(1).replace(",", ".")
                        price = float(price_str)
                        yesterday_prices.append((price, msg_time))
        
        if yesterday_prices:
            # آخرین قیمت دیروز را برمی‌گرداند
            yesterday_prices.sort(key=lambda x: x[1], reverse=True)
            return yesterday_prices[0][0]
        
        logger.warning("⚠️ قیمت بسته شدن طلای دیروز پیدا نشد. 0 برگردانده می‌شود.")
        return 0
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت طلای دیروز: {e}")
        return 0

async def fetch_dollar_prices(client: TelegramClient):
    """دریافت قیمت‌های دلار"""
    try:
        channel_username = "dollar_tehran3bze"
        tehran_tz = pytz.timezone("Asia/Tehran")

        def extract_prices(text):
            prices = {"معامله": None, "خرید": None, "فروش": None}
            patterns = [
                (r"([\d,،]+)\s*مـعاملـه\s*شد", "معامله"),
                (r"([\d,،]+)\s*خــرید", "خرید"),
                (r"([\d,،]+)\s*فروش", "فروش"),
            ]
            for pattern, key in patterns:
                match = re.search(pattern, text)
                if match:
                    price_str = match.group(1).replace("،", "").replace(",", "")
                    prices[key] = int(price_str)
            return prices

        messages = await client.get_messages(channel_username, limit=50)
        final_prices = {"معامله": None, "خرید": None, "فروش": None,
                        "معامله_time": None, "خرید_time": None, "فروش_time": None}

        for message in messages:
            if message.text and "دلار فردایی تهران" in message.text:
                prices = extract_prices(message.text)
                msg_time_tehran = message.date.astimezone(tehran_tz)

                for key in ["معامله", "خرید", "فروش"]:
                    if prices[key] and not final_prices[key]:
                        final_prices[key] = prices[key]
                        final_prices[f"{key}_time"] = msg_time_tehran

                if all([final_prices["معامله"], final_prices["خرید"], final_prices["فروش"]]):
                    break

        return {
            'last_trade': final_prices["معامله"],
            'bid': final_prices["خرید"],
            'ask': final_prices["فروش"],
            'last_trade_time': final_prices["معامله_time"],
            'bid_time': final_prices["خرید_time"],
            'ask_time': final_prices["فروش_time"]
        }
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت دلار: {e}")
        return None

async def fetch_yesterday_close(client: TelegramClient):
    """آخرین معامله دیروز"""
    try:
        channel_username = "dollar_tehran3bze"
        tehran_tz = pytz.timezone("Asia/Tehran")

        def extract_last_trade(text):
            patterns = [
                r"⌛\s*([0-9,،]+)\s*آخرین[\sـ]*معاملـه[\sـ]*فردایی",
                r"⌛([0-9,،]+)\s*آخرین[\sـ]*معاملـه[\sـ]*فردایی",
                r"([0-9,،]+)\s*آخرین[\sـ]*معاملـه[\sـ]*فردایی",
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

        messages = await client.get_messages(channel_username, limit=200)
        for message in messages:
            if message.text and "پایان معاملات" in message.text:
                price = extract_last_trade(message.text)
                if price:
                    return price
        
        logger.warning("⚠️ قیمت بسته شدن دلار دیروز پیدا نشد. 0 برگردانده می‌شود.")
        return 0
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت بسته دیروز: {e}")
        return 0

async def fetch_market_data():
    """دریافت داده‌های بازار"""
    import requests
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
