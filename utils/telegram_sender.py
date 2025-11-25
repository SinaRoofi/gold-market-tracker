# utils/telegram_sender.py

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

# ────────────────── تنظیمات آستانه‌ها ──────────────────
DOLLAR_HIGH = 114_000
DOLLAR_LOW  = 113_000
SHAMS_HIGH  = 15_000_000
SHAMS_LOW   = 14_900_000
GOLD_HIGH   = 4200
GOLD_LOW    = 4080

ALERT_THRESHOLD_PERCENT = 0.5   # تغییر سریع دلار
EKHTELAF_THRESHOLD      = 10    # تغییر اختلاف سرانه (میلیون تومان)

GIST_ID    = os.getenv("GIST_ID")
GIST_TOKEN = os.getenv("GIST_TOKEN")
ALERT_STATUS_FILE = "alert_status.json"


# ────────────────── مدیریت وضعیت هشدارهای قیمتی (یک‌بار در هر عبور) ──────────────────
def get_alert_status():
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200 and ALERT_STATUS_FILE in r.json()["files"]:
            return json.loads(r.json()["files"][ALERT_STATUS_FILE]["content"])
    except Exception as e:
        logger.error(f"خطا در خواندن alert_status: {e}")
    return {"dollar": "normal", "shams": "normal", "gold": "normal"}

def save_alert_status(status):
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        requests.patch(url, headers=headers, json={
            "files": {ALERT_STATUS_FILE: {"content": json.dumps(status)}}
        }, timeout=10)
    except Exception as e:
        logger.error(f"خطا در ذخیره alert_status: {e}")


# ────────────────── توابع Gist قدیمی (message_id) ──────────────────
def get_gist_data():
    try:
        if not GIST_ID or not GIST_TOKEN:
            return {"message_id": None, "date": None}
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            content = response.json()["files"]["message_id.json"]["content"]
            return json.loads(content)
    except Exception as e:
        logger.error(f"خطا در خواندن Gist: {e}")
    return {"message_id": None, "date": None}

def save_gist_data(message_id, date):
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        data = {"files": {"message_id.json": {"content": json.dumps({"message_id": message_id, "date": date})}}}
        requests.patch(url, headers=headers, json=data, timeout=10)
    except Exception as e:
        logger.error(f"خطا در ذخیره Gist: {e}")

def get_today_date():
    return datetime.now(pytz.timezone("Asia/Tehran")).strftime("%Y-%m-%d")


# ────────────────── وضعیت قبلی از شیت ──────────────────
def get_previous_state_from_sheet():
    try:
        rows = read_from_sheets(limit=1)
        if rows and len(rows) > 0:
            last_row = rows[-1]
            return {
                "dollar_price":    float(last_row[2]) if len(last_row) > 2 else None,
                "shams_price":    float(last_row[3]) if len(last_row) > 3 else None,
                "gold_price":     float(last_row[1]) if len(last_row) > 1 else None,
                "ekhtelaf_sarane":float(last_row[10]) if len(last_row) > 10 else None,
            }
    except Exception as e:
        logger.error(f"خطا در خواندن وضعیت قبلی: {e}")
    return {"dollar_price": None, "shams_price": None, "gold_price": None, "ekhtelaf_sarane": None}


# ────────────────── ارسال اصلی به تلگرام ──────────────────
def send_to_telegram(bot_token, chat_id, data, dollar_prices, gold_price, gold_yesterday, gold_time, yesterday_close):
    if data is None:
        logger.error("داده‌ها None است")
        return False

    try:
        img1_bytes = create_combined_image(data["Fund_df"], dollar_prices["last_trade"], gold_price, gold_yesterday, data["dfp"], yesterday_close)
        img2_bytes = create_market_charts()
        caption = create_simple_caption(data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time)

        # هشدارها
        check_and_send_alerts(bot_token, chat_id, data, dollar_prices, gold_price, yesterday_close, gold_yesterday)

        # مدیریت پیام پین‌شده
        gist_data = get_gist_data()
        saved_message_id = gist_data.get("message_id")
        saved_date = gist_data.get("date")
        today = get_today_date()

        if saved_date != today:
            saved_message_id = None

        if saved_message_id:
            if update_media_group_correctly(bot_token, chat_id, saved_message_id, img1_bytes, img2_bytes, caption):
                return True

        new_message_id = send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption)
        if new_message_id:
            save_gist_data(new_message_id, today)
            pin_message(bot_token, chat_id, new_message_id)
            return True
        return False

    except Exception as e:
        logger.error(f"خطا در ارسال به تلگرام: {e}", exc_info=True)
        return False


# ────────────────── MediaGroup ──────────────────
def send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"
        files = {
            "photo1": ("treemap.png", io.BytesIO(img1_bytes), "image/png"),
            "photo2": ("charts.png", io.BytesIO(img2_bytes), "image/png"),
        }
        media = [
            {"type": "photo", "media": "attach://photo1", "caption": caption, "parse_mode": "HTML"},
            {"type": "photo", "media": "attach://photo2"},
        ]
        response = requests.post(url, files=files, data={"chat_id": chat_id, "media": json.dumps(media)}, timeout=60)
        if response.status_code == 200:
            return response.json()["result"][0]["message_id"]
    except Exception as e:
        logger.error(f"خطا در sendMediaGroup: {e}")
    return None

def update_media_group_correctly(bot_token, chat_id, first_message_id, img1_bytes, img2_bytes, caption):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/editMessageMedia"

        # عکس اول
        media1 = {"type": "photo", "media": "attach://photo1", "caption": caption, "parse_mode": "HTML"}
        files1 = {"photo1": ("treemap.png", io.BytesIO(img1_bytes), "image/png")}
        r1 = requests.post(url, data={
            "chat_id": chat_id,
            "message_id": first_message_id,
            "media": json.dumps(media1)
        }, files=files1, timeout=30)

        # عکس دوم
        media2 = {"type": "photo", "media": "attach://photo2"}
        files2 = {"photo2": ("charts.png", io.BytesIO(img2_bytes), "image/png")}
        r2 = requests.post(url, data={
            "chat_id": chat_id,
            "message_id": first_message_id + 1,
            "media": json.dumps(media2)
        }, files=files2, timeout=30)

        return r1.ok and r2.ok
    except Exception as e:
        logger.error(f"خطا در آپدیت عکس‌ها: {e}")
        return False

def pin_message(bot_token, chat_id, message_id):
    try:
        requests.post(f"https://api.telegram.org/bot{bot_token}/pinChatMessage",
                      data={"chat_id": chat_id, "message_id": message_id, "disable_notification": True}, timeout=30)
    except Exception as e:
        logger.error(f"خطا در پین: {e}")


# ────────────────── هسته هشدارها (فرمت نهایی تو) ──────────────────
def check_and_send_alerts(bot_token, chat_id, data, dollar_prices, gold_price, yesterday_close, gold_yesterday):
    prev = get_previous_state_from_sheet()
    status = get_alert_status()

    current_dollar = dollar_prices["last_trade"]
    current_shams  = data["dfp"].loc["شمش-طلا", "close_price"] if "شمش-طلا" in data["dfp"].index else 0
    current_gold   = gold_price

    df_funds = data["Fund_df"]
    total_value = df_funds["value"].sum()
    current_ekhtelaf = (df_funds["ekhtelaf_sarane"] * df_funds["value"]).sum() / total_value if total_value > 0 else 0

    changed = False

    # تغییر سریع دلار
    if prev["dollar_price"] and prev["dollar_price"] > 0:
        change_5min = (current_dollar - prev["dollar_price"]) / prev["dollar_price"] * 100
        if abs(change_5min) >= ALERT_THRESHOLD_PERCENT:
            send_alert_dollar_fast(bot_token, chat_id, current_dollar, change_5min)

    # اختلاف سرانه
    if prev["ekhtelaf_sarane"] is not None:
        diff_ekhtelaf = current_ekhtelaf - prev["ekhtelaf_sarane"]
        if abs(diff_ekhtelaf) >= EKHTELAF_THRESHOLD:
            send_alert_ekhtelaf_fast(bot_token, chat_id, prev["ekhtelaf_sarane"], current_ekhtelaf,
                                     diff_ekhtelaf, df_funds["pol_hagigi"].sum())

    # هشدار قیمتی دلار
    if current_dollar >= DOLLAR_HIGH and status["dollar"] == "normal":
        send_alert_threshold("دلار", current_dollar, DOLLAR_HIGH, above=True, bot_token=bot_token, chat_id=chat_id)
        status["dollar"] = "above"; changed = True
    elif current_dollar < DOLLAR_LOW and status["dollar"] == "normal":
        send_alert_threshold("دلار", current_dollar, DOLLAR_LOW, above=False, bot_token=bot_token, chat_id=chat_id)
        status["dollar"] = "below"; changed = True
    elif DOLLAR_LOW <= current_dollar < DOLLAR_HIGH and status["dollar"] != "normal":
        status["dollar"] = "normal"; changed = True

    # شمش طلا
    if current_shams >= SHAMS_HIGH and status["shams"] == "normal":
        send_alert_threshold("شمش طلا", current_shams, SHAMS_HIGH, above=True, bot_token=bot_token, chat_id=chat_id)
        status["shams"] = "above"; changed = True
    elif current_shams < SHAMS_LOW and status["shams"] == "normal":
        send_alert_threshold("شمش طلا", current_shams, SHAMS_LOW, above=False, bot_token=bot_token, chat_id=chat_id)
        status["shams"] = "below"; changed = True
    elif SHAMS_LOW <= current_shams < SHAMS_HIGH and status["shams"] != "normal":
        status["shams"] = "normal"; changed = True

    # اونس طلا
    if current_gold >= GOLD_HIGH and status["gold"] == "normal":
        send_alert_threshold("اونس طلا", current_gold, GOLD_HIGH, above=True, bot_token=bot_token, chat_id=chat_id)
        status["gold"] = "above"; changed = True
    elif current_gold < GOLD_LOW and status["gold"] == "normal":
        send_alert_threshold("اونس طلا", current_gold, GOLD_LOW, above=False, bot_token=bot_token, chat_id=chat_id)
        status["gold"] = "below"; changed = True
    elif GOLD_LOW <= current_gold < GOLD_HIGH and status["gold"] != "normal":
        status["gold"] = "normal"; changed = True

    if changed:
        save_alert_status(status)


# ────────────────── پیام‌های هشدار (فرمت دقیق تو) ──────────────────
def send_alert_dollar_fast(bot_token, chat_id, price, change_5min):
    change_text = f"{change_5min:+.2f}%".replace("+-", "−")
    caption = f"""
هشدار تغییر سریع دلار (۵ دقیقه)

قیمت: {int(round(price)):,} تومان
تغییر: {change_text}

@Gold_Iran_Market
""".strip()
    send_alert_message(bot_token, chat_id, caption)

def send_alert_ekhtelaf_fast(bot_token, chat_id, prev_val, curr_val, diff, pol_hagigi):
    direction = "افزایش شدید (مثبت)" if diff > 0 else "کاهش شدید (منفی)"
    diff_text = f"{diff:+.1f}".replace("+-", "−")
    pol_text  = f"{pol_hagigi:+,.0f}".replace("+-", "−")
    caption = f"""
هشدار اختلاف سرانه

{direction}
تغییر ۵ دقیقه: {diff_text} میلیون تومان
ورود پول حقیقی: {pol_text} میلیارد تومان

@Gold_Iran_Market
""".strip()
    send_alert_message(bot_token, chat_id, caption)

def send_alert_threshold(asset, price, threshold, above, bot_token, chat_id):
    direction = "بالای" if above else "زیر"
    unit = "تومان" if asset == "دلار" else "ریال" if asset == "شمش طلا" else "دلار"
    caption = f"""
هشدار قیمتی

قیمت {asset} به {direction} {threshold:,} رسید.
قیمت فعلی: {int(round(price)):,} {unit}

@Gold_Iran_Market
""".strip()
    send_alert_message(bot_token, chat_id, caption)

def send_alert_message(bot_token, chat_id, caption):
    try:
        requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage",
                      data={"chat_id": chat_id, "text": caption, "parse_mode": "HTML"}, timeout=30)
        logger.info("هشدار ارسال شد")
    except Exception as e:
        logger.error(f"خطا در ارسال هشدار: {e}")


# ────────────────── ساخت تصویر ترکیبی (دقیقاً کد اصلی تو) ──────────────────
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


# ────────────────── کپشن اصلی (دقیقاً کد خودت) ──────────────────
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
آخرین آپدیت: {current_time}

━━━━━━━━━━━━━━━━━━━━━━━━
<b>دلار</b>
آخرین معامله: <b>{dollar_prices['last_trade']:,} تومان</b> ({dollar_change:+.2f}%)
خرید: {dollar_prices['bid']:,} | فروش: {dollar_prices['ask']:,}
━━━━━━━━━━━━━━━━━━━━━━━━
<b>اونس طلا </b>
قیمت: <b>${gold_price:,.2f}</b> ({gold_change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━━━━━
<b>آمار صندوق‌های طلا</b>
ارزش معاملات: <b>{total_value:,.0f}</b> میلیارد تومان
ورود پول حقیقی: <b>{total_pol:+,.0f}</b> میلیارد تومان
پول حقیقی به ارزش معاملات: <b>{pol_to_value_ratio:+.0f}%</b>
آخرین قیمت: <b>{avg_price_weighted:,.0f}</b> ({avg_change_percent_weighted:+.2f}%)
میانگین حباب: <b>{avg_bubble_weighted:+.2f}%</b>
━━━━━━━━━━━━━━━━━━━━━━━━
<b>شمش طلا</b>
قیمت: <b>{shams['close_price']:,}</b> ریال
تغییر: {shams['close_price_change_percent']:+.2f}% | حباب: {shams['Bubble']:+.2f}%
دلار محاسباتی: {d_shams:,.0f} ({diff_shams:+,.0f})
اونس محاسباتی: ${o_shams:,.0f} ({diff_o_shams:+.0f})

<b>طلا ۲۴ عیار</b>
قیمت: <b>{gold_24_price:,.0f}</b> تومان
تغییر: {gold_24['close_price_change_percent']:+.2f}% | حباب: {gold_24['Bubble']:+.2f}%
دلار محاسباتی: {d_24:,.0f} ({diff_24:+,.0f})

<b>طلا ۱۸ عیار</b>
قیمت: <b>{gold_18_price:,.0f}</b> تومان
تغییر: {gold_18['close_price_change_percent']:+.2f}% | حباب: {gold_18['Bubble']:+.2f}%
دلار محاسباتی: {d_18:,.0f} ({diff_18:+,.0f})

<b>سکه امامی</b>
قیمت: <b>{sekeh_price:,.0f}</b> تومان
تغییر: {sekeh['close_price_change_percent']:+.2f}% | حباب: {sekeh['Bubble']:+.2f}%
دلار محاسباتی: {d_sekeh:,.0f} ({diff_sekeh:+,.0f})
━━━━━━━━━━━━━━━━━━━━━━━━
<a href='https://t.me/Gold_Iran_Market'>@Gold_Iran_Market</a>
"""
    return caption.strip()
