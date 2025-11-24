# utils/telegram_sender.py — نسخه نهایی

import io
import os
import logging
import json
import requests
import pytz
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from persiantools.jdatetime import JalaliDateTime
from PIL import Image, ImageDraw, ImageFont
from utils.chart_creator import create_market_charts
from utils.sheets_storage import read_from_sheets

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════
# ⚙️ تنظیمات هشدارها - اینجا عدد بذار
# ═══════════════════════════════════════════════════════════

# هشدار عبور از قیمت مشخص - دلار
DOLLAR_ALERT_PRICE_HIGH = 114000  # تومان (صعودی)
DOLLAR_ALERT_PRICE_LOW = 113000   # تومان (نزولی)

# هشدار عبور از قیمت مشخص - شمش
SHAMS_ALERT_PRICE_HIGH = 15_000_000  # ریال (صعودی)
SHAMS_ALERT_PRICE_LOW = 14_900_000   # ریال (نزولی)

# هشدار عبور از قیمت مشخص - اونس
GOLD_ALERT_PRICE_HIGH = 4200  # دلار (صعودی)
GOLD_ALERT_PRICE_LOW = 4080   # دلار (نزولی)

# هشدار تغییر سریع (درصد نسبت به 5 دقیقه قبل)
ALERT_THRESHOLD_PERCENT = 0.5  # ±0.5%

# هشدار تغییر شدید اختلاف سرانه (واحد)
EKHTELAF_THRESHOLD = 10  # ±10 واحد

# Gist Settings
GIST_ID = os.getenv("GIST_ID")
GIST_TOKEN = os.getenv("GIST_TOKEN")


# ═══════════════════════════════════════════════════════════
# توابع Gist
# ═══════════════════════════════════════════════════════════

def get_gist_data():
    """خواندن message_id، date و آخرین هشدارها از Gist"""
    try:
        if not GIST_ID or not GIST_TOKEN:
            logger.error("❌ GIST_ID یا GIST_TOKEN تنظیم نشده!")
            return {"message_id": None, "date": None, "last_alerts": {}}
        
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            content = response.json()["files"]["message_id.json"]["content"]
            data = json.loads(content)
            logger.info(f"📖 Gist خوانده شد: message_id={data.get('message_id')}, date={data.get('date')}")
            
            # اگه last_alerts نداره، اضافه کن
            if "last_alerts" not in data:
                data["last_alerts"] = {}
            
            return data
        else:
            logger.error(f"❌ خطا در خواندن Gist: HTTP {response.status_code}")
    except Exception as e:
        logger.error(f"❌ خطا در خواندن Gist: {e}")
    
    return {"message_id": None, "date": None, "last_alerts": {}}


def save_gist_data(message_id, date, last_alerts=None):
    """ذخیره message_id، date و آخرین هشدارها در Gist"""
    try:
        # خواندن داده فعلی
        current_data = get_gist_data()
        
        # اگه last_alerts جدید داده نشده، از قبلی استفاده کن
        if last_alerts is None:
            last_alerts = current_data.get("last_alerts", {})
        
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        data = {
            "files": {
                "message_id.json": {
                    "content": json.dumps({
                        "message_id": message_id,
                        "date": date,
                        "last_alerts": last_alerts
                    })
                }
            }
        }
        requests.patch(url, headers=headers, json=data, timeout=10)
        logger.info(f"✅ Gist آپدیت شد: message_id={message_id}, date={date}")
    except Exception as e:
        logger.error(f"❌ خطا در ذخیره Gist: {e}")


def get_today_date():
    """تاریخ امروز میلادی"""
    tz = pytz.timezone("Asia/Tehran")
    return datetime.now(tz).strftime("%Y-%m-%d")


# ═══════════════════════════════════════════════════════════
# خواندن وضعیت قبلی از Sheet
# ═══════════════════════════════════════════════════════════

def get_previous_state_from_sheet():
    """
    خواندن آخرین ردیف از Sheet
    
    ستون‌های Sheet (11 ستون):
    0: timestamp
    1: gold_price_usd
    2: dollar_price
    3: shams_price
    4: dollar_change_percent
    5: shams_change_percent
    6: fund_weighted_change_percent
    7: fund_weighted_bubble_percent
    8: sarane_kharid_weighted
    9: sarane_forosh_weighted
    10: ekhtelaf_sarane_weighted
    """
    try:
        rows = read_from_sheets(limit=1)
        if rows and len(rows) > 0:
            last_row = rows[-1]
            return {
                "dollar_price": float(last_row[2]) if len(last_row) > 2 else None,
                "shams_price": float(last_row[3]) if len(last_row) > 3 else None,
                "dollar_change": float(last_row[4]) if len(last_row) > 4 else None,
                "shams_change": float(last_row[5]) if len(last_row) > 5 else None,
                "gold_price": float(last_row[1]) if len(last_row) > 1 else None,
                "fund_change": float(last_row[6]) if len(last_row) > 6 else None,
                "ekhtelaf_sarane": float(last_row[10]) if len(last_row) > 10 else None,
            }
    except Exception as e:
        logger.error(f"❌ خطا در خواندن وضعیت قبلی از Sheet: {e}")
    
    return {
        "dollar_price": None,
        "shams_price": None,
        "dollar_change": None,
        "shams_change": None,
        "gold_price": None,
        "fund_change": None,
        "ekhtelaf_sarane": None
    }


# ═══════════════════════════════════════════════════════════
# تابع اصلی ارسال به تلگرام
# ═══════════════════════════════════════════════════════════

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
        logger.error("❌ داده‌های پردازش‌شده (data) مقدار None دارد.")
        return False

    try:
        # ساخت تصاویر
        img1_bytes = create_combined_image(
            data["Fund_df"],
            dollar_prices["last_trade"],
            gold_price,
            gold_yesterday,
            data["dfp"],
            yesterday_close,
        )
        img2_bytes = create_market_charts()

        # ساخت کپشن
        caption = create_simple_caption(
            data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
        )

        # چک کردن و ارسال هشدارها
        check_and_send_alerts(
            bot_token, chat_id, data, dollar_prices, gold_price, yesterday_close, gold_yesterday
        )

        # خواندن message_id از Gist
        gist_data = get_gist_data()
        saved_message_id = gist_data.get("message_id")
        saved_date = gist_data.get("date")
        today = get_today_date()

        # اگر روز عوض شده → پیام جدید
        if saved_date != today:
            saved_message_id = None
            logger.info(f"📅 روز جدید: {today} - پیام جدید ارسال می‌شود")

        # اگر پیام قبلی وجود داره → آپدیت کن
        if saved_message_id:
            success = edit_media_group(bot_token, chat_id, saved_message_id, img1_bytes, img2_bytes, caption)
            if success:
                logger.info(f"✅ پیام {saved_message_id} آپدیت شد")
                return True
            else:
                logger.warning("⚠️ آپدیت ناموفق، پیام جدید ارسال می‌شود")
                saved_message_id = None

        # ارسال پیام جدید
        if img2_bytes:
            new_message_id = send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption)
            if new_message_id:
                save_gist_data(new_message_id, today)
                pin_message(bot_token, chat_id, new_message_id)
                return True
            return False
        else:
            logger.warning("⚠️ نمودارها موجود نیست، فقط تصویر اول ارسال می‌شود")
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": ("market_report.png", io.BytesIO(img1_bytes), "image/png")}
            params = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            response = requests.post(url, files=files, data=params, timeout=60)
            if response.status_code == 200:
                result = response.json()
                new_message_id = result.get("result", {}).get("message_id")
                save_gist_data(new_message_id, today)
                pin_message(bot_token, chat_id, new_message_id)
            return response.status_code == 200

    except Exception as e:
        logger.error(f"❌ خطا در ارسال به تلگرام: {e}", exc_info=True)
        return False


# ═══════════════════════════════════════════════════════════
# توابع ارسال و ویرایش پیام
# ═══════════════════════════════════════════════════════════

def send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption):
    """ارسال دو عکس به صورت گروهی"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"
        files = {
            "photo1": ("market_treemap.png", io.BytesIO(img1_bytes), "image/png"),
            "photo2": ("market_charts.png", io.BytesIO(img2_bytes), "image/png"),
        }
        media = [
            {"type": "photo", "media": "attach://photo1", "caption": caption, "parse_mode": "HTML"},
            {"type": "photo", "media": "attach://photo2"},
        ]
        response = requests.post(url, files=files, data={"chat_id": chat_id, "media": json.dumps(media)}, timeout=60)
        if response.status_code == 200:
            result = response.json()
            messages = result.get("result", [])
            if messages:
                return messages[0].get("message_id")
        return None
    except Exception as e:
        logger.error(f"❌ خطا در ارسال Media Group: {e}", exc_info=True)
        return None


def edit_media_group(bot_token, chat_id, message_id, img1_bytes, img2_bytes, caption):
    """ویرایش پیام موجود"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/editMessageMedia"
        files = {"photo": ("market_treemap.png", io.BytesIO(img1_bytes), "image/png")}
        media = {
            "type": "photo",
            "media": "attach://photo",
            "caption": caption,
            "parse_mode": "HTML"
        }
        data = {
            "chat_id": chat_id,
            "message_id": message_id,
            "media": json.dumps(media)
        }
        response = requests.post(url, files=files, data=data, timeout=60)
        return response.status_code == 200
    except Exception as e:
        logger.error(f"❌ خطا در ویرایش پیام: {e}", exc_info=True)
        return False


def pin_message(bot_token, chat_id, message_id):
    """پین کردن پیام"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/pinChatMessage"
        data = {"chat_id": chat_id, "message_id": message_id, "disable_notification": True}
        requests.post(url, data=data, timeout=30)
        logger.info(f"📌 پیام {message_id} پین شد")
    except Exception as e:
        logger.error(f"❌ خطا در Pin کردن پیام: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════
# توابع هشدار
# ═══════════════════════════════════════════════════════════

def check_and_send_alerts(bot_token, chat_id, data, dollar_prices, gold_price, yesterday_close, gold_yesterday):
    """چک کردن شرایط هشدار - بدون ذخیره در Gist"""
    
    prev = get_previous_state_from_sheet()
    
    df_funds = data["Fund_df"]
    total_value = df_funds["value"].sum()

    if total_value > 0:
        current_fund_change = (df_funds["close_price_change_percent"] * df_funds["value"]).sum() / total_value
        current_ekhtelaf = (df_funds["ekhtelaf_sarane"] * df_funds["value"]).sum() / total_value
    else:
        current_fund_change = 0
        current_ekhtelaf = 0

    current_dollar_price = dollar_prices["last_trade"]
    current_dollar_change = ((current_dollar_price - yesterday_close) / yesterday_close * 100) if yesterday_close else 0
    
    if "شمش-طلا" in data["dfp"].index:
        current_shams_price = data["dfp"].loc["شمش-طلا", "close_price"]
        current_shams_change = data["dfp"].loc["شمش-طلا", "close_price_change_percent"]
    else:
        current_shams_price = 0
        current_shams_change = 0

    # ═══════════════════════════════════════════════════════
    # هشدار تغییر سریع (±0.5% نسبت به 5 دقیقه قبل)
    # ═══════════════════════════════════════════════════════
    
    # هشدار دلار - تغییر درصد
    if prev["dollar_change"] is not None:
        dollar_diff = abs(current_dollar_change - prev["dollar_change"])
        if dollar_diff >= ALERT_THRESHOLD_PERCENT:
            send_alert_dollar_fast(bot_token, chat_id, current_dollar_price, current_dollar_change, dollar_diff)
    
    # هشدار شمش - تغییر درصد
    if prev["shams_change"] is not None and current_shams_price > 0:
        shams_diff = abs(current_shams_change - prev["shams_change"])
        if shams_diff >= ALERT_THRESHOLD_PERCENT:
            send_alert_shams_fast(bot_token, chat_id, current_shams_price, current_shams_change, shams_diff)

    # هشدار اونس - تغییر سریع
    if prev["gold_price"] is not None and gold_yesterday and prev["gold_price"] > 0:
        prev_gold_change = ((prev["gold_price"] - gold_yesterday) / gold_yesterday * 100)
        current_gold_change = ((gold_price - gold_yesterday) / gold_yesterday * 100)
        gold_diff = abs(current_gold_change - prev_gold_change)
        if gold_diff >= ALERT_THRESHOLD_PERCENT:
            send_alert_gold_fast(bot_token, chat_id, gold_price, current_gold_change, gold_diff)

    # هشدار صندوق‌ها - تغییر سریع
    if prev["fund_change"] is not None:
        fund_diff = abs(current_fund_change - prev["fund_change"])
        if fund_diff >= ALERT_THRESHOLD_PERCENT:
            send_alert_funds_fast(bot_token, chat_id, current_fund_change, current_ekhtelaf, df_funds["pol_hagigi"].sum())

    # ═══════════════════════════════════════════════════════
    # هشدار عبور از قیمت مشخص (فقط وقتی از خط عبور کنه)
    # ═══════════════════════════════════════════════════════
    
    # هشدار دلار - عبور از آستانه بالا
    if prev["dollar_price"] is not None:
        # حالت ۱: از پایین به بالا (عبور صعودی)
        if prev["dollar_price"] < DOLLAR_ALERT_PRICE_HIGH <= current_dollar_price:
            send_alert_dollar_threshold(bot_token, chat_id, current_dollar_price, DOLLAR_ALERT_PRICE_HIGH, above=True)
        # حالت ۲: از بالا به پایین (عبور نزولی)
        elif prev["dollar_price"] >= DOLLAR_ALERT_PRICE_HIGH > current_dollar_price:
            send_alert_dollar_threshold(bot_token, chat_id, current_dollar_price, DOLLAR_ALERT_PRICE_HIGH, above=False)
        
        # هشدار دلار - عبور از آستانه پایین
        if prev["dollar_price"] >= DOLLAR_ALERT_PRICE_LOW > current_dollar_price:
            send_alert_dollar_threshold(bot_token, chat_id, current_dollar_price, DOLLAR_ALERT_PRICE_LOW, above=False)
        elif prev["dollar_price"] < DOLLAR_ALERT_PRICE_LOW <= current_dollar_price:
            send_alert_dollar_threshold(bot_token, chat_id, current_dollar_price, DOLLAR_ALERT_PRICE_LOW, above=True)
    
    # هشدار شمش - عبور از آستانه بالا
    if prev["shams_price"] is not None and current_shams_price > 0:
        if prev["shams_price"] < SHAMS_ALERT_PRICE_HIGH <= current_shams_price:
            send_alert_shams_threshold(bot_token, chat_id, current_shams_price, SHAMS_ALERT_PRICE_HIGH, above=True)
        elif prev["shams_price"] >= SHAMS_ALERT_PRICE_HIGH > current_shams_price:
            send_alert_shams_threshold(bot_token, chat_id, current_shams_price, SHAMS_ALERT_PRICE_HIGH, above=False)
        
        # هشدار شمش - عبور از آستانه پایین
        if prev["shams_price"] >= SHAMS_ALERT_PRICE_LOW > current_shams_price:
            send_alert_shams_threshold(bot_token, chat_id, current_shams_price, SHAMS_ALERT_PRICE_LOW, above=False)
        elif prev["shams_price"] < SHAMS_ALERT_PRICE_LOW <= current_shams_price:
            send_alert_shams_threshold(bot_token, chat_id, current_shams_price, SHAMS_ALERT_PRICE_LOW, above=True)
    
    # هشدار اونس - عبور از آستانه بالا
    if prev["gold_price"] is not None and gold_price > 0:
        if prev["gold_price"] < GOLD_ALERT_PRICE_HIGH <= gold_price:
            send_alert_gold_threshold(bot_token, chat_id, gold_price, GOLD_ALERT_PRICE_HIGH, above=True)
        elif prev["gold_price"] >= GOLD_ALERT_PRICE_HIGH > gold_price:
            send_alert_gold_threshold(bot_token, chat_id, gold_price, GOLD_ALERT_PRICE_HIGH, above=False)
        
        # هشدار اونس - عبور از آستانه پایین
        if prev["gold_price"] >= GOLD_ALERT_PRICE_LOW > gold_price:
            send_alert_gold_threshold(bot_token, chat_id, gold_price, GOLD_ALERT_PRICE_LOW, above=False)
        elif prev["gold_price"] < GOLD_ALERT_PRICE_LOW <= gold_price:
            send_alert_gold_threshold(bot_token, chat_id, gold_price, GOLD_ALERT_PRICE_LOW, above=True)

    # ═══════════════════════════════════════════════════════
    # هشدارهای اختلاف سرانه (تغییر شدید ±10 واحد)
    # ═══════════════════════════════════════════════════════
    
    if prev["ekhtelaf_sarane"] is not None:
        ekhtelaf_diff = current_ekhtelaf - prev["ekhtelaf_sarane"]
        
        # صعودی (به سمت مثبت)
        if ekhtelaf_diff >= EKHTELAF_THRESHOLD:
            send_alert_ekhtelaf_movement(
                bot_token, chat_id, 
                prev["ekhtelaf_sarane"], current_ekhtelaf, 
                df_funds["pol_hagigi"].sum(), current_fund_change,
                ascending=True
            )
        
        # نزولی (به سمت منفی)
        elif ekhtelaf_diff <= -EKHTELAF_THRESHOLD:
            send_alert_ekhtelaf_movement(
                bot_token, chat_id, 
                prev["ekhtelaf_sarane"], current_ekhtelaf, 
                df_funds["pol_hagigi"].sum(), current_fund_change,
                ascending=False
            )


# ═══════════════════════════════════════════════════════════
# پیام‌های هشدار - تغییر سریع
# ═══════════════════════════════════════════════════════════

def send_alert_dollar_fast(bot_token, chat_id, price, change_percent, diff):
    caption = f"""
🚨 <b>دلار | تغییر سریع</b>

💵 قیمت: <b>{price:,} تومان</b>
📈 تغییر امروز: <b>{change_percent:+.2f}%</b>
⚡ تغییر ۵ دقیقه: <b>{diff:+.2f}%</b>

🔗 @Gold_Iran_Market
"""
    send_alert_message(bot_token, chat_id, caption)


def send_alert_shams_fast(bot_token, chat_id, price, change_percent, diff):
    caption = f"""
🚨 <b>شمش طلا | تغییر سریع</b>

✨ قیمت: <b>{price:,} ریال</b>
📈 تغییر امروز: <b>{change_percent:+.2f}%</b>
⚡ تغییر ۵ دقیقه: <b>{diff:+.2f}%</b>

🔗 @Gold_Iran_Market
"""
    send_alert_message(bot_token, chat_id, caption)


def send_alert_gold_fast(bot_token, chat_id, price, change, diff):
    caption = f"""
🚨 <b>اونس طلا | تغییر سریع</b>

🔆 قیمت: <b>${price:,.2f}</b>
📈 تغییر امروز: <b>{change:+.2f}%</b>
⚡ تغییر ۵ دقیقه: <b>{diff:+.2f}%</b>

🔗 @Gold_Iran_Market
"""
    send_alert_message(bot_token, chat_id, caption)


def send_alert_funds_fast(bot_token, chat_id, avg_change, ekhtelaf, pol_hagigi):
    caption = f"""
🚨 <b>صندوق‌های طلا | تغییر سریع</b>

📈 درصد آخرین: <b>{avg_change:+.2f}%</b>
📊 اختلاف سرانه: <b>{ekhtelaf:+.2f}</b>
💸 پول حقیقی: <b>{pol_hagigi:+,.0f}</b> میلیارد تومان

🔗 @Gold_Iran_Market
"""
    send_alert_message(bot_token, chat_id, caption)


# ═══════════════════════════════════════════════════════════
# پیام‌های هشدار - عبور از آستانه قیمتی
# ═══════════════════════════════════════════════════════════

def send_alert_dollar_threshold(bot_token, chat_id, price, threshold, above=True):
    if above:
        emoji = "📈"
        text = f"دلار از {threshold:,} تومان عبور کرد"
    else:
        emoji = "📉"
        text = f"دلار از {threshold:,} تومان پایین‌تر شد"

    caption = f"""
{emoji} <b>{text}</b>

💵 قیمت فعلی: <b>{price:,} تومان</b>

🔗 @Gold_Iran_Market
"""
    send_alert_message(bot_token, chat_id, caption)


def send_alert_shams_threshold(bot_token, chat_id, price, threshold, above=True):
    if above:
        emoji = "📈"
        text = f"شمش طلا از {threshold:,} ریال عبور کرد"
    else:
        emoji = "📉"
        text = f"شمش طلا از {threshold:,} ریال پایین‌تر شد"

    caption = f"""
{emoji} <b>{text}</b>

✨ قیمت فعلی: <b>{price:,} ریال</b>

🔗 @Gold_Iran_Market
"""
    send_alert_message(bot_token, chat_id, caption)


def send_alert_gold_threshold(bot_token, chat_id, price, threshold, above=True):
    if above:
        emoji = "📈"
        text = f"اونس طلا از ${threshold:,.2f} عبور کرد"
    else:
        emoji = "📉"
        text = f"اونس طلا از ${threshold:,.2f} پایین‌تر شد"

    caption = f"""
{emoji} <b>{text}</b>

🔆 قیمت فعلی: <b>${price:,.2f}</b>

🔗 @Gold_Iran_Market
"""
    send_alert_message(bot_token, chat_id, caption)


# ═══════════════════════════════════════════════════════════
# پیام‌های هشدار - اختلاف سرانه
# ═══════════════════════════════════════════════════════════

def send_alert_ekhtelaf_sign(bot_token, chat_id, ekhtelaf, pol_hagigi, avg_change, positive=True):
    if positive:
        emoji = "🟢"
        text = "مثبت شد"
    else:
        emoji = "🔴"
        text = "منفی شد"

    caption = f"""
{emoji} <b>اختلاف سرانه {text}</b>

📊 اختلاف سرانه: <b>{ekhtelaf:+.2f}</b>
💸 پول حقیقی: <b>{pol_hagigi:+,.0f}</b> میلیارد تومان
📈 درصد آخرین: <b>{avg_change:+.2f}%</b>

🔗 @Gold_Iran_Market
"""
    send_alert_message(bot_token, chat_id, caption)


def send_alert_ekhtelaf_20(bot_token, chat_id, ekhtelaf, pol_hagigi, avg_change, above=True, threshold=20):
    if above:
        emoji = "🚀"
        if threshold > 0:
            text = f"بالای +{abs(threshold)} میلیون تومان"
        else:
            text = f"بالاتر از {threshold} میلیون تومان"
    else:
        emoji = "⚠️"
        if threshold > 0:
            text = f"پایین‌تر از +{abs(threshold)} میلیون تومان"
        else:
            text = f"زیر {threshold} میلیون تومان"

    caption = f"""
{emoji} <b>اختلاف سرانه {text}</b>

📊 اختلاف سرانه: <b>{ekhtelaf:+.2f}</b>
💸 پول حقیقی: <b>{pol_hagigi:+,.0f}</b>  میلیارد تومان
📈 میانگین تغییر قیمت وزنی: <b>{avg_change:+.2f}%</b>

🔗 @Gold_Iran_Market
"""
    send_alert_message(bot_token, chat_id, caption)


def send_alert_message(bot_token, chat_id, caption):
    """ارسال پیام هشدار"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {"chat_id": chat_id, "text": caption, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=30)
        logger.info("🚨 هشدار ارسال شد")
    except Exception as e:
        logger.error(f"❌ خطا در ارسال هشدار: {e}", exc_info=True)


# ═══════════════════════════════════════════════════════════
# تابع ساخت تصویر
# ═══════════════════════════════════════════════════════════

def create_combined_image(Fund_df, last_trade, Gold, Gold_yesterday, dfp, yesterday_close):
    tehran_tz = pytz.timezone("Asia/Tehran")
    now_jalali = JalaliDateTime.now(tehran_tz)
    date_time_str = now_jalali.strftime("%Y/%m/%d - %H:%M")

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.02,
        specs=[[{"type": "treemap"}], [{"type": "table"}]],
    )

    df_sorted = Fund_df.copy()
    df_sorted["color_value"] = df_sorted["close_price_change_percent"]
    df_sorted = df_sorted.sort_values("value", ascending=False)

    colorscale = [
        [0.0, "#E57373"], [0.1, "#D85C5C"], [0.2, "#C94444"],
        [0.3, "#A52A2A"], [0.4, "#6B1A1A"], [0.5, "#2C2C2C"],
        [0.6, "#1B5E20"], [0.7, "#2E7D32"], [0.8, "#43A047"],
        [0.9, "#5CB860"], [1.0, "#66BB6A"],
    ]

    try:
        ImageFont.truetype("assets/fonts/Vazirmatn-Medium.ttf", 40)
        treemap_font_family = "Vazirmatn-Medium, sans-serif"
    except:
        treemap_font_family = "sans-serif"

    fig.add_trace(
        go.Treemap(
            labels=df_sorted.index,
            parents=[""] * len(df_sorted),
            values=df_sorted["value"],
            text=[f"<b>{i}</b>" for i in df_sorted.index],
            textinfo="text",
            textposition="middle center",
            textfont=dict(size=28, color="white", family=treemap_font_family),
            hoverinfo="skip",
            marker=dict(
                colors=df_sorted["color_value"],
                colorscale=colorscale,
                cmid=0, cmin=-10, cmax=10,
                line=dict(width=3, color="#1A1A1A"),
            ),
            pathbar=dict(visible=False),
        ),
        row=1, col=1,
    )

    top_10 = df_sorted.head(10)
    table_header = ["نماد","قیمت","NAV","تغییر %","حباب %","اختلاف سرانه","پول حقیقی","ارزش معاملات"]
    table_cells = [
        top_10.index.tolist(),
        [f"{x:,.0f}" for x in top_10["close_price"]],
        [f"{x:,.0f}" for x in top_10["NAV"]],
        [f"{x:+.2f}%" for x in top_10["close_price_change_percent"]],
        [f"{x:+.2f}%" for x in top_10["nominal_bubble"]],
        [f"{x:+.2f}" for x in top_10["ekhtelaf_sarane"]],
        [f"{x:+,.0f}" for x in top_10["pol_hagigi"]],
        [f"{x:,.0f}" for x in top_10["value"]],
    ]

    def col_color(v):
        try:
            x = float(v.replace("%", "").replace("+", "").replace(",", ""))
            return "#1B5E20" if x > 0 else "#A52A2A" if x < 0 else "#2C2C2C"
        except:
            return "#1C2733"

    cell_colors = [
        ["#1C2733"] * 10, ["#1C2733"] * 10, ["#1C2733"] * 10,
        [col_color(x) for x in table_cells[3]],
        [col_color(x) for x in table_cells[4]],
        [col_color(x) for x in table_cells[5]],
        [col_color(x) for x in table_cells[6]],
        ["#1C2733"] * 10,
    ]

    fig.add_trace(
        go.Table(
            header=dict(
                values=[f"<b>{h}</b>" for h in table_header],
                fill_color="#242F3D", align="center",
                font=dict(color="white", size=20, family=treemap_font_family),
                height=38,
            ),
            cells=dict(
                values=table_cells,
                fill_color=cell_colors, align="center",
                font=dict(color="white", size=18, family=treemap_font_family),
                height=36,
            ),
        ),
        row=2, col=1,
    )

    fig.update_layout(
        paper_bgcolor="#000000", plot_bgcolor="#000000",
        height=1350, width=1350,
        margin=dict(t=140, l=20, r=20, b=20),
        title=dict(
            text="<b>نقشه بازار صندوق‌های طلا</b>",
            font=dict(size=35, color="#FFD700"),
            x=0.5, y=0.96, xanchor="center", yanchor="top",
        ),
        showlegend=False,
    )

    img_bytes = fig.to_image(format="png", width=1350, height=1350, scale=2)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    try:
        font_date = ImageFont.truetype("assets/fonts/Vazirmatn-Bold.ttf", 64)
        font_desc = ImageFont.truetype("assets/fonts/Vazirmatn-Medium.ttf", 50)
    except:
        font_date = font_desc = ImageFont.load_default()

    draw.text((60, 35), date_time_str, font=font_date, fill="#FFFFFF")
    draw.text((60, 110), "اندازه: ارزش معاملات", font=font_desc, fill="#FFFFFF")

    try:
        wfont = ImageFont.truetype("assets/fonts/Vazirmatn-Regular.ttf", 70)
    except:
        wfont = ImageFont.load_default()

    wtext = "Gold_Iran_Market"
    bbox = draw.textbbox((0,0), wtext, font=wfont)
    w, h = bbox[2] - bbox[0] + 80, bbox[3] - bbox[1] + 80
    txt_img = Image.new("RGBA", (w, h), (0,0,0,0))
    ImageDraw.Draw(txt_img).text((40, 40), wtext, font=wfont, fill=(255,255,255,100))
    rotated = txt_img.rotate(45, expand=True)
    img.paste(rotated, ((img.width - rotated.width)//2, (img.height - rotated.height)//2), rotated)

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True, quality=92)
    output.seek(0)
    return output.getvalue()


# ═══════════════════════════════════════════════════════════
# تابع ساخت کپشن
# ═══════════════════════════════════════════════════════════

def create_simple_caption(data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time):
    tehran_tz = pytz.timezone("Asia/Tehran")
    now = JalaliDateTime.now(tehran_tz)
    current_time = now.strftime("%Y/%m/%d - %H:%M")

    df_funds = data["Fund_df"]
    total_value = df_funds["value"].sum()
    total_pol = df_funds["pol_hagigi"].sum()

    if total_value > 0:
        avg_price_weighted = (df_funds["close_price"] * df_funds["value"]).sum() / total_value
        avg_change_percent_weighted = (df_funds["close_price_change_percent"] * df_funds["value"]).sum() / total_value
        avg_bubble_weighted = (df_funds["nominal_bubble"] * df_funds["value"]).sum() / total_value
    else:
        avg_price_weighted = avg_change_percent_weighted = avg_bubble_weighted = 0

    dollar_change = ((dollar_prices["last_trade"] - yesterday_close) / yesterday_close * 100) if yesterday_close else 0
    gold_change = ((gold_price - gold_yesterday) / gold_yesterday * 100) if gold_yesterday else 0

    shams = data["dfp"].loc["شمش-طلا"]
    gold_24 = data["dfp"].loc["طلا-گرم-24-عیار"]
    gold_18 = data["dfp"].loc["طلا-گرم-18-عیار"]
    sekeh = data["dfp"].loc["سکه-امامی-طرح-جدید"]

    def calc_diffs(row, d_cur, g_cur):
        d_calc = row.get("pricing_dollar", 0)
        o_calc = row.get("pricing_Gold", 0)
        return d_calc, d_calc - d_cur, o_calc, o_calc - g_cur

    d_shams, diff_shams, o_shams, diff_o_shams = calc_diffs(shams, dollar_prices["last_trade"], gold_price)
    d_24, diff_24, _, _ = calc_diffs(gold_24, dollar_prices["last_trade"], gold_price)
    d_18, diff_18, _, _ = calc_diffs(gold_18, dollar_prices["last_trade"], gold_price)
    d_sekeh, diff_sekeh, _, _ = calc_diffs(sekeh, dollar_prices["last_trade"], gold_price)

    gold_24_price = gold_24["close_price"] / 10
    gold_18_price = gold_18["close_price"] / 10
    sekeh_price = sekeh["close_price"] / 10

    pol_to_value_ratio = (total_pol / total_value * 100) if total_value != 0 else 0

    caption = f"""
🔄 <b>آخرین آپدیت: {current_time}</b>

━━━━━━━━━━━━━━━━━━━━━━━━
<b>💵 دلار</b>
💰 آخرین معامله: <b>{dollar_prices['last_trade']:,} تومان</b> ({dollar_change:+.2f}%)
🟢 خرید: {dollar_prices['bid']:,} | 🔴 فروش: {dollar_prices['ask']:,}
━━━━━━━━━━━━━━━━━━━━━━━━
<b>🔆 اونس طلا </b>
💰 قیمت: <b>${gold_price:,.2f}</b> ({gold_change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━━━━━
<b>📊 آمار صندوق‌های طلا</b>
💰 ارزش معاملات: <b>{total_value:,.0f}</b> میلیارد تومان
💸 ورود پول حقیقی: <b>{total_pol:+,.0f}</b> میلیارد تومان
📊 پول حقیقی به ارزش معاملات: <b>{pol_to_value_ratio:+.0f}%</b>
📈 آخرین قیمت: <b>{avg_price_weighted:,.0f}</b> ({avg_change_percent_weighted:+.2f}%)
🎈 میانگین حباب: <b>{avg_bubble_weighted:+.2f}%</b>
━━━━━━━━━━━━━━━━━━━━━━━━
✨ <b>شمش طلا</b>
💰 قیمت: <b>{shams['close_price']:,}</b> ریال
📊 تغییر: {shams['close_price_change_percent']:+.2f}% | حباب: {shams['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_shams:,.0f} ({diff_shams:+,.0f})
🔆 اونس محاسباتی: ${o_shams:,.0f} ({diff_o_shams:+.0f})

🔸 <b>طلا ۲۴ عیار</b>
💰 قیمت: <b>{gold_24_price:,.0f}</b> تومان
📊 تغییر: {gold_24['close_price_change_percent']:+.2f}% | حباب: {gold_24['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_24:,.0f} ({diff_24:+,.0f})

🔸 <b>طلا ۱۸ عیار</b>
💰 قیمت: <b>{gold_18_price:,.0f}</b> تومان
📊 تغییر: {gold_18['close_price_change_percent']:+.2f}% | حباب: {gold_18['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_18:,.0f} ({diff_18:+,.0f})

🪙 <b>سکه امامی</b>
💰 قیمت: <b>{sekeh_price:,.0f}</b> تومان
📊 تغییر: {sekeh['close_price_change_percent']:+.2f}% | حباب: {sekeh['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_sekeh:,.0f} ({diff_sekeh:+,.0f})
━━━━━━━━━━━━━━━━━━━━━━━━
🔗 <a href='https://t.me/Gold_Iran_Market'>@Gold_Iran_Market</a>
"""
    return caption