"""
تنظیمات پروژه
"""

# کانال‌های تلگرام
TELEGRAM_CHANNELS = {
    'gold': 'XAUUSD_ONE',
    'dollar': 'dollar_tehran3bze'
}

# API URLs
API_URLS = {
    'rahavard': 'https://rahavard365.com/api/v2/gold/intrinsic-values',
    'traders': 'https://tradersarena.ir/data/industries-stocks-csv/gold-funds?_=1762346248071'
}

# تنظیمات زمانی
TIMEZONE = 'Asia/Tehran'
TRADING_HOURS = {
    'start': 12,  # ساعت شروع
    'end': 18,    # ساعت پایان
}
TRADING_DAYS = [5, 6, 0, 1, 2]  # شنبه=5, یکشنبه=6, دوشنبه=0, سه‌شنبه=1, چهارشنبه=2

# تنظیمات نمودار
CHART_CONFIG = {
    'width': 1400,
    'height': 800,
    'colorscale': [
        [0.0, "#E57373"], [0.1, "#D85C5C"], [0.2, "#C94444"],
        [0.3, "#A52A2A"], [0.4, "#6B1A1A"], [0.5, "#2C2C2C"],
        [0.6, "#1B5E20"], [0.7, "#2E7D32"], [0.8, "#43A047"],
        [0.9, "#5CB860"], [0.0, "#66BB6A"]
    ]
}

# ترتیب نمایش دارایی‌ها
ASSET_ORDER = [
    "طلا-گرم-18-عیار",
    "طلا-گرم-24-عیار",
    "شمش-طلا",
    "سطلا",
    "سکه-امامی-طرح-جدید",
    "سکه-بهار-آزادی-طرح-قدیم",
    "طلا-مظنه-آبشده-تهران",
    "سکه0312پ01",
    "سکه0411پ05",
    "سکه0412پ03",
    "نیم-سکه",
    "ربع-سکه",
    "سکه-1-گرمی",
]

# قیمت پیش‌فرض طلای دیروز (در صورت عدم دسترسی)
DEFAULT_GOLD_YESTERDAY = 4085.06

# تنظیمات Retry
MAX_RETRIES = 3
RETRY_DELAY = 5  # ثانیه

# تنظیمات Logging
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = 'gold_tracker.log'
