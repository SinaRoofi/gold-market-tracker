# utils/alerts.py

import json
import logging
import requests
from datetime import datetime, timedelta
import pytz
from config import (
    DOLLAR_HIGH, DOLLAR_LOW,
    SHAMS_HIGH, SHAMS_LOW,
    GOLD_HIGH, GOLD_LOW,
    ALERT_THRESHOLD_PERCENT,
    EKHTELAF_THRESHOLD,
    BUBBLE_POSITIVE_THRESHOLD,
    BUBBLE_NEGATIVE_THRESHOLD,
    BUBBLE_SHARP_CHANGE_THRESHOLD,
    GIST_ID, GIST_TOKEN,
    ALERT_STATUS_FILE,
    ALERT_CHANNEL_HANDLE,
    REQUEST_TIMEOUT,
    TIMEZONE
)
from utils.sheets_storage import read_from_sheets

logger = logging.getLogger(__name__)
FUND_ALERTS_FILE = "fund_alerts.json"

# ✅ آستانه‌های هشدار پول حقیقی
POL_SHARP_CHANGE_THRESHOLD = 5.0  # تغییر شدید: 5 میلیارد تومان در 1 دقیقه

# ✅ کش محلی برای جلوگیری از reset در صورت خطای Gist
ALERT_STATUS_CACHE = None


# ════════════════════════════════════════════════════════════════
# مدیریت Gist
# ════════════════════════════════════════════════════════════════

def get_alert_status():
    """دریافت وضعیت هشدارها از Gist با fallback به کش محلی"""
    global ALERT_STATUS_CACHE

    try:
        if not GIST_ID or not GIST_TOKEN:
            logger.warning("GIST_ID یا GIST_TOKEN تنظیم نشده است")
            default = {
                "dollar": "normal",
                "shams": "normal",
                "gold": "normal",
                "bubble": "normal",
                "pol_hagigi": "normal"  # ✅ وضعیت پول حقیقی
            }
            return ALERT_STATUS_CACHE or default

        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

        if r.status_code == 200 and ALERT_STATUS_FILE in r.json()["files"]:
            status = json.loads(r.json()["files"][ALERT_STATUS_FILE]["content"])

            # ✅ اطمینان از وجود کلیدهای جدید
            if "bubble" not in status:
                status["bubble"] = "normal"
            if "pol_hagigi" not in status:
                status["pol_hagigi"] = "normal"

            ALERT_STATUS_CACHE = status
            return status

    except Exception as e:
        logger.error(f"خطا در خواندن alert_status: {e}")
        if ALERT_STATUS_CACHE:
            logger.info("استفاده از کش محلی")
            return ALERT_STATUS_CACHE

    default = {
        "dollar": "normal",
        "shams": "normal",
        "gold": "normal",
        "bubble": "normal",
        "pol_hagigi": "normal"
    }
    ALERT_STATUS_CACHE = default
    return default


def save_alert_status(status):
    """ذخیره وضعیت هشدارها در Gist"""
    global ALERT_STATUS_CACHE

    try:
        if not GIST_ID or not GIST_TOKEN:
            return

        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}

        response = requests.patch(url, headers=headers, json={
            "files": {ALERT_STATUS_FILE: {"content": json.dumps(status, ensure_ascii=False)}}
        }, timeout=REQUEST_TIMEOUT)

        if response.status_code == 200:
            ALERT_STATUS_CACHE = status

    except Exception as e:
        logger.error(f"خطا در ذخیره alert_status: {e}")


def get_fund_alerts():
    """دریافت تاریخچه هشدارهای صندوق‌ها"""
    try:
        if not GIST_ID or not GIST_TOKEN:
            return {}

        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

        if r.status_code == 200 and FUND_ALERTS_FILE in r.json()["files"]:
            return json.loads(r.json()["files"][FUND_ALERTS_FILE]["content"])

    except Exception as e:
        logger.error(f"خطا در خواندن fund_alerts: {e}")

    return {}


def save_fund_alerts(fund_alerts):
    """ذخیره تاریخچه هشدارهای صندوق‌ها"""
    try:
        if not GIST_ID or not GIST_TOKEN:
            return

        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}

        requests.patch(url, headers=headers, json={
            "files": {FUND_ALERTS_FILE: {"content": json.dumps(fund_alerts, ensure_ascii=False, indent=2)}}
        }, timeout=REQUEST_TIMEOUT)

    except Exception as e:
        logger.error(f"خطا در ذخیره fund_alerts: {e}")


# ════════════════════════════════════════════════════════════════
# پاک‌سازی داده‌های قدیمی
# ════════════════════════════════════════════════════════════════

def cleanup_old_alerts(alerts_dict, max_days=7):
    """پاک‌سازی بهینه‌شده داده‌های قدیمی‌تر از 7 روز"""
    if not alerts_dict:
        return {}

    try:
        tz = pytz.timezone(TIMEZONE)
        cutoff = (datetime.now(tz) - timedelta(days=max_days)).strftime("%Y-%m-%d")

        if all(d >= cutoff for d in alerts_dict.keys()):
            return alerts_dict

        cleaned = {d: items for d, items in alerts_dict.items() if d >= cutoff}
        removed = len(alerts_dict) - len(cleaned)

        if removed > 0:
            logger.info(f"{removed} روز قدیمی از تاریخچه پاک شد")

        return cleaned

    except Exception as e:
        logger.error(f"خطا در پاکسازی: {e}")
        return alerts_dict


# ════════════════════════════════════════════════════════════════
# دریافت وضعیت قبلی از Sheet
# ════════════════════════════════════════════════════════════════

def get_previous_state_from_sheet():
    """دریافت وضعیت قبلی با بررسی فاصله زمانی"""
    try:
        rows = read_from_sheets(limit=3)

        if len(rows) < 2:
            logger.warning("داده کافی برای مقایسه نیست")
            return {
                "dollar_price": None, 
                "shams_price": None, 
                "gold_price": None, 
                "ekhtelaf_sarane": None,
                "sarane_kharid": None,
                "bubble_weighted": None,
                "pol_hagigi": None  # ✅ پول حقیقی
            }

        prev_row = rows[-2]
        last_row = rows[-1]

        # بررسی فاصله زمانی
        try:
            prev_time = datetime.strptime(prev_row[0][:19], '%Y-%m-%d %H:%M:%S')
            last_time = datetime.strptime(last_row[0][:19], '%Y-%m-%d %H:%M:%S')
            time_diff = (last_time - prev_time).total_seconds() / 60

            if time_diff > 10:
                logger.warning(f"⚠️ فاصله زمانی غیرعادی: {time_diff:.1f} دقیقه")
            else:
                logger.debug(f"✓ فاصله زمانی: {time_diff:.1f} دقیقه")

        except Exception as e:
            logger.warning(f"نمی‌تونم فاصله زمانی رو بررسی کنم: {e}")

        return {
            "dollar_price": float(prev_row[2]) if len(prev_row) > 2 and prev_row[2] else None,
            "shams_price": float(prev_row[3]) if len(prev_row) > 3 and prev_row[3] else None,
            "gold_price": float(prev_row[1]) if len(prev_row) > 1 and prev_row[1] else None,
            "ekhtelaf_sarane": float(prev_row[11]) if len(prev_row) > 11 and prev_row[11] else None,
            "sarane_kharid": float(last_row[9]) if len(last_row) > 9 and last_row[9] else None,
            "bubble_weighted": float(prev_row[8]) if len(prev_row) > 8 and prev_row[8] else None,
            "pol_hagigi": float(prev_row[12]) if len(prev_row) > 12 and prev_row[12] else None,  # ✅ ستون 12
        }

    except Exception as e:
        logger.error(f"خطا در خواندن وضعیت قبلی: {e}")
        return {
            "dollar_price": None, 
            "shams_price": None, 
            "gold_price": None, 
            "ekhtelaf_sarane": None,
            "sarane_kharid": None,
            "bubble_weighted": None,
            "pol_hagigi": None
        }


# ════════════════════════════════════════════════════════════════
# تابع اصلی بررسی و ارسال هشدارها
# ════════════════════════════════════════════════════════════════

def check_and_send_alerts(bot_token, chat_id, data, dollar_prices, gold_price, yesterday_close, gold_yesterday, alert_channel_handle=None):
    """
    بررسی و ارسال همه هشدارها
    
    1️⃣ نوسان 5 دقیقه‌ای (دلار، شمش، طلا) - بدون Cooldown
    2️⃣ تغییر شدید اختلاف سرانه - بدون Cooldown
    3️⃣ هشدارهای حباب (وضعیت + تغییر شدید)
    4️⃣ ✅ هشدارهای پول حقیقی (وضعیت + تغییر شدید)
    5️⃣ هشدار صندوق‌های فعال - یک بار در روز
    6️⃣ هشدار کراس سرانه - یک بار در روز
    7️⃣ آستانه‌های قیمتی - با Cooldown
    """

    prev = get_previous_state_from_sheet()
    status = get_alert_status()

    current_dollar = dollar_prices.get("last_trade", 0)
    current_shams = data["dfp"].loc["شمش-طلا", "close_price"] if "شمش-طلا" in data["dfp"].index else 0
    current_gold = gold_price

    df_funds = data["Fund_df"]
    total_value = df_funds["value"].sum()
    current_ekhtelaf = (df_funds["ekhtelaf_sarane"] * df_funds["value"]).sum() / total_value if total_value > 0 else 0

    # محاسبه حباب وزنی فعلی
    current_bubble = (df_funds["nominal_bubble"] * df_funds["value"]).sum() / total_value if total_value > 0 else 0

    # ✅ محاسبه پول حقیقی وزنی فعلی
    current_pol = (df_funds["pol_hagigi"] * df_funds["value"]).sum() / total_value if total_value > 0 else 0

    changed = False
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # ───────────────────────────────────────────────────
    # 1️⃣ نوسان ۵ دقیقه‌ای (بدون Cooldown)
    # ───────────────────────────────────────────────────

    # دلار
    if prev["dollar_price"] and prev["dollar_price"] > 0:
        change = (current_dollar - prev["dollar_price"]) / prev["dollar_price"] * 100
        if abs(change) >= ALERT_THRESHOLD_PERCENT:
            send_price_alert(bot_token, chat_id, "دلار", current_dollar, change, "تومان")

    # شمش
    if prev["shams_price"] and prev["shams_price"] > 0:
        change = (current_shams - prev["shams_price"]) / prev["shams_price"] * 100
        if abs(change) >= ALERT_THRESHOLD_PERCENT:
            send_price_alert(bot_token, chat_id, "شمش طلا", current_shams, change, "ریال")

    # طلا
    if prev["gold_price"] and prev["gold_price"] > 0:
        change = (current_gold - prev["gold_price"]) / prev["gold_price"] * 100
        if abs(change) >= ALERT_THRESHOLD_PERCENT:
            send_price_alert(bot_token, chat_id, "اونس طلا", current_gold, change, "دلار", is_gold=True)

    # ───────────────────────────────────────────────────
    # 2️⃣ تغییر شدید اختلاف سرانه (بدون Cooldown)
    # ───────────────────────────────────────────────────
    if prev["ekhtelaf_sarane"] is not None:
        diff = current_ekhtelaf - prev["ekhtelaf_sarane"]
        if abs(diff) >= EKHTELAF_THRESHOLD:
            send_alert_ekhtelaf_fast(bot_token, chat_id, prev["ekhtelaf_sarane"], current_ekhtelaf, diff, df_funds["pol_hagigi"].sum())

    # ───────────────────────────────────────────────────
    # 3️⃣ هشدارهای حباب (وضعیت + تغییر شدید)
    # ───────────────────────────────────────────────────
    bubble_status_changed = check_bubble_alerts(
        bot_token, chat_id,
        current_bubble,
        prev["bubble_weighted"],
        status,
        tz, now
    )

    if bubble_status_changed:
        changed = True

    # ───────────────────────────────────────────────────
    # 4️⃣ ✅ هشدارهای پول حقیقی (وضعیت + تغییر شدید)
    # ───────────────────────────────────────────────────
    pol_status_changed = check_pol_alerts(
        bot_token, chat_id,
        current_pol,
        prev["pol_hagigi"],
        status,
        tz, now
    )

    if pol_status_changed:
        changed = True

    # ───────────────────────────────────────────────────
    # 5️⃣ هشدار صندوق فعال
    # ───────────────────────────────────────────────────
    check_active_funds_alert(bot_token, chat_id, df_funds, tz, now)

    # ───────────────────────────────────────────────────
    # 6️⃣ هشدار کراس سرانه
    # ───────────────────────────────────────────────────
    check_sarane_cross_alert(bot_token, chat_id, df_funds, tz, now)

    # ───────────────────────────────────────────────────
    # 7️⃣ آستانه‌های قیمتی (با Cooldown)
    # ───────────────────────────────────────────────────
    for asset, price, high, low, key in [
        ("دلار", current_dollar, DOLLAR_HIGH, DOLLAR_LOW, "dollar"),
        ("شمش طلا", current_shams, SHAMS_HIGH, SHAMS_LOW, "shams"),
        ("اونس طلا", current_gold, GOLD_HIGH, GOLD_LOW, "gold")
    ]:
        if price > high:
            if status[key] != "above":
                send_alert_threshold(asset, price, high, above=True, bot_token=bot_token, chat_id=chat_id)
                status[key] = "above"
                changed = True
        elif price < low:
            if status[key] != "below":
                send_alert_threshold(asset, price, low, above=False, bot_token=bot_token, chat_id=chat_id)
                status[key] = "below"
                changed = True
        else:
            if status[key] != "normal":
                status[key] = "normal"
                changed = True

    if changed:
        save_alert_status(status)


# ════════════════════════════════════════════════════════════════
# هشدارهای حباب
# ════════════════════════════════════════════════════════════════

def check_bubble_alerts(bot_token, chat_id, current_bubble, prev_bubble, status, tz, now):
    """
    بررسی و ارسال هشدارهای حباب
    
    1️⃣ تغییر وضعیت (مثبت/منفی/خنثی) - با Anti-spam
    2️⃣ تغییر شدید در 1 دقیقه - همیشه
    
    Returns:
        bool: True اگر وضعیت تغییر کرد
    """
    status_changed = False

    # ───────────────────────────────────────────────────
    # 1️⃣ هشدار تغییر وضعیت (با Anti-spam)
    # ───────────────────────────────────────────────────
    if current_bubble >= BUBBLE_POSITIVE_THRESHOLD:
        if status["bubble"] != "positive":
            send_bubble_state_alert(bot_token, chat_id, current_bubble, "positive", tz, now)
            status["bubble"] = "positive"
            status_changed = True
            logger.info(f"🟢 حباب به حالت مثبت تغییر کرد: {current_bubble:+.2f}%")

    elif current_bubble <= BUBBLE_NEGATIVE_THRESHOLD:
        if status["bubble"] != "negative":
            send_bubble_state_alert(bot_token, chat_id, current_bubble, "negative", tz, now)
            status["bubble"] = "negative"
            status_changed = True
            logger.info(f"🔴 حباب به حالت منفی تغییر کرد: {current_bubble:+.2f}%")

    else:
        if status["bubble"] != "normal":
            status["bubble"] = "normal"
            status_changed = True
            logger.info(f"⚪ حباب به حالت خنثی برگشت: {current_bubble:+.2f}%")

    # ───────────────────────────────────────────────────
    # 2️⃣ هشدار تغییر شدید در 1 دقیقه (بدون Cooldown)
    # ───────────────────────────────────────────────────
    if prev_bubble is not None:
        bubble_change = current_bubble - prev_bubble

        if abs(bubble_change) >= BUBBLE_SHARP_CHANGE_THRESHOLD:
            send_bubble_sharp_change_alert(
                bot_token, chat_id, 
                prev_bubble, current_bubble, 
                bubble_change, tz, now
            )

    return status_changed


def send_bubble_state_alert(bot_token, chat_id, bubble_value, state, tz, now):
    """ارسال هشدار تغییر وضعیت حباب"""
    if state == "positive":
        direction = "مثبت"
        dir_emoji = "🟢"
        description = f"حباب به بالای {BUBBLE_POSITIVE_THRESHOLD:+.1f}% رسید"
    else:
        direction = "منفی"
        dir_emoji = "🔴"
        description = f"حباب به زیر {BUBBLE_NEGATIVE_THRESHOLD:+.1f}% رسید"

    main_text = f"""
🎈 هشدار حباب {dir_emoji}

{description}
💹 حباب فعلی: {bubble_value:+.2f}%
📊 وضعیت: {direction}
""".strip()

    footer = f"\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"

    send_alert_message(bot_token, chat_id, caption)


def send_bubble_sharp_change_alert(bot_token, chat_id, prev_value, curr_value, change, tz, now):
    """ارسال هشدار تغییر شدید حباب"""
    direction = "افزایش" if change > 0 else "کاهش"
    dir_emoji = "📈" if change > 0 else "📉"
    change_text = f"{change:+.2f}%".replace("+-", "−")

    main_text = f"""
🚨 تغییر شدید حباب {dir_emoji}

⏱ {direction} در 1 دقیقه: {change_text}
🔴 قبلی: {prev_value:+.2f}%
🟢 فعلی: {curr_value:+.2f}%
""".strip()

    footer = f"\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"

    send_alert_message(bot_token, chat_id, caption)


# ════════════════════════════════════════════════════════════════
# ✅ هشدارهای پول حقیقی (جدید)
# ════════════════════════════════════════════════════════════════

def check_pol_alerts(bot_token, chat_id, current_pol, prev_pol, status, tz, now):
    """
    بررسی و ارسال هشدارهای پول حقیقی
    
    1️⃣ تغییر وضعیت (مثبت/منفی/خنثی) - با Anti-spam
    2️⃣ تغییر شدید در 1 دقیقه - همیشه
    
    Returns:
        bool: True اگر وضعیت تغییر کرد
    """
    status_changed = False

    # ───────────────────────────────────────────────────
    # 1️⃣ هشدار کراس صفر (با Anti-spam)
    # ───────────────────────────────────────────────────
    if current_pol > 0:
        # پول حقیقی مثبت شد (ورود پول)
        if status["pol_hagigi"] != "positive":
            send_pol_state_alert(bot_token, chat_id, current_pol, "positive", tz, now)
            status["pol_hagigi"] = "positive"
            status_changed = True
            logger.info(f"🟢 پول حقیقی به حالت مثبت تغییر کرد: {current_pol:+.2f} م.ت")

    elif current_pol < 0:
        # پول حقیقی منفی شد (خروج پول)
        if status["pol_hagigi"] != "negative":
            send_pol_state_alert(bot_token, chat_id, current_pol, "negative", tz, now)
            status["pol_hagigi"] = "negative"
            status_changed = True
            logger.info(f"🔴 پول حقیقی به حالت منفی تغییر کرد: {current_pol:+.2f} م.ت")

    else:
        # پول حقیقی صفر (خنثی)
        if status["pol_hagigi"] != "normal":
            status["pol_hagigi"] = "normal"
            status_changed = True
            logger.info(f"⚪ پول حقیقی در حالت خنثی است: {current_pol:.2f} م.ت")

    # ───────────────────────────────────────────────────
    # 2️⃣ هشدار تغییر شدید در 1 دقیقه (بدون Cooldown)
    # ───────────────────────────────────────────────────
    if prev_pol is not None:
        pol_change = current_pol - prev_pol

        if abs(pol_change) >= POL_SHARP_CHANGE_THRESHOLD:
            send_pol_sharp_change_alert(
                bot_token, chat_id, 
                prev_pol, current_pol, 
                pol_change, tz, now
            )

    return status_changed


def send_pol_state_alert(bot_token, chat_id, pol_value, state, tz, now):
    """ارسال هشدار تغییر وضعیت پول حقیقی"""
    if state == "positive":
        direction = "مثبت"
        dir_emoji = "🟢"
        description = "ورود پول حقیقی به صندوق‌های طلا"
    else:  # negative
        direction = "منفی"
        dir_emoji = "🔴"
        description = "خروج پول حقیقی از صندوق‌های طلا"

    main_text = f"""
💸 هشدار پول حقیقی {dir_emoji}

{description}
💰 پول حقیقی: {pol_value:+.2f} میلیارد تومان
📊 وضعیت: {direction}
""".strip()

    footer = f"\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"

    send_alert_message(bot_token, chat_id, caption)


def send_pol_sharp_change_alert(bot_token, chat_id, prev_value, curr_value, change, tz, now):
    """ارسال هشدار تغییر شدید پول حقیقی"""
    direction = "ورود" if change > 0 else "خروج"
    dir_emoji = "📈" if change > 0 else "📉"
    change_text = f"{abs(change):.2f}"

    main_text = f"""
🚨 تغییر شدید پول حقیقی {dir_emoji}

⏱ {direction} در 1 دقیقه: {change_text} میلیارد تومان
🔴 قبلی: {prev_value:+.2f} م.ت
🟢 فعلی: {curr_value:+.2f} م.ت
""".strip()

    footer = f"\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"

    send_alert_message(bot_token, chat_id, caption)


# ════════════════════════════════════════════════════════════════
# هشدار صندوق‌های فعال
# ════════════════════════════════════════════════════════════════

def check_active_funds_alert(bot_token, chat_id, df_funds, tz, now):
    """بررسی و ارسال هشدار صندوق‌های فعال (فقط یک بار در روز)"""
    try:
        latest_row = read_from_sheets(limit=1)

        if not latest_row:
            logger.warning("هیچ داده‌ای از شیت دریافت نشد")
            return

        latest_row = latest_row[-1]
        sarane_kol = float(latest_row[9]) if len(latest_row) > 9 and latest_row[9] else 0

        active_funds = df_funds[
            (df_funds["value_to_avg_ratio"] >= 150) &
            (df_funds["pol_to_value_ratio"] >= 0.3) &
            (df_funds["ekhtelaf_sarane"] > 0) &
            (df_funds["sarane_kharid"] >= sarane_kol)
        ].copy()

        if active_funds.empty:
            logger.debug("هیچ صندوق فعالی با شرایط سخت خرید پیدا نشد")
            return

        active_funds = active_funds.sort_values("value", ascending=False)
        active_funds["sarane_kharid_diff"] = active_funds["sarane_kharid"] - sarane_kol

        fund_alerts = get_fund_alerts()
        fund_alerts = cleanup_old_alerts(fund_alerts)

        today = now.strftime("%Y-%m-%d")
        today_list = fund_alerts.get(today, [])
        already_sent = {item["symbol"] for item in today_list}
        new_symbols = [s for s in active_funds.index if s not in already_sent]

        if not new_symbols:
            logger.debug("همه صندوق‌های فعال امروز قبلاً هشدار دادن")
            return

        # ذخیره در تاریخچه
        for sym in new_symbols:
            today_list.append({"symbol": sym, "alert_type": "هشدار سخت خرید"})
        fund_alerts[today] = today_list
        save_fund_alerts(fund_alerts)

        logger.info(f"هشدار سخت خرید: {len(new_symbols)} صندوق جدید → {', '.join(new_symbols)}")

        # ساخت متن هشدار
        funds_text = ""
        for symbol, row in active_funds.loc[new_symbols].iterrows():
            value_str = f"{row['value']:.0f} م.ت ({row['value_to_avg_ratio']:.0f}%)"
            pol_str = f"{row['pol_hagigi']:+.0f} م.ت ({row['pol_to_value_ratio']*100:+.1f}%)"
            sarane_str = f"{row['sarane_kharid']:.0f}M (+{row['sarane_kharid_diff']:.0f}M)"
            ekhtelaf_str = f"{row['ekhtelaf_sarane']:+.0f}M"

            funds_text += f"""
📌 {symbol}
💰 ارزش معاملات: {value_str}
💸 ورود پول حقیقی: {pol_str}
🟢 سرانه خرید: {sarane_str}
📊 اختلاف سرانه: {ekhtelaf_str}
🎈 حباب: {row['nominal_bubble']:+.1f}%

"""

        main_text = f"🚨 هشدار سخت خرید\n\n{funds_text}".strip()
        footer = f"\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {ALERT_CHANNEL_HANDLE}"
        caption = f"{main_text}\n{footer}"

        send_alert_message(bot_token, chat_id, caption)

    except Exception as e:
        logger.error(f"خطا در بررسی صندوق‌های فعال: {e}")

# ════════════════════════════════════════════════════════════════
# هشدار کراس سرانه
# ════════════════════════════════════════════════════════════════

def check_sarane_cross_alert(bot_token, chat_id, df_funds, tz, now):
    """بررسی و ارسال هشدار کراس سرانه خرید و فروش (فقط یک بار در روز)"""
    try:
        # 🟢 کراس مثبت: سرانه خرید > سرانه فروش
        positive_cross = df_funds[
            (df_funds["sarane_kharid"] > df_funds["sarane_forosh"])
        ].copy()

        # 🔴 کراس منفی: سرانه فروش > سرانه خرید
        negative_cross = df_funds[
            (df_funds["sarane_forosh"] > df_funds["sarane_kharid"])
        ].copy()

        fund_alerts = get_fund_alerts()
        fund_alerts = cleanup_old_alerts(fund_alerts)

        today = now.strftime("%Y-%m-%d")
        today_list = fund_alerts.get(today, [])

        already_sent_positive = {item["symbol"] for item in today_list if item.get("alert_type") == "کراس مثبت"}
        already_sent_negative = {item["symbol"] for item in today_list if item.get("alert_type") == "کراس منفی"}

        new_positive = [s for s in positive_cross.index if s not in already_sent_positive]
        new_negative = [s for s in negative_cross.index if s not in already_sent_negative]

        # ارسال هشدار کراس مثبت
        if new_positive:
            positive_cross = positive_cross.loc[new_positive].sort_values("value", ascending=False)

            for sym in new_positive:
                today_list.append({"symbol": sym, "alert_type": "کراس مثبت"})

            logger.info(f"🟢 کراس مثبت: {len(new_positive)} صندوق → {', '.join(new_positive)}")

            funds_text = ""
            for symbol, row in positive_cross.iterrows():
                pol_ratio = (row["pol_hagigi"] / row["value"] * 100) if row["value"] > 0 else 0
                funds_text += f"""
📌 {symbol}
💹 تغییر قیمت: {row["close_price_change_percent"]:+.1f}%
🎈 حباب: {row["nominal_bubble"]:+.1f}%
🟢 سرانه خرید: {row["sarane_kharid"]:,.0f}M
🔴 سرانه فروش: {row["sarane_forosh"]:,.0f}M
💰 ارزش معاملات: {row["value"]:.0f} م.ت ({row["value_to_avg_ratio"]*100:.0f}%)
💸 پول حقیقی: {row["pol_hagigi"]:+.1f} م.ت ({pol_ratio:+.1f}%)

"""

            main_text = f"🟢 هشدار کراس مثبت سرانه\n\n{funds_text}".strip()
            footer = f"\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {ALERT_CHANNEL_HANDLE}"
            caption = f"{main_text}\n{footer}"

            send_alert_message(bot_token, chat_id, caption)

        # ارسال هشدار کراس منفی
        if new_negative:
            negative_cross = negative_cross.loc[new_negative].sort_values("value", ascending=False)

            for sym in new_negative:
                today_list.append({"symbol": sym, "alert_type": "کراس منفی"})

            logger.info(f"🔴 کراس منفی: {len(new_negative)} صندوق → {', '.join(new_negative)}")

            funds_text = ""
            for symbol, row in negative_cross.iterrows():
                pol_ratio = (row["pol_hagigi"] / row["value"] * 100) if row["value"] > 0 else 0
                funds_text += f"""
📌 {symbol}
💹 تغییر قیمت: {row["close_price_change_percent"]:+.1f}%
🎈 حباب: {row["nominal_bubble"]:+.1f}%
🔴 سرانه فروش: {row["sarane_forosh"]:,.0f}M
🟢 سرانه خرید: {row["sarane_kharid"]:,.0f}M
💰 ارزش معاملات: {row["value"]:.0f} م.ت ({row["value_to_avg_ratio"]*100:.1f}%)
💸 پول حقیقی: {row["pol_hagigi"]:+.1f} م.ت ({pol_ratio:+.1f}%)

"""

            main_text = f"🔴 هشدار کراس منفی سرانه\n\n{funds_text}".strip()
            footer = f"\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {ALERT_CHANNEL_HANDLE}"
            caption = f"{main_text}\n{footer}"

            send_alert_message(bot_token, chat_id, caption)

        # ذخیره تاریخچه
        if new_positive or new_negative:
            fund_alerts[today] = today_list
            save_fund_alerts(fund_alerts)

    except Exception as e:
        logger.error(f"خطا در بررسی کراس سرانه: {e}")


# ════════════════════════════════════════════════════════════════
# پیام‌های هشدار یکپارچه
# ════════════════════════════════════════════════════════════════

def send_price_alert(bot_token, chat_id, asset_name, price, change_5min, unit="تومان", is_gold=False):
    """ارسال هشدار نوسان قیمتی (یکپارچه برای دلار/شمش/طلا)"""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    change_text = f"{change_5min:+.2f}%".replace("+-", "−")

    # فرمت قیمت بر اساس نوع دارایی
    if is_gold:
        price_formatted = f"${price:,.2f}"
    else:
        price_formatted = f"{int(round(price)):,} {unit}"

    main_text = f"🚨 هشدار نوسان {asset_name}\n\n💰 قیمت: {price_formatted}\n📊 تغییر: {change_text}"
    footer = f"\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"

    send_alert_message(bot_token, chat_id, caption)


def send_alert_ekhtelaf_fast(bot_token, chat_id, prev_val, curr_val, diff, pol_hagigi):
    """ارسال هشدار تغییر شدید اختلاف سرانه"""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    direction = "افزایش شدید (مثبت)" if diff > 0 else "کاهش شدید (منفی)"
    dir_emoji = "🟢" if diff > 0 else "🔴"
    diff_text = f"{diff:+.0f}".replace("+-", "−")
    pol_text = f"{pol_hagigi:+,.0f}".replace("+-", "−")

    main_text = f"🚨 هشدار اختلاف سرانه\n\n{dir_emoji} {direction}\n⏱ تغییر: {diff_text} میلیون تومان\n💰 پول حقیقی: {pol_text} میلیارد تومان"
    footer = f"\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"

    send_alert_message(bot_token, chat_id, caption)


def send_alert_threshold(asset, price, threshold, above, bot_token, chat_id):
    """ارسال هشدار عبور از آستانه قیمتی"""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    direction = "بالای" if above else "زیر"
    dir_emoji = "📈" if above else "📉"

    # تعیین واحد و ایموجی
    if asset == "دلار":
        unit = "تومان"
        asset_emoji = "💵"
        price_formatted = f"{int(round(price)):,}"
    elif asset == "شمش طلا":
        unit = "ریال"
        asset_emoji = "✨"
        price_formatted = f"{int(round(price)):,}"
    elif asset == "اونس طلا":
        unit = "دلار"
        asset_emoji = "🔆"
        price_formatted = f"{price:,.2f}"
    else:
        unit = ""
        asset_emoji = ""
        price_formatted = f"{int(round(price)):,}"

    main_text = f"""
🔔 هشدار قیمتی {dir_emoji} {asset_emoji} {asset}

📈 قیمت به {direction} {threshold:,} رسید.
💰 قیمت فعلی: {price_formatted} {unit}
""".strip()

    footer = f"\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"

    send_alert_message(bot_token, chat_id, caption)


def send_alert_message(bot_token, chat_id, caption):
    """ارسال پیام هشدار به تلگرام با مدیریت Rate Limit"""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": caption, "parse_mode": "HTML"},
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            logger.info("✅ هشدار ارسال شد")
        elif response.status_code == 429:  # Rate Limit
            retry_after = response.json().get("parameters", {}).get("retry_after", 5)
            logger.warning(f"⚠️ Rate limit hit, waiting {retry_after}s")
            import time
            time.sleep(retry_after)
            return send_alert_message(bot_token, chat_id, caption)  # Retry
        else:
            logger.warning(f"⚠️ ارسال هشدار با خطا: {response.status_code}")

    except Exception as e:
        logger.error(f"❌ خطا در ارسال هشدار: {e}")
