# utils/chart_creator.py
"""ماژول ساخت نمودارهای بازار با نمایش قیمت پایانی"""

import logging
import pytz
import math
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
from PIL import Image, ImageDraw, ImageFont
from utils.sheets_storage import read_from_sheets
from persiantools.jdatetime import JalaliDateTime
from config import (
    FONT_MEDIUM_PATH, FONT_REGULAR_PATH,
    CHART_WIDTH, CHART_HEIGHT, CHART_SCALE,
    COLOR_POSITIVE, COLOR_NEGATIVE, COLOR_BACKGROUND,
    COLOR_GRID, COLOR_GOLD, CHANNEL_HANDLE,
    TIMEZONE, Y_AXIS_STEP
)

logger = logging.getLogger(__name__)


def round_to_nearest(value, step=50):
    return round(value / step) * step


def calculate_y_range_with_steps(data_min, data_max, step=50):
    if data_min == 0 and data_max == 0:
        return -step, step
    if data_min == data_max:
        return data_min - step, data_max + step
    y_min = math.floor(data_min / step) * step - step
    y_max = math.ceil(data_max / step) * step + step
    return y_min, y_max


def set_y_range(fig, df, column, row, padding_percent=0.3):
    col_min = df[column].min()
    col_max = df[column].max()
    padding = 0.1 if col_min == col_max else (col_max - col_min) * padding_percent
    fig.update_yaxes(range=[col_min - padding, col_max + padding], row=row, col=1)


def set_y_range_for_series(fig, series, row, padding_percent=0.3):
    col_min = series.min()
    col_max = series.max()
    padding = 0.1 if col_min == col_max else (col_max - col_min) * padding_percent
    fig.update_yaxes(range=[col_min - padding, col_max + padding], row=row, col=1)


def add_conditional_line(fig, df, column, row):
    for i in range(len(df) - 1):
        curr_val = df[column].iloc[i]
        next_val = df[column].iloc[i + 1]
        curr_time = df['timestamp'].iloc[i]
        next_time = df['timestamp'].iloc[i + 1]

        color = COLOR_POSITIVE if curr_val >= 0 else COLOR_NEGATIVE

        if (curr_val >= 0 and next_val < 0) or (curr_val < 0 and next_val >= 0):
            t = abs(curr_val) / (abs(curr_val) + abs(next_val))
            cross_time = curr_time + (next_time - curr_time) * t

            fig.add_trace(go.Scatter(
                x=[curr_time, cross_time], y=[curr_val, 0],
                mode='lines', line=dict(color=color, width=5, shape='spline'),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=1)

            color_next = COLOR_NEGATIVE if next_val < 0 else COLOR_POSITIVE
            fig.add_trace(go.Scatter(
                x=[cross_time, next_time], y=[0, next_val],
                mode='lines', line=dict(color=color_next, width=5, shape='spline'),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=1)
        else:
            fig.add_trace(go.Scatter(
                x=[curr_time, next_time], y=[curr_val, next_val],
                mode='lines', line=dict(color=color, width=5, shape='spline'),
                showlegend=False,
                hovertemplate='<b>%{y:+.2f}%</b><extra></extra>' if i == 0 else None
            ), row=row, col=1)


def create_market_charts():
    try:
        data_rows = read_from_sheets(limit=500)
        if not data_rows:
            logger.warning("⚠️ داده‌ای از Sheets دریافت نشد")
            return None

        df = pd.DataFrame(data_rows, columns=[
            'timestamp', 'gold_price_usd', 'dollar_price', 'shams_price',
            'dollar_change_percent', 'shams_change_percent',
            'fund_weighted_change_percent', 'fund_final_price_avg',
            'fund_weighted_bubble_percent',
            'sarane_kharid_weighted', 'sarane_forosh_weighted',
            'ekhtelaf_sarane_weighted'
        ])

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        numeric_cols = df.columns[1:]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

        tehran_tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tehran_tz).date()
        df = df[df['timestamp'].dt.date == today].copy()

        if df.empty:
            logger.info("ℹ️ داده‌ای برای امروز پیدا نشد")
            return None

        df = df.sort_values('timestamp')
        jalali_now = JalaliDateTime.now(tehran_tz)
        date_time_str = jalali_now.strftime("%Y/%m/%d - %H:%M")

        fig = make_subplots(
            rows=6, cols=1,
            subplot_titles=(
                '<b>قیمت اونس طلا ($)</b>',
                '<b>دلار آزاد (%)</b>',
                '<b>شمش طلای بورس کالا (%)</b>',
                '<b>آخرین قیمت و قیمت پایانی صندوق‌های طلا (%)</b>',
                '<b>میانگین حباب صندوق‌های طلا (%)</b>',
                '<b>سرانه خرید و فروش و اختلاف آن</b>'
            ),
            vertical_spacing=0.045,
            shared_xaxes=True,
            specs=[[{}], [{}], [{}], [{}], [{}], [{"secondary_y": True}]]
        )

        try:
            ImageFont.truetype(FONT_MEDIUM_PATH, 40)
            chart_font_family = "Vazirmatn-Medium, Vazirmatn, sans-serif"
        except:
            chart_font_family = "Vazirmatn, Arial, sans-serif"

        for annotation in fig['layout']['annotations']:
            annotation.font = dict(size=32, color='#8B949E', family=chart_font_family)

        last_gold = df['gold_price_usd'].iloc[-1]
        last_dollar = df['dollar_change_percent'].iloc[-1]
        last_shams = df['shams_change_percent'].iloc[-1]
        last_fund = df['fund_weighted_change_percent'].iloc[-1]
        last_final = df['fund_final_price_avg'].iloc[-1]
        last_bubble = df['fund_weighted_bubble_percent'].iloc[-1]
        last_kharid = df['sarane_kharid_weighted'].iloc[-1]
        last_forosh = df['sarane_forosh_weighted'].iloc[-1]
        last_ekhtelaf = df['ekhtelaf_sarane_weighted'].iloc[-1]

        # نمودار 1: طلا
        gold_min = last_gold * 0.98
        gold_max = last_gold * 1.02
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['gold_price_usd'],
            name='طلا', line=dict(color=COLOR_GOLD, width=5),
            hovertemplate='<b>%{y:.0f} $</b><extra></extra>'
        ), row=1, col=1)
        fig.update_yaxes(range=[gold_min, gold_max], row=1, col=1)

        # نمودار 2 و 3
        add_conditional_line(fig, df, 'dollar_change_percent', 2)
        set_y_range(fig, df, 'dollar_change_percent', 2)
        add_conditional_line(fig, df, 'shams_change_percent', 3)
        set_y_range(fig, df, 'shams_change_percent', 3)

        # نمودار 4: آخرین قیمت و پایانی
        add_conditional_line(fig, df, 'fund_weighted_change_percent', 4)
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['fund_final_price_avg'],
            name='قیمت پایانی', line=dict(color='#2196F3', width=4),
            hovertemplate='پایانی: <b>%{y:+.2f}%</b><extra></extra>'
        ), row=4, col=1)
        all_values = pd.concat([df['fund_weighted_change_percent'], df['fund_final_price_avg']])
        set_y_range_for_series(fig, all_values, 4)

        # نمودار 5: حباب
        add_conditional_line(fig, df, 'fund_weighted_bubble_percent', 5)
        set_y_range(fig, df, 'fund_weighted_bubble_percent', 5)

        # نمودار 6: سرانه با محور دوم مخفی
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['sarane_kharid_weighted'],
            name='خرید حقیقی', line=dict(color=COLOR_POSITIVE, width=5),
            hovertemplate='خرید: <b>%{y:.2f}</b><extra></extra>'
        ), row=6, col=1, secondary_y=False)
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['sarane_forosh_weighted'],
            name='فروش حقیقی', line=dict(color=COLOR_NEGATIVE, width=5),
            hovertemplate='فروش: <b>%{y:.2f}</b><extra></extra>'
        ), row=6, col=1, secondary_y=False)

        colors_fill = [
            'rgba(0,230,118,0.75)' if x > 0 else
            'rgba(255,23,68,0.75)' if x < 0 else
            'rgba(72,79,88,0.75)' for x in df['ekhtelaf_sarane_weighted']
        ]
        fig.add_trace(go.Bar(
            x=df['timestamp'], y=df['ekhtelaf_sarane_weighted'],
            name='اختلاف سرانه', width=0.9,
            marker=dict(color=colors_fill, line=dict(color=colors_fill, width=4)),
            hovertemplate='اختلاف: <b>%{y:.2f}</b><extra></extra>'
        ), row=6, col=1, secondary_y=True)
        fig.update_yaxes(showticklabels=False, showline=False, showgrid=False, row=6, col=1, secondary_y=True)

        kharid_min = df['sarane_kharid_weighted'].min()
        kharid_max = df['sarane_kharid_weighted'].max()
        forosh_min = df['sarane_forosh_weighted'].min()
        forosh_max = df['sarane_forosh_weighted'].max()
        y_min, y_max = calculate_y_range_with_steps(min(kharid_min, forosh_min), max(kharid_max, forosh_max), step=Y_AXIS_STEP)
        fig.update_yaxes(range=[y_min, y_max], dtick=Y_AXIS_STEP, row=6, col=1, secondary_y=False)

        # Layout و تنظیمات کلی
        fig.update_layout(
            height=CHART_HEIGHT,
            paper_bgcolor=COLOR_BACKGROUND,
            plot_bgcolor=COLOR_BACKGROUND,
            font=dict(color='#C9D1D9', family=chart_font_family, size=25),
            hovermode='x unified',
            showlegend=False,
            margin=dict(l=60, r=120, t=120, b=40),
        )

        fig.add_annotation(
            text='<b>📊 روند بازار</b>',
            x=0.98, y=1.04, xref='paper', yref='paper',
            xanchor='right', yanchor='top',
            font=dict(size=40, color=COLOR_GOLD, family=chart_font_family),
            showarrow=False
        )

        fig.add_annotation(
            text=f'<b>{date_time_str}</b>',
            x=0.02, y=1.04, xref='paper', yref='paper',
            xanchor='left', yanchor='top',
            font=dict(size=40, color='#FFFFFF', family=chart_font_family),
            showarrow=False
        )

        step = max(1, len(df) // 10)
        tick_vals = df['timestamp'][::step].tolist()
        for i in range(1, 7):
            fig.update_xaxes(
                type='date', tickformat='%H:%M', tickmode='array',
                tickvals=tick_vals, tickangle=0, tickfont=dict(size=25),
                gridcolor=COLOR_GRID, showgrid=True, zeroline=False,
                showline=True, linewidth=1, linecolor='#30363D',
                row=i, col=1
            )
            fig.update_yaxes(
                tickfont=dict(size=25), gridcolor=COLOR_GRID, showgrid=True,
                zeroline=True, zerolinecolor='#30363D', zerolinewidth=2,
                showline=True, linewidth=1, linecolor='#30363D',
                row=i, col=1
            )
            if i > 1:
                fig.add_hline(y=0, line_dash='dot', line_color='#484F58', line_width=2, row=i, col=1)

        # تبدیل به تصویر
        img_bytes = fig.to_image(format='png', width=CHART_WIDTH, height=CHART_HEIGHT, scale=CHART_SCALE)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')

        # واترمارک
        try:
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(FONT_REGULAR_PATH, 46)
            text = CHANNEL_HANDLE.replace("@", "")
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            x = img.width - w - 25
            y = int(img.height * 0.83)
            draw.text((x, y), text, fill=(201, 209, 217, 160), font=font)
        except Exception as e:
            logger.warning(f"⚠️ خطا در واترمارک: {e}")

        output = io.BytesIO()
        img.save(output, format='PNG', optimize=True, quality=92)
        output.seek(0)

        logger.info("✅ نمودارهای بازار ساخته شدند")
        return output.getvalue()

    except Exception as e:
        logger.error(f'❌ خطا در ساخت نمودار: {e}', exc_info=True)
        return None