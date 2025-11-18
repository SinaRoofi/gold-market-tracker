import io
import logging
import requests
import json
from utils.chart_creator import create_market_charts, create_combined_image
from persiantools.jdatetime import JalaliDateTime
import pytz

logger = logging.getLogger(__name__)

def send_to_telegram(
    bot_token,
    chat_id,
    data,
    dollar_prices,
    gold_price,
    gold_yesterday,
    gold_time,
    yesterday_close,
):
    if data is None:
        logger.error("❌ داده‌های پردازش‌شده (data) مقدار None دارد. ارسال متوقف شد.")
        return False

    try:
        # ایجاد تصویر اول (Treemap + جدول)
        img1_bytes = create_combined_image(
            data["Fund_df"],
            dollar_prices["last_trade"],
            gold_price,
            gold_yesterday,
            data["dfp"],
            yesterday_close,
        )

        # ایجاد تصویر دوم (نمودارها)
        img2_bytes = create_market_charts()

        # ایجاد کپشن
        caption = create_simple_caption(
            data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
        )

        # ارسال به صورت Media Group (آلبوم)
        if img2_bytes:
            return send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption)
        else:
            # اگر نمودار نبود، فقط تصویر اول رو بفرست
            logger.warning("⚠️ نمودارها موجود نیست، فقط تصویر اول ارسال می‌شود")
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": ("market_report.png", io.BytesIO(img1_bytes), "image/png")}
            params = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}

            response = requests.post(url, files=files, data=params, timeout=60)

            if response.status_code == 200:
                return True
            else:
                logger.error(f"❌ خطا در ارسال: {response.text}")
                return False

    except Exception as e:
        logger.error(f"❌ خطا در ارسال به تلگرام: {e}", exc_info=True)
        return False


def send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption):
    """ارسال 2 عکس + کپشن به صورت Media Group"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"

        files = {
            'photo1': ('market_treemap.png', io.BytesIO(img1_bytes), 'image/png'),
            'photo2': ('market_charts.png', io.BytesIO(img2_bytes), 'image/png')
        }

        media = [
            {
                'type': 'photo',
                'media': 'attach://photo1',
                'caption': caption,
                'parse_mode': 'HTML'
            },
            {
                'type': 'photo',
                'media': 'attach://photo2'
            }
        ]

        data = {
            'chat_id': chat_id,
            'media': json.dumps(media)  # <-- اصلاح این خط
        }

        response = requests.post(url, files=files, data=data, timeout=60)

        if response.status_code == 200:
            logger.info("✅ Media Group ارسال شد")
            return True
        else:
            logger.error(f"❌ خطا در ارسال Media Group: {response.text}")
            return False

    except Exception as e:
        logger.error(f"❌ خطا در ارسال Media Group: {e}", exc_info=True)
        return False


def create_simple_caption(
    data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
):
    # نسخه ساده و بدون تغییر، همان تابع قدیمی شما
    from utils.telegram_sender_utils import create_caption_text
    return create_caption_text(data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time)
