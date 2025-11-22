# utils/sheets_storage.py — نسخه هوشمند با مدیریت خودکار هدر

import os
import json
import logging
from datetime import datetime, timedelta
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

# خواندن از Secrets
SHEET_ID = os.getenv("SHEET_ID")
SERVICE_ACCOUNT_JSON = os.getenv("SHEETS_SERVICE_ACCOUNT")

if not SHEET_ID or not SERVICE_ACCOUNT_JSON:
    raise Exception("SHEET_ID یا SHEETS_SERVICE_ACCOUNT در Secrets تنظیم نشده!")

# هدر استاندارد (نسخه 9 ستونی)
STANDARD_HEADER = [
    'timestamp',
    'gold_price_usd',
    'dollar_change_percent',
    'shams_change_percent',
    'fund_weighted_change_percent',
    'fund_weighted_bubble_percent',
    'sarane_kharid_weighted',
    'sarane_forosh_weighted',
    'ekhtelaf_sarane_weighted'
]

def get_sheets_service():
    """اتصال به Google Sheets API"""
    creds_info = json.loads(SERVICE_ACCOUNT_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=['https://www.googleapis.com/auth/spreadsheets']
    )
    return build('sheets', 'v4', credentials=credentials)


def ensure_header():
    """
    بررسی و ایجاد/آپدیت خودکار هدر
    اگه هدر نیست → می‌سازه
    اگه تعداد ستون‌ها اشتباهه → آپدیت می‌کنه
    اگه درسته → رد می‌شه
    """
    try:
        service = get_sheets_service()

        # خواندن هدر فعلی
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A1:I1'
        ).execute()

        existing_values = result.get('values', [])
        existing_header = existing_values[0] if existing_values else []

        # حالت 1: هدر نداره → بساز
        if not existing_header:
            logger.info("📝 هدر وجود ندارد، در حال ساخت...")
            service.spreadsheets().values().update(
                spreadsheetId=SHEET_ID,
                range='Sheet1!A1:I1',
                valueInputOption='RAW',
                body={'values': [STANDARD_HEADER]}
            ).execute()
            logger.info("✅ هدر جدید با موفقیت ساخته شد")
            return True

        # حالت 2: تعداد ستون‌ها درسته → رد شو
        if len(existing_header) == len(STANDARD_HEADER):
            logger.debug("✓ هدر معتبر است (9 ستون)")
            return True

        # حالت 3: تعداد ستون‌ها اشتباهه → آپدیت کن
        logger.warning(f"⚠️ هدر نامعتبر ({len(existing_header)} ستون، باید {len(STANDARD_HEADER)} ستون باشه)")
        logger.info("🔄 در حال آپدیت هدر...")

        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A1:I1',
            valueInputOption='RAW',
            body={'values': [STANDARD_HEADER]}
        ).execute()

        logger.info("✅ هدر با موفقیت آپدیت شد")

        # اخطار: داده‌های قدیمی ممکنه مشکل داشته باشن
        data_result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A2:I100'
        ).execute()

        old_data = data_result.get('values', [])
        if old_data:
            logger.warning(f"⚠️ توجه: {len(old_data)} ردیف داده قدیمی وجود دارد که ممکن است با فرمت جدید ناسازگار باشد")
            logger.warning("💡 توصیه: ردیف‌های قدیمی را دستی پاک کنید یا از clear_old_data() استفاده کنید")

        return True

    except Exception as e:
        logger.error(f"❌ خطا در بررسی/ساخت هدر: {e}", exc_info=True)
        return False


def is_today(date_str):
    """
    چک می‌کنه که تاریخ داده شده مال امروز هست یا نه
    
    Args:
        date_str: تاریخ به فرمت "2025-05-21"
    
    Returns:
        bool: True اگه مال امروز باشه
    """
    try:
        tz = pytz.timezone('Asia/Tehran')
        today = datetime.now(tz).strftime('%Y-%m-%d')
        return date_str == today
    except:
        return False


def save_to_sheets(row_dict):
    """
    ذخیره یک ردیف جدید در Google Sheet
    
    Args:
        row_dict: دیکشنری حاوی داده‌ها با کلیدهای:
            - gold_price: قیمت طلا
            - dollar_change: درصد تغییر دلار
            - shams_change: درصد تغییر شمش
            - shams_date: تاریخ داده شمش (برای چک کردن)
            - fund_change_weighted: میانگین وزنی تغییر صندوق‌ها
            - fund_bubble_weighted: میانگین وزنی حباب صندوق‌ها
            - sarane_kharid_w: سرانه خرید وزنی
            - sarane_forosh_w: سرانه فروش وزنی
            - ekhtelaf_sarane_w: اختلاف سرانه وزنی
    """
    try:
        # ✅ اول مطمئن شو که هدر درست هست
        ensure_header()

        service = get_sheets_service()

        # زمان فعلی (تهران)
        tz = pytz.timezone('Asia/Tehran')
        timestamp = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

        # ✅ چک کردن تاریخ شمش - اگه مال امروز نبود، صفر بذار
        shams_change = row_dict['shams_change']
        shams_date = row_dict.get('shams_date', None)
        
        if shams_date and not is_today(shams_date):
            logger.warning(f"⚠️ داده شمش مال امروز نیست (تاریخ: {shams_date})، مقدار صفر ذخیره می‌شود")
            shams_change = 0.0

        # آماده‌سازی ردیف جدید (9 ستون)
        new_row = [
            timestamp,
            round(row_dict['gold_price'], 2),
            round(row_dict['dollar_change'], 2),
            round(shams_change, 2),
            round(row_dict['fund_change_weighted'], 2),
            round(row_dict['fund_bubble_weighted'], 2),
            round(row_dict['sarane_kharid_w'], 2),
            round(row_dict['sarane_forosh_w'], 2),
            round(row_dict['ekhtelaf_sarane_w'], 2)
        ]

        # اضافه کردن ردیف جدید
        service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:I',
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
        # ✅ اول مطمئن شو که هدر درست هست
        ensure_header()

        service = get_sheets_service()

        # خواندن تمام داده‌ها
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:I'
        ).execute()

        values = result.get('values', [])

        if not values:
            logger.warning("⚠️ Sheet خالی است")
            return []

        # بدون هدر برگردون (فقط داده‌ها)
        data_rows = values[1:]  # ردیف اول هدره

        # فیلتر: فقط ردیف‌هایی که 9 ستون دارن (برای جلوگیری از خطا)
        valid_rows = [row for row in data_rows if len(row) == 9]

        if len(valid_rows) < len(data_rows):
            logger.warning(f"⚠️ {len(data_rows) - len(valid_rows)} ردیف نامعتبر نادیده گرفته شد")

        # فقط N ردیف آخر
        if len(valid_rows) > limit:
            valid_rows = valid_rows[-limit:]

        logger.info(f"✅ {len(valid_rows)} ردیف معتبر از Sheet خوانده شد")
        return valid_rows

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
            range='Sheet1!A:I'
        ).execute()

        values = result.get('values', [])
        if len(values) <= 1:  # فقط هدر یا خالی
            return

        # پیدا کردن اولین ردیف معتبر
        first_valid_row = 2  # ردیف 2 (بعد از هدر)
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


def clear_invalid_rows():
    """
    پاک کردن ردیف‌هایی که 9 ستون ندارن (برای پاکسازی داده‌های قدیمی)
    """
    try:
        service = get_sheets_service()

        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:I'
        ).execute()

        values = result.get('values', [])
        if len(values) <= 1:
            logger.info("ℹ️ فقط هدر وجود دارد، نیازی به پاکسازی نیست")
            return

        header = values[0]
        valid_rows = [header]  # هدر رو نگه دار
        invalid_count = 0

        # فقط ردیف‌های 9 ستونی رو نگه دار
        for row in values[1:]:
            if len(row) == 9:
                valid_rows.append(row)
            else:
                invalid_count += 1

        if invalid_count == 0:
            logger.info("✅ همه ردیف‌ها معتبرند")
            return

        # پاک کردن همه و نوشتن دوباره
        logger.info(f"🧹 در حال پاکسازی {invalid_count} ردیف نامعتبر...")

        # پاک کردن کل Sheet
        service.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:I'
        ).execute()

        # نوشتن داده‌های معتبر
        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:I',
            valueInputOption='RAW',
            body={'values': valid_rows}
        ).execute()

        logger.info(f"✅ {invalid_count} ردیف نامعتبر پاک شد، {len(valid_rows)-1} ردیف معتبر باقی ماند")

    except Exception as e:
        logger.error(f"❌ خطا در پاکسازی ردیف‌های نامعتبر: {e}", exc_info=True)