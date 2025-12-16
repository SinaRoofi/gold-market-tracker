# utils/alerts.py

import json
import logging
import requests
from datetime import datetime, timedelta
import pytz
import jdatetime
from config import (
    DOLLAR_HIGH,
    DOLLAR_LOW,
    SHAMS_HIGH,
    SHAMS_LOW,
    GOLD_HIGH,
    GOLD_LOW,
    ALERT_THRESHOLD_PERCENT,
    EKHTELAF_THRESHOLD,
    BUBBLE_SHARP_CHANGE_THRESHOLD,
    GIST_ID,
    GIST_TOKEN,
    ALERT_STATUS_FILE,
    ALERT_CHANNEL_HANDLE,
    REQUEST_TIMEOUT,
    TIMEZONE,
    POL_SHARP_CHANGE_THRESHOLD,
)
from utils.sheets_storage import read_from_sheets

logger = logging.getLogger(__name__)
FUND_ALERTS_FILE = "fund_alerts.json"

# ✅ کش محلی برای جلوگیری از reset در صورت خطای Gist
ALERT_STATUS_CACHE = None


# ════════════════════════════════════════════════════════════════
# تابع کمکی برای تبدیل به تاریخ شمسی
# ════════════════════════════════════════════════════════════════


def get_jalali_timestamp(dt):
    """تبدیل datetime به تاریخ و ساعت شمسی"""
    j = jdatetime.datetime.fromgregorian(datetime=dt)
    return j.strftime("%Y/%m/%d - %H:%M")


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
                "pol_hagigi": "normal",
            }
            return ALERT_STATUS_CACHE or default

        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)

        if r.status_code == 200 and ALERT_STATUS_FILE in r.json()["files"]:
            status = json.loads(r.json()["files"][ALERT_STATUS_FILE]["content"])

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
        "pol_hagigi": "normal",
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

        response = requests.patch(
            url,
            headers=headers,
            json={
                "files": {
                    ALERT_STATUS_FILE: {
                        "content": json.dumps(status, ensure_ascii=False)
                    }
                }
            },
            timeout=REQUEST_TIMEOUT,
        )

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

        requests.patch(
            url,
            headers=headers,
            json={
                "files": {
                    FUND_ALERTS_FILE: {
                        "content": json.dumps(fund_alerts, ensure_ascii=False, indent=2)
                    }
                }
            },
            timeout=REQUEST_TIMEOUT,
        )

    except Exception as e:
        logger.error(f"خطا در ذخیره fund_alerts: {e}")


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


def get_previous_state_from_sheet():
    """دریافت وضعیت قبلی با بررسی فاصله زمانی"""
    try:
        rows = read_from_sheets(limit=7)  # ✅ حداقل 6 ردیف بخون

        if len(rows) < 6:
            logger.warning("داده کافی برای مقایسه نیست")
            return {
                "dollar_price": None,
                "shams_price": None,
                "gold_price": None,
                "ekhtelaf_sarane": None,
                "sarane_kharid": None,
                "bubble_weighted": None,
                "pol_hagigi": None,
            }

        prev_row = rows[-6]  # ✅ ردیف 5 دقیقه قبل (ردیف ششم از آخر)
        last_row = rows[-1]

        try:
            prev_time = datetime.strptime(prev_row[0][:19], "%Y-%m-%d %H:%M:%S")
            last_time = datetime.strptime(last_row[0][:19], "%Y-%m-%d %H:%M:%S")
            time_diff = (last_time - prev_time).total_seconds() / 60

            if abs(time_diff - 5) > 2:  # ✅ انتظار داریم حدود 5 دقیقه باشه
                logger.warning(
                    f"⚠️ فاصله زمانی غیرعادی: {time_diff:.1f} دقیقه (انتظار: ~5 دقیقه)"
                )
            else:
                logger.debug(f"✓ فاصله زمانی: {time_diff:.1f} دقیقه")

        except Exception as e:
            logger.warning(f"نمی‌تونم فاصله زمانی رو بررسی کنم: {e}")

        return {
            "dollar_price": (
                float(prev_row[2]) if len(prev_row) > 2 and prev_row[2] else None
            ),
            "shams_price": (
                float(prev_row[3]) if len(prev_row) > 3 and prev_row[3] else None
            ),
            "gold_price": (
                float(prev_row[1]) if len(prev_row) > 1 and prev_row[1] else None
            ),
            "ekhtelaf_sarane": (
                float(prev_row[11]) if len(prev_row) > 11 and prev_row[11] else None
            ),
            "sarane_kharid": (
                float(last_row[9]) if len(last_row) > 9 and last_row[9] else None
            ),
            "bubble_weighted": (
                float(prev_row[8]) if len(prev_row) > 8 and prev_row[8] else None
            ),
            "pol_hagigi": (
                float(prev_row[12]) if len(prev_row) > 12 and prev_row[12] else None
            ),
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
            "pol_hagigi": None,
        }


def check_and_send_alerts(
    bot_token,
    chat_id,
    data,
    dollar_prices,
    gold_price,
    yesterday_close,
    gold_yesterday,
    alert_channel_handle=None,
):
    """بررسی و ارسال همه هشدارها"""
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
        if total_value > 0
        else 0
    )
    current_bubble = (
        (df_funds["nominal_bubble"] * df_funds["value"]).sum() / total_value
        if total_value > 0
        else 0
    )
    current_pol = (df_funds["pol_hagigi"]).sum()

    changed = False
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)

    # نوسان 5 دقیقه‌ای
    if prev["dollar_price"] and prev["dollar_price"] > 0:
        change = (current_dollar - prev["dollar_price"]) / prev["dollar_price"] * 100
        if abs(change) >= ALERT_THRESHOLD_PERCENT:
            send_price_alert(
                bot_token, chat_id, "دلار", current_dollar, change, "تومان"
            )

    if prev["shams_price"] and prev["shams_price"] > 0:
        change = (current_shams - prev["shams_price"]) / prev["shams_price"] * 100
        if abs(change) >= ALERT_THRESHOLD_PERCENT:
            send_price_alert(
                bot_token, chat_id, "شمش طلا", current_shams, change, "ریال"
            )

    if prev["gold_price"] and prev["gold_price"] > 0:
        change = (current_gold - prev["gold_price"]) / prev["gold_price"] * 100
        if abs(change) >= ALERT_THRESHOLD_PERCENT:
            send_price_alert(
                bot_token,
                chat_id,
                "اونس طلا",
                current_gold,
                change,
                "دلار",
                is_gold=True,
            )

    # تغییر شدید اختلاف سرانه
    if prev["ekhtelaf_sarane"] is not None:
        diff = current_ekhtelaf - prev["ekhtelaf_sarane"]
        if abs(diff) >= EKHTELAF_THRESHOLD:
            send_alert_ekhtelaf_fast(
                bot_token,
                chat_id,
                prev["ekhtelaf_sarane"],
                current_ekhtelaf,
                diff,
                df_funds["pol_hagigi"].sum(),
            )

    # هشدارهای حباب و پول حقیقی
    bubble_status_changed = check_bubble_alerts(
        bot_token, chat_id, current_bubble, prev["bubble_weighted"], status, tz, now
    )
    if bubble_status_changed:
        changed = True

    pol_status_changed = check_pol_alerts(
        bot_token, chat_id, current_pol, prev["pol_hagigi"], status, tz, now
    )
    if pol_status_changed:
        changed = True

    # هشدار صندوق‌های فعال و کراس سرانه
    check_active_funds_alert(bot_token, chat_id, df_funds, tz, now)
    check_sarane_cross_alert(bot_token, chat_id, df_funds, tz, now)

    # آستانه‌های قیمتی
    for asset, price, high, low, key in [
        ("دلار", current_dollar, DOLLAR_HIGH, DOLLAR_LOW, "dollar"),
        ("شمش طلا", current_shams, SHAMS_HIGH, SHAMS_LOW, "shams"),
        ("اونس طلا", current_gold, GOLD_HIGH, GOLD_LOW, "gold"),
    ]:
        if price > high:
            if status[key] != "above":
                send_alert_threshold(
                    asset, price, high, above=True, bot_token=bot_token, chat_id=chat_id
                )
                status[key] = "above"
                changed = True
        elif price < low:
            if status[key] != "below":
                send_alert_threshold(
                    asset, price, low, above=False, bot_token=bot_token, chat_id=chat_id
                )
                status[key] = "below"
                changed = True
        else:
            if status[key] != "normal":
                status[key] = "normal"
                changed = True

    if changed or bubble_status_changed or pol_status_changed:
        save_alert_status(status)


def check_bubble_alerts(
    bot_token, chat_id, current_bubble, prev_bubble, status, tz, now
):
    """بررسی و ارسال هشدارهای حباب - کراس صفر + تغییر شدید"""
    status_changed = False

    # هشدار کراس صفر
    if current_bubble > 0:
        if status["bubble"] != "positive":
            send_bubble_state_alert(
                bot_token, chat_id, current_bubble, "positive", tz, now
            )
            status["bubble"] = "positive"
            status_changed = True
            logger.info(f"🟢 حباب مثبت شد (کراس صفر): {current_bubble:+.2f}%")

    elif current_bubble < 0:
        if status["bubble"] != "negative":
            send_bubble_state_alert(
                bot_token, chat_id, current_bubble, "negative", tz, now
            )
            status["bubble"] = "negative"
            status_changed = True
            logger.info(f"🔴 حباب منفی شد (کراس صفر): {current_bubble:+.2f}%")

    else:
        if status["bubble"] != "normal":
            status["bubble"] = "normal"
            status_changed = True
            logger.info(f"⚪ حباب صفر است: {current_bubble:+.2f}%")

    # هشدار تغییر شدید
    if prev_bubble is not None:
        bubble_change = current_bubble - prev_bubble
        if abs(bubble_change) >= BUBBLE_SHARP_CHANGE_THRESHOLD:
            send_bubble_sharp_change_alert(
                bot_token, chat_id, prev_bubble, current_bubble, bubble_change, tz, now
            )

    return status_changed


def send_bubble_state_alert(bot_token, chat_id, bubble_value, state, tz, now):
    """ارسال هشدار کراس صفر حباب"""
    if state == "positive":
        dir_emoji = "🟢"
        description = "حباب مثبت شد"
    else:
        dir_emoji = "🔴"
        description = "حباب منفی شد"

    main_text = f"""
🎈 هشدار حباب {dir_emoji}

{description}
💹 حباب فعلی: {bubble_value:+.2f}%
""".strip()

    footer = f"\n🕐 {get_jalali_timestamp(now)}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


def send_bubble_sharp_change_alert(
    bot_token, chat_id, prev_value, curr_value, change, tz, now
):
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

    footer = f"\n🕐 {get_jalali_timestamp(now)}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


def check_pol_alerts(bot_token, chat_id, current_pol, prev_pol, status, tz, now):
    """بررسی و ارسال هشدارهای پول حقیقی - کراس صفر + تغییر شدید (1 دقیقه، فقط همون روز)"""
    status_changed = False

    # هشدار کراس صفر
    if current_pol > 0:
        if status["pol_hagigi"] != "positive":
            send_pol_state_alert(bot_token, chat_id, current_pol, "positive", tz, now)
            status["pol_hagigi"] = "positive"
            status_changed = True
            logger.info(f"🟢 پول حقیقی مثبت شد: {current_pol:+,.0f} م.ت")

    elif current_pol < 0:
        if status["pol_hagigi"] != "negative":
            send_pol_state_alert(bot_token, chat_id, current_pol, "negative", tz, now)
            status["pol_hagigi"] = "negative"
            status_changed = True
            logger.info(f"🔴 پول حقیقی منفی شد: {current_pol:+,.0f} م.ت")

    else:
        if status["pol_hagigi"] != "normal":
            status["pol_hagigi"] = "normal"
            status_changed = True
            logger.info(f"⚪ پول حقیقی صفر است: {current_pol:,.0f} م.ت")

    # ✅ هشدار تغییر شدید - 1 دقیقه قبل، فقط اگر همون روز باشه
    if prev_pol is not None:
        try:
            rows = read_from_sheets(limit=3)  # ✅ فقط 2 ردیف آخر کافیه
            if len(rows) >= 2:
                prev_row = rows[-2]  # ✅ 1 دقیقه قبل
                last_row = rows[-1]

                prev_time = datetime.strptime(prev_row[0][:19], "%Y-%m-%d %H:%M:%S")
                last_time = datetime.strptime(last_row[0][:19], "%Y-%m-%d %H:%M:%S")

                # ✅ بررسی کن که همون روز باشن
                if prev_time.date() == last_time.date():
                    pol_change = current_pol - prev_pol
                    if abs(pol_change) >= POL_SHARP_CHANGE_THRESHOLD:
                        send_pol_sharp_change_alert(
                            bot_token,
                            chat_id,
                            prev_pol,
                            current_pol,
                            pol_change,
                            tz,
                            now,
                        )
                else:
                    logger.debug(f"پول حقیقی در روزهای مختلف - هشدار ارسال نمیشه")
        except Exception as e:
            logger.warning(f"خطا در بررسی تاریخ پول حقیقی: {e}")

    return status_changed


def send_pol_state_alert(bot_token, chat_id, pol_value, state, tz, now):
    """ارسال هشدار کراس صفر پول حقیقی"""
    if state == "positive":
        direction = "مثبت"
        dir_emoji = "🟢"
        description = "پول حقیقی مثبت شد"
    else:
        direction = "منفی"
        dir_emoji = "🔴"
        description = "پول حقیقی منفی شد"

    main_text = f"""
💸 هشدار پول حقیقی {dir_emoji}

{description}
💰 پول حقیقی: {pol_value:+,.0f} میلیارد تومان
📊 وضعیت: {direction}
""".strip()

    footer = f"\n🕐 {get_jalali_timestamp(now)}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


def send_pol_sharp_change_alert(
    bot_token, chat_id, prev_value, curr_value, change, tz, now
):
    """ارسال هشدار تغییر شدید پول حقیقی"""
    direction = "ورود" if change > 0 else "خروج"
    dir_emoji = "📈" if change > 0 else "📉"
    change_text = f"{abs(change):,.0f}"

    main_text = f"""
🚨 تغییر شدید پول حقیقی {dir_emoji}

⏱ {direction} در 1 دقیقه: {change_text} میلیارد تومان
🔴 قبلی: {prev_value:+,.0f} م.ت
🟢 فعلی: {curr_value:+,.0f} م.ت
""".strip()

    footer = f"\n🕐 {get_jalali_timestamp(now)}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


def check_active_funds_alert(bot_token, chat_id, df_funds, tz, now):
    """بررسی و ارسال هشدار صندوق‌های فعال"""
    try:
        latest_row = read_from_sheets(limit=1)
        if not latest_row:
            logger.warning("هیچ داده‌ای از شیت دریافت نشد")
            return

        latest_row = latest_row[-1]
        sarane_kol = (
            float(latest_row[9]) if len(latest_row) > 9 and latest_row[9] else 0
        )

        active_funds = df_funds[
            (df_funds["value_to_avg_ratio"] >= 150)
            & (df_funds["pol_to_value_ratio"] >= 0.3)
            & (df_funds["ekhtelaf_sarane"] > 0)
            & (df_funds["sarane_kharid"] >= sarane_kol)
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

        logger.info(
            f"هشدار سخت خرید: {len(new_symbols)} صندوق جدید → {', '.join(new_symbols)}"
        )

        funds_text = ""
        for symbol, row in active_funds.loc[new_symbols].iterrows():
            value_str = f"{row['value']:.0f} م.ت ({row['value_to_avg_ratio']:.0f}%)"
            pol_str = (
                f"{row['pol_hagigi']:+.0f} م.ت ({row['pol_to_value_ratio']*100:+.1f}%)"
            )
            sarane_str = (
                f"{row['sarane_kharid']:.0f}M (+{row['sarane_kharid_diff']:.0f}M)"
            )
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
        footer = f"\n🕐 {get_jalali_timestamp(now)}\n🔗 {ALERT_CHANNEL_HANDLE}"
        caption = f"{main_text}\n{footer}"
        send_alert_message(bot_token, chat_id, caption)

    except Exception as e:
        logger.error(f"خطا در بررسی صندوق‌های فعال: {e}")


def check_sarane_cross_alert(bot_token, chat_id, df_funds, tz, now):
    """بررسی و ارسال هشدار کراس سرانه"""
    try:
        positive_cross = df_funds[
            df_funds["sarane_kharid"] > df_funds["sarane_forosh"]
        ].copy()
        negative_cross = df_funds[
            df_funds["sarane_forosh"] > df_funds["sarane_kharid"]
        ].copy()

        fund_alerts = get_fund_alerts()
        fund_alerts = cleanup_old_alerts(fund_alerts)

        today = now.strftime("%Y-%m-%d")
        today_list = fund_alerts.get(today, [])

        already_sent_positive = {
            item["symbol"]
            for item in today_list
            if item.get("alert_type") == "کراس مثبت"
        }
        already_sent_negative = {
            item["symbol"]
            for item in today_list
            if item.get("alert_type") == "کراس منفی"
        }

        new_positive = [
            s for s in positive_cross.index if s not in already_sent_positive
        ]
        new_negative = [
            s for s in negative_cross.index if s not in already_sent_negative
        ]

        if new_positive:
            positive_cross = positive_cross.loc[new_positive].sort_values(
                "value", ascending=False
            )
            for sym in new_positive:
                today_list.append({"symbol": sym, "alert_type": "کراس مثبت"})

            logger.info(
                f"🟢 کراس مثبت: {len(new_positive)} صندوق → {', '.join(new_positive)}"
            )

            funds_text = ""
            for symbol, row in positive_cross.iterrows():
                pol_ratio = (
                    (row["pol_hagigi"] / row["value"] * 100) if row["value"] > 0 else 0
                )
                funds_text += f"""
📌 {symbol}
💹 تغییر قیمت: {row["close_price_change_percent"]:+.1f}%
🎈 حباب: {row["nominal_bubble"]:+.1f}%
🟢 سرانه خرید: {row["sarane_kharid"]:,.0f}M
🔴 سرانه فروش: {row["sarane_forosh"]:,.0f}M
💰 ارزش معاملات: {row["value"]:.0f} م.ت ({row["value_to_avg_ratio"]*100:.0f}%)
💸 پول حقیقی: {row["pol_hagigi"]:+,.0f} م.ت ({pol_ratio:+.1f}%)

"""

            main_text = f"🟢 هشدار کراس مثبت سرانه\n{funds_text}".strip()
            footer = f"\n🕐 {get_jalali_timestamp(now)}\n🔗 {ALERT_CHANNEL_HANDLE}"
            caption = f"{main_text}\n{footer}"
            send_alert_message(bot_token, chat_id, caption)

        if new_negative:
            negative_cross = negative_cross.loc[new_negative].sort_values(
                "value", ascending=False
            )
            for sym in new_negative:
                today_list.append({"symbol": sym, "alert_type": "کراس منفی"})

            logger.info(
                f"🔴 کراس منفی: {len(new_negative)} صندوق → {', '.join(new_negative)}"
            )

            funds_text = ""
            for symbol, row in negative_cross.iterrows():
                pol_ratio = (
                    (row["pol_hagigi"] / row["value"] * 100) if row["value"] > 0 else 0
                )
                funds_text += f"""
📌 {symbol}
💹 تغییر قیمت: {row["close_price_change_percent"]:+.1f}%
🎈 حباب: {row["nominal_bubble"]:+.1f}%
🔴 سرانه فروش: {row["sarane_forosh"]:,.0f}M
🟢 سرانه خرید: {row["sarane_kharid"]:,.0f}M
💰 ارزش معاملات: {row["value"]:,.0f} م.ت ({row["value_to_avg_ratio"]*100:.1f}%)
💸 پول حقیقی: {row["pol_hagigi"]:+,.0f} م.ت ({pol_ratio:+.1f}%)

"""

            main_text = f"🔴 هشدار کراس منفی سرانه\n{funds_text}".strip()
            footer = f"\n🕐 {get_jalali_timestamp(now)}\n🔗 {ALERT_CHANNEL_HANDLE}"
            caption = f"{main_text}\n{footer}"
            send_alert_message(bot_token, chat_id, caption)

        if new_positive or new_negative:
            fund_alerts[today] = today_list
            save_fund_alerts(fund_alerts)

    except Exception as e:
        logger.error(f"خطا در بررسی کراس سرانه: {e}")


def send_price_alert(
    bot_token, chat_id, asset_name, price, change_5min, unit="تومان", is_gold=False
):
    """ارسال هشدار نوسان قیمتی"""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    change_text = f"{change_5min:+.2f}%".replace("+-", "−")

    if is_gold:
        price_formatted = f"${price:,.2f}"
    else:
        price_formatted = f"{int(round(price)):,} {unit}"

    main_text = f"🚨 هشدار نوسان {asset_name}\n\n💰 قیمت: {price_formatted}\n📊 تغییر: {change_text}"
    footer = f"\n🕐 {get_jalali_timestamp(now)}\n🔗 {ALERT_CHANNEL_HANDLE}"
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
    footer = f"\n🕐 {get_jalali_timestamp(now)}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


def send_alert_threshold(asset, price, threshold, above, bot_token, chat_id):
    """ارسال هشدار عبور از آستانه قیمتی"""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    direction = "بالای" if above else "زیر"
    dir_emoji = "📈" if above else "📉"

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

    footer = f"\n🕐 {get_jalali_timestamp(now)}\n🔗 {ALERT_CHANNEL_HANDLE}"
    caption = f"{main_text}\n{footer}"
    send_alert_message(bot_token, chat_id, caption)


def send_alert_message(bot_token, chat_id, caption):
    """ارسال پیام هشدار به تلگرام"""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data={"chat_id": chat_id, "text": caption, "parse_mode": "HTML"},
            timeout=REQUEST_TIMEOUT,
        )

        if response.status_code == 200:
            logger.info("✅ هشدار ارسال شد")
        elif response.status_code == 429:
            retry_after = response.json().get("parameters", {}).get("retry_after", 5)
            logger.warning(f"⚠️ Rate limit hit, waiting {retry_after}s")
            import time

            time.sleep(retry_after)
            return send_alert_message(bot_token, chat_id, caption)
        else:
            logger.warning(f"⚠️ ارسال هشدار با خطا: {response.status_code}")

    except Exception as e:
        logger.error(f"❌ خطا در ارسال هشدار: {e}")