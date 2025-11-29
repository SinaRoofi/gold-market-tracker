# config.py
"""تنظیمات و ثابت‌های پروژه Gold Market Tracker"""

import os

# ════════════════════════════════════════════════════════════════
# 🔐 متغیرهای محیطی (Environment Variables)
# ════════════════════════════════════════════════════════════════

# GitHub Gist
GIST_ID = os.getenv("GIST_ID")
GIST_TOKEN = os.getenv("GIST_TOKEN")
ALERT_STATUS_FILE = "alert_status.json"
MESSAGE_ID_FILE = "message_id.json"

# Google Sheets
SHEET_ID = os.getenv("SHEET_ID")
SERVICE_ACCOUNT_JSON = os.getenv("SHEETS_SERVICE_ACCOUNT")

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TELETHON_API_ID = int(os.getenv('TELETHON_API_ID', 0))
TELETHON_API_HASH = os.getenv('TELETHON_API_HASH')
TELEGRAM_SESSION = os.getenv('TELEGRAM_SESSION')

# ════════════════════════════════════════════════════════════════
# 📡 کانال‌های تلگرام
# ════════════════════════════════════════════════════════════════

TELEGRAM_CHANNELS = {
    'gold': 'XAUUSD_ONE',
    'dollar': 'dollar_tehran3bze'
}

# ════════════════════════════════════════════════════════════════
# 🌐 API URLs
# ════════════════════════════════════════════════════════════════

API_URLS = {
    'rahavard': 'https://rahavard365.com/api/v2/gold/intrinsic-values',
    'traders': 'https://tradersarena.ir/data/industries-stocks-csv/gold-funds?_=1762346248071'
}

# ════════════════════════════════════════════════════════════════
# ⏰ تنظیمات زمانی
# ════════════════════════════════════════════════════════════════

TIMEZONE = 'Asia/Tehran'

TRADING_HOURS = {
    'start': 12,  # ساعت شروع معاملات
    'end': 18,    # ساعت پایان معاملات
}

# روزهای معاملاتی (شنبه=5, یکشنبه=6, دوشنبه=0, سه‌شنبه=1, چهارشنبه=2)
TRADING_DAYS = [5, 6, 0, 1, 2]

# ════════════════════════════════════════════════════════════════
# 🚨 آستانه‌های هشدار قیمتی
# ════════════════════════════════════════════════════════════════

# آستانه‌های دلار (تومان)
DOLLAR_HIGH = 115_000
DOLLAR_LOW = 114_000

# آستانه‌های شمش طلا (ریال)
SHAMS_HIGH = 15_600_000
SHAMS_LOW = 15_000_000

# آستانه‌های اونس طلا (دلار)
GOLD_HIGH = 4200
GOLD_LOW = 4080

# آستانه‌های تغییرات
ALERT_THRESHOLD_PERCENT = 0.5  # تغییر سریع دلار (%)
EKHTELAF_THRESHOLD = 10        # تغییر اختلاف سرانه (میلیون تومان)

# ════════════════════════════════════════════════════════════════
# 🎨 تنظیمات نمودارها
# ════════════════════════════════════════════════════════════════

# نمودار روند بازار (Charts)
CHART_WIDTH = 1400
CHART_HEIGHT = 2200
CHART_SCALE = 2

# نمودار Treemap
TREEMAP_WIDTH = 1350
TREEMAP_HEIGHT = 1350
TREEMAP_SCALE = 2

# رنگ‌های نمودار
COLOR_POSITIVE = '#00E676'      # سبز (مثبت)
COLOR_NEGATIVE = '#FF1744'      # قرمز (منفی)
COLOR_NEUTRAL = '#2C2C2C'       # خاکستری (خنثی)
COLOR_BACKGROUND = '#0D1117'    # پس‌زمینه
COLOR_GRID = '#21262D'          # خطوط شبکه
COLOR_GOLD = '#FFD700'          # طلایی

# Colorscale برای Treemap (منفی → صفر → مثبت)
TREEMAP_COLORSCALE = [
    [0.0, "#E57373"], [0.1, "#D85C5C"], [0.2, "#C94444"], 
    [0.3, "#A52A2A"], [0.4, "#6B1A1A"],
    [0.5, "#2C2C2C"],  # خنثی
    [0.6, "#1B5E20"], [0.7, "#2E7D32"], [0.8, "#43A047"], 
    [0.9, "#5CB860"], [1.0, "#66BB6A"],
]

# گام محور Y برای نمودار سرانه
Y_AXIS_STEP = 50  # افزایش 50 تایی

# ════════════════════════════════════════════════════════════════
# 📝 ترتیب نمایش دارایی‌ها
# ════════════════════════════════════════════════════════════════

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

# ════════════════════════════════════════════════════════════════
# 🔤 مسیر فونت‌ها
# ════════════════════════════════════════════════════════════════

FONT_BOLD_PATH = "assets/fonts/Vazirmatn-Bold.ttf"
FONT_MEDIUM_PATH = "assets/fonts/Vazirmatn-Medium.ttf"
FONT_REGULAR_PATH = "assets/fonts/Vazirmatn-Regular.ttf"

# ════════════════════════════════════════════════════════════════
# 🔄 تنظیمات Retry و Network
# ════════════════════════════════════════════════════════════════

MAX_RETRIES = 3
RETRY_DELAY = 5  # ثانیه
REQUEST_TIMEOUT = 30  # ثانیه

# Headers برای درخواست‌های HTTP
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# ════════════════════════════════════════════════════════════════
# 📊 تنظیمات Google Sheets
# ════════════════════════════════════════════════════════════════

# هدر استاندارد (12 ستونی)
STANDARD_HEADER = [
    'timestamp',
    'gold_price_usd',
    'dollar_price',
    'shams_price',
    'dollar_change_percent',
    'shams_change_percent',
    'fund_weighted_change_percent',
    'fund_final_price_avg',              # ✅ ستون 7: میانگین ساده قیمت پایانی
    'fund_weighted_bubble_percent',
    'sarane_kharid_weighted',
    'sarane_forosh_weighted',
    'ekhtelaf_sarane_weighted'
]

# تعداد روزهای نگهداری داده
KEEP_DAYS = 30

# ════════════════════════════════════════════════════════════════
# 📝 تنظیمات Logging
# ════════════════════════════════════════════════════════════════

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = 'gold_tracker.log'
LOG_LEVEL = 'INFO'

# ════════════════════════════════════════════════════════════════
# 🎯 تنظیمات پیش‌فرض (Fallback Values)
# ════════════════════════════════════════════════════════════════

DEFAULT_GOLD_PRICE = 4200  # دلار (در صورت عدم دریافت)
DEFAULT_DOLLAR_PRICE = 114000  # تومان (در صورت عدم دریافت)

# ════════════════════════════════════════════════════════════════
# 📌 تنظیمات Telegram Message
# ════════════════════════════════════════════════════════════════

CHANNEL_HANDLE = "@Gold_Iran_Market"  # هندل کانال برای نمایش در پیام‌ها

# حداکثر تعداد پیام‌های بررسی شده برای یافتن قیمت بسته
MAX_MESSAGES_TO_CHECK = 10000

# اندازه batch برای خواندن پیام‌های تلگرام
MESSAGE_BATCH_SIZE = 100