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
                '<b> شمش طلا (%)</b>',
                '<b>  درصد آخرین صندوق‌های طلا (%)</b>',
                '<b>  حباب صندوق‌های طلا (%)</b>',
                '<b>سرانه خرید/فروش حقیقی</b>'
            ),
            vertical_spacing=0.045,
            shared_xaxes=True
        )
        
        # ═══════════════════════════════════════════════════════
        # ۱. قیمت طلا - فقط طلایی زیبا با محدوده ±5%
        # ═══════════════════════════════════════════════════════
        gold_current = df['gold_price_usd'].iloc[-1]
        gold_min = gold_current * 0.95  # -5%
        gold_max = gold_current * 1.05  # +5%
        
        fig.add_trace(go.Scatter(
            x=df['timestamp'], 
            y=df['gold_price_usd'],
            name='طلا', 
            line=dict(color='#FFD700', width=5),
            fill='tozeroy', 
            fillcolor='rgba(255,215,0,0.15)',
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
            font=dict(color='#C9D1D9', family='Vazirmatn, Arial', size=17),  # فونت +3
            hovermode='x unified',
            showlegend=False,
            margin=dict(l=60, r=30, t=40, b=40),
            title=dict(
                text='<b style="color:#FFD700">📊 روند بازار</b>',
                x=0.5,
                y=0.99,
                xanchor='center',
                font=dict(size=28)
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
            annotation['font'] = dict(size=19, color='#8B949E')
        
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
    """
    # جدا کردن قسمت‌های مثبت و منفی
    df_positive = df[df[column] >= 0].copy()
    df_negative = df[df[column] < 0].copy()
    
    # خط سبز برای مثبت
    if not df_positive.empty:
        fig.add_trace(go.Scatter(
            x=df_positive['timestamp'],
            y=df_positive[column],
            mode='lines',
            line=dict(color='#00E676', width=5),
            showlegend=False,
            hovertemplate='<b>%{y:+.2f}%</b><extra></extra>'
        ), row=row, col=1)
    
    # خط قرمز برای منفی
    if not df_negative.empty:
        fig.add_trace(go.Scatter(
            x=df_negative['timestamp'],
            y=df_negative[column],
            mode='lines',
            line=dict(color='#FF1744', width=5),
            showlegend=False,
            hovertemplate='<b>%{y:+.2f}%</b><extra></extra>'
        ), row=row, col=1)
    
    # اگه از مثبت به منفی یا بالعکس میره، باید خطوط وصل بشن
    # پیدا کردن نقاط تلاقی با صفر
    transitions = []
    for i in range(len(df) - 1):
        curr_val = df[column].iloc[i]
        next_val = df[column].iloc[i + 1]
        
        # اگه علامت عوض شد
        if (curr_val >= 0 and next_val < 0) or (curr_val < 0 and next_val >= 0):
            # محاسبه نقطه دقیق تلاقی با صفر
            curr_time = df['timestamp'].iloc[i]
            next_time = df['timestamp'].iloc[i + 1]
            
            # میانیابی خطی
            t = abs(curr_val) / (abs(curr_val) + abs(next_val))
            cross_time = curr_time + (next_time - curr_time) * t
            
            transitions.append({
                'time': cross_time,
                'value': 0,
                'prev_time': curr_time,
                'prev_val': curr_val,
                'next_time': next_time,
                'next_val': next_val
            })
    
    # رسم خطوط اتصال
    for trans in transitions:
        color = '#00E676' if trans['prev_val'] >= 0 else '#FF1744'
        fig.add_trace(go.Scatter(
            x=[trans['prev_time'], trans['time']],
            y=[trans['prev_val'], 0],
            mode='lines',
            line=dict(color=color, width=5),
            showlegend=False,
            hoverinfo='skip'
        ), row=row, col=1)
        
        color = '#FF1744' if trans['next_val'] < 0 else '#00E676'
        fig.add_trace(go.Scatter(
            x=[trans['time'], trans['next_time']],
            y=[0, trans['next_val']],
            mode='lines',
            line=dict(color=color, width=5),
            showlegend=False,
            hoverinfo='skip'
        ), row=row, col=1)
