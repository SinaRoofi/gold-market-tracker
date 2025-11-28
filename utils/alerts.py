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
    GIST_ID, GIST_TOKEN,
    ALERT_STATUS_FILE,
    CHANNEL_HANDLE,
    REQUEST_TIMEOUT,
    TIMEZONE
)
from utils.sheets_storage import read_from_sheets

logger = logging.getLogger(__name__)
FUND_ALERTS_FILE = "fund_alerts.json"

# ────────────────── مدیریت Gist ──────────────────
def get_alert_status():
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
    try:
        if not GIST_ID or not GIST_TOKEN: return
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        requests.patch(url, headers=headers, json={
            "files": {ALERT_STATUS_FILE: {"content": json.dumps(status, ensure_ascii=False)}}
        }, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        logger.error(f"خطا در ذخیره alert_status: {e}")


def get_fund_alerts():
    try:
        if not GIST_ID or not GIST_TOKEN: return {}
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if r.status_code == 200 and FUND_ALERTS_FILE in r.json()["files"]:
            return json.loads(r.json()["files"][FUND_ALERTS_FILE]["content"])
    except Exception as e:
        logger.error(f"خطا در خواندن fund_alerts: {e}")
    return {}


def save_fund_alerts(fund_alerts):
    try:
        if not GIST_ID or not GIST_TOKEN: return
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        requests.patch(url, headers=headers, json={
            "files": {FUND_ALERTS_FILE: {"content": json.dumps(fund_alerts, ensure_ascii=False, indent=2)}}
        }, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        logger.error(f"خطا در ذخیره fund_alerts: {e}")


# ────────────────── پاک‌سازی داده‌های قدیمی‌تر از ۷ روز ──────────────────
def cleanup_old_alerts(alerts_dict):
    try:
        tz = pytz.timezone(TIMEZONE)
        cutoff = (datetime.now(tz) - timedelta(days=7)).strftime("%Y-%m-%d")
        cleaned = {d: items for d, items in alerts_dict.items() if d >= cutoff}
        removed = len(alerts_dict) - len(cleaned)
        if removed > 0:
            logger.info(f"{removed} روز قدیمی از تاریخچه پاک شد")
        return cleaned
    except:
        return alerts_dict


# ────────────────── دریافت وضعیت قبلی از شیت ──────────────────
def get_previous_state_from_sheet():
    try:
        rows = read_from_sheets(limit=2)
        if len(rows) >= 2:
            prev_row = rows[-2]
            last_row = rows[-1]
            return {
                "dollar_price": float(prev_row[2]) if len(prev_row) > 2 and prev_row[2] else None,
                "shams_price": float(prev_row[3]) if len(prev_row) > 3 and prev_row[3] else None,
                "gold_price": float(prev_row[1]) if len(prev_row) > 1 and prev_row[1] else None,
                "ekhtelaf_sarane": float(prev_row[11]) if len(prev_row) > 11 and prev_row[11] else None,
                "sarane_kharid": float(last_row[9]) if len(last_row) > 9 and last_row[9] else None,
            }
    except Exception as e:
        logger.error(f"خطا در خواندن وضعیت قبلی: {e}")
    return {"dollar_price": None, "shams_price": None, "gold_price": None, "ekhtelaf_sarane": None, "sarane_kharid": None}


# ────────────────── چک و ارسال هشدارها ──────────────────
def check_and_send_alerts(bot_token, chat_id, data, dollar_prices, gold_price, yesterday_close, gold_yesterday):
    prev = get_previous_state_from_sheet()
    status = get_alert_status()

    current_dollar = dollar_prices.get("last_trade", 0)
    current_shams = data["dfp"].loc["شمش-طلا", "close_price"] if "شمش-طلا" in data["dfp"].index else 0
    current_gold = gold_price

    df_funds = data["Fund_df"]
    total_value = df_funds["value"].sum()
    current_ekhtelaf = (df_funds["ekhtelaf_sarane"] * df_funds["value"]).sum() / total_value if total_value > 0 else 0

    changed = False
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # نوسان ۵ دقیقه‌ای
    if prev["dollar_price"] and prev["dollar_price"] > 0:
        change = (current_dollar - prev["dollar_price"]) / prev["dollar_price"] * 100
        if abs(change) >= ALERT_THRESHOLD_PERCENT:
            send_alert_dollar_fast(bot_token, chat_id, current_dollar, change)

    if prev["shams_price"] and prev["shams_price"] > 0:
        change = (current_shams - prev["shams_price"]) / prev["shams_price"] * 100
        if abs(change) >= ALERT_THRESHOLD_PERCENT:
            send_alert_shams_fast(bot_token, chat_id, current_shams, change)

    if prev["gold_price"] and prev["gold_price"] > 0:
        change = (current_gold - prev["gold_price"]) / prev["gold_price"] * 100
        if abs(change) >= ALERT_THRESHOLD_PERCENT:
            send_alert_gold_fast(bot_token, chat_id, current_gold, change)

    # تغییر شدید اختلاف سرانه
    if prev["ekhtelaf_sarane"] is not None:
        diff = current_ekhtelaf - prev["ekhtelaf_sarane"]
        if abs(diff) >= EKHTELAF_THRESHOLD:
            send_alert_ekhtelaf_fast(bot_token, chat_id, prev["ekhtelaf_sarane"], current_ekhtelaf, diff, df_funds["pol_hagigi"].sum())

    # هشدار صندوق فعال — ۴ شرط + فقط یک بار در روز + تاریخچه بدون ساعت
    check_active_funds_alert(bot_token, chat_id, df_funds, tz, now)

    # آستانه‌های قیمتی — بدون باگ
    for asset, price, high, low, key in [
        ("دلار", current_dollar, DOLLAR_HIGH, DOLLAR_LOW, "dollar"),
        ("شمش طلا", current_shams, SHAMS_HIGH, SHAMS_LOW, "shams"),
        ("اونس طلا", current_gold, GOLD_HIGH, GOLD_LOW, "gold")
    ]:
        if price >= high:
            if status[key] != "above":
                send_alert_threshold(asset, price, high, above=True, bot_token=bot_token, chat_id=chat_id)
                status[key] = "above"; changed = True
        elif price < low:
            if status[key] != "below":
                send_alert_threshold(asset, price, low, above=False, bot_token=bot_token, chat_id=chat_id)
                status[key] = "below"; changed = True
        else:
            if status[key] != "normal":
                status[key] = "normal"; changed = True

    if changed:
        save_alert_status(status)


# ────────────────── هشدار صندوق‌های فعال — ۴ شرط + فقط یک بار در روز + بدون ذخیره ساعت ──────────────────
def check_active_funds_alert(bot_token, chat_id, df_funds, tz, now):
    try:
        latest_row = read_from_sheets(limit=1)[-1]
        sarane_kol = float(latest_row[9]) if len(latest_row) > 9 and latest_row[9] else 0

        active_funds = df_funds[
            (df_funds["value_to_avg_ratio"] >= 150) &
            (df_funds["pol_to_value_ratio"] >= 50) &
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

        for sym in new_symbols:
            today_list.append({"symbol": sym, "alert_type": "هشدار سخت خرید"})
        fund_alerts[today] = today_list
        save_fund_alerts(fund_alerts)

        logger.info(f"هشدار سخت خرید: {len(new_symbols)} صندوق جدید → {', '.join(new_symbols)}")

        funds_text = ""
        for symbol, row in active_funds.loc[new_symbols].iterrows():
            value_str = f"{row['value']:.0f}B ({row['value_to_avg_ratio']:.0f}%)"
            pol_str = f"{row['pol_hagigi']:+.1f}".replace(".", "/") + f"B ({row['pol_to_value_ratio']:+.0f}%)"
            sarane_str = f"{row['sarane_kharid']:.0f}M (+{row['sarane_kharid_diff']:.0f}M)"
            ekhtelaf_str = f"{row['ekhtelaf_sarane']:+.1f}".replace(".", "/") + "M"

            funds_text += f"""
📌 {symbol}
💰 ارزش معاملات: {value_str}
💸 ورود پول حقیقی: {pol_str}
🟢 سرانه خرید: {sarane_str}
📊 اختلاف سرانه: {ekhtelaf_str}
🎈 حباب: {row['nominal_bubble']:+.1f}%
━━━━━━━━━━━━━━━━━━━━━━━━"""

        main_text = f"🚨 هشدار سخت خرید\n\n{funds_text}".strip()
        footer = f"-------------------------\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {CHANNEL_HANDLE}"
        caption = f"{main_text}\n{footer}"
        send_alert_message(bot_token, chat_id, caption)

    except Exception as e:
        logger.error(f"خطا در بررسی صندوق‌های فعال: {e}")


# ────────────────── پیام‌های هشدار سریع ──────────────────
def send_alert_dollar_fast(bot_token, chat_id, price, change_5min):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    change_text = f"{change_5min:+.2f}%".replace("+-", "−")
    main_text = f"🚨 هشدار نوسان دلار\n\n💰 قیمت: {int(round(price)):,} تومان\n📊 تغییر: {change_text}"
    footer = f"-------------------------\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


def send_alert_shams_fast(bot_token, chat_id, price, change_5min):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    change_text = f"{change_5min:+.2f}%".replace("+-", "−")
    main_text = f"🚨 هشدار نوسان شمش طلا\n\n💰 قیمت: {int(round(price)):,} ریال\n📊 تغییر: {change_text}"
    footer = f"-------------------------\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


def send_alert_gold_fast(bot_token, chat_id, price, change_5min):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    change_text = f"{change_5min:+.2f}%".replace("+-", "−")
    main_text = f"🚨 هشدار نوسان اونس طلا\n\n💰 قیمت: ${price:,.2f}\n📊 تغییر: {change_text}"
    footer = f"-------------------------\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


def send_alert_ekhtelaf_fast(bot_token, chat_id, prev_val, curr_val, diff, pol_hagigi):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    direction = "افزایش شدید (مثبت)" if diff > 0 else "کاهش شدید (منفی)"
    dir_emoji = "🟢" if diff > 0 else "🔴"
    diff_text = f"{diff:+.1f}".replace("+-", "−")
    pol_text = f"{pol_hagigi:+,.0f}".replace("+-", "−")
    main_text = f"🚨 هشدار اختلاف سرانه\n\n{dir_emoji} {direction}\n⏱ تغییر ۵ دقیقه: {diff_text} میلیون تومان\n💰 ارزش معاملات: {pol_text} میلیارد تومان"
    footer = f"-------------------------\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


# ────────────────── هشدار قیمتی با نام دارایی و ایموجی ──────────────────
def send_alert_threshold(asset, price, threshold, above, bot_token, chat_id):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    direction = "بالای" if above else "زیر"
    dir_emoji = "📈" if above else "📉"  # اضافه شد

    # تعیین واحد و ایموجی دارایی
    if asset == "دلار":
        unit = "تومان"
        asset_emoji = "💵"
    elif asset == "شمش طلا":
        unit = "ریال"
        asset_emoji = "✨"
    elif asset == "اونس طلا":
        unit = "دلار"
        asset_emoji = "🔆"
    else:
        unit = ""
        asset_emoji = ""

    main_text = f"""
🔔 هشدار قیمتی {dir_emoji} {asset_emoji} {asset}

📈 قیمت به {direction} {threshold:,} رسید.
💰 قیمت فعلی: {int(round(price)):,} {unit}
""".strip()

    footer = f"-------------------------\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


# ────────────────── ارسال پیام به تلگرام ──────────────────
def send_alert_message(bot_token, chat_id, caption):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": caption, "parse_mode": "HTML"},
            timeout=REQUEST_TIMEOUT
        )
        if response.status_code == 200:
            logger.info("هشدار ارسال شد")
        else:
            logger.warning(f"ارسال هشدار با خطا: {response.status_code}")
    except Exception as e:
        logger.error(f"خطا در ارسال هشدار: {e}")