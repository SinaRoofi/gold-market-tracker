# utils/telegram_sender.py
"""ماژول ارسال داده‌ها به تلگرام"""

import io
import json
import logging
import requests
import pytz
from datetime import datetime
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from persiantools.jdatetime import JalaliDateTime
from PIL import Image, ImageDraw, ImageFont

from config import (
    GIST_ID, GIST_TOKEN, MESSAGE_ID_FILE,
    FONT_BOLD_PATH, FONT_MEDIUM_PATH, FONT_REGULAR_PATH,
    TREEMAP_WIDTH, TREEMAP_HEIGHT, TREEMAP_SCALE,
    TREEMAP_COLORSCALE, CHANNEL_HANDLE,
    REQUEST_TIMEOUT, TIMEZONE
)
from utils.chart_creator import create_market_charts

logger = logging.getLogger(__name__)

# ────────────────── توابع Gist (message_id) ──────────────────

def get_gist_data():
    """دریافت message_id از GitHub Gist"""
    try:
        if not GIST_ID or not GIST_TOKEN:
            return {"message_id": None, "date": None}
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            content = response.json()["files"][MESSAGE_ID_FILE]["content"]
            return json.loads(content)
    except Exception as e:
        logger.error(f"خطا در خواندن Gist: {e}")
        return {"message_id": None, "date": None}


def save_gist_data(message_id, date):
    """ذخیره message_id در GitHub Gist"""
    try:
        url = f"https://api.github.com/gists/{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        data = {
            "files": {
                MESSAGE_ID_FILE: {
                    "content": json.dumps({"message_id": message_id, "date": date})
                }
            }
        }
        requests.patch(url, headers=headers, json=data, timeout=REQUEST_TIMEOUT)
    except Exception as e:
        logger.error(f"خطا در ذخیره Gist: {e}")


def get_today_date():
    """دریافت تاریخ امروز به فرمت YYYY-MM-DD"""
    return datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")


# ────────────────── ارسال اصلی به تلگرام ──────────────────

def send_to_telegram(bot_token, chat_id, data, dollar_prices, gold_price, 
                     gold_yesterday, gold_time, yesterday_close):
    """
    ارسال داده‌ها به کانال تلگرام
    
    Args:
        bot_token: توکن ربات
        chat_id: شناسه چت
        data: داده‌های پردازش شده
        dollar_prices: قیمت‌های دلار
        gold_price: قیمت طلا
        gold_yesterday: قیمت طلای دیروز
        gold_time: زمان قیمت طلا
        yesterday_close: قیمت بسته دیروز
    
    Returns:
        bool: موفقیت ارسال
    """
    if data is None:
        logger.error("❌ داده‌ها None است")
        return False

    try:
        # ساخت تصاویر
        logger.info("🎨 در حال ساخت تصویر Treemap...")
        img1_bytes = create_combined_image(
            data["Fund_df"], 
            dollar_prices["last_trade"], 
            gold_price, 
            gold_yesterday, 
            data["dfp"], 
            yesterday_close
        )

        logger.info("📊 در حال ساخت نمودارهای بازار...")
        img2_bytes = create_market_charts()

        # ساخت کپشن
        logger.info("📝 در حال ساخت کپشن...")
        caption = create_simple_caption(
            data, 
            dollar_prices, 
            gold_price, 
            gold_yesterday, 
            yesterday_close, 
            gold_time
        )

        # مدیریت پیام پین‌شده
        gist_data = get_gist_data()
        saved_message_id = gist_data.get("message_id")
        saved_date = gist_data.get("date")
        today = get_today_date()

        # اگر تاریخ عوض شده، message_id رو ریست کن
        if saved_date != today:
            logger.info(f"📅 روز جدید ({today}) - ریست message_id")
            saved_message_id = None

        # اگر message_id داریم، سعی کن آپدیت کنی
        if saved_message_id:
            logger.info(f"🔄 در حال آپدیت پیام پین‌شده (ID: {saved_message_id})...")
            if update_media_group_correctly(bot_token, chat_id, saved_message_id, 
                                           img1_bytes, img2_bytes, caption):
                logger.info("✅ پیام پین‌شده آپدیت شد")
                return True
            else:
                logger.warning("⚠️ آپدیت پیام ناموفق بود، پیام جدید ارسال می‌شود")

        # اگر آپدیت نشد، پیام جدید بفرست
        logger.info("📤 ارسال پیام جدید...")
        new_message_id = send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption)
        if new_message_id:
            save_gist_data(new_message_id, today)
            pin_message(bot_token, chat_id, new_message_id)
            logger.info(f"✅ پیام جدید ارسال و پین شد (ID: {new_message_id})")
            return True

        logger.error("❌ ارسال پیام ناموفق بود")
        return False

    except Exception as e:
        logger.error(f"❌ خطا در ارسال به تلگرام: {e}", exc_info=True)
        return False


# ────────────────── MediaGroup ──────────────────

def send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption):
    """ارسال MediaGroup (دو عکس) به تلگرام"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"
        files = {
            "photo1": ("treemap.png", io.BytesIO(img1_bytes), "image/png"),
            "photo2": ("charts.png", io.BytesIO(img2_bytes), "image/png"),
        }
        media = [
            {
                "type": "photo", 
                "media": "attach://photo1", 
                "caption": caption, 
                "parse_mode": "HTML"
            },
            {
                "type": "photo", 
                "media": "attach://photo2"
            },
        ]
        response = requests.post(
            url, 
            files=files, 
            data={"chat_id": chat_id, "media": json.dumps(media)}, 
            timeout=60
        )
        if response.status_code == 200:
            return response.json()["result"][0]["message_id"]
        else:
            logger.error(f"خطای ارسال MediaGroup: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"خطا در sendMediaGroup: {e}")
    return None


def update_media_group_correctly(bot_token, chat_id, first_message_id, 
                                 img1_bytes, img2_bytes, caption):
    """آپدیت کردن MediaGroup موجود"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/editMessageMedia"

        # آپدیت عکس اول (با کپشن)
        media1 = {
            "type": "photo", 
            "media": "attach://photo1", 
            "caption": caption, 
            "parse_mode": "HTML"
        }
        files1 = {"photo1": ("treemap.png", io.BytesIO(img1_bytes), "image/png")}
        r1 = requests.post(
            url, 
            data={
                "chat_id": chat_id,
                "message_id": first_message_id,
                "media": json.dumps(media1)
            }, 
            files=files1, 
            timeout=REQUEST_TIMEOUT
        )

        # آپدیت عکس دوم
        media2 = {"type": "photo", "media": "attach://photo2"}
        files2 = {"photo2": ("charts.png", io.BytesIO(img2_bytes), "image/png")}
        r2 = requests.post(
            url, 
            data={
                "chat_id": chat_id,
                "message_id": first_message_id + 1,
                "media": json.dumps(media2)
            }, 
            files=files2, 
            timeout=REQUEST_TIMEOUT
        )

        if not r1.ok:
            logger.warning(f"خطای آپدیت عکس اول: {r1.status_code} - {r1.text}")
        if not r2.ok:
            logger.warning(f"خطای آپدیت عکس دوم: {r2.status_code} - {r2.text}")

        return r1.ok and r2.ok

    except Exception as e:
        logger.error(f"خطا در آپدیت عکس‌ها: {e}")
        return False


def pin_message(bot_token, chat_id, message_id):
    """پین کردن پیام در کانال"""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/pinChatMessage",
            data={
                "chat_id": chat_id, 
                "message_id": message_id, 
                "disable_notification": True
            }, 
            timeout=REQUEST_TIMEOUT
        )
        if response.status_code == 200:
            logger.info("📌 پیام پین شد")
        else:
            logger.warning(f"⚠️ خطای پین: {response.status_code}")
    except Exception as e:
        logger.error(f"خطا در پین: {e}")


# ────────────────── ساخت تصویر ترکیبی ──────────────────

def create_combined_image(Fund_df, last_trade, Gold, Gold_yesterday, dfp, yesterday_close):
    """ساخت تصویر Treemap + Table"""
    tehran_tz = pytz.timezone(TIMEZONE)
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

    # بارگذاری فونت
    try:
        ImageFont.truetype(FONT_MEDIUM_PATH, 40)
        treemap_font_family = "Vazirmatn-Medium, sans-serif"
    except:
        treemap_font_family = "sans-serif"

    # Treemap
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
                colorscale=TREEMAP_COLORSCALE,
                cmid=0,
                cmin=-10,
                cmax=10,
                line=dict(width=3, color="#1A1A1A"),
            ),
            pathbar=dict(visible=False),
        ),
        row=1, col=1,
    )

    # جدول 10 صندوق برتر
    top_10 = df_sorted.head(10)
    table_header = [
        "نماد", "قیمت", "NAV", "تغییر %", "حباب %", 
        "اختلاف سرانه", "پول حقیقی", "ارزش معاملات"
    ]
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
        ["#1C2733"] * 10,
        ["#1C2733"] * 10,
        ["#1C2733"] * 10,
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
                fill_color="#242F3D",
                align="center",
                font=dict(color="white", size=20, family=treemap_font_family),
                height=38,
            ),
            cells=dict(
                values=table_cells,
                fill_color=cell_colors,
                align="center",
                font=dict(color="white", size=18, family=treemap_font_family),
                height=36,
            ),
        ),
        row=2, col=1,
    )

    fig.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=TREEMAP_HEIGHT,
        width=TREEMAP_WIDTH,
        margin=dict(t=140, l=20, r=20, b=20),
        title=dict(
            text="<b>نقشه بازار صندوق‌های طلا</b>",
            font=dict(size=35, color="#FFD700"),
            x=0.5, y=0.96,
            xanchor="center",
            yanchor="top",
        ),
        showlegend=False,
    )

    # تبدیل به تصویر
    img_bytes = fig.to_image(
        format="png", 
        width=TREEMAP_WIDTH, 
        height=TREEMAP_HEIGHT, 
        scale=TREEMAP_SCALE
    )
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # اضافه کردن متن‌ها
    try:
        font_date = ImageFont.truetype(FONT_BOLD_PATH, 64)
        font_desc = ImageFont.truetype(FONT_MEDIUM_PATH, 50)
    except:
        font_date = font_desc = ImageFont.load_default()

    draw.text((60, 35), date_time_str, font=font_date, fill="#FFFFFF")
    draw.text((60, 110), "اندازه: ارزش معاملات", font=font_desc, fill="#FFFFFF")

    # واترمارک
    try:
        wfont = ImageFont.truetype(FONT_REGULAR_PATH, 70)
    except:
        wfont = ImageFont.load_default()

    wtext = CHANNEL_HANDLE.replace("@", "")
    bbox = draw.textbbox((0, 0), wtext, font=wfont)
    w, h = bbox[2] - bbox[0] + 80, bbox[3] - bbox[1] + 80
    txt_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(txt_img).text((40, 40), wtext, font=wfont, fill=(255, 255, 255, 100))
    rotated = txt_img.rotate(45, expand=True)
    img.paste(rotated, ((img.width - rotated.width) // 2, (img.height - rotated.height) // 2), rotated)

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True, quality=92)
    output.seek(0)
    return output.getvalue()


# ────────────────── کپشن اصلی ──────────────────

def create_simple_caption(data, dollar_prices, gold_price, gold_yesterday, 
                         yesterday_close, gold_time):
    """ساخت کپشن برای پست تلگرام"""
    tehran_tz = pytz.timezone(TIMEZONE)
    now = JalaliDateTime.now(tehran_tz)
    current_time = now.strftime("%Y/%m/%d - %H:%M")

    df_funds = data["Fund_df"]
    total_value = df_funds["value"].sum()
    total_pol = df_funds["pol_hagigi"].sum()

    # محاسبه میانگین ماهانه کل صندوق‌ها
    total_avg_monthly = df_funds["avg_monthly_value"].sum()

    if total_value > 0:
        avg_price_weighted = (df_funds["close_price"] * df_funds["value"]).sum() / total_value
        avg_change_percent_weighted = (df_funds["close_price_change_percent"] * df_funds["value"]).sum() / total_value
        avg_bubble_weighted = (df_funds["nominal_bubble"] * df_funds["value"]).sum() / total_value
    else:
        avg_price_weighted = avg_change_percent_weighted = avg_bubble_weighted = 0

    # محاسبه نسبت ارزش معاملات به میانگین ماهانه
    if total_avg_monthly > 0:
        value_to_avg_ratio = (total_value / total_avg_monthly) * 100
    else:
        value_to_avg_ratio = 0

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
🔄 آخرین آپدیت: {current_time}

━━━━━━━━━━━━━━━━━━━━━━━━
💵 دلار
💰 آخرین معامله: {dollar_prices['last_trade']:,} تومان ({dollar_change:+.2f}%)
🟢 خرید: {dollar_prices['bid']:,} | 🔴 فروش: {dollar_prices['ask']:,}
━━━━━━━━━━━━━━━━━━━━━━━━
🔆 اونس طلا 
💰 قیمت: ${gold_price:,.2f} ({gold_change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━━━━━
📊 آمار صندوق‌های طلا
💰 ارزش معاملات: B{total_value:,.0f} ({value_to_avg_ratio:.0f}%)
💸 پول حقیقی: B{total_pol:+,.0f} ({pol_to_value_ratio:+.0f}%)
📈 آخرین قیمت: {avg_price_weighted:,.0f} ({avg_change_percent_weighted:+.2f}%)
🎈 میانگین حباب: {avg_bubble_weighted:+.2f}%
━━━━━━━━━━━━━━━━━━━━━━━━
✨ شمش طلا
💰 قیمت: {shams['close_price']:,} ریال
📊 تغییر: {shams['close_price_change_percent']:+.2f}% | حباب: {shams['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_shams:,.0f} ({diff_shams:+,.0f})
🔆 اونس محاسباتی: ${o_shams:,.0f} ({diff_o_shams:+.0f})

🔸 طلا ۲۴ عیار
💰 قیمت: {gold_24_price:,.0f} تومان
📊 تغییر: {gold_24['close_price_change_percent']:+.2f}% | حباب: {gold_24['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_24:,.0f} ({diff_24:+,.0f})

🔸 طلا ۱۸ عیار
💰 قیمت: {gold_18_price:,.0f} تومان
📊 تغییر: {gold_18['close_price_change_percent']:+.2f}% | حباب: {gold_18['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_18:,.0f} ({diff_18:+,.0f})

🪙 سکه امامی
💰 قیمت: {sekeh_price:,.0f} تومان
📊 تغییر: {sekeh['close_price_change_percent']:+.2f}% | حباب: {sekeh['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_sekeh:,.0f} ({diff_sekeh:+,.0f})
━━━━━━━━━━━━━━━━━━━━━━━━
🔗 {CHANNEL_HANDLE}
"""
    return caption.strip()