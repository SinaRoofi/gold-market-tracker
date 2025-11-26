# utils/sheets_storage.py
"""ماژول مدیریت ذخیره‌سازی داده‌ها در Google Sheets"""

import json
import logging
from datetime import datetime, timedelta
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build

from config import (
    SHEET_ID,
    SERVICE_ACCOUNT_JSON,
    STANDARD_HEADER,
    KEEP_DAYS,
    TIMEZONE
)

logger = logging.getLogger(__name__)

# بررسی متغیرهای محیطی
if not SHEET_ID or not SERVICE_ACCOUNT_JSON:
    raise Exception("⚠️ SHEET_ID یا SHEETS_SERVICE_ACCOUNT در Secrets تنظیم نشده!")


def get_sheets_service():
    """اتصال به Google Sheets API"""
    try:
        creds_info = json.loads(SERVICE_ACCOUNT_JSON)
        credentials = service_account.Credentials.from_service_account_info(
            creds_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        return build('sheets', 'v4', credentials=credentials, cache_discovery=False)
    except Exception as e:
        logger.error(f"❌ خطا در اتصال به Google Sheets: {e}")
        raise


def ensure_header():
    """بررسی و ایجاد/آپدیت خودکار هدر"""
    try:
        service = get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A1:K1'
        ).execute()

        existing_values = result.get('values', [])
        existing_header = existing_values[0] if existing_values else []

        # اگر هدر وجود نداره، بساز
        if not existing_header:
            logger.info("📝 هدر وجود ندارد، در حال ساخت...")
            service.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range='Sheet1!A1:K1',
                valueInputOption='RAW',
                body={'values': [STANDARD_HEADER]}
            ).execute()
            logger.info("✅ هدر جدید ساخته شد (11 ستون)")
            return True

        # اگر تعداد ستون‌ها درسته
        if len(existing_header) == len(STANDARD_HEADER):
            logger.debug("✓ هدر معتبر است (11 ستون)")
            return True

        # اگر تعداد ستون‌ها اشتباهه، آپدیت کن
        logger.warning(f"⚠️ هدر نامعتبر ({len(existing_header)} ستون)")
        logger.info("🔄 در حال آپدیت هدر...")
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A1:K1',
            valueInputOption='RAW',
            body={'values': [STANDARD_HEADER]}
        ).execute()
        logger.info("✅ هدر آپدیت شد")
        return True

    except Exception as e:
        logger.error(f"❌ خطا در بررسی/ساخت هدر: {e}", exc_info=True)
        return False


def is_today(date_str):
    """چک می‌کنه که تاریخ داده شده مال امروز هست یا نه"""
    try:
        tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tz).strftime('%Y-%m-%d')
        return date_str == today
    except:
        return False


def save_to_sheets(row_dict):
    """
    ذخیره یک ردیف جدید در Google Sheet
    
    Args:
        row_dict: دیکشنری حاوی داده‌های یک ردیف با کلیدهای زیر:
            - gold_price: قیمت طلا (دلار)
            - dollar_price: قیمت دلار (تومان)
            - shams_price: قیمت شمش (ریال)
            - dollar_change: درصد تغییر دلار
            - shams_change: درصد تغییر شمش
            - shams_date: تاریخ معاملات شمش
            - fund_change_weighted: میانگین وزنی تغییر صندوق‌ها
            - fund_bubble_weighted: میانگین وزنی حباب
            - sarane_kharid_w: سرانه خرید
            - sarane_forosh_w: سرانه فروش
            - ekhtelaf_sarane_w: اختلاف سرانه
    """
    try:
        ensure_header()
        service = get_sheets_service()
        tz = pytz.timezone(TIMEZONE)
        timestamp = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

        # بررسی تاریخ شمش
        shams_change = row_dict['shams_change']
        shams_date = row_dict.get('shams_date', None)

        if shams_date and not is_today(shams_date):
            logger.warning(f"⚠️ داده شمش مال امروز نیست (تاریخ: {shams_date})")
            shams_change = 0.0

        # ساخت ردیف جدید (11 ستونی)
        new_row = [
            timestamp,
            round(row_dict['gold_price'], 2),
            int(row_dict['dollar_price']),
            int(row_dict['shams_price']),
            round(row_dict['dollar_change'], 2),
            round(shams_change, 2),
            round(row_dict['fund_change_weighted'], 2),
            round(row_dict['fund_bubble_weighted'], 2),
            round(row_dict['sarane_kharid_w'], 2),
            round(row_dict['sarane_forosh_w'], 2),
            round(row_dict['ekhtelaf_sarane_w'], 2)
        ]

        # ذخیره در Sheet
        service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:K',
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body={'values': [new_row]}
        ).execute()

        logger.info(f"✅ داده در Sheet ذخیره شد: {timestamp}")

    except Exception as e:
        logger.error(f"❌ خطا در ذخیره‌سازی در Google Sheet: {e}", exc_info=True)


def read_from_sheets(limit=1000):
    """
    خواندن داده‌ها از Google Sheet
    
    Args:
        limit: حداکثر تعداد ردیف‌های برگشتی (پیش‌فرض 1000)
    
    Returns:
        list: لیستی از ردیف‌ها (هر ردیف یک لیست 11 عنصری)
    """
    try:
        ensure_header()
        service = get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:K'
        ).execute()

        values = result.get('values', [])
        if not values:
            logger.warning("⚠️ Sheet خالی است")
            return []

        # حذف هدر (ردیف اول)
        data_rows = values[1:]
        
        # فقط ردیف‌های معتبر (11 ستونی)
        valid_rows = [row for row in data_rows if len(row) == 11]

        if len(valid_rows) < len(data_rows):
            invalid_count = len(data_rows) - len(valid_rows)
            logger.warning(f"⚠️ {invalid_count} ردیف نامعتبر نادیده گرفته شد")

        # محدود کردن به limit آخرین ردیف
        if len(valid_rows) > limit:
            valid_rows = valid_rows[-limit:]

        logger.info(f"✅ {len(valid_rows)} ردیف از Sheet خوانده شد")
        return valid_rows

    except Exception as e:
        logger.error(f"❌ خطا در خواندن از Google Sheet: {e}", exc_info=True)
        return []


def clear_old_data(keep_days=None):
    """
    پاک کردن داده‌های قدیمی‌تر از X روز
    
    Args:
        keep_days: تعداد روزهای نگهداری (پیش‌فرض از config)
    """
    if keep_days is None:
        keep_days = KEEP_DAYS
        
    try:
        service = get_sheets_service()
        tz = pytz.timezone(TIMEZONE)
        cutoff_date = datetime.now(tz) - timedelta(days=keep_days)
        
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:K'
        ).execute()

        values = result.get('values', [])
        if len(values) <= 1:  # فقط هدر یا خالی
            logger.info("ℹ️ داده‌ای برای پاکسازی وجود ندارد")
            return

        first_valid_row = 2  # ردیف اول بعد از هدر
        for i, row in enumerate(values[1:], start=2):
            if not row or len(row) < 1:
                continue
            try:
                row_date = datetime.strptime(row[0], '%Y-%m-%d %H:%M:%S')
                row_date = tz.localize(row_date)
                if row_date >= cutoff_date:
                    first_valid_row = i
                    break
            except:
                continue

        # اگر ردیف‌های قدیمی داریم، پاک کن
        if first_valid_row > 2:
            rows_to_delete = first_valid_row - 2
            service.spreadsheets().batchUpdate(
                spreadsheetId=SHEET_ID,
                body={
                    'requests': [{
                        'deleteDimension': {
                            'range': {
                                'sheetId': 0,
                                'dimension': 'ROWS',
                                'startIndex': 1,  # بعد از هدر
                                'endIndex': first_valid_row - 1
                            }
                        }
                    }]
                }
            ).execute()
            logger.info(f"🗑️ {rows_to_delete} ردیف قدیمی پاک شد")
        else:
            logger.info("✅ داده قدیمی برای پاک کردن پیدا نشد")

    except Exception as e:
        logger.error(f"❌ خطا در پاک‌سازی: {e}", exc_info=True)


def clear_invalid_rows():
    """پاک کردن ردیف‌هایی که 11 ستون ندارن"""
    try:
        service = get_sheets_service()
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:K'
        ).execute()

        values = result.get('values', [])
        if len(values) <= 1:
            logger.info("ℹ️ فقط هدر وجود دارد")
            return

        header = values[0]
        valid_rows = [header]
        invalid_count = 0

        for row in values[1:]:
            if len(row) == 11:
                valid_rows.append(row)
            else:
                invalid_count += 1

        if invalid_count == 0:
            logger.info("✅ همه ردیف‌ها معتبرند")
            return

        logger.info(f"🧹 در حال پاکسازی {invalid_count} ردیف نامعتبر...")
        
        # پاک کردن همه
        service.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:K'
        ).execute()

        # نوشتن دوباره ردیف‌های معتبر
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:K',
            valueInputOption='RAW',
            body={'values': valid_rows}
        ).execute()

        logger.info(f"✅ {invalid_count} ردیف نامعتبر پاک شد")

    except Exception as e:
        logger.error(f"❌ خطا در پاکسازی: {e}", exc_info=True)


def get_sheet_stats():
    """دریافت آمار Sheet (تعداد ردیف‌ها، قدیمی‌ترین و جدیدترین تاریخ)"""
    try:
        rows = read_from_sheets(limit=10000)
        if not rows:
            return {"total_rows": 0, "oldest": None, "newest": None}

        timestamps = [row[0] for row in rows if len(row) > 0]
        
        return {
            "total_rows": len(rows),
            "oldest": timestamps[0] if timestamps else None,
            "newest": timestamps[-1] if timestamps else None,
        }
    except Exception as e:
        logger.error(f"❌ خطا در دریافت آمار: {e}")
        return {"total_rows": 0, "oldest": None, "newest": None}