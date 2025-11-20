# utils/chart_creator.py — نسخه نهایی با تاریخ سفید چپ بالا + تیتر زرد راست بالا

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
from persiantools.jdatetime import JalaliDateTime

logger = logging.getLogger(__name__)

def create_market_charts():
    """
    ساخت نمودار ۶ خطی زیبا با فونت Vazirmatn-Medium
    تیتر "روند بازار" در بالا راست (زرد) + تاریخ و ساعت در بالا چپ (سفید)
    """
    try:
        data_rows = read_from_sheets(limit=500)
        if not data_rows:
            logger.warning("داده‌ای از Sheets دریافت نشد")
            return None

        df = pd.DataFrame(data_rows, columns=[
            'timestamp', 'gold_price_usd', 'dollar_change_percent',
            'shams_change_percent', 'fund_weighted_change_percent',
            'fund_weighted_bubble_percent',
            'sarane_kharid_weighted', 'sarane_forosh_weighted',
            'ekhtelaf_sarane_weighted'
        ])

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        numeric_cols = df.columns[1:]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

        tehran_tz = pytz.timezone('Asia/Tehran')
        today = datetime.now(tehran_tz).date()
        df = df[df['timestamp'].dt.date == today].copy()

        if df.empty:
            logger.info("داده‌ای برای امروز پیدا نشد")
            return None

        df = df.sort_values('timestamp')

        # تاریخ و ساعت شمسی برای بالا چپ
        jalali_now = JalaliDateTime.now(tehran_tz)
        date_time_str = jalali_now.strftime("%Y/%m/%d - %H:%M")

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

        # فونت Vazirmatn-Medium برای کل نمودار
        try:
            ImageFont.truetype("assets/fonts/Vazirmatn-Medium.ttf", 40)
            chart_font_family = "Vazirmatn-Medium, Vazirmatn, sans-serif"
        except:
            chart_font_family = "Vazirmatn, Arial, sans-serif"

        # ۱. قیمت طلا
        gold_current = df['gold_price_usd'].iloc[-1]
        gold_min = gold_current * 0.97
        gold_max = gold_current * 1.03

        fig.add_trace(go.Scatter(
            x=df['timestamp'], 
            y=df['gold_price_usd'],
            name='طلا', 
            line=dict(color='#FFD700', width=5), 
            hovertemplate='<b>%{y:.2f} $</b><extra></extra>'
        ), row=1, col=1)

        fig.update_yaxes(range=[gold_min, gold_max], row=1, col=1)

        # ۲ تا ۵: خطوط شرطی
        add_conditional_line(fig, df, 'dollar_change_percent', 2)
        add_conditional_line(fig, df, 'shams_change_percent', 3)
        add_conditional_line(fig, df, 'fund_weighted_change_percent', 4)
        add_conditional_line(fig, df, 'fund_weighted_bubble_percent', 5)

        # ۶. سرانه‌ها
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

        colors_sarane = ['rgba(0,230,118,0.75)' if x >= 0 else 'rgba(255,23,68,0.75)' 
                         for x in df['ekhtelaf_sarane_weighted']]

        fig.add_trace(go.Bar(
            x=df['timestamp'], 
            y=df['ekhtelaf_sarane_weighted'],
            name='اختلاف سرانه', 
            marker_color=colors_sarane,
            hovertemplate='اختلاف: <b>%{y:.2f}</b><extra></extra>'
        ), row=6, col=1)

        # تنظیمات کلی
        fig.update_layout(
            height=2200,
            paper_bgcolor='#0D1117',
            plot_bgcolor='#0D1117',
            font=dict(color='#C9D1D9', family=chart_font_family, size=25),
            hovermode='x unified',
            showlegend=False,
            margin=dict(l=60, r=60, t=120, b=40),
        )

        # تیتر "روند بازار" — سمت راست بالا (زرد)
        fig.add_annotation(
            text='<b>📊 روند بازار</b>',
            x=0.98,
            y=1.04,
            xref='paper',
            yref='paper',
            xanchor='right',
            yanchor='top',
            font=dict(size=36, color='#FFD700', family=chart_font_family),
            showarrow=False
        )

        # تاریخ و ساعت — سمت چپ بالا (سفید)
        fig.add_annotation(
            text=f'<b>{date_time_str}</b>',
            x=0.02,
            y=1.04,
            xref='paper',
            yref='paper',
            xanchor='left',
            yanchor='top',
            font=dict(size=38, color='#FFFFFF', family=chart_font_family),
            showarrow=False
        )

        # تنظیمات محورها
        for i in range(1, 7):
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

            if i > 1:
                fig.add_hline(y=0, line_dash='dot', line_color='#484F58', line_width=2, row=i, col=1)

        for annotation in fig['layout']['annotations']:
            # فقط عنوان‌های subplot را تنظیم کن، نه annotation‌های جدید
            if annotation.xref != 'paper':
                annotation.font = dict(size=28, color='#8B949E', family=chart_font_family)

        # تولید تصویر
        img_bytes = fig.to_image(format='png', width=1400, height=2200, scale=2)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')

        # واترمارک — پایین راست (مکان امن)
        try:
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype('assets/fonts/Vazirmatn-Regular.ttf', 46)
            text = 'Gold_Iran_Market'
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]

            # امن‌ترین نقطه
            x = img.width - w - 25
            y = img.height - h - 25

            draw.text((x, y), text, fill=(201,209,217,160), font=font)
        except:
            pass

        output = io.BytesIO()
        img.save(output, format='PNG', optimize=True, quality=92)
        output.seek(0)
        return output.getvalue()

    except Exception as e:
        logger.error(f'خطا در ساخت نمودار: {e}', exc_info=True)
        return None


def add_conditional_line(fig, df, column, row):
    """
    خط شرطی با رنگ سبز/قرمز — دقیقاً مثل کد اصلی
    """
    for i in range(len(df) - 1):
        curr_val = df[column].iloc[i]
        next_val = df[column].iloc[i + 1]
        curr_time = df['timestamp'].iloc[i]
        next_time = df['timestamp'].iloc[i + 1]

        color = '#00E676' if curr_val >= 0 else '#FF1744'

        if (curr_val >= 0 and next_val < 0) or (curr_val < 0 and next_val >= 0):
            t = abs(curr_val) / (abs(curr_val) + abs(next_val))
            cross_time = curr_time + (next_time - curr_time) * t

            fig.add_trace(go.Scatter(
                x=[curr_time, cross_time],
                y=[curr_val, 0],
                mode='lines',
                line=dict(color=color, width=5, shape='spline'),
                showlegend=False,
                hoverinfo='skip'
            ), row=row, col=1)

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
            fig.add_trace(go.Scatter(
                x=[curr_time, next_time],
                y=[curr_val, next_val],
                mode='lines',
                line=dict(color=color, width=5, shape='spline'),
                showlegend=False,
                hovertemplate='<b>%{y:+.2f}%</b><extra></extra>' if i == 0 else None
            ), row=row, col=1)