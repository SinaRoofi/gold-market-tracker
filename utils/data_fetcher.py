# data_fetcher.py
import re
import logging
import pytz
from datetime import datetime, timedelta
from telethon import TelegramClient
import requests
from config import TELEGRAM_CHANNELS

logger = logging.getLogger(__name__)


DOLLAR_CHANNEL = TELEGRAM_CHANNELS['dollar']
GOLD_CHANNEL = TELEGRAM_CHANNELS['gold']
# ==============================================================================
# توابع کمکی استخراج قیمت‌ها
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
    """دریافت قیمت لحظه‌ای اونس طلای امروز"""
    try:
        channel_username = GOLD_CHANNEL 
        tehran_tz = pytz.timezone("Asia/Tehran")

        messages = await client.get_messages(channel_username, limit=5)

        for message in messages:
            if message.text and "XAUUSD" in message.text:
                price = extract_gold_price(message.text)

                if price:
                    msg_time_tehran = message.date.astimezone(tehran_tz)
                    return price, msg_time_tehran

        return None, None
    except Exception as e:
        logger.error(f"خطا در دریافت قیمت طلای امروز: {e}")
        return None, None


async def fetch_dollar_prices(client: TelegramClient):
    """دریافت قیمت‌های دلار از کانال"""
    try:
        channel_username = DOLLAR_CHANNEL
        tehran_tz = pytz.timezone("Asia/Tehran")

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
            # ✅ چک انعطاف‌پذیر: فقط "دلار فردایی" کافیه (تایپو تهران/تهرا مشکلی نیست)
            if message.text and "دلار فردایی" in message.text:
                prices = extract_prices_new(message.text)
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

        # ✅ لاگ برای دیباگ
        if final_prices["last_trade"]:
            logger.info(f"✅ قیمت‌های دلار: معامله={final_prices['last_trade']:,}, خرید={final_prices['bid']:,}, فروش={final_prices['ask']:,}")
        else:
            logger.warning("❌ قیمت معامله دلار پیدا نشد")

        if any([final_prices["last_trade"], final_prices["bid"], final_prices["ask"]]):
            return final_prices
        else:
            logger.warning("❌ هیچ قیمت دلاری پیدا نشد.")
            return None

    except Exception as e:
        logger.error(f"خطا در دریافت قیمت دلار: {e}")
        return None


async def fetch_market_data():
    """دریافت داده‌های بازار"""
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