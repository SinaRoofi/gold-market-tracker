"""
ماژول دریافت داده‌ها از منابع مختلف
"""

import re
import logging
import asyncio
import requests
import nest_asyncio
from datetime import datetime
import pytz
from telethon import TelegramClient

nest_asyncio.apply()
logger = logging.getLogger(__name__)


def fetch_gold_price(api_id, api_hash, phone):
    """دریافت قیمت اونس طلا از کانال تلگرام"""
    try:
        channel_username = "XAUUSD_ONE"
        tehran_tz = pytz.timezone("Asia/Tehran")

        async def get_price():
            client = TelegramClient("sessions/gold_session", api_id, api_hash)
            await client.start(phone)

            messages = await client.get_messages(channel_username, limit=5)

            for message in messages:
                if message.text and "XAUUSD" in message.text:
                    pattern = r"XAUUSD\s*➡\s*\*\*([\d.,]+)\*\*"
                    match = re.search(pattern, message.text)

                    if match:
                        price_str = match.group(1).replace(",", ".")
                        price = float(price_str)
                        msg_time_tehran = message.date.astimezone(tehran_tz)

                        await client.disconnect()
                        return price, msg_time_tehran

            await client.disconnect()
            return None, None

        return asyncio.run(get_price())

    except Exception as e:
        logger.error(f"خطا در دریافت قیمت طلا: {e}")
        return None, None


def fetch_dollar_prices(api_id, api_hash, phone):
    """دریافت قیمت‌های دلار از کانال تلگرام"""
    try:
        channel_username = "dollar_tehran3bze"
        tehran_tz = pytz.timezone("Asia/Tehran")

        def extract_prices(text):
            prices = {"معامله": None, "خرید": None, "فروش": None}

            معامله_pattern = r"([\d,،]+)\s*مـعاملـه\s*شد"
            خرید_pattern = r"([\d,،]+)\s*خــرید"
            فروش_pattern = r"([\d,،]+)\s*فروش"

            for pattern, key in [
                (معامله_pattern, "معامله"),
                (خرید_pattern, "خرید"),
                (فروش_pattern, "فروش"),
            ]:
                match = re.search(pattern, text)
                if match:
                    price_str = match.group(1).replace("،", "").replace(",", "")
                    prices[key] = int(price_str)

            return prices

        async def get_prices():
            client = TelegramClient("sessions/dollar_session", api_id, api_hash)
            await client.start(phone)

            messages = await client.get_messages(channel_username, limit=50)

            final_prices = {
                "معامله": None,
                "خرید": None,
                "فروش": None,
                "معامله_time": None,
                "خرید_time": None,
                "فروش_time": None,
            }

            for message in messages:
                if message.text and "دلار فردایی تهران" in message.text:
                    prices = extract_prices(message.text)
                    msg_time_tehran = message.date.astimezone(tehran_tz)

                    if prices["معامله"] and not final_prices["معامله"]:
                        final_prices["معامله"] = prices["معامله"]
                        final_prices["معامله_time"] = msg_time_tehran

                    if prices["خرید"] and not final_prices["خرید"]:
                        final_prices["خرید"] = prices["خرید"]
                        final_prices["خرید_time"] = msg_time_tehran

                    if prices["فروش"] and not final_prices["فروش"]:
                        final_prices["فروش"] = prices["فروش"]
                        final_prices["فروش_time"] = msg_time_tehran

                    if all(
                        [
                            final_prices["معامله"],
                            final_prices["خرید"],
                            final_prices["فروش"],
                        ]
                    ):
                        break

            await client.disconnect()

            return {
                "last_trade": final_prices["معامله"],
                "bid": final_prices["خرید"],
                "ask": final_prices["فروش"],
                "last_trade_time": final_prices["معامله_time"],
                "bid_time": final_prices["خرید_time"],
                "ask_time": final_prices["فروش_time"],
            }

        return asyncio.run(get_prices())

    except Exception as e:
        logger.error(f"خطا در دریافت قیمت دلار: {e}")
        return None


def fetch_yesterday_close(api_id, api_hash, phone):
    """دریافت آخرین معامله دیروز"""
    try:
        channel_username = "dollar_tehran3bze"
        tehran_tz = pytz.timezone("Asia/Tehran")

        def extract_yesterday_last_trade(text):
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

        async def get_yesterday():
            client = TelegramClient("sessions/dollar_session", api_id, api_hash)
            await client.start(phone)

            batch_size = 100
            offset_id = 0
            total_checked = 0
            max_messages = 10000

            for batch_num in range(max_messages // batch_size):
                messages = await client.get_messages(
                    channel_username, limit=batch_size, offset_id=offset_id
                )

                if not messages:
                    break

                total_checked += len(messages)
                offset_id = messages[-1].id

                for message in messages:
                    if message.text and "پایان معاملات" in message.text:
                        price = extract_yesterday_last_trade(message.text)

                        await client.disconnect()

                        if price:
                            return price
                        else:
                            return None

            await client.disconnect()
            return None

        return asyncio.run(get_yesterday())

    except Exception as e:
        logger.error(f"خطا در دریافت قیمت بسته دیروز: {e}")
        return None


def fetch_market_data():
    """دریافت داده‌های بازار (صندوق‌ها و...)"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}

        # داده‌های Rahavard365
        url1 = "https://rahavard365.com/api/v2/gold/intrinsic-values"
        resp1 = requests.get(url1, headers=headers, timeout=30)
        data1 = resp1.json()

        # داده‌های TradersArena
        url2 = "https://tradersarena.ir/data/industries-stocks-csv/gold-funds?_=1762346248071"
        resp2 = requests.get(url2, headers=headers, timeout=30)
        data2 = resp2.json()

        return {"rahavard_data": data1, "traders_data": data2}

    except Exception as e:
        logger.error(f"خطا در دریافت داده‌های بازار: {e}")
        return None
