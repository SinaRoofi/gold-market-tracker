# utils/sheets_storage.py — نسخه نهایی

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

# هدر استاندارد (11 ستونی)
STANDARD_HEADER = [
    'timestamp',
    'gold_price_usd',
    'dollar_price',
    'shams_price',
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
    return build('sheets', 'v4', credentials=credentials,cache_discovery=False)


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

        if len(existing_header) == len(STANDARD_HEADER):
            logger.debug("✓ هدر معتبر است (11 ستون)")
            return True

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
        tz = pytz.timezone('Asia/Tehran')
        today = datetime.now(tz).strftime('%Y-%m-%d')
        return date_str == today
    except:
        return False


def save_to_sheets(row_dict):
    """ذخیره یک ردیف جدید در Google Sheet"""
    try:
        ensure_header()
        service = get_sheets_service()
        tz = pytz.timezone('Asia/Tehran')
        timestamp = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

        shams_change = row_dict['shams_change']
        shams_date = row_dict.get('shams_date', None)

        if shams_date and not is_today(shams_date):
            logger.warning(f"⚠️ داده شمش مال امروز نیست (تاریخ: {shams_date})")
            shams_change = 0.0

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
    """خواندن داده‌ها از Google Sheet"""
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

        data_rows = values[1:]
        valid_rows = [row for row in data_rows if len(row) == 11]

        if len(valid_rows) < len(data_rows):
            logger.warning(f"⚠️ {len(data_rows) - len(valid_rows)} ردیف نامعتبر نادیده گرفته شد")

        if len(valid_rows) > limit:
            valid_rows = valid_rows[-limit:]

        logger.info(f"✅ {len(valid_rows)} ردیف از Sheet خوانده شد")
        return valid_rows

    except Exception as e:
        logger.error(f"❌ خطا در خواندن از Google Sheet: {e}", exc_info=True)
        return []


def clear_old_data(keep_days=30):
    """پاک کردن داده‌های قدیمی‌تر از X روز"""
    try:
        service = get_sheets_service()
        tz = pytz.timezone('Asia/Tehran')
        cutoff_date = datetime.now(tz) - timedelta(days=keep_days)
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:K'
        ).execute()

        values = result.get('values', [])
        if len(values) <= 1:
            return

        first_valid_row = 2
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
        service.spreadsheets().values().clear(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:K'
        ).execute()

        service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range='Sheet1!A:K',
            valueInputOption='RAW',
            body={'values': valid_rows}
        ).execute()

        logger.info(f"✅ {invalid_count} ردیف نامعتبر پاک شد")

    except Exception as e:
        logger.error(f"❌ خطا در پاکسازی: {e}", exc_info=True)