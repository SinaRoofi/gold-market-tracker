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
FONT_BIG = 20

# =========================================
# توابع کمکی (Helpers)
# =========================================

def safe_float(val):
    """تبدیل ایمن مقادیر به عدد اعشاری"""
    try:
        return float(str(val).replace("%", "").replace("+", "").replace(",", ""))
    except (ValueError, AttributeError, TypeError):
        return 0.0

def get_color_for_value(val):
    """تعیین رنگ سبز/قرمز بر اساس مقدار"""
    v = safe_float(val)
    if v > 0: return "#2E7D32"  # سبز
    if v < 0: return "#C62828"  # قرمز
    return "#263238"            # خنثی

def get_asset_safe(df, index_name):
    """دسترسی ایمن به ردیف‌های دیتافریم"""
    if index_name in df.index:
        return df.loc[index_name]
    return pd.Series({
        'close_price': 0, 'close_price_change_percent': 0, 
        'Bubble': 0, 'pricing_dollar': 0, 'pricing_Gold': 0
    })

# =========================================
# توابع ارسال به تلگرام (Telegram Functions)
# =========================================

def send_to_telegram(bot_token, chat_id, data, dollar_prices, gold_price, gold_yesterday, gold_time, yesterday_close):
    """مدیریت کلی تولید تصاویر و کپشن و ارسال به تلگرام"""
    if data is None:
        logger.error("❌ داده‌های پردازش‌شده (data) مقدار None دارد. ارسال متوقف شد.")
        return False
    try:
        # 1. ایجاد تصویر اول (Treemap + جدول)
        img1_bytes = create_combined_image(
            data["Fund_df"], dollar_prices["last_trade"], gold_price, gold_yesterday, data["dfp"], yesterday_close,
        )
        
        # 2. ایجاد تصویر دوم (نمودارها)
        img2_bytes = create_market_charts()
        
        # 3. ایجاد کپشن
        caption = create_simple_caption(
            data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
        )
        
        # 4. تصمیم‌گیری برای ارسال
        if img2_bytes:
            return send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption)
        else:
            logger.warning("⚠️ نمودارها موجود نیست، فقط تصویر اول ارسال می‌شود")
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = { "photo": ("market_report.png", io.BytesIO(img1_bytes), "image/png") }
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

# =========================================
# توابع تولید تصویر (Image Generation)
# =========================================

def create_combined_image(Fund_df, last_trade, Gold, Gold_yesterday, dfp, yesterday_close):
    """تولید تصویر ترکیبی شامل Treemap و جدول (اصلاح شده)"""
    fig = make_subplots(
        rows=2, cols=1, 
        row_heights=[0.65, 0.35], 
        vertical_spacing=0.02,
        specs=[[{"type": "treemap"}], [{"type": "table"}]],
    )

    # --- بخش 1: Treemap ---
    df_sorted = Fund_df.copy()
    # سورت بر اساس ارزش معاملات
    df_sorted = df_sorted.sort_values("value", ascending=False)
    
    # فرمت‌دهی درصد تغییر
    df_sorted['change_fmt'] = df_sorted['close_price_change_percent'].apply(lambda x: f"%{x:+.2f}")

    # مقیاس رنگی
    colorscale = [
        [0.0, "#D32F2F"], [0.5, "#212121"], [1.0, "#388E3C"]
    ]

    fig.add_trace(go.Treemap(
        labels=df_sorted.index,
        parents=[""] * len(df_sorted),
        values=df_sorted["value"],
        customdata=df_sorted[['change_fmt']],
        
        # فقط نام نماد و درصد تغییر برای جلوگیری از درهم ریختگی
        texttemplate="<b>%{label}</b><br>%{customdata[0]}",
        textposition="middle center",
        
        # فونت بزرگ (18) و پیش‌فرض
        textfont=dict(
            size=18, 
            color="white", 
            family="Arial, sans-serif"
        ),
        
        marker=dict(
            colors=df_sorted["close_price_change_percent"],
            colorscale=colorscale,
            cmid=0, cmin=-3, cmax=3,
            line=dict(width=1, color="#000000"),
        ),
        pathbar=dict(visible=False),
        root=dict(color="#263238"),
    ), row=1, col=1)

    # --- اضافه کردن متن راهنما در گوشه نقشه ---
    fig.add_annotation(
        text="اندازه مربع‌ها بر اساس ارزش معاملات",
        xref="paper", yref="paper",
        x=0.99, y=0.36, # گوشه پایین سمت راستِ تری‌مپ
        showarrow=False,
        font=dict(size=14, color="#90A4AE", family="Arial"),
        align="right",
        bgcolor="rgba(0,0,0,0.7)",
        bordercolor="#37474F",
        borderwidth=1,
        borderpad=4
    )

    # --- بخش 2: جدول ---
    top_10 = df_sorted.head(10)
    headers = ["نماد", "قیمت", "NAV", "تغییر %", "حباب %", "سرانه", "پول حقیقی", "ارزش معاملات"]
    
    vals = [
        top_10.index.tolist(),
        [f"{x:,.0f}" for x in top_10["close_price"]],
        [f"{x:,.0f}" for x in top_10["NAV"]],
        [f"{x:+.2f}%" for x in top_10["close_price_change_percent"]],
        [f"{x:+.2f}%" for x in top_10["nominal_bubble"]],
        [f"{x:+.2f}" for x in top_10["ekhtelaf_sarane"]],
        [f"{x:+,.0f}" for x in top_10["pol_hagigi"]],
        [f"{x:,.0f}" for x in top_10["value"]],
    ]

    base_color = ["#1C2733"] * len(top_10)
    cell_colors = [
        base_color, base_color, base_color,
        [get_color_for_value(x) for x in vals[3]],
        [get_color_for_value(x) for x in vals[4]],
        [get_color_for_value(x) for x in vals[5]],
        [get_color_for_value(x) for x in vals[6]],
        base_color,
    ]

    fig.add_trace(go.Table(
        header=dict(
            values=[f"<b>{h}</b>" for h in headers],
            fill_color="#242F3D",
            align="center",
            font=dict(color="white", size=16, family="Arial"),
            height=35,
        ),
        cells=dict(
            values=vals,
            fill_color=cell_colors,
            align="center",
            font=dict(color="white", size=15, family="Arial"),
            height=35,
        ),
    ), row=2, col=1)

    fig.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=1400, width=1400,
        margin=dict(t=90, l=10, r=10, b=10),
        title=dict(
            text="<b>📊 نقشه بازار و جدول ۱۰ صندوق طلا</b>",
            font=dict(size=32, color="#FFD700", family="Arial"),
            x=0.5, y=1.0, xanchor="center", yanchor="top",
        ),
        showlegend=False,
        # مخفی کردن متن اگر جا نشود
        uniformtext=dict(minsize=10, mode='hide') 
    )

    img_bytes = fig.to_image(format="png", width=1200, height=1200)
    return add_watermark(img_bytes)

def add_watermark(img_bytes):
    """اضافه کردن واترمارک با استفاده از فونت پیش‌فرض"""
    try:
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
        watermark_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(watermark_layer)
        
        # استفاده از فونت پیش‌فرض
        font = ImageFont.load_default()
        watermark_text = "Gold_Iran_Market"
        
        # محاسبه سایز متن (تقریبی با فونت دیفالت)
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        w_txt = bbox[2] - bbox[0]
        h_txt = bbox[3] - bbox[1]
        
        txt_img = Image.new("RGBA", (w_txt + 20, h_txt + 20), (255, 255, 255, 0))
        txt_draw = ImageDraw.Draw(txt_img)
        txt_draw.text((10, 10), watermark_text, font=font, fill=(255, 255, 255, 100))
        
        rotated = txt_img.rotate(45, expand=True)
        x = (img.width - rotated.width) // 2
        y = (img.height - rotated.height) // 2
        watermark_layer.paste(rotated, (x, y), rotated)
        img = Image.alpha_composite(img, watermark_layer)
        
        output = io.BytesIO()
        img.save(output, format="PNG", optimize=True, quality=85)
        return output.getvalue()
    except Exception as e:
        logger.error(f"خطا در واترمارک: {e}")
        return img_bytes

def create_simple_caption(data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time):
    """ساخت کپشن"""
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
        avg_price_weighted = 0
        avg_change_percent_weighted = 0
        avg_bubble_weighted = 0

    dollar_last = dollar_prices.get("last_trade", 0)
    dollar_change = ((dollar_last - yesterday_close) / yesterday_close * 100) if yesterday_close else 0
    gold_change = ((gold_price - gold_yesterday) / gold_yesterday * 100) if gold_yesterday else 0

    shams = get_asset_safe(data["dfp"], "شمش-طلا")
    sekeh = get_asset_safe(data["dfp"], "سکه-امامی-طرح-جدید")
    
    def get_pricing_dollar(row):
        try: return row["pricing_dollar"]
        except: return 0
        
    d_shams = get_pricing_dollar(shams)
    diff_shams = d_shams - dollar_last
    d_sekeh = get_pricing_dollar(sekeh)
    diff_sekeh = d_sekeh - dollar_last
    
    sekeh_price = sekeh["close_price"] / 10
    pol_to_value_ratio = (total_pol / total_value * 100) if total_value != 0 else 0

    caption = f"""
📅 <b>{current_time}</b>
━━━━━━━━━━━━━━━━━━━━━━━━
<b>💵 دلار بازار</b>
💰 قیمت: <b>{dollar_last:,} تومان</b> ({dollar_change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━━━━━
<b>🔆 اونس جهانی طلا</b>
💰 قیمت: <b>${gold_price:,.2f}</b> ({gold_change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━━━━━
<b>📊 آمار صندوق‌های طلا</b>
💰 ارزش معاملات: <b>{total_value:,.0f}</b> میلیارد تومان
💸 ورود پول حقیقی: <b>{total_pol:+,.0f}</b> میلیارد تومان
📊 نسبت خریدار حقیقی: <b>{pol_to_value_ratio:+.0f}%</b>
📈 میانگین قیمت وزنی: <b>{avg_price_weighted:,.0f}</b> ({avg_change_percent_weighted:+.2f}%)
🎈 میانگین حباب وزنی: <b>{avg_bubble_weighted:+.2f}%</b>
━━━━━━━━━━━━━━━━━━━━━━━━
✨ <b>شمش طلا</b>
💰 قیمت: <b>{shams['close_price']:,}</b> ریال
📊 تغییر: {shams['close_price_change_percent']:+.2f}% | حباب: {shams['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_shams:,.0f} ({diff_shams:+,.0f})

🪙 <b>سکه امامی</b>
💰 قیمت: <b>{sekeh_price:,.0f}</b> تومان
📊 تغییر: {sekeh['close_price_change_percent']:+.2f}% | حباب: {sekeh['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_sekeh:,.0f} ({diff_sekeh:+,.0f})
━━━━━━━━━━━━━━━━━━━━━━━━
🔗 <a href='https://t.me/Gold_Iran_Market'>@Gold_Iran_Market</a>
"""
    return caption
