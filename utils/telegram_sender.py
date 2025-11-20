import io
import logging
import json
import requests
import pytz
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from persiantools.jdatetime import JalaliDateTime
from PIL import Image, ImageDraw, ImageFont
from utils.chart_creator import create_market_charts

logger = logging.getLogger(__name__)
pd.set_option('future.no_silent_downcasting', True)


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
        logger.error("داده‌های پردازش‌شده (data) مقدار None دارد. ارسال متوقف شد.")
        return False

    try:
        img1_bytes = create_combined_image(
            data["Fund_df"],
            dollar_prices["last_trade"],
            gold_price,
            gold_yesterday,
            data["dfp"],
            yesterday_close,
        )

        img2_bytes = create_market_charts()

        caption = create_simple_caption(
            data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
        )

        if img2_bytes:
            return send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption)
        else:
            logger.warning("نمودارها موجود نیست، فقط تصویر اول ارسال می‌شود")
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": ("market_report.png", io.BytesIO(img1_bytes), "image/png")}
            params = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            response = requests.post(url, files=files, data=params, timeout=60)
            return response.status_code == 200

    except Exception as e:
        logger.error(f"خطا در ارسال به تلگرام: {e}", exc_info=True)
        return False


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
        return response.status_code == 200
    except Exception as e:
        logger.error(f"خطا در ارسال Media Group: {e}", exc_info=True)
        return False


def create_combined_image(Fund_df, last_trade, Gold, Gold_yesterday, dfp, yesterday_close):
    """نقشه + جدول حرفه‌ای با فونت Vazirmatn-Medium از assets + رنگ‌های شیک و هدر زیبا"""

    # تاریخ و ساعت شمسی
    tehran_tz = pytz.timezone("Asia/Tehran")
    now_jalali = JalaliDateTime.now(tehran_tz)
    date_time_str = now_jalali.strftime("%Y/%m/%d - %H:%M")

    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.025,
        specs=[[{"type": "treemap"}], [{"type": "table"}]],
    )

    df = Fund_df.copy()
    df["color_value"] = df["close_price_change_percent"].fillna(0)
    df["display_text"] = df.apply(lambda row: f"\u202B<b>{row.name}</b>\u202C", axis=1)
    df = df.sort_values("value", ascending=False)

    # استفاده از فونت Vazirmatn-Medium برای Treemap و جدول
    try:
        ImageFont.truetype("assets/fonts/Vazirmatn-Medium.ttf", 40)
        font_family = "Vazirmatn-Medium, sans-serif"
    except:
        font_family = "sans-serif"

    # Treemap
    fig.add_trace(go.Treemap(
        labels=df.index,
        parents=[""] * len(df),
        values=df["value"],
        text=df["display_text"],
        textinfo="text",
        textposition="middle center",
        textfont=dict(size=25, color="white", family=font_family),
        marker=dict(
            colors=df["color_value"],
            colorscale=[
                [0.0, "#cc4444"],   # قرمز ملایم
                [0.4, "#aa6666"],
                [0.5, "#222222"],
                [0.6, "#448844"],
                [1.0, "#006633"],   # سبز تیره و شیک
            ],
            cmid=0, cmin=-10, cmax=10,
            line=dict(width=3, color="#000000"),
        ),
        pathbar=dict(visible=False),
        hoverinfo="skip",
    ), row=1, col=1)

    # جدول ۱۰ تایی
    top10 = df.head(10)
    headers = ["نماد", "قیمت", "NAV", "تغییر %", "حباب %", "اختلاف سرانه", "پول حقیقی", "ارزش معاملات"]

    cells = [
        top10.index.tolist(),
        [f"{x:,.0f}" for x in top10["close_price"]],
        [f"{x:,.0f}" for x in top10["NAV"]],
        [f"{x:+.2f}%" for x in top10["close_price_change_percent"]],
        [f"{x:+.2f}%" for x in top10["nominal_bubble"]],
        [f"{x:+.2f}" if pd.notna(x) and x != 0 else "۰" for x in top10.get("ekhtelaf_sarane", [0]*10)],
        [f"{x:+,.0f}" for x in top10["pol_hagigi"]],
        [f"{x:,.0f}" for x in top10["value"]],
    ]

    # رنگ پس‌زمینه سلول‌ها — سبز تیره‌تر، قرمز ملایم‌تر
    def cell_bg(val):
        try:
            n = float(str(val).replace("%","").replace("+","").replace(",","").replace("-",""))
            if n > 0:
                return "#004d26"    # سبز تیره خیلی شیک
            elif n < 0:
                return "#663333"    # قرمز ملایم و لوکس
            else:
                return "#1e1e1e"
        except:
            return "#1e1e1e"

    cell_colors = [
        ["#1e1e1e"]*10,
        ["#1e1e1e"]*10,
        ["#1e1e1e"]*10,
        [cell_bg(v) for v in cells[3]],
        [cell_bg(v) for v in cells[4]],
        [cell_bg(v) for v in cells[5]],
        [cell_bg(v) for v in cells[6]],
        ["#1e1e1e"]*10,
    ]

    # جدول با هدر فوق‌العاده زیبا
    fig.add_trace(go.Table(
        header=dict(
            values=[f"<b>{h}</b>" for h in headers],
            fill_color="#008855",          # سبز زمردی درخشان — هدر
            font=dict(color="#FFFFFF", size=23, family=font_family),
            height=52,
            align="center"
        ),
        cells=dict(
            values=cells,
            fill_color=cell_colors,
            font=dict(color="#FFFFFF", size=19, family=font_family),
            height=42,
            align="center"
        )
    ), row=2, col=1)

    fig.update_layout(
        height=1380, width=1380,
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        margin=dict(t=150, l=20, r=20, b=20),
        title=dict(
            text="<b>نقشه بازار صندوق‌های طلا</b>",
            font=dict(size=36, color="#FFD700", family=font_family),
            x=0.5, y=0.96, xanchor="center", yanchor="top"
        ),
        showlegend=False,
    )

    # تولید تصویر
    img_bytes = fig.to_image(format="png", width=1380, height=1380, scale=2.2)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # تاریخ و توضیح با فونت وزیر
    try:
        font_date = ImageFont.truetype("assets/fonts/Vazirmatn-Bold.ttf", 66)
        font_desc = ImageFont.truetype("assets/fonts/Vazirmatn-Medium.ttf", 52)
    except:
        font_date = font_desc = ImageFont.load_default()

    draw.text((65, 32), date_time_str, font=font_date, fill="#FFFFFF")
    draw.text((65, 108), "اندازه: ارزش معاملات", font=font_desc, fill="#FFFFFF")

    # واترمارک
    overlay = Image.new("RGBA", img.size, (0,0,0,0))
    d = ImageDraw.Draw(overlay)
    try:
        wf = ImageFont.truetype("assets/fonts/Vazirmatn-Regular.ttf", 75)
    except:
        wf = ImageFont.load_default()
    txt = "Gold_Iran_Market"
    bbox = d.textbbox((0,0), txt, font=wf)
    w = bbox[2]-bbox[0] + 100
    h = bbox[3]-bbox[1] + 100
    txtimg = Image.new("RGBA", (w,h), (0,0,0,0))
    td = ImageDraw.Draw(txtimg)
    td.text((50,50), txt, font=wf, fill=(255,255,255,100))
    rotated = txtimg.rotate(45, expand=True)
    img.paste(rotated, ((img.width-rotated.width)//2, (img.height-rotated.height)//2), rotated)

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True, quality=95)
    out.seek(0)
    return out.getvalue()


def create_simple_caption(
    data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
):
    tehran_tz = pytz.timezone("Asia/Tehran")
    now = JalaliDateTime.now(tehran_tz)
    current_time = now.strftime("%Y/%m/%d - %H:%M:%S")

    df_funds = data["Fund_df"]
    total_value = df_funds["value"].sum()
    total_pol = df_funds["pol_hagigi"].sum()

    if total_value > 0:
        avg_price_weighted = (df_funds["close_price"] * df_funds["value"]).sum() / total_value
        avg_change_percent_weighted = (df_funds["close_price_change_percent"] * df_funds["value"]).sum() / total_value
        avg_bubble_weighted = (df_funds["nominal_bubble"] * df_funds["value"]).sum() / total_value
    else:
        avg_price_weighted = avg_change_percent_weighted = avg_bubble_weighted = 0

    dollar_change = ((dollar_prices["last_trade"] - yesterday_close) / yesterday_close * 100) if yesterday_close and yesterday_close != 0 else 0
    gold_change = ((gold_price - gold_yesterday) / gold_yesterday * 100) if gold_yesterday and gold_yesterday != 0 else 0

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
📅 <b>{current_time}</b>

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