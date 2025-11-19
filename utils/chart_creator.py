# utils/chart_creator.py — نسخه نهایی با خواندن مستقیم از گوگل درایو

import logging
import pytz
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from PIL import Image, ImageDraw, ImageFont
from utils.drive_storage import download_for_chart  # ← فقط این اضافه شد

logger = logging.getLogger(__name__)

def create_market_charts():
    """
    ساخت نمودار ۵ خطی زنده (هر ۵ دقیقه یه نقطه جدید)
    داده‌ها مستقیم از گوگل درایو میاد → هیچوقت پاک نمیشه!
    """
    try:
        # دانلود فایل CSV از گوگل درایو
        fh = download_for_chart()
        if not fh:
            logger.warning("نمی‌تونم فایل رو از گوگل درایو بگیرم")
            return None

        df = pd.read_csv(fh)
        if df.empty:
            logger.info("فایل خالیه")
            return None

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # فقط داده‌های امروز
        tehran_tz = pytz.timezone('Asia/Tehran')
        today = datetime.now(tehran_tz).date()
        df = df[df['timestamp'].dt.date == today].copy()
        
        if df.empty:
            logger.info("داده‌ای برای امروز پیدا نشد")
            return None

        df = df.sort_values('timestamp')

        # ساخت نمودار ۵ قسمتی
        fig = make_subplots(
            rows=5, cols=1,
            subplot_titles=(
                'قیمت اونس طلا ($)',
                'تغییر دلار آزاد (%)',
                'تغییر شمش طلا (%)',
                'میانگین وزنی تغییر صندوق‌های طلا (%)',
                'سرانه خرید/فروش حقیقی (وزنی)'
            ),
            vertical_spacing=0.06,
            shared_xaxes=True
        )

        # ۱. قیمت طلا
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['gold_price_usd'],
            name='طلا', line=dict(color='#FFD700', width=4),
            fill='tozeroy', fillcolor='rgba(255,215,0,0.15)'
        ), row=1, col=1)

        # ۲. دلار
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['dollar_change_percent'],
            name='دلار', line=dict(color='#3498DB', width=3)
        ), row=2, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

        # ۳. شمش
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['shams_change_percent'],
            name='شمش', line=dict(color='#E67E22', width=3)
        ), row=3, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)

        # ۴. صندوق‌ها
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['fund_weighted_change_percent'],
            name='صندوق‌ها', line=dict(color='#9B59B6', width=4)
        ), row=4, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="gray", row=4, col=1)

        # ۵. سرانه‌ها
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['sarane_kharid_weighted'],
            name='خرید حقیقی', line=dict(color='#2ECC71', width=4)
        ), row=5, col=1)
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['sarane_forosh_weighted'],
            name='فروش حقیقی', line=dict(color='#E74C3C', width=4)
        ), row=5, col=1)
        fig.add_trace(go.Bar(
            x=df['timestamp'], y=df['ekhtelaf_sarane_weighted'],
            name='اختلاف سرانه', marker_color='#F1C40F', opacity=0.7
        ), row=5, col=1)

        # تنظیمات کلی
        fig.update_layout(
            height=1800,
            paper_bgcolor='#121212',
            plot_bgcolor='#121212',
            font=dict(color="white", family="Vazirmatn, Tahoma", size=14),
            hovermode="x unified",
            showlegend=False,
            margin=dict(l=20, r=20, t=60, b=20)
        )

        for i in range(1, 6):
            fig.update_xaxes(tickformat="%H:%M", row=i, col=1)
            fig.update_yaxes(gridcolor="#333333", row=i, col=1)

        # تبدیل به عکس
        img_bytes = fig.to_image(format="png", width=1400, height=1800)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        # واترمارک (اختیاری — اگه فونت داری)
        try:
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype("Vazirmatn-Regular.ttf", 36)
            text = f"به‌روزرسانی: {datetime.now(tehran_tz).strftime('%H:%M')}"
            w, h = draw.textsize(text, font=font)
            draw.text(((1400-w)/2, 20), text, fill=(255,255,255,180), font=font)
        except:
            pass  # اگه فونت نبود، بی‌خیال

        output = io.BytesIO()
        img.save(output, format="PNG", optimize=True)
        output.seek(0)
        return output.getvalue()

    except Exception as e:
        logger.error(f"خطا در ساخت نمودار: {e}", exc_info=True)
        return None