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
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)

def get_csv_filename():
    """فایل CSV ثابت در پوشه data/"""
    return os.path.join("data", "market_data.csv")

def create_market_charts():
    """ایجاد نمودارهای بازار از داده‌های CSV فقط برای امروز"""
    try:
        csv_file = get_csv_filename()
        if not os.path.exists(csv_file):
            logger.warning("⚠️ فایل CSV وجود ندارد")
            return None

        df = pd.read_csv(csv_file, encoding='utf-8')
        if df.empty:
            logger.warning("⚠️ فایل CSV خالی است")
            return None

        df['timestamp'] = pd.to_datetime(df['timestamp'])

        # فیلتر برای داده‌های امروز به وقت تهران
        tehran_tz = pytz.timezone('Asia/Tehran')
        today_str = datetime.now(tehran_tz).strftime('%Y-%m-%d')
        df = df[df['timestamp'].dt.strftime('%Y-%m-%d') == today_str]
        if df.empty:
            logger.warning("⚠️ داده‌ای برای امروز موجود نیست")
            return None

        # تابع میانگین وزنی
        def weighted_mean(group, column):
            total_value = group['value'].sum()
            if total_value == 0:
                return 0
            return (group[column] * group['value']).sum() / total_value

        # محاسبه میانگین وزنی
        weighted_change = df.groupby('timestamp').apply(
            lambda x: weighted_mean(x, 'fund_price_change_percent')
        ).reset_index(name='fund_price_change_percent_weighted')

        weighted_sarane_kharid = df.groupby('timestamp').apply(
            lambda x: weighted_mean(x, 'sarane_kharid')
        ).reset_index(name='sarane_kharid_weighted')

        weighted_sarane_forosh = df.groupby('timestamp').apply(
            lambda x: weighted_mean(x, 'sarane_forosh')
        ).reset_index(name='sarane_forosh_weighted')

        weighted_sarane_forosh['sarane_forosh_weighted'] *= -1
        ekhtelaf_weighted = (weighted_sarane_kharid['sarane_kharid_weighted'] -
                             weighted_sarane_forosh['sarane_forosh_weighted'] * -1)

        grouped = df.groupby('timestamp').agg({
            'gold_price': 'first',
            'dollar_change_percent': 'first',
            'shams_change_percent': 'first'
        }).reset_index()
        grouped = grouped.merge(weighted_change, on='timestamp')
        grouped = grouped.merge(weighted_sarane_kharid, on='timestamp')
        grouped = grouped.merge(weighted_sarane_forosh, on='timestamp')
        grouped['ekhtelaf_sarane_weighted'] = ekhtelaf_weighted

        # -------------------------------
        # رسم نمودار با ۵ ساب‌پلات
        # -------------------------------
        fig = make_subplots(
            rows=5, cols=1,
            row_heights=[0.2]*5,
            subplot_titles=(
                'قیمت اونس طلا',
                'قیمت دلار',
                'شمش طلا',
                'درصد آخرین صندوق‌های طلا',
                'سرانه خرید و فروش و اختلاف سرانه صندوق‌های طلا'
            ),
            vertical_spacing=0.08
        )

        # نمودار 1: طلای جهانی
        first_gold = grouped['gold_price'].iloc[0]
        colors_gold = ['#2ECC71' if x >= first_gold else '#E74C3C' for x in grouped['gold_price']]
        gold_min = grouped['gold_price'].min()
        gold_max = grouped['gold_price'].max()
        gold_padding = (gold_max - gold_min) * 0.1
        fig.add_trace(go.Scatter(x=grouped['timestamp'], y=grouped['gold_price'],
                                 name='قیمت اونس', mode='lines+markers',
                                 line=dict(width=3, color='#FFD700'),
                                 marker=dict(size=8, color=colors_gold),
                                 fill='tozeroy', fillcolor='rgba(255, 215, 0, 0.1)'),
                      row=1, col=1)
        fig.add_hline(y=first_gold, line_dash="dash", line_color="yellow", opacity=0.5, row=1, col=1)
        fig.update_yaxes(range=[gold_min - gold_padding, gold_max + gold_padding], row=1, col=1)

        # نمودار 2: دلار
        colors_dollar = ['#2ECC71' if x >= 0 else '#E74C3C' for x in grouped['dollar_change_percent']]
        fig.add_trace(go.Scatter(x=grouped['timestamp'], y=grouped['dollar_change_percent'],
                                 name='تغییر دلار', mode='lines+markers',
                                 line=dict(width=3, color='gray'),
                                 marker=dict(size=8, color=colors_dollar),
                                 fill='tozeroy', fillcolor='rgba(46, 204, 113, 0.1)'),
                      row=2, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=2, col=1)

        # نمودار 3: شمش
        colors_shams = ['#2ECC71' if x >= 0 else '#E74C3C' for x in grouped['shams_change_percent']]
        fig.add_trace(go.Scatter(x=grouped['timestamp'], y=grouped['shams_change_percent'],
                                 name='شمش طلا', mode='lines+markers',
                                 line=dict(width=3, color='gray'),
                                 marker=dict(size=8, color=colors_shams),
                                 fill='tozeroy', fillcolor='rgba(46, 204, 113, 0.1)'),
                      row=3, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=3, col=1)

        # نمودار 4: درصد آخرین صندوق‌ها
        colors_fund = ['#2ECC71' if x >= 0 else '#E74C3C' for x in grouped['fund_price_change_percent_weighted']]
        fig.add_trace(go.Scatter(x=grouped['timestamp'], y=grouped['fund_price_change_percent_weighted'],
                                 name='درصد آخرین', mode='lines+markers',
                                 line=dict(width=3, color='gray'),
                                 marker=dict(size=8, color=colors_fund),
                                 fill='tozeroy', fillcolor='rgba(46, 204, 113, 0.1)'),
                      row=4, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=4, col=1)

        # نمودار 5: سرانه‌ها
        fig.add_trace(go.Scatter(x=grouped['timestamp'], y=grouped['sarane_kharid_weighted'],
                                 name='سرانه خرید', mode='lines+markers',
                                 line=dict(width=3, color='#2ECC71'), marker=dict(size=6)), row=5, col=1)
        fig.add_trace(go.Scatter(x=grouped['timestamp'], y=grouped['sarane_forosh_weighted'],
                                 name='سرانه فروش', mode='lines+markers',
                                 line=dict(width=3, color='#E74C3C'), marker=dict(size=6)), row=5, col=1)
        colors_ekhtelaf = ['#2ECC71' if x >= 0 else '#E74C3C' for x in grouped['ekhtelaf_sarane_weighted']]
        fig.add_trace(go.Bar(x=grouped['timestamp'], y=grouped['ekhtelaf_sarane_weighted'],
                             name='اختلاف سرانه', marker=dict(color=colors_ekhtelaf, opacity=0.6)),
                      row=5, col=1)
        fig.add_hline(y=0, line_dash="dash", line_color="white", opacity=0.5, row=5, col=1)

        # محور X فقط ساعت و دقیقه
        for i in range(1, 6):
            fig.update_xaxes(tickformat="%H:%M", row=i, col=1)

        # تنظیمات کلی نمودار
        fig.update_layout(height=2000, width=1400, showlegend=True,
                          paper_bgcolor='#000000', plot_bgcolor='#1A1A1A',
                          font=dict(family='Vazirmatn, Arial', size=12, color='white'),
                          hovermode='x unified')

        # تبدیل به تصویر با PIL و افزودن واترمارک
        img_bytes = fig.to_image(format="png", width=1400, height=2000)
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
        txt_img = Image.new("RGBA", (bbox[2] - bbox[0] + 40, bbox[3] - bbox[1] + 40), (255, 255, 255, 0))
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