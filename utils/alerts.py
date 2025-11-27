# utils/alerts.py
"""سیستم هشدارهای قیمتی و نوسانی بازار"""

import json
import logging
import requests
from config import (
    DOLLAR_HIGH, DOLLAR_LOW,
    SHAMS_HIGH, SHAMS_LOW,
    GOLD_HIGH, GOLD_LOW,
    ALERT_THRESHOLD_PERCENT,
    EKHTELAF_THRESHOLD,
    GIST_ID, GIST_TOKEN,
    ALERT_STATUS_FILE,
    CHANNEL_HANDLE,
    REQUEST_TIMEOUT
)
from utils.sheets_storage import read_from_sheets

logger = logging.getLogger(__name__)

# ────────────────── مدیریت وضعیت هشدارهای قیمتی ──────────────────

def get_alert_status():
    """دریافت وضعیت فعلی هشدارها از GitHub Gist"""
    try:
        if not GIST_ID or not GIST_TOKEN:
            logger.warning("GIST_ID یا GIST_TOKEN تنظیم نشده است")
            return {"dollar": "normal", "shams": "normal", "gold": "normal"}

        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

        if r.status_code == 200 and ALERT_STATUS_FILE in r.json()["files"]:
            return json.loads(r.json()["files"][ALERT_STATUS_FILE]["content"])

    except Exception as e:
        logger.error(f"خطا در خواندن alert_status: {e}")

    return {"dollar": "normal", "shams": "normal", "gold": "normal"}


def save_alert_status(status):
    """ذخیره وضعیت هشدارها در GitHub Gist"""
    try:
        if not GIST_ID or not GIST_TOKEN:
            logger.warning("امکان ذخیره alert_status: GIST تنظیم نشده")
            return

        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        requests.patch(url, headers=headers, json={
            "files": {ALERT_STATUS_FILE: {"content": json.dumps(status)}}
        }, timeout=REQUEST_TIMEOUT)

        logger.debug("✅ وضعیت هشدارها ذخیره شد")

    except Exception as e:
        logger.error(f"خطا در ذخیره alert_status: {e}")


# ────────────────── دریافت وضعیت قبلی از شیت ──────────────────

def get_previous_state_from_sheet():
    """دریافت آخرین رکورد از Google Sheets برای مقایسه"""
    try:
        rows = read_from_sheets(limit=1)
        if rows and len(rows) > 0:
            last_row = rows[-1]
            return {
                "dollar_price": float(last_row[2]) if len(last_row) > 2 and last_row[2] else None,
                "shams_price": float(last_row[3]) if len(last_row) > 3 and last_row[3] else None,
                "gold_price": float(last_row[1]) if len(last_row) > 1 and last_row[1] else None,
                "ekhtelaf_sarane": float(last_row[11]) if len(last_row) > 11 and last_row[11] else None,
            }
    except Exception as e:
        logger.error(f"خطا در خواندن وضعیت قبلی: {e}")

    return {
        "dollar_price": None,
        "shams_price": None,
        "gold_price": None,
        "ekhtelaf_sarane": None
    }


# ────────────────── چک و ارسال هشدارها ──────────────────

def check_and_send_alerts(bot_token, chat_id, data, dollar_prices, gold_price, 
                          yesterday_close, gold_yesterday):
    """
    بررسی شرایط و ارسال هشدارها
    
    Args:
        bot_token: توکن ربات تلگرام
        chat_id: شناسه چت
        data: داده‌های پردازش شده بازار
        dollar_prices: قیمت‌های دلار
        gold_price: قیمت طلای فعلی
        yesterday_close: قیمت بسته دیروز
        gold_yesterday: قیمت طلای دیروز
    """
    prev = get_previous_state_from_sheet()
    status = get_alert_status()

    current_dollar = dollar_prices.get("last_trade", 0)
    current_shams = (
        data["dfp"].loc["شمش-طلا", "close_price"] 
        if "شمش-طلا" in data["dfp"].index 
        else 0
    )
    current_gold = gold_price

    df_funds = data["Fund_df"]
    total_value = df_funds["value"].sum()
    current_ekhtelaf = (
        (df_funds["ekhtelaf_sarane"] * df_funds["value"]).sum() / total_value 
        if total_value > 0 else 0
    )

    changed = False

    # ═══════════════════════════════════════════════════════
    # 1️⃣ هشدار تغییر سریع دلار (بیش از 0.5% در 5 دقیقه)
    # ═══════════════════════════════════════════════════════
    if prev["dollar_price"] and prev["dollar_price"] > 0:
        change_5min = (current_dollar - prev["dollar_price"]) / prev["dollar_price"] * 100
        if abs(change_5min) >= ALERT_THRESHOLD_PERCENT:
            send_alert_dollar_fast(bot_token, chat_id, current_dollar, change_5min)

    # ═══════════════════════════════════════════════════════
    # 2️⃣ هشدار تغییر شدید اختلاف سرانه (بیش از 10 میلیون)
    # ═══════════════════════════════════════════════════════
    if prev["ekhtelaf_sarane"] is not None:
        diff_ekhtelaf = current_ekhtelaf - prev["ekhtelaf_sarane"]
        if abs(diff_ekhtelaf) >= EKHTELAF_THRESHOLD:
            send_alert_ekhtelaf_fast(
                bot_token, chat_id, 
                prev["ekhtelaf_sarane"], 
                current_ekhtelaf, 
                diff_ekhtelaf, 
                df_funds["pol_hagigi"].sum()
            )

    # ═══════════════════════════════════════════════════════
    # 3️⃣ هشدار صندوق‌های فعال (شرایط خرید)
    # ═══════════════════════════════════════════════════════
    check_active_funds_alert(bot_token, chat_id, df_funds)

    # ═══════════════════════════════════════════════════════
    # 4️⃣ هشدار آستانه قیمتی دلار
    # ═══════════════════════════════════════════════════════
    if current_dollar >= DOLLAR_HIGH and status["dollar"] == "normal":
        send_alert_threshold(
            "دلار", current_dollar, DOLLAR_HIGH, above=True, 
            bot_token=bot_token, chat_id=chat_id
        )
        status["dollar"] = "above"
        changed = True

    elif current_dollar < DOLLAR_LOW and status["dollar"] == "normal":
        send_alert_threshold(
            "دلار", current_dollar, DOLLAR_LOW, above=False, 
            bot_token=bot_token, chat_id=chat_id
        )
        status["dollar"] = "below"
        changed = True

    elif DOLLAR_LOW <= current_dollar < DOLLAR_HIGH and status["dollar"] != "normal":
        status["dollar"] = "normal"
        changed = True

    # ═══════════════════════════════════════════════════════
    # 5️⃣ هشدار آستانه شمش طلا
    # ═══════════════════════════════════════════════════════
    if current_shams >= SHAMS_HIGH and status["shams"] == "normal":
        send_alert_threshold(
            "شمش طلا", current_shams, SHAMS_HIGH, above=True, 
            bot_token=bot_token, chat_id=chat_id
        )
        status["shams"] = "above"
        changed = True

    elif current_shams < SHAMS_LOW and status["shams"] == "normal":
        send_alert_threshold(
            "شمش طلا", current_shams, SHAMS_LOW, above=False, 
            bot_token=bot_token, chat_id=chat_id
        )
        status["shams"] = "below"
        changed = True

    elif SHAMS_LOW <= current_shams < SHAMS_HIGH and status["shams"] != "normal":
        status["shams"] = "normal"
        changed = True

    # ═══════════════════════════════════════════════════════
    # 6️⃣ هشدار آستانه اونس طلا
    # ═══════════════════════════════════════════════════════
    if current_gold >= GOLD_HIGH and status["gold"] == "normal":
        send_alert_threshold(
            "اونس طلا", current_gold, GOLD_HIGH, above=True, 
            bot_token=bot_token, chat_id=chat_id
        )
        status["gold"] = "above"
        changed = True

    elif current_gold < GOLD_LOW and status["gold"] == "normal":
        send_alert_threshold(
            "اونس طلا", current_gold, GOLD_LOW, above=False, 
            bot_token=bot_token, chat_id=chat_id
        )
        status["gold"] = "below"
        changed = True

    elif GOLD_LOW <= current_gold < GOLD_HIGH and status["gold"] != "normal":
        status["gold"] = "normal"
        changed = True

    # ذخیره تغییرات وضعیت
    if changed:
        save_alert_status(status)


# ────────────────── هشدار صندوق‌های فعال ──────────────────

def check_active_funds_alert(bot_token, chat_id, df_funds):
    """
    بررسی و ارسال هشدار سخت خرید
    
    شرایط (عین فیلتر):
    - ارزش معاملات به میانگین ماهانه >= 150%
    - پول حقیقی به ارزش معاملات >= 50%
    - اختلاف سرانه > 0
    
    این هشدار در هر اجرا چک میشه و اگه صندوقی شرایط داشته باشه ارسال میشه
    """
    try:
        # فیلتر صندوق‌هایی که شرایط رو دارن
        active_funds = df_funds[
            (df_funds["value_to_avg_ratio"] >= 150) &
            (df_funds["pol_to_value_ratio"] >= 50) &
            (df_funds["ekhtelaf_sarane"] > 0)
        ].copy()

        if len(active_funds) == 0:
            logger.debug("هیچ صندوق فعالی با شرایط هشدار پیدا نشد")
            return

        # مرتب‌سازی بر اساس ارزش معاملات (بزرگترین اول)
        active_funds = active_funds.sort_values("value", ascending=False)

        logger.info(f"🔔 {len(active_funds)} صندوق فعال با شرایط سخت خرید پیدا شد")

        # ساخت پیام - همه صندوق‌ها رو نشون بده
        funds_text = ""
        for symbol, row in active_funds.iterrows():
            funds_text += f"""
📌 <b>{symbol}</b>
💰 ارزش معاملات: {row['value']:.1f}B (<b>{row['value_to_avg_ratio']:.0f}%</b>)
💸 پول حقیقی: {row['pol_hagigi']:+.1f}B (<b>{row['pol_to_value_ratio']:+.0f}%</b>)
🟢 سرانه خرید: <b>{row['sarane_kharid']:.0f}M</b>
📊 اختلاف سرانه: <b>{row['ekhtelaf_sarane']:+.1f}M</b>
🎈 حباب: {row['nominal_bubble']:+.1f}%
━━━━━━━━━━━━━━━━━━━━━━━━"""

        caption = f"""
🚨 <b>هشدار سخت خرید</b>

<b>{len(active_funds)} صندوق</b> با شرایط سخت خرید:
{funds_text}

✅ شرایط: ارزش معاملات ≥150% میانگین، پول حقیقی ≥50% ارزش معاملات، اختلاف سرانه مثبت

🔗 {CHANNEL_HANDLE}
""".strip()

        send_alert_message(bot_token, chat_id, caption)

    except Exception as e:
        logger.error(f"❌ خطا در بررسی صندوق‌های فعال: {e}")


# ────────────────── پیام‌های هشدار ──────────────────

def send_alert_dollar_fast(bot_token, chat_id, price, change_5min):
    """هشدار تغییر سریع قیمت دلار"""
    change_text = f"{change_5min:+.2f}%".replace("+-", "−")
    caption = f"""
🚨 هشدار نوسان دلار

💰 قیمت: {int(round(price)):,} تومان
📊 تغییر: {change_text}

🔗 {CHANNEL_HANDLE}
""".strip()
    send_alert_message(bot_token, chat_id, caption)


def send_alert_ekhtelaf_fast(bot_token, chat_id, prev_val, curr_val, diff, pol_hagigi):
    """هشدار تغییر شدید اختلاف سرانه"""
    direction = "افزایش شدید (مثبت)" if diff > 0 else "کاهش شدید (منفی)"
    dir_emoji = "🟢" if diff > 0 else "🔴"
    diff_text = f"{diff:+.1f}".replace("+-", "−")
    pol_text = f"{pol_hagigi:+,.0f}".replace("+-", "−")

    caption = f"""
🚨 هشدار اختلاف سرانه

{dir_emoji} {direction}
⏱ تغییر ۵ دقیقه: {diff_text} میلیون تومان
💸 ورود پول حقیقی: {pol_text} میلیارد تومان

🔗 {CHANNEL_HANDLE}
""".strip()
    send_alert_message(bot_token, chat_id, caption)


def send_alert_threshold(asset, price, threshold, above, bot_token, chat_id):
    """هشدار عبور از آستانه قیمتی"""
    direction = "بالای" if above else "زیر"
    dir_emoji = "📈" if above else "📉"

    # تعیین واحد بر اساس نوع دارایی
    unit = "تومان" if asset == "دلار" else "ریال" if asset == "شمش طلا" else "دلار"

    # انتخاب ایموجی بر اساس نوع دارایی
    asset_emoji = "💵"
    if "شمش" in asset:
        asset_emoji = "✨"
    elif "اونس" in asset:
        asset_emoji = "🔆"

    caption = f"""
🔔 هشدار قیمتی {asset_emoji}

{dir_emoji} قیمت به {direction} {threshold:,} رسید.
💰 قیمت فعلی: {int(round(price)):,} {unit}

🔗 {CHANNEL_HANDLE}
""".strip()
    send_alert_message(bot_token, chat_id, caption)


def send_alert_message(bot_token, chat_id, caption):
    """ارسال پیام هشدار به تلگرام"""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": caption, "parse_mode": "HTML"},
            timeout=REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            logger.info("✅ هشدار ارسال شد")
        else:
            logger.warning(f"⚠️ ارسال هشدار با خطا: {response.status_code}")

    except Exception as e:
        logger.error(f"❌ خطا در ارسال هشدار: {e}")