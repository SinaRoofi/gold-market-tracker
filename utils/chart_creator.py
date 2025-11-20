# utils/chart_creator.py — نسخه زیبا و حرفه‌ای

import logging
import pytz
from datetime import datetime
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from PIL import Image, ImageDraw, ImageFont
from utils.sheets_storage import read_from_sheets

logger = logging.getLogger(__name__)

def create_market_charts():
    """
    ساخت نمودار ۶ خطی زیبا با رنگ‌های پویا
    """
    try:
        # خواندن از Google Sheets
        data_rows = read_from_sheets(limit=500)
        
        if not data_rows:
            logger.warning("داده‌ای از Sheets دریافت نشد")
            return None
        
        # تبدیل به DataFrame
        df = pd.DataFrame(data_rows, columns=[
            'timestamp', 'gold_price_usd', 'dollar_change_percent',
            'shams_change_percent', 'fund_weighted_change_percent',
            'fund_weighted_bubble_percent',
            'sarane_kharid_weighted', 'sarane_forosh_weighted',
            'ekhtelaf_sarane_weighted'
        ])
        
        # تبدیل انواع داده
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        numeric_cols = df.columns[1:]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')
        
        # فیلتر: فقط داده‌های امروز
        tehran_tz = pytz.timezone('Asia/Tehran')
        today = datetime.now(tehran_tz).date()
        df = df[df['timestamp'].dt.date == today].copy()
        
        if df.empty:
            logger.info("داده‌ای برای امروز پیدا نشد")
            return None
        
        df = df.sort_values('timestamp')
        
        # ساخت نمودار ۶ قسمتی
        fig = make_subplots(
            rows=6, cols=1,
            subplot_titles=(
                '<b>قیمت اونس طلا ($)</b>',
                '<b> دلار آزاد (%)</b>',
                '<b> شمش طلای بورس کالا (%)</b>',
                '<b> آخرین قیمت صندوق‌های طلا (%)</b>',
                '<b>میانگین حباب صندوق‌های طلا (%)</b>',
                '<b>سرانه خرید و فروش و اختلاف آن</b>'
            ),
            vertical_spacing=0.045,
            shared_xaxes=True
        )
        
        # ═══════════════════════════════════════════════════════
        # ۱. قیمت طلا - فقط طلایی زیبا با محدوده ±5%
        # ═══════════════════════════════════════════════════════
        gold_current = df['gold_price_usd'].iloc[-1]
        gold_min = gold_current * 0.93 # -5%
        gold_max = gold_current * 1.03  # +5%
        
        fig.add_trace(go.Scatter(
            x=df['timestamp'], 
            y=df['gold_price_usd'],
            name='طلا', 
            line=dict(color='#FFD700', width=5), 
            hovertemplate='<b>%{y:.2f} $</b><extra></extra>'
        ), row=1, col=1)
        
        fig.update_yaxes(range=[gold_min, gold_max], row=1, col=1)
        
        # ═══════════════════════════════════════════════════════
        # ۲. دلار - سبز/قرمز بر اساس مثبت/منفی
        # ═══════════════════════════════════════════════════════
        add_conditional_line(fig, df, 'dollar_change_percent', 2)
        
        # ═══════════════════════════════════════════════════════
        # ۳. شمش - سبز/قرمز
        # ═══════════════════════════════════════════════════════
        add_conditional_line(fig, df, 'shams_change_percent', 3)
        
        # ═══════════════════════════════════════════════════════
        # ۴. صندوق‌ها - سبز/قرمز
        # ═══════════════════════════════════════════════════════
        add_conditional_line(fig, df, 'fund_weighted_change_percent', 4)
        
        # ═══════════════════════════════════════════════════════
        # ۵. حباب - سبز/قرمز
        # ═══════════════════════════════════════════════════════
        add_conditional_line(fig, df, 'fund_weighted_bubble_percent', 5)
        
        # ═══════════════════════════════════════════════════════
        # ۶. سرانه‌ها - خرید (سبز)، فروش (قرمز)، اختلاف (کم‌رنگ)
        # ═══════════════════════════════════════════════════════
        fig.add_trace(go.Scatter(
            x=df['timestamp'], 
            y=df['sarane_kharid_weighted'],
            name='خرید حقیقی', 
            line=dict(color='#00E676', width=5),
            hovertemplate='خرید: <b>%{y:.2f}</b><extra></extra>'
        ), row=6, col=1)
        
        fig.add_trace(go.Scatter(
            x=df['timestamp'], 
            y=df['sarane_forosh_weighted'],
            name='فروش حقیقی', 
            line=dict(color='#FF1744', width=5),
            hovertemplate='فروش: <b>%{y:.2f}</b><extra></extra>'
        ), row=6, col=1)
        
        # اختلاف سرانه - بار چارت با رنگ شرطی کم‌رنگ
        colors_sarane = ['rgba(0,230,118,0.4)' if x >= 0 else 'rgba(255,23,68,0.4)' 
                         for x in df['ekhtelaf_sarane_weighted']]
        
        fig.add_trace(go.Bar(
            x=df['timestamp'], 
            y=df['ekhtelaf_sarane_weighted'],
            name='اختلاف سرانه', 
            marker_color=colors_sarane,
            hovertemplate='اختلاف: <b>%{y:.2f}</b><extra></extra>'
        ), row=6, col=1)
        
        # ═══════════════════════════════════════════════════════
        # تنظیمات کلی - تم دارک زیبا
        # ═══════════════════════════════════════════════════════
        fig.update_layout(
            height=2200,
            paper_bgcolor='#0D1117',
            plot_bgcolor='#0D1117',
            font=dict(color='#C9D1D9', family='Vazirmatn, Arial', size=25),  # ← فونت بزرگتر (17→20)
            hovermode='x unified',
            showlegend=False,
            margin=dict(l=60, r=30, t=100, b=40),  # ← فضای بالا بیشتر برای تیتر
            title=dict(
                text='<b style="color:#FFD700; font-size:36px">📊 روند بازار</b>',  # ← فونت بزرگتر
                x=0.02,  # ← سمت چپ بالا
                y=0.995,  # ← خیلی بالا
                xanchor='left',
                yanchor='top',
                font=dict(size=36, color='#FFD700')
            )
        )
        
        # تنظیمات محورها
        for i in range(1, 7):
            # محور X - فقط ساعت
            fig.update_xaxes(
                tickformat='%H:%M',
                gridcolor='#21262D',
                showgrid=True,
                zeroline=False,
                showline=True,
                linewidth=1,
                linecolor='#30363D',
                row=i, col=1
            )
            
            # محور Y - با خطوط عمودی و افقی کم‌رنگ
            fig.update_yaxes(
                gridcolor='#21262D',
                showgrid=True,
                zeroline=True,
                zerolinecolor='#30363D',
                zerolinewidth=2,
                showline=True,
                linewidth=1,
                linecolor='#30363D',
                row=i, col=1
            )
            
            # خط صفر برای نمودارهای 2-6
            if i > 1:
                fig.add_hline(
                    y=0, 
                    line_dash='dot', 
                    line_color='#484F58', 
                    line_width=2,
                    row=i, col=1
                )
        
        # تنظیم عنوان‌های subplot
        for annotation in fig['layout']['annotations']:
            annotation['font'] = dict(size=22, color='#8B949E')  # ← فونت بزرگتر (19→22)
        
        # تبدیل به عکس
        img_bytes = fig.to_image(format='png', width=1400, height=2200)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')
        
        # واترمارک
        try:
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype('Vazirmatn-Regular.ttf', 38)
            text = f'🕐 {datetime.now(tehran_tz).strftime("%H:%M")}'
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            draw.text(((1400-w)/2, 15), text, fill=(201,209,217,200), font=font)
        except:
            pass
        
        output = io.BytesIO()
        img.save(output, format='PNG', optimize=True, quality=90)
        output.seek(0)
        return output.getvalue()
        
    except Exception as e:
        logger.error(f'خطا در ساخت نمودار: {e}', exc_info=True)
        return None


def add_conditional_line(fig, df, column, row):
    """
    اضافه کردن خط با رنگ شرطی (سبز اگه مثبت، قرمز اگه منفی)
    خطوط کاملاً صاف و هموار با line smoothing
    """
    # یک خط پیوسته با رنگ‌های مختلف
    colors = ['#00E676' if val >= 0 else '#FF1744' for val in df[column]]
    
    # برای خطوط صاف‌تر، از shape='spline' استفاده می‌کنیم
    for i in range(len(df) - 1):
        curr_val = df[column].iloc[i]
        next_val = df[column].iloc[i + 1]
        curr_time = df['timestamp'].iloc[i]
        next_time = df['timestamp'].iloc[i + 1]
        
        # تعیین رنگ بر اساس مقدار فعلی
        color = '#00E676' if curr_val >= 0 else '#FF1744'
        
        # اگه از مثبت به منفی یا بالعکس می‌ره
        if (curr_val >= 0 and next_val < 0) or (curr_val < 0 and next_val >= 0):
            # نقطه تلاقی با صفر
            t = abs(curr_val) / (abs(curr_val) + abs(next_val))
            cross_time = curr_time + (next_time - curr_time) * t
            
            # خط اول تا نقطه صفر
            fig.add_trace(go.Scatter(
                x=[curr_time, cross_time],
                y=[curr_val, 0],
                mode='lines',
                line=dict(color=color, width=5, shape='spline'),
                showlegend=False,
                hoverinfo='skip'
            ), row=row, col=1)
            
            # خط دوم از نقطه صفر
            color_next = '#FF1744' if next_val < 0 else '#00E676'
            fig.add_trace(go.Scatter(
                x=[cross_time, next_time],
                y=[0, next_val],
                mode='lines',
                line=dict(color=color_next, width=5, shape='spline'),
                showlegend=False,
                hoverinfo='skip'
            ), row=row, col=1)
        else:
            # خط عادی
            fig.add_trace(go.Scatter(
                x=[curr_time, next_time],
                y=[curr_val, next_val],
                mode='lines',
                line=dict(color=color, width=5, shape='spline'),
                showlegend=False,
                hovertemplate='<b>%{y:+.2f}%</b><extra></extra>' if i == 0 else None
            ), row=row, col=1)
