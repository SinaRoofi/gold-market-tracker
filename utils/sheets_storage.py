import os
import json
import logging
from datetime import datetime
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# خواندن از Secrets
SHEET_ID = os.getenv("SHEET_ID")
SERVICE_ACCOUNT_JSON = os.getenv("SHEETS_SERVICE_ACCOUNT")

if not SHEET_ID or not SERVICE_ACCOUNT_JSON:
    raise Exception("SHEET_ID یا SHEETS_SERVICE_ACCOUNT در Secrets تنظیم نشده!")

def get_sheets_service():
    """اتصال به Google Sheets API"""
    creds_info = json.loads(SERVICE_ACCOUNT_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    return build('sheets', 'v4', credentials=credentials)


def save_to_sheets(row_dict):
    """
    ذخیره یک ردیف جدید در Google Sheet
    
    Args:
        row_dict: دیکشنری حاوی داده‌ها با کلیدهای:
            - gold_price: قیمت طلا
            - dollar_change: درصد تغییر دلار
            - shams_change: درصد تغییر شمش
            - fund_change_weighted: میانگین وزنی تغییر صندوق‌ها
            - sarane_kharid_w: سرانه خرید وزنی
            - sarane_forosh_w: سرانه فروش وزنی
            - ekhtelaf_sarane_w: اختلاف سرانه وزنی
    """
    try:
        service = get_sheets_service()
        
        # زمان فعلی (تهران)
        tz = pytz.timezone('Asia/Tehran')
        timestamp = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        
        # آماده‌سازی ردیف جدید
        new_row = [
            timestamp,
            round(row_dict['gold_price'], 2),
            round(row_dict['dollar_change'], 2),
            round(row_dict['shams_change'], 2),
            round(row_dict['fund_change_weighted'], 2),
            round(row_dict['sarane_kharid_w'], 2),
            round(row_dict['sarane_forosh_w'], 2),
            round(row_dict['ekhtelaf_sarane_w'], 2)
        ]
        
        # بررسی وجود هدر
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A1:H1'
        ).execute()
        
        # اگه هدر نداشته باشه، اول هدر رو بنویس
        if 'values' not in result:
            header = [
                'timestamp',
                'gold_price_usd',
                'dollar_change_percent',
                'shams_change_percent',
                'fund_weighted_change_percent',
                'sarane_kharid_weighted',
                'sarane_forosh_weighted',
                'ekhtelaf_sarane_weighted'
            ]
            service.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range='Sheet1!A1:H1',
                valueInputOption='RAW',
                body={'values': [header]}
            ).execute()
            logger.info("✅ هدر Google Sheet ساخته شد")
        
        # اضافه کردن ردیف جدید
        service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:H',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': [new_row]}
        ).execute()
        
        logger.info(f"✅ داده با موفقیت در Sheet ذخیره شد: {timestamp}")
        
    except Exception as e:
        logger.error(f"❌ خطا در ذخیره‌سازی در Google Sheet: {e}", exc_info=True)


def read_from_sheets(limit=1000):
    """
    خواندن داده‌ها از Google Sheet برای نمودارها
    
    Args:
        limit: تعداد ردیف‌های اخیر (پیش‌فرض 1000)
    
    Returns:
        list: لیستی از ردیف‌ها (هر ردیف یک لیست است)
    """
    try:
        service = get_sheets_service()
        
        # خواندن تمام داده‌ها
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:H'
        ).execute()
        
        values = result.get('values', [])
        
        if not values:
            logger.warning("⚠️ Sheet خالی است")
            return []
        
        # بدون هدر برگردون (فقط داده‌ها)
        data_rows = values[1:]  # ردیف اول هدره
        
        # فقط N ردیف آخر
        if len(data_rows) > limit:
            data_rows = data_rows[-limit:]
        
        logger.info(f"✅ {len(data_rows)} ردیف از Sheet خوانده شد")
        return data_rows
        
    except Exception as e:
        logger.error(f"❌ خطا در خواندن از Google Sheet: {e}", exc_info=True)
        return []


def clear_old_data(keep_days=30):
    """
    پاک کردن داده‌های قدیمی‌تر از X روز (اختیاری)
    
    Args:
        keep_days: تعداد روزهایی که باید نگه‌داری شود
    """
    try:
        service = get_sheets_service()
        tz = pytz.timezone('Asia/Tehran')
        cutoff_date = datetime.now(tz) - timedelta(days=keep_days)
        
        # خواندن تمام داده‌ها
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:H'
        ).execute()
        
        values = result.get('values', [])
        if len(values) <= 1:  # فقط هدر یا خالی
            return
        
        # پیدا کردن اولین ردیف معتبر
        first_valid_row = 2  # ردیف 2 (بعد از هدر)
        for i, row in enumerate(values[1:], start=2):
            if not row:
                continue
            try:
                row_date = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                row_date = tz.localize(row_date)
                if row_date >= cutoff_date:
                    first_valid_row = i
                    break
            except:
                continue
        
        # اگه ردیف‌های قدیمی داریم، پاکشون کن
        if first_valid_row > 2:
            service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={
                    'requests': [{
                        'deleteDimension': {
                            'range': {
                                'sheetId': 0,
                                'dimension': 'ROWS',
                                'startIndex': 1,
                                'endIndex': first_valid_row - 1
                            }
                        }
                    }]
                }
            ).execute()
            logger.info(f"🗑️ {first_valid_row - 2} ردیف قدیمی پاک شد")
            
    except Exception as e:
        logger.error(f"❌ خطا در پاک‌سازی داده‌های قدیمی: {e}", exc_info=True)
