import io
import logging
import json
import requests
import pytz
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from persiantools.jdatetime import JalaliDateTime
from PIL import Image, ImageDraw, ImageFont
from utils.chart_creator import create_market_charts  # فرض بر این است که این ماژول وجود دارد

logger = logging.getLogger(__name__)

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
        # 1. ایجاد تصویر اول (Treemap + جدول)
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

        # 3. ایجاد کپشن (شامل محاسبه حباب وزنی)
        caption = create_simple_caption(
            data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
        )

        # 4. تصمیم‌گیری برای ارسال (تکی یا آلبوم)
        if img2_bytes:
            return send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption)
        else:
            # اگر نمودار نبود، فقط تصویر اول رو بفرست
            logger.warning("⚠️ نمودارها موجود نیست، فقط تصویر اول ارسال می‌شود")
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": ("market_report.png", io.BytesIO(img1_bytes), "image/png")}
            params = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}

            response = requests.post(url, files=files, data=params, timeout=60)

            if response.status_code == 200:
                logger.info("✅ گزارش (تک عکس) ارسال شد")
                return True
            else:
                logger.error(f"❌ خطا در ارسال تک عکس: {response.text}")
                return False

    except Exception as e:
        logger.error(f"❌ خطا در فرآیند ارسال به تلگرام: {e}", exc_info=True)
        return False


def send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption):
    """ارسال 2 عکس + کپشن به صورت Media Group (آلبوم)"""
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"

        files = {
            'photo1': ('market_treemap.png', io.BytesIO(img1_bytes), 'image/png'),
            'photo2': ('market_charts.png', io.BytesIO(img2_bytes), 'image/png')
        }

        media = [
            {
                'type': 'photo',
                'media': 'attach://photo1',
                'caption': caption,
                'parse_mode': 'HTML'
            },
            {
                'type': 'photo',
                'media': 'attach://photo2'
            }
        ]

        data_payload = {
            'chat_id': chat_id,
            'media': json.dumps(media)
        }

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
    """تولید تصویر ترکیبی شامل Treemap و جدول"""
    fig = make_subplots(
        rows=2,
        cols=1,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.02,
        specs=[[{"type": "treemap"}], [{"type": "table"}]],
    )

    df_sorted = Fund_df.copy()
    # برای رنگ‌بندی از درصد تغییر قیمت استفاده می‌کنیم
    df_sorted["color_value"] = df_sorted["close_price_change_percent"]

    FONT_BIG = 19

    def create_text(row):
        # تنظیم اندازه فونت بر اساس اهمیت (ارزش معاملات)
        if row["value"] > 100:
            return (
                f"<b style='font-size:{FONT_BIG+3}px'>{row.name}</b><br>"
                f"<span style='font-size:{FONT_BIG}px'>{row['close_price']:,.0f}</span><br>"
                f"<span style='font-size:{FONT_BIG-1}px'>{row['close_price_change_percent']:+.2f}%</span><br>"
                f"<span style='font-size:{FONT_BIG-2}px'>حباب: {row['nominal_bubble']:+.2f}%</span>"
            )
        elif row["value"] > 50:
            return (
                f"<b style='font-size:{FONT_BIG+1}px'>{row.name}</b><br>"
                f"<span style='font-size:{FONT_BIG-1}px'>{row['close_price']:,.0f}</span><br>"
                f"<span style='font-size:{FONT_BIG-2}px'>{row['close_price_change_percent']:+.2f}%</span>"
            )
        else:
            return f"<b style='font-size:{FONT_BIG}px'>{row.name}</b><br><span style='font-size:{FONT_BIG-2}px'>{row['close_price_change_percent']:+.2f}%</span>"

    df_sorted["display_text"] = df_sorted.apply(create_text, axis=1)
    df_sorted = df_sorted.sort_values("value", ascending=False)

    # تعریف طیف رنگی (قرمز تا سبز)
    colorscale = [
        [0.0, "#E57373"],
        [0.1, "#D85C5C"],
        [0.2, "#C94444"],
        [0.3, "#A52A2A"],
        [0.4, "#6B1A1A"],
        [0.5, "#2C2C2C"],
        [0.6, "#1B5E20"],
        [0.7, "#2E7D32"],
        [0.8, "#43A047"],
        [0.9, "#5CB860"],
        [1.0, "#66BB6A"],
    ]

    # افزودن Treemap
    fig.add_trace(
        go.Treemap(
            labels=df_sorted.index,
            parents=[""] * len(df_sorted),
            values=df_sorted["value"],
            text=df_sorted["display_text"],
            textinfo="text",
            textposition="middle center",
            textfont=dict(size=FONT_BIG, family="Vazirmatn, Arial", color="white"),
            hoverinfo="skip",
            marker=dict(
                colors=df_sorted["color_value"],
                colorscale=colorscale,
                cmid=0,
                cmin=-10,
                cmax=10,
                line=dict(width=2, color="#1A1A1A"),
            ),
        ),
        row=1,
        col=1,
    )

    # آماده‌سازی داده‌های جدول (۱۰ تای برتر)
    top_10 = df_sorted.head(10)

    table_header = [
        "نماد",
        "قیمت",
        "NAV",
        "تغییر %",
        "حباب %",
        "اختلاف سرانه",
        "پول حقیقی",
        "ارزش معاملات",
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
            # حذف کاراکترهای غیر عددی برای تشخیص مثبت/منفی
            x = float(v.replace("%", "").replace("+", "").replace(",", ""))
            return "#1B5E20" if x > 0 else "#A52A2A" if x < 0 else "#2C2C2C"
        except:
            return "#1C2733"

    cell_colors = [
        ["#1C2733"] * len(top_10),
        ["#1C2733"] * len(top_10),
        ["#1C2733"] * len(top_10),
        [col_color(x) for x in table_cells[3]], # تغییر %
        [col_color(x) for x in table_cells[4]], # حباب
        [col_color(x) for x in table_cells[5]], # اختلاف سرانه
        [col_color(x) for x in table_cells[6]], # پول حقیقی
        ["#1C2733"] * len(top_10),
    ]

    # افزودن جدول
    fig.add_trace(
        go.Table(
            header=dict(
                values=[f"<b>{h}</b>" for h in table_header],
                fill_color="#242F3D",
                align="center",
                font=dict(color="white", size=FONT_BIG - 3, family="Vazirmatn, Arial"),
                height=32,
            ),
            cells=dict(
                values=table_cells,
                fill_color=cell_colors,
                align="center",
                font=dict(color="white", size=FONT_BIG - 3, family="Vazirmatn, Arial"),
                height=35,
            ),
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=1400,
        width=1400,
        margin=dict(t=90, l=10, r=10, b=10),
        title=dict(
            text="<b>📊 نقشه بازار ۱۰ صندوق طلا با ارزش معاملات بالا </b>",
            font=dict(size=32, color="#FFD700", family="Vazirmatn, Arial"),
            x=0.5,
            y=1.0,
            xanchor="center",
            yanchor="top",
        ),
        showlegend=False,
    )

    # تبدیل پلات به عکس
    img_bytes = fig.to_image(format="png", width=1200, height=1200)
    
    # افزودن واترمارک با PIL
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    watermark_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(watermark_layer)

    font_size = 60
    try:
        font = ImageFont.truetype("Vazirmatn.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    watermark_text = "Gold_Iran_Market"
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    textwidth = bbox[2] - bbox[0]
    textheight = bbox[3] - bbox[1]
    
    # ساخت واترمارک چرخیده
    txt_img = Image.new("RGBA", (textwidth + 40, textheight + 40), (255, 255, 255, 0))
    txt_draw = ImageDraw.Draw(txt_img)
    txt_draw.text((20, 20), watermark_text, font=font, fill=(255, 255, 255, 100))
    rotated = txt_img.rotate(45, expand=True)
    
    x = (img.width - rotated.width) // 2
    y = (img.height - rotated.height) // 2
    watermark_layer.paste(rotated, (x, y), rotated)
    
    img = Image.alpha_composite(img, watermark_layer)

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True, quality=85)
    return output.getvalue()


def create_simple_caption(
    data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
):
    """ساخت کپشن برای تلگرام"""
    tehran_tz = pytz.timezone("Asia/Tehran")
    now = JalaliDateTime.now(tehran_tz)
    current_time = now.strftime("%Y/%m/%d - %H:%M:%S")

    try:
        dollar_time = gold_time.strftime("%H:%M") if gold_time else "نامشخص"
    except:
        dollar_time = "نامشخص"

    # --- دسترسی راحت‌تر به داده‌های صندوق ---
    df_funds = data["Fund_df"]

    # --- محاسبات آماری صندوق‌ها ---
    total_value = df_funds["value"].sum()
    total_pol = df_funds["pol_hagigi"].sum()
    avg_price = df_funds["close_price"].mean()
    avg_change_percent = df_funds["close_price_change_percent"].mean()

    # ✅ محاسبه میانگین حباب وزنی (Weighted Average Bubble)
    if total_value > 0:
        avg_bubble = (df_funds["value"] * df_funds["nominal_bubble"]).sum() / total_value
    else:
        avg_bubble = 0

    # --- محاسبات تغییرات ---
    dollar_change = (
        ((dollar_prices["last_trade"] - yesterday_close) / yesterday_close * 100)
        if yesterday_close and yesterday_close != 0
        else 0
    )
    gold_change = (
        ((gold_price - gold_yesterday) / gold_yesterday * 100) if gold_yesterday and gold_yesterday != 0 else 0
    )

    # --- استخراج داده‌های طلا و سکه ---
    shams = data["dfp"].loc["شمش-طلا"]
    gold_24 = data["dfp"].loc["طلا-گرم-24-عیار"]
    gold_18 = data["dfp"].loc["طلا-گرم-18-عیار"]
    sekeh = data["dfp"].loc["سکه-امامی-طرح-جدید"]

    # --- توابع کمکی برای محاسبه حباب دلاری/اونسی ---
    def calc_diffs(asset_row, dollar_current, gold_current):
        # محاسبه دلار
        try:
            d_calc = asset_row["pricing_dollar"]
            d_diff = d_calc - dollar_current
        except:
            d_calc = 0
            d_diff = 0
        
        # محاسبه اونس (فقط برای شمش)
        try:
            o_calc = asset_row["pricing_Gold"]
            o_diff = o_calc - gold_current
        except:
            o_calc = 0
            o_diff = 0
            
        return d_calc, d_diff, o_calc, o_diff

    # محاسبات شمش
    d_shams, diff_shams, o_shams, diff_o_shams = calc_diffs(shams, dollar_prices["last_trade"], gold_price)

    # محاسبات سایر اقلام (اونس برای اینها محاسبه نمی‌شود)
    d_24, diff_24, _, _ = calc_diffs(gold_24, dollar_prices["last_trade"], gold_price)
    d_18, diff_18, _, _ = calc_diffs(gold_18, dollar_prices["last_trade"], gold_price)
    d_sekeh, diff_sekeh, _, _ = calc_diffs(sekeh, dollar_prices["last_trade"], gold_price)

    # تبدیل قیمت‌ها (تقسیم بر ۱۰ برای تبدیل ریال به تومان اگر لازم است - در کد اصلی شما بود)
    gold_24_price = gold_24["close_price"] / 10
    gold_18_price = gold_18["close_price"] / 10
    sekeh_price = sekeh["close_price"] / 10

    # نسبت پول حقیقی
    pol_to_value_ratio = (total_pol / total_value * 100) if total_value != 0 else 0

    # --- ساخت متن کپشن ---
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
📈 آخرین قیمت : <b>{avg_price:,.0f}</b> تومان ({avg_change_percent:+.2f}%)
🎈 میانگین حباب (وزنی): <b>{avg_bubble:+.2f}%</b>
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
