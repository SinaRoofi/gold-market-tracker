# utils/drive_storage.py   ← فقط این فایل رو کپی-پیست کن (هیچ چیز دیگه‌ای لازم نیست)

import os
import io
import json
import logging
from datetime import datetime
import pytz
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

logger = logging.getLogger(__name__)

# این دو تا رو از Secret می‌خونه (تو کد هیچ ID یا کلیدی نیست!)
DRIVE_FILE_ID = os.getenv("DRIVE_FILE_ID")          # ← از گیتهاب میاد
SERVICE_ACCOUNT_JSON = os.getenv("DRIVE_SERVICE_ACCOUNT")  # ← از گیتهاب میاد

if not DRIVE_FILE_ID or not SERVICE_ACCOUNT_JSON:
    raise Exception("DRIVE_FILE_ID یا DRIVE_SERVICE_ACCOUNT در Secrets تنظیم نشده!")

def get_drive_service():
    creds_info = json.loads(SERVICE_ACCOUNT_JSON)
    credentials = service_account.Credentials.from_service_account_info(
        creds_info,
        scopes=['https://www.googleapis.com/auth/drive.file']
    )
    return build('drive', 'v3', credentials=credentials)

def save_to_drive(row_dict):
    try:
        service = get_drive_service()
        temp_file = "/tmp/temp_chart.csv"

        # دانلود فایل فعلی
        try:
            request = service.files().get_media(fileId=DRIVE_FILE_ID)
            fh = io.BytesIO()
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
            fh.seek(0)
            with open(temp_file, "wb") as f:
                f.write(fh.read())
            logger.info("فایل از درایو دانلود شد")
        except:
            logger.info("فایل وجود نداشت → جدید ساخته میشه")
            with open(temp_file, "w", encoding="utf-8") as f:
                f.write("timestamp,gold_price_usd,dollar_change_percent,shams_change_percent,fund_weighted_change_percent,sarane_kharid_weighted,sarane_forosh_weighted,ekhtelaf_sarane_weighted\n")

        # اضافه کردن ردیف جدید
        tz = pytz.timezone('Asia/Tehran')
        ts = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
        with open(temp_file, "a", encoding="utf-8") as f:
            f.write(f"{ts},{row_dict['gold_price']:.2f},{row_dict['dollar_change']:.2f},"
                    f"{row_dict['shams_change']:.2f},{row_dict['fund_change_weighted']:.2f},"
                    f"{row_dict['sarane_kharid_w']:.2f},{row_dict['sarane_forosh_w']:.2f},"
                    f"{row_dict['ekhtelaf_sarane_w']:.2f}\n")

        # آپلود
        media = MediaFileUpload(temp_file, mimetype='text/csv')
        service.files().update(fileId=DRIVE_FILE_ID, media_body=media).execute()
        logger.info("داده جدید با موفقیت آپلود شد")

    except Exception as e:
        logger.error(f"خطا در ذخیره در درایو: {e}", exc_info=True)

def download_for_chart():
    try:
        service = get_drive_service()
        request = service.files().get_media(fileId=DRIVE_FILE_ID)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return fh
    except Exception as e:
        logger.error(f"دانلود از درایو ناموفق: {e}")
        return None