# data_fetcher.py
import re
import logging
import pytz
import time
from datetime import datetime, timedelta
from telethon import TelegramClient
import requests
from bs4 import BeautifulSoup
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

    # ✅ الگوی بهبود یافته - پوشش نیم‌فاصله و فاصله‌های مختلف
    معامله_pattern = r"(\d{1,3})[,،\u200c\u200b\s]*(\d{3})\s*مـعامله\s*شد"
    خرید_pattern = r"(\d{1,3})[,،\u200c\u200b\s]*(\d{3})\s*خــرید"
    فروش_pattern = r"(\d{1,3})[,،\u200c\u200b\s]*(\d{3})\s*فروش"

    معامله_match = re.search(معامله_pattern, text)
    if معامله_match:
        price_str = معامله_match.group(1) + معامله_match.group(2)
        prices["معامله"] = int(price_str)

    خرید_match = re.search(خرید_pattern, text)
    if خرید_match:
        price_str = خرید_match.group(1) + خرید_match.group(2)
        prices["خرید"] = int(price_str)

    فروش_match = re.search(فروش_pattern, text)
    if فروش_match:
        price_str = فروش_match.group(1) + فروش_match.group(2)
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


async def fetch_market_data(max_retries=3, retry_delay=5):
    """دریافت داده‌های بازار با قابلیت retry"""

    for attempt in range(1, max_retries + 1):
        try:
            headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "fa-IR,fa;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://tradersarena.ir/",
    "Origin": "https://tradersarena.ir",
}

            # ═══════════════════════════════════════════════════
            # درخواست اول: rahavard365
            # ═══════════════════════════════════════════════════
            url1 = "https://rahavard365.com/api/v2/gold/intrinsic-values"
            logger.info(f"📡 تلاش {attempt}/{max_retries} - درخواست به rahavard365...")

            resp1 = requests.get(url1, headers=headers, timeout=30)

            if resp1.status_code != 200:
                logger.error(f"❌ خطای HTTP {resp1.status_code} از rahavard365")
                raise requests.exceptions.RequestException(f"HTTP {resp1.status_code}")

            try:
                data1 = resp1.json()
                logger.info("✅ rahavard365 پاسخ داد")
            except requests.exceptions.JSONDecodeError as e:
                logger.error(f"❌ پاسخ rahavard365 JSON نیست")
                logger.debug(f"Response: {resp1.text[:500]}")
                raise

            # تأخیر بین درخواست‌ها
            time.sleep(2)

            # ═══════════════════════════════════════════════════
            # درخواست دوم: tradersarena
            # ═══════════════════════════════════════════════════
            url2 = "https://tradersarena.ir/data/industries-stocks-csv/gold-funds"
            logger.info(f"📡 تلاش {attempt}/{max_retries} - درخواست به tradersarena...")

            resp2 = requests.get(url2, headers=headers, timeout=(10, 20))

            if resp2.status_code != 200:
                logger.error(f"❌ خطای HTTP {resp2.status_code} از tradersarena")
                raise requests.exceptions.RequestException(f"HTTP {resp2.status_code}")

            try:
                data2 = resp2.json()
                logger.info("✅ tradersarena پاسخ داد")
            except requests.exceptions.JSONDecodeError as e:
                logger.error(f"❌ پاسخ tradersarena JSON نیست")
                logger.debug(f"Response: {resp2.text[:500]}")
                raise

            # ═══════════════════════════════════════════════════
            # موفقیت
            # ═══════════════════════════════════════════════════
            logger.info(f"✅ دریافت موفق در تلاش {attempt}")
            return {'rahavard_data': data1, 'traders_data': data2}

        except requests.exceptions.Timeout:
            logger.error(f"❌ تلاش {attempt}: Timeout")
            if attempt < max_retries:
                logger.info(f"⏳ صبر {retry_delay} ثانیه قبل از تلاش مجدد...")
                time.sleep(retry_delay)
            else:
                logger.error("❌ همه تلاش‌ها به دلیل Timeout ناموفق بود")
                return None

        except requests.exceptions.ConnectionError as e:
            logger.error(f"❌ تلاش {attempt}: خطای اتصال - {e}")
            if attempt < max_retries:
                logger.info(f"⏳ صبر {retry_delay} ثانیه قبل از تلاش مجدد...")
                time.sleep(retry_delay)
            else:
                logger.error("❌ همه تلاش‌ها به دلیل خطای اتصال ناموفق بود")
                return None

        except requests.exceptions.JSONDecodeError as e:
            logger.error(f"❌ تلاش {attempt}: پاسخ JSON معتبر نیست - {e}")
            if attempt < max_retries:
                logger.info(f"⏳ صبر {retry_delay} ثانیه قبل از تلاش مجدد...")
                time.sleep(retry_delay)
            else:
                logger.error("❌ همه تلاش‌ها به دلیل پاسخ نامعتبر ناموفق بود")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ تلاش {attempt}: خطای درخواست - {e}")
            if attempt < max_retries:
                logger.info(f"⏳ صبر {retry_delay} ثانیه قبل از تلاش مجدد...")
                time.sleep(retry_delay)
            else:
                logger.error("❌ همه تلاش‌ها ناموفق بود")
                return None

        except Exception as e:
            logger.error(f"❌ تلاش {attempt}: خطای غیرمنتظره - {e}")
            if attempt < max_retries:
                logger.info(f"⏳ صبر {retry_delay} ثانیه قبل از تلاش مجدد...")
                time.sleep(retry_delay)
            else:
                logger.error("❌ همه تلاش‌ها به دلیل خطای غیرمنتظره ناموفق بود")
                return None

    return None


def fetch_dirham_price():
    """دریافت قیمت فروش درهم امارات از alanchand.com"""
    try:
        def persian_to_english_number(s):
            persian_numbers = "۰۱۲۳۴۵۶۷۸۹"
            english_numbers = "0123456789"
            for p, e in zip(persian_numbers, english_numbers):
                s = s.replace(p, e)
            return s

        url = "https://alanchand.com/currencies-price"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=30)

        soup = BeautifulSoup(resp.text, "html.parser")

        table = soup.find("table")

        price_sale_dirham = None
        for row in table.find_all("tr")[1:]:
            cols = row.find_all("td")
            if cols and cols[0].text.strip() == "درهم":
                price_sale_dirham = cols[2].text.strip()  # ستون قیمت فروش
                break

        if price_sale_dirham:
            # تبدیل ارقام فارسی به انگلیسی و حذف کاما
            price_sale_dirham = persian_to_english_number(price_sale_dirham).replace(",", "")
            price_sale_dirham_int = int(price_sale_dirham)
            logger.info(f"✅ قیمت درهم: {price_sale_dirham_int:,} تومان")
            return price_sale_dirham_int
        else:
            logger.warning("⚠️ قیمت فروش درهم پیدا نشد")
            return None

    except Exception as e:
        logger.error(f"❌ خطا در دریافت قیمت درهم: {e}")
        return None
