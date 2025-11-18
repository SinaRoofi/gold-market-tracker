import pandas as pd
import logging
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
from datetime import datetime
import pytz
import io
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

DATA_FILE = "market_data_today.csv"

def create_market_charts():
    """ایجاد نمودارهای بازار از داده‌های CSV"""
    try:
        if not os.path.exists(DATA_FILE):
            logger.warning("⚠️ فایل CSV وجود ندارد")
            return None
        
        # خواندن داده‌ها
        df = pd.read_csv(DATA_FILE, encoding='utf-8')
        
        if df.empty:
            logger.warning("⚠️ فایل CSV خالی است")
            return None
        
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # محاسبه میانگین‌ها برای هر timestamp
        grouped = df.groupby('timestamp').agg({
            'gold_price': 'first',
            'dollar_change_percent': 'first',
            'shams_change_percent': 'first',
            'fund_price_change_percent': 'mean',
            'sarane_kharid': 'mean',
            'sarane_forosh': 'mean',
            'ekhtelaf_sarane': 'mean'
        }).reset_index()
        
        # ایجاد subplot با 5 نمودار
        fig = make_subplots(
            rows=5, cols=1,
            row_heights=[0.2, 0.2, 0.2, 0.2, 0.2],
            subplot_titles=(
                '🟡 قیمت اونس طلا (دلار)',
                '💵 درصد تغییر دلار',
                '📊 درصد تغییر شمش طلا',
                '📈 درصد تغییر میانگین قیمت صندوق‌ها',
                '💰 سرانه خرید و فروش صندوق‌ها'
            ),
            vertical_spacing=0.08
        )
        
        # نمودار 1: قیمت اونس طلا
        fig.add_trace(
            go.Scatter(
                x=grouped['timestamp'],
                y=grouped['gold_price'],
                name='قیمت اونس',
                mode='lines+markers',
                line=dict(width=3, color='#FFD700'),
                marker=dict(size=6, color='#FFD700'),
                fill='tozeroy',
                fillcolor='rgba(255, 215, 0, 0.1)'
            ),
            row=1, col=1
        )
        
        # نمودار 2: درصد تغییر دلار (با رنگ داینامیک)
        colors_dollar = ['#2ECC71' if x >= 0 else '#E74C3C' for x in grouped['dollar_change_percent']]
        
        fig.add_trace(
            go.Scatter(
                x=grouped['timestamp'],
                y=grouped['dollar_change_percent'],
                name='تغییر دلار',
                mode='lines+markers',
                line=dict(width=3, color='gray'),
                marker=dict(size=8, color=colors_dollar),
                fill='tozeroy',
                fillcolor='rgba(46, 204, 113, 0.1)'
            ),
            row=2, col=1
        )
        
        # اضافه کردن خط صفر
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=2, col=1)
        
        # نمودار 3: درصد تغییر شمش طلا
        colors_shams = ['#2ECC71' if x >= 0 else '#E74C3C' for x in grouped['shams_change_percent']]
        
        fig.add_trace(
            go.Scatter(
                x=grouped['timestamp'],
                y=grouped['shams_change_percent'],
                name='تغییر شمش',
                mode='lines+markers',
                line=dict(width=3, color='gray'),
                marker=dict(size=8, color=colors_shams),
                fill='tozeroy',
                fillcolor='rgba(46, 204, 113, 0.1)'
            ),
            row=3, col=1
        )
        
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=3, col=1)
        
        # نمودار 4: درصد تغییر میانگین قیمت صندوق‌ها
        colors_fund = ['#2ECC71' if x >= 0 else '#E74C3C' for x in grouped['fund_price_change_percent']]
        
        fig.add_trace(
            go.Scatter(
                x=grouped['timestamp'],
                y=grouped['fund_price_change_percent'],
                name='تغییر صندوق‌ها',
                mode='lines+markers',
                line=dict(width=3, color='gray'),
                marker=dict(size=8, color=colors_fund),
                fill='tozeroy',
                fillcolor='rgba(46, 204, 113, 0.1)'
            ),
            row=4, col=1
        )
        
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=4, col=1)
        
        # نمودار 5: سرانه‌ها (Line + Bar)
        # Line 1: سرانه خرید (سبز)
        fig.add_trace(
            go.Scatter(
                x=grouped['timestamp'],
                y=grouped['sarane_kharid'],
                name='سرانه خرید',
                mode='lines+markers',
                line=dict(width=3, color='#2ECC71'),
                marker=dict(size=6)
            ),
            row=5, col=1
        )
        
        # Line 2: سرانه فروش × (-1) (قرمز)
        fig.add_trace(
            go.Scatter(
                x=grouped['timestamp'],
                y=grouped['sarane_forosh'] * -1,
                name='سرانه فروش',
                mode='lines+markers',
                line=dict(width=3, color='#E74C3C'),
                marker=dict(size=6)
            ),
            row=5, col=1
        )
        
        # Bar: اختلاف سرانه
        colors_ekhtelaf = ['#2ECC71' if x >= 0 else '#E74C3C' for x in grouped['ekhtelaf_sarane']]
        
        fig.add_trace(
            go.Bar(
                x=grouped['timestamp'],
                y=grouped['ekhtelaf_sarane'],
                name='اختلاف سرانه',
                marker=dict(color=colors_ekhtelaf, opacity=0.6)
            ),
            row=5, col=1
        )
        
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=5, col=1)
        
        # تنظیمات ظاهری
        fig.update_xaxes(title_text="زمان (تهران)", row=5, col=1)
        fig.update_yaxes(title_text="دلار", row=1, col=1)
        fig.update_yaxes(title_text="درصد", row=2, col=1)
        fig.update_yaxes(title_text="درصد", row=3, col=1)
        fig.update_yaxes(title_text="درصد", row=4, col=1)
        fig.update_yaxes(title_text="میلیون تومان", row=5, col=1)
        
        fig.update_layout(
            height=2000,
            width=1400,
            showlegend=True,
            title={
                'text': '📊 نمودار تحلیل لحظه‌ای بازار طلا',
                'x': 0.5,
                'xanchor': 'center',
                'font': {'size': 32, 'color': '#FFD700', 'family': 'Vazirmatn, Arial'}
            },
            paper_bgcolor='#000000',
            plot_bgcolor='#1A1A1A',
            font={'family': 'Vazirmatn, Arial', 'size': 12, 'color': 'white'},
            hovermode='x unified',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                bgcolor='rgba(0,0,0,0.5)'
            )
        )
        
        # ذخیره تصویر
        img_bytes = fig.to_image(format="png", width=1400, height=2000)
        
        # اضافه کردن واترمارک
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
        
        logger.info("✅ نمودارها ایجاد شدند")
        return output.getvalue()
        
    except Exception as e:
        logger.error(f"❌ خطا در ایجاد نمودارها: {e}", exc_info=True)
        return None
