import os
import json
import logging
from datetime import datetime, date
import pytz
import requests

logger = logging.getLogger(__name__)

CACHE_FILE = "gold_yesterday_cache.json"
API_KEY = "2f7b4b6c885940fbb1705a8520d9b540"

def get_cached_gold_yesterday():
    """خواندن قیمت طلای دیروز از کش"""
    try:
        if not os.path.exists(CACHE_FILE):
            return None
            
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache_data = json.load(f)
        
        # بررسی تاریخ کش
        tehran_tz = pytz.timezone('Asia/Tehran')
        today = datetime.now(tehran_tz).date()
        cache_date = datetime.fromisoformat(cache_data['date']).date()
        
        # اگر کش امروز است، استفاده کن
        if cache_date == today:
            logger.info(f"✅ استفاده از کش: قیمت طلای دیروز = ${cache_data['price']:,.2f}")
            return cache_data['price']
        else:
            logger.info(f"⚠️ کش قدیمی است ({cache_date}), نیاز به بروزرسانی")
            return None
            
    except Exception as e:
        logger.error(f"خطا در خواندن کش: {e}")
        return None

def fetch_and_cache_gold_yesterday():
    """دریافت قیمت طلای دیروز از API و ذخیره در کش"""
    try:
        logger.info("📡 دریافت قیمت طلای دیروز از Twelve Data API...")
        
        url = f"https://api.twelvedata.com/time_series"
        params = {
            'symbol': 'XAU/USD',
            'interval': '1day',
            'apikey': API_KEY,
            'outputsize': 2
        }
        
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # استخراج قیمت بسته‌شدن روز قبل
        if "values" in data and len(data["values"]) >= 2:
            previous_close = float(data["values"][1]["close"])
            
            # ذخیره در کش
            tehran_tz = pytz.timezone('Asia/Tehran')
            cache_data = {
                'price': previous_close,
                'date': datetime.now(tehran_tz).isoformat(),
                'source': 'Twelve Data API'
            }
            
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"✅ قیمت طلای دیروز دریافت و ذخیره شد: ${previous_close:,.2f}")
            return previous_close
        else:
            logger.error("❌ داده‌های API ناقص است")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ خطا در دریافت از API: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ خطای غیرمنتظره: {e}")
        return None

def get_gold_yesterday():
    """
    گرفتن قیمت طلای دیروز (اول از کش، در صورت نیاز از API)
    """
    # ابتدا چک کن کش معتبر داریم یا نه
    cached_price = get_cached_gold_yesterday()
    
    if cached_price is not None:
        return cached_price
    
    # اگر کش نداریم یا قدیمی است، از API بگیر
    return fetch_and_cache_gold_yesterday()
