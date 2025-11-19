import os
import csv
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

def get_csv_filename():
    """نام فایل CSV بر اساس تاریخ امروز تولید می‌شود"""
    tehran_tz = pytz.timezone('Asia/Tehran')
    today_str = datetime.now(tehran_tz).strftime('%Y-%m-%d')
    return f"market_data_{today_str}.csv"

def initialize_csv(file_path):
    """ایجاد فایل CSV با هدرها اگر وجود نداشته باشد"""
    if not os.path.exists(file_path):
        with open(file_path, 'w', encoding='utf-8', newline='') as f:
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
                'value'
            ])
        logger.info(f"✅ فایل CSV جدید ایجاد شد: {file_path}")

def save_market_snapshot(dollar_prices, yesterday_close, Fund_df, gold_price, gold_yesterday, dfp):
    """ذخیره یک snapshot از بازار"""
    try:
        csv_file = get_csv_filename()
        initialize_csv(csv_file)

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
        with open(csv_file, 'a', encoding='utf-8', newline='') as f:
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
                    row['value']
                ])

        logger.info(f"✅ داده‌های ساعت {timestamp} ذخیره شد در {csv_file}")
        return True

    except Exception as e:
        logger.error(f"❌ خطا در ذخیره داده‌ها: {e}", exc_info=True)
        return False