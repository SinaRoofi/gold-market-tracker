import os
import csv
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)

DATA_FILE = "market_data_today.csv"

def initialize_csv():
    """ایجاد فایل CSV با هدرها اگر وجود نداشته باشد"""
    tehran_tz = pytz.timezone('Asia/Tehran')
    today = datetime.now(tehran_tz).date()

    # چک کردن آیا فایل مربوط به امروز است یا باید ریست شود
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                first_line = f.readline().strip()
                if first_line and not first_line.startswith('timestamp'):
                    os.remove(DATA_FILE)
                    logger.info("🗑️ فایل CSV خراب بود، حذف و ایجاد مجدد")
                else:
                    # چک کردن آخرین رکورد
                    f.seek(0)
                    lines = f.readlines()
                    if len(lines) > 1:
                        last_line = lines[-1].strip()
                        if last_line:
                            last_date_str = last_line.split(',')[0]
                            last_date = datetime.fromisoformat(last_date_str).date()

                            if last_date != today:
                                os.remove(DATA_FILE)
                                logger.info(f"📅 فایل CSV مربوط به {last_date} بود، ایجاد فایل جدید برای {today}")
        except Exception as e:
            logger.error(f"خطا در چک کردن فایل CSV: {e}")
            if os.path.exists(DATA_FILE):
                os.remove(DATA_FILE)

    # ایجاد فایل جدید اگر وجود نداشته باشد
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp',
                'gold_price',
                'dollar_last_trade',
                'dollar_change_percent',
                'shams_close_price',
                'shams_change_percent',
                'fund_symbol',
                'fund_close_price',
                'fund_price_change_percent',
                'sarane_kharid',
                'sarane_forosh',
                'ekhtelaf_sarane',
                'value'  # اضافه شدن ستون value
            ])
        logger.info("✅ فایل CSV جدید ایجاد شد")

def save_market_snapshot(dollar_prices, yesterday_close, Fund_df, gold_price, gold_yesterday, dfp):
    """ذخیره یک snapshot از بازار"""
    try:
        initialize_csv()

        tehran_tz = pytz.timezone('Asia/Tehran')
        timestamp = datetime.now(tehran_tz).strftime('%Y-%m-%d %H:%M:%S')

        # محاسبه درصد تغییر دلار
        dollar_change_percent = 0
        if yesterday_close and yesterday_close != 0:
            dollar_change_percent = ((dollar_prices['last_trade'] - yesterday_close) / yesterday_close) * 100

        # گرفتن قیمت شمش
        shams = dfp.loc['شمش-طلا']
        shams_close_price = shams['close_price']
        shams_change_percent = shams['close_price_change_percent']

        # ذخیره داده‌های هر صندوق
        with open(DATA_FILE, 'a', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)

            for symbol, row in Fund_df.iterrows():
                writer.writerow([
                    timestamp,
                    gold_price,
                    dollar_prices['last_trade'],
                    round(dollar_change_percent, 2),
                    shams_close_price,
                    shams_change_percent,
                    symbol,
                    row['close_price'],
                    row['close_price_change_percent'],
                    row['sarane_kharid'],
                    row['sarane_forosh'],
                    row['ekhtelaf_sarane'],
                    row['value']  # اضافه شدن مقدار value
                ])

        logger.info(f"✅ داده‌های ساعت {timestamp} ذخیره شد")
        return True

    except Exception as e:
        logger.error(f"❌ خطا در ذخیره داده‌ها: {e}", exc_info=True)
        return False