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
        
        # محاسبه رنج قیمت اونس برای رنگ‌بندی داینامیک
        gold_min = grouped['gold_price'].min()
        gold_max = grouped['gold_price'].max()
        gold_range = gold_max - gold_min
        
        # ایجاد subplot با 5 نمودار
        fig = make_subplots(
            rows=5, cols=1,
            row_heights=[0.2, 0.2, 0.2, 0.2, 0.2],
            subplot_titles=(
                '<b style="font-size:18px">قیمت اونس طلا جهانی</b>',
                '<b style="font-size:18px">قیمت دلار</b>',
                '<b style="font-size:18px">شمش طلا</b>',
                '<b style="font-size:18px">آخرین قیمت صندوق‌ها</b>',
                '<b style="font-size:18px">سرانه خرید و فروش و اختلاف سرانه صندوق‌های طلا</b>'
            ),
            vertical_spacing=0.08
        )
        
        # نمودار 1: قیمت اونس طلا با رنگ‌بندی داینامیک
        colors_gold = []
        for price in grouped['gold_price']:
            if gold_range > 0:
                # نرمال‌سازی به بازه 0-1
                normalized = (price - gold_min) / gold_range
                # انتخاب رنگ بر اساس مقدار
                if normalized < 0.33:
                    colors_gold.append('#E74C3C')  # قرمز
                elif normalized < 0.67:
                    colors_gold.append('#F39C12')  # نارنجی
                else:
                    colors_gold.append('#2ECC71')  # سبز
            else:
                colors_gold.append('#FFD700')  # طلایی
        
        fig.add_trace(
            go.Scatter(
                x=grouped['timestamp'],
                y=grouped['gold_price'],
                name='قیمت اونس',
                mode='lines+markers',
                line=dict(width=3, color='#FFD700'),
                marker=dict(size=8, color=colors_gold),
                fill='tozeroy',
                fillcolor='rgba(255, 215, 0, 0.1)'
            ),
            row=1, col=1
        )
        
        # نمودار 2: درصد تغییر دلار
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
        
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=2, col=1)
        
        # نمودار 3: درصد تغییر شمش طلا
        colors_shams = ['#2ECC71' if x >= 0 else '#E74C3C' for x in grouped['shams_change_percent']]
        
        fig.add_trace(
            go.Scatter(
                x=grouped['timestamp'],
                y=grouped['shams_change_percent'],
                name='شمش طلا',
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
                name='صندوق‌ها',
                mode='lines+markers',
                line=dict(width=3, color='gray'),
                marker=dict(size=8, color=colors_fund),
                fill='tozeroy',
                fillcolor='rgba(46, 204, 113, 0.1)'
            ),
            row=4, col=1
        )
        
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=4, col=1)
        
        # نمودار 5: سرانه‌ها
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
        fig.update_xaxes(title_text="زمان (تهران)", row=5, col=1, title_font=dict(size=14))
        fig.update_yaxes(title_text="دلار", row=1, col=1, title_font=dict(size=14))
        fig.update_yaxes(title_text="درصد", row=2, col=1, title_font=dict(size=14))
        fig.update_yaxes(title_text="درصد", row=3, col=1, title_font=dict(size=14))
        fig.update_yaxes(title_text="درصد", row=4, col=1, title_font=dict(size=14))
        fig.update_yaxes(title_text="میلیون تومان", row=5, col=1, title_font=dict(size=14))
        
        # تنظیم font برای تیترها
        fig.update_annotations(font=dict(size=18, color='white', family='Vazirmatn, Arial'))
        
        fig.update_layout(
            height=2000,
            width=1400,
            showlegend=True,
            title={
                'text': '<b>📊 نمودارهای تحلیل بازار</b>',
                'x': 0.02,
                'y': 0.99,
                'xanchor': 'left',
                'yanchor': 'top',
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
                bgcolor='rgba(0,0,0,0.5)',
                font=dict(size=12)
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
