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

# ✅ کش محلی برای جلوگیری از reset در صورت خطای Gist
ALERT_STATUS_CACHE = None

# ────────────────── مدیریت Gist ──────────────────

# ────────────────── مدیریت Gist ──────────────────
def get_alert_status():
    """دریافت وضعیت هشدارها از Gist با fallback به کش محلی"""
    global ALERT_STATUS_CACHE
    
    try:
        if not GIST_ID or not GIST_TOKEN:
            logger.warning("GIST_ID یا GIST_TOKEN تنظیم نشده است")
            return ALERT_STATUS_CACHE or {"dollar": "normal", "shams": "normal", "gold": "normal"}

        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

        if r.status_code == 200 and ALERT_STATUS_FILE in r.json()["files"]:
            status = json.loads(r.json()["files"][ALERT_STATUS_FILE]["content"])
            ALERT_STATUS_CACHE = status  # ✅ ذخیره موفق
            return status

    except Exception as e:
        logger.error(f"خطا در خواندن alert_status: {e}")
        if ALERT_STATUS_CACHE:
            logger.info("استفاده از کش محلی")
            return ALERT_STATUS_CACHE

    default = {"dollar": "normal", "shams": "normal", "gold": "normal"}
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
            ALERT_STATUS_CACHE = status  # ✅ آپدیت کش
            
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


# ────────────────── پاک‌سازی داده‌های قدیمی‌تر از ۷ روز ──────────────────
def cleanup_old_alerts(alerts_dict, max_days=7):
    """پاک‌سازی بهینه‌شده داده‌های قدیمی"""
    if not alerts_dict:
        return {}
        
    try:
        tz = pytz.timezone(TIMEZONE)
        cutoff = (datetime.now(tz) - timedelta(days=max_days)).strftime("%Y-%m-%d")
        
        # اگه همه تاریخ‌ها جدیدن، نیازی به پاکسازی نیست
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


# ────────────────── دریافت وضعیت قبلی از شیت با Validation ──────────────────
def get_previous_state_from_sheet():
    """دریافت وضعیت قبلی با بررسی فاصله زمانی"""
    try:
        rows = read_from_sheets(limit=3)  # ✅ 3 ردیف برای اطمینان
        
        if len(rows) < 2:
            logger.warning("داده کافی برای مقایسه نیست")
            return {
                "dollar_price": None, 
                "shams_price": None, 
                "gold_price": None, 
                "ekhtelaf_sarane": None,
                "sarane_kharid": None
            }
            
        prev_row = rows[-2]
        last_row = rows[-1]
        
        # ✅ بررسی فاصله زمانی
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
        }
        
    except Exception as e:
        logger.error(f"خطا در خواندن وضعیت قبلی: {e}")
        return {
            "dollar_price": None, 
            "shams_price": None, 
            "gold_price": None, 
            "ekhtelaf_sarane": None,
            "sarane_kharid": None
        }


# ────────────────── چک و ارسال هشدارها ──────────────────
def check_and_send_alerts(bot_token, chat_id, data, dollar_prices, gold_price, yesterday_close, gold_yesterday):
    """بررسی شرایط و ارسال هشدارها"""
    
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
    
    # ───────────────────────────────────────────────────
    # 1️⃣ نوسان ۵ دقیقه‌ای (بدون Cooldown - همیشه مانیتور)
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
    # 3️⃣ هشدار صندوق فعال
    # ───────────────────────────────────────────────────
    check_active_funds_alert(bot_token, chat_id, df_funds, tz, now)
    
    # ───────────────────────────────────────────────────
    # 4️⃣ آستانه‌های قیمتی (این‌ها با Cooldown هستن)
    # ───────────────────────────────────────────────────
    for asset, price, high, low, key in [
        ("دلار", current_dollar, DOLLAR_HIGH, DOLLAR_LOW, "dollar"),
        ("شمش طلا", current_shams, SHAMS_HIGH, SHAMS_LOW, "shams"),
        ("اونس طلا", current_gold, GOLD_HIGH, GOLD_LOW, "gold")
    ]:
        if price >= high:
            if status[key] != "above":
                send_alert_threshold(asset, price, high, above=True, bot_token=bot_token, chat_id=chat_id)
                status[key] = "above"
                changed = True
        elif price <= low:  # ✅ تغییر از < به <=
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


# ────────────────── هشدار صندوق‌های فعال ──────────────────
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
            value_str = f"{row['value']:.0f}B ({row['value_to_avg_ratio']:.0f}%)"
            pol_str = f"{row['pol_hagigi']:+.1f}B ({row['pol_to_value_ratio']*100:+.0f}%)"
            sarane_str = f"{row['sarane_kharid']:.0f}M (+{row['sarane_kharid_diff']:.0f}M)"
            ekhtelaf_str = f"{row['ekhtelaf_sarane']:+.0f}M"
            
            funds_text += f"""
📌 {symbol}
💰 ارزش معاملات: {value_str}
💸 ورود پول حقیقی: {pol_str}
🟢 سرانه خرید: {sarane_str}
📊 اختلاف سرانه: {ekhtelaf_str}
🎈 حباب: {row['nominal_bubble']:+.1f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""
        
        main_text = f"🚨 هشدار سخت خرید\n\n{funds_text}".strip()
        footer = f"------------------------------------------\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {CHANNEL_HANDLE}"
        caption = f"{main_text}\n{footer}"
        
        send_alert_message(bot_token, chat_id, caption)
        
    except Exception as e:
        logger.error(f"خطا در بررسی صندوق‌های فعال: {e}")


# ────────────────── پیام هشدار قیمتی یکپارچه ──────────────────
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
    footer = f"------------------------------------------\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    
    send_alert_message(bot_token, chat_id, caption)


# ────────────────── هشدار اختلاف سرانه ──────────────────
def send_alert_ekhtelaf_fast(bot_token, chat_id, prev_val, curr_val, diff, pol_hagigi):
    """ارسال هشدار تغییر شدید اختلاف سرانه"""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    direction = "افزایش شدید (مثبت)" if diff > 0 else "کاهش شدید (منفی)"
    dir_emoji = "🟢" if diff > 0 else "🔴"
    diff_text = f"{diff:+.0f}".replace("+-", "−")
    pol_text = f"{pol_hagigi:+,.0f}".replace("+-", "−")
    
    main_text = f"🚨 هشدار اختلاف سرانه\n\n{dir_emoji} {direction}\n⏱ تغییر ۵ دقیقه: {diff_text} میلیون تومان\n💰 ارزش معاملات: {pol_text} میلیارد تومان"
    footer = f"------------------------------------------\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    
    send_alert_message(bot_token, chat_id, caption)


# ────────────────── هشدار آستانه قیمتی ──────────────────
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
    
    footer = f"------------------------------------------\n🕐 {now.strftime('%Y-%m-%d - %H:%M')}\n🔗 {CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    
    send_alert_message(bot_token, chat_id, caption)


# ────────────────── ارسال پیام به تلگرام ──────────────────
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
