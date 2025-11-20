import io
import logging
import json
import requests
import pytz
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from persiantools.jdatetime import JalaliDateTime
from PIL import Image, ImageDraw, ImageFont
from utils.chart_creator import create_market_charts

logger = logging.getLogger(__name__)
FONT_BIG = 20


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
    """
    مدیریت کلی تولید تصاویر و کپشن و ارسال به تلگرام
    """
    if data is None:
        logger.error("❌ داده‌های پردازش‌شده (data) مقدار None دارد. ارسال متوقف شد.")
        return False

    try:
        # 1. ایجاد تصویر اول (Treemap + جدول + تاریخ سفید)
        img1_bytes = create_combined_image(
            data["Fund_df"],
            dollar_prices["last_trade"],
            gold_price,
            gold_yesterday,
            data["dfp"],
            yesterday_close,
        )

        # 2. ایجاد تصویر دوم (نمودارها)
        img2_bytes = create_market_charts()

        # 3. ایجاد کپشن
        caption = create_simple_caption(
            data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
        )

        # 4. ارسال
        if img2_bytes:
            return send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption)
        else:
            logger.warning("⚠️ نمودارها موجود نیست، فقط تصویر اول ارسال می‌شود")
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": ("market_report.png", io.BytesIO(img1_bytes), "image/png")}
            params = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}

            response = requests.post(url, files=files, data=params, timeout=60)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"❌ خطا در ارسال تک عکس: {response.text}")
                return False

    except Exception as e:
        logger.error(f"❌ خطا در فرآیند ارسال به تلگرام: {e}", exc_info=True)
        return False


def send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption):
    """ارسال 2 عکس + کپشن به صورت Media Group"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"
        files = {
            "photo1": ("market_treemap.png", io.BytesIO(img1_bytes), "image/png"),
            "photo2": ("market_charts.png", io.BytesIO(img2_bytes), "image/png"),
        }
        media = [
            {
                "type": "photo",
                "media": "attach://photo1",
                "caption": caption,
                "parse_mode": "HTML",
            },
            {"type": "photo", "media": "attach://photo2"},
        ]
        data_payload = {"chat_id": chat_id, "media": json.dumps(media)}
        response = requests.post(url, files=files, data=data_payload, timeout=60)
        if response.status_code == 200:
            logger.info("✅ Media Group ارسال شد")
            return True
        else:
            logger.error(f"❌ خطا در ارسال Media Group: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در ارسال Media Group: {e}", exc_info=True)
        return False


def create_combined_image(
    Fund_df, last_trade, Gold, Gold_yesterday, dfp, yesterday_close
):
    """تولید تصویر ترکیبی Treemap + جدول + تاریخ و توضیح سفید در بالا چپ"""
    
    # تاریخ و ساعت شمسی
    tehran_tz = pytz.timezone("Asia/Tehran")
    now_jalali = JalaliDateTime.now(tehran_tz)
    date_time_str = now_jalali.strftime("%Y/%m/%d - %H:%M")

    # ساخت نمودار
    fig = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.02,
        specs=[[{"type": "treemap"}], [{"type": "table"}]],
    )

    df_sorted = Fund_df.copy()
    df_sorted["color_value"] = df_sorted["close_price_change_percent"].fillna(0)

    # متن RTL ایمن برای Treemap
    df_sorted["display_text"] = df_sorted.apply(lambda row: f"\u202B<b>{row.name}</b>\u202C", axis=1)
    df_sorted = df_sorted.sort_values("value", ascending=False)

    colorscale = [
        [0.0, "#E57373"], [0.1, "#D85C5C"], [0.2, "#C94444"],
        [0.3, "#A52A2A"], [0.4, "#6B1A1A"], [0.5, "#2C2C2C"],
        [0.6, "#1B5E20"], [0.7, "#2E7D32"], [0.8, "#43A047"],
        [0.9, "#5CB860"], [1.0, "#66BB6A"],
    ]

    fig.add_trace(
        go.Treemap(
            labels=df_sorted.index,
            parents=[""] * len(df_sorted),
            values=df_sorted["value"],
            text=df_sorted["display_text"],
            textinfo="text",
            textposition="middle center",
            textfont=dict(size=22, color="white"),
            hoverinfo="skip",
            marker=dict(
                colors=df_sorted["color_value"],
                colorscale=colorscale,
                cmid=0,
                cmin=-10,
                cmax=10,
                line=dict(width=3, color="#1A1A1A"),
            ),
            pathbar=dict(visible=False),
        ),
        row=1, col=1
    )

    # جدول ۱۰ صندوق برتر
    top_10 = df_sorted.head(10)
    table_header = ["نماد","قیمت","NAV","تغییر %","حباب %","اختلاف سرانه","پول حقیقی","ارزش معاملات"]
    table_cells = [
        top_10.index.tolist(),
        [f"{x:,.0f}" for x in top_10["close_price"]],
        [f"{x:,.0f}" for x in top_10["NAV"]],
        [f"{x:+.2f}%" for x in top_10["close_price_change_percent"]],
        [f"{x:+.2f}%" for x in top_10["nominal_bubble"]],
        [f"{x:+.2f}" for x in top_10.get("ekhtelaf_sarane", [0]*10)],
        [f"{x:+,.0f}" for x in top_10["pol_hagigi"]],
        [f"{x:,.0f}" for x in top_10["value"]],
    ]

    def col_color(v):
        try:
            num = float(str(v).replace("%","").replace("+","").replace(",",""))
            return "#1B5E20" if num > 0 else "#A52A2A" if num < 0 else "#2C2C2C"
        except:
            return "#1C2733"

    cell_colors = [
        ["#1C2733"]*10, ["#1C2733"]*10, ["#1C2733"]*10,
        [col_color(x) for x in table_cells[3]],
        [col_color(x) for x in table_cells[4]],
        [col_color(x) for x in table_cells[5]],
        [col_color(x) for x in table_cells[6]],
        ["#1C2733"]*10,
    ]

    fig.add_trace(go.Table(
        header=dict(values=[f"<b>{h}</b>" for h in table_header],
                    fill_color="#242F3D", font=dict(color="white", size=20), height=35, align="center"),
        cells=dict(values=table_cells, fill_color=cell_colors,
                   font=dict(color="white", size=18), height=35, align="center")
    ), row=2, col=1)

    fig.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=1350,
        width=1350,
        margin=dict(t=140, l=20, r=20, b=20),
        title=dict(
            text="<b>نقشه بازار صندوق‌های طلا</b>",
            font=dict(size=35, color="#FFD700"),
            x=0.5, y=0.96, xanchor="center", yanchor="top"
        ),
        showlegend=False,
    )

    # تبدیل به تصویر با کیفیت بالا
    img_bytes = fig.to_image(format="png", width=1350, height=1350, scale=2)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    draw = ImageDraw.Draw(img)

    # فونت تاریخ و توضیح (سفید)
    try:
        font_date = ImageFont.truetype("assets/fonts/Vazirmatn-Bold.ttf", 62)
        font_desc = ImageFont.truetype("assets/fonts/Vazirmatn-Medium.ttf", 48)
    except:
        try:
            font_date = ImageFont.truetype("Vazirmatn-Bold.ttf", 62)
            font_desc = ImageFont.truetype("Vazirmatn-Medium.ttf", 48)
        except:
            font_date = ImageFont.load_default()
            font_desc = ImageFont.load_default()

    # نوشتن تاریخ و توضیح سفید در بالا چپ
    draw.text((50, 30), date_time_str, font=font_date, fill="#FFFFFF")
    draw.text((50, 105), "اندازه: ارزش معاملات", font=font_desc, fill="#FFFFFF")

    # واترمارک مورب Gold_Iran_Market
    watermark_layer = Image.new("RGBA", img.size, (0,0,0,0))
    wdraw = ImageDraw.Draw(watermark_layer)
    try:
        wfont = ImageFont.truetype("assets/fonts/Vazirmatn-Regular.ttf", 70)
    except:
        wfont = ImageFont.load_default()

    wtext = "Gold_Iran_Market"
    bbox = wdraw.textbbox((0,0), wtext, font=wfont)
    w = bbox[2] - bbox[0] + 60
    h = bbox[3] - bbox[1] + 60
    txt_img = Image.new("RGBA", (w, h), (0,0,0,0))
    td = ImageDraw.Draw(txt_img)
    td.text((30, 30), wtext, font=wfont, fill=(255,255,255,110))
    rotated = txt_img.rotate(45, expand=True)
    img.paste(rotated, ((img.width-rotated.width)//2, (img.height-rotated.height)//2), rotated)

    # ذخیره نهایی
    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True, quality=92)
    output.seek(0)
    return output.getvalue()


def create_simple_caption(
    data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
):
    """ساخت کپشن برای تلگرام با محاسبات وزنی کامل"""
    tehran_tz = pytz.timezone("Asia/Tehran")
    now = JalaliDateTime.now(tehran_tz)
    current_time = now.strftime("%Y/%m/%d - %H:%M:%S")

    try:
        dollar_time = gold_time.strftime("%H:%M") if gold_time else "نامشخص"
    except:
        dollar_time = "نامشخص"

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
    gold_change = ((gold_price - gold_yesterday) / gold_yesterday * 100) if gold_yesterday and gold_yesterday !=0 else 0

    shams = data["dfp"].loc["شمش-طلا"]
    gold_24 = data["dfp"].loc["طلا-گرم-24-عیار"]
    gold_18 = data["dfp"].loc["طلا-گرم-18-عیار"]
    sekeh = data["dfp"].loc["سکه-امامی-طرح-جدید"]

    def calc_diffs(asset_row, dollar_current, gold_current):
        try:
            d_calc = asset_row["pricing_dollar"]
            d_diff = d_calc - dollar_current
        except:
            d_calc = d_diff = 0
        try:
            o_calc = asset_row["pricing_Gold"]
            o_diff = o_calc - gold_current
        except:
            o_calc = o_diff = 0
        return d_calc, d_diff, o_calc, o_diff

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