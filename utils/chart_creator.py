# utils/chart_creator.py

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
    """گرد کردن عدد به نزدیک‌ترین مضرب step"""
    return round(value / step) * step

def calculate_y_range_with_steps(data_min, data_max, step=50):
    """محاسبه محدوده محور Y با گام‌های مشخص"""
    if data_min == 0 and data_max == 0:
        return -step, step

    if data_min == data_max:
        return data_min - step, data_max + step

    y_min = math.floor(data_min / step) * step
    y_max = math.ceil(data_max / step) * step
    margin = step * 0.3
    y_min -= margin
    y_max += margin
    return y_min, y_max

def create_market_charts():
    """ساخت نمودارهای بازار با 7 subplot (اضافه شدن پول حقیقی)"""
    try:
        data_rows = read_from_sheets(limit=800)
        if not data_rows:
            logger.warning("⚠️ داده‌ای از Sheets دریافت نشد")
            return None

        # تعریف DataFrame با 13 ستون
        df = pd.DataFrame(data_rows, columns=[
            'timestamp', 'gold_price_usd', 'dollar_price', 'shams_price',
            'dollar_change_percent', 'shams_change_percent',
            'fund_weighted_change_percent', 'fund_final_price_avg',
            'fund_weighted_bubble_percent', 'sarane_kharid_weighted',
            'sarane_forosh_weighted', 'ekhtelaf_sarane_weighted',
            'pol_hagigi' 
        ])

        df['timestamp'] = pd.to_datetime(df['timestamp'])
        numeric_cols = df.columns[1:]
        df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors='coerce')

        # فیلتر کردن داده‌های امروز
        tehran_tz = pytz.timezone(TIMEZONE)
        today = datetime.now(tehran_tz).date()
        df = df[df['timestamp'].dt.date == today].copy()

        if df.empty:
            logger.info("ℹ️ داده‌ای برای امروز پیدا نشد")
            return None

        df = df.sort_values('timestamp')
        jalali_now = JalaliDateTime.now(tehran_tz)
        date_time_str = jalali_now.strftime("%Y/%m/%d - %H:%M")

        # ساخت نمودار با 7 ردیف
        fig = make_subplots(
            rows=7, cols=1, 
            subplot_titles=(
                '<b>قیمت اونس طلا ($)</b>',
                '<b>دلار آزاد (%)</b>',
                '<b>شمش طلای بورس کالا (%)</b>',
                '<b>آخرین قیمت و قیمت پایانی صندوق‌های طلا (%)</b>',
                '<b>میانگین حباب صندوق‌های طلا (%)</b>',
                '<b>ورود پول حقیقی</b>',  
                '<b>سرانه خرید و فروش و اختلاف آن</b>'
            ),
            vertical_spacing=0.035,  
            shared_xaxes=True
        )

        # بارگذاری فونت
        try:
            ImageFont.truetype(FONT_MEDIUM_PATH, 40)
            chart_font_family = "Vazirmatn-Medium, Vazirmatn, sans-serif"
        except:
            chart_font_family = "Vazirmatn, Arial, sans-serif"

        for annotation in fig['layout']['annotations']:
            annotation.font = dict(size=32, color='#8B949E', family=chart_font_family)

        # مقادیر آخرین داده
        last_gold = df['gold_price_usd'].iloc[-1]
        last_dollar = df['dollar_change_percent'].iloc[-1]
        last_shams = df['shams_change_percent'].iloc[-1]
        last_fund = df['fund_weighted_change_percent'].iloc[-1]
        last_final = df['fund_final_price_avg'].iloc[-1]
        last_bubble = df['fund_weighted_bubble_percent'].iloc[-1]
        last_pol = df['pol_hagigi'].iloc[-1]  
        last_kharid = df['sarane_kharid_weighted'].iloc[-1]
        last_forosh = df['sarane_forosh_weighted'].iloc[-1]
        last_ekhtelaf = df['ekhtelaf_sarane_weighted'].iloc[-1]

        # ═══════════════════════════════════════════════════════
        # نمودار 1: قیمت طلا
        # ═══════════════════════════════════════════════════════
        window = 200
        recent_prices = df['gold_price_usd'].iloc[-window:]
        margin = 0.005
        gold_min = recent_prices.min() * (1 - margin)
        gold_max = recent_prices.max() * (1 + margin)

        fig.add_trace(go.Scatter(
            x=df['timestamp'],
            y=df['gold_price_usd'],
            name='طلا',
            line=dict(color=COLOR_GOLD, width=5),
            hovertemplate='<b>%{y:.0f} $</b><extra></extra>'
        ), row=1, col=1)

        fig.update_yaxes(range=[gold_min, gold_max], row=1, col=1)

        # ═══════════════════════════════════════════════════════
        # نمودار 2-3: دلار و شمش
        # ═══════════════════════════════════════════════════════
        add_conditional_line(fig, df, 'dollar_change_percent', 2)
        set_y_range(fig, df, 'dollar_change_percent', 2)

        add_conditional_line(fig, df, 'shams_change_percent', 3)
        set_y_range(fig, df, 'shams_change_percent', 3)

        # ═══════════════════════════════════════════════════════
        # نمودار 4: آخرین قیمت + قیمت پایانی
        # ═══════════════════════════════════════════════════════
        add_conditional_line(fig, df, 'fund_weighted_change_percent', 4)

        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['fund_final_price_avg'],
            name='قیمت پایانی',
            line=dict(color='#2196F3', width=4),
            hovertemplate='پایانی: <b>%{y:+.2f}%</b><extra></extra>'
        ), row=4, col=1)

        all_values = pd.concat([
            df['fund_weighted_change_percent'],
            df['fund_final_price_avg']
        ])
        set_y_range_for_series(fig, all_values, 4)
        logger.info(f"✅ نمودار 4: آخرین={last_fund:+.2f}%, پایانی={last_final:+.2f}%")

        # ═══════════════════════════════════════════════════════
        # نمودار 5: حباب
        # ═══════════════════════════════════════════════════════
        add_conditional_line(fig, df, 'fund_weighted_bubble_percent', 5)
        set_y_range(fig, df, 'fund_weighted_bubble_percent', 5)

        # ═══════════════════════════════════════════════════════
        # ✅ نمودار 6: پول حقیقی (جدید)
        # ═══════════════════════════════════════════════════════
        add_conditional_line(fig, df, 'pol_hagigi', 6)
        set_y_range(fig, df, 'pol_hagigi', 6)

        # ═══════════════════════════════════════════════════════
        # نمودار 7: سرانه با دو محور Y جداگانه
        # ═══════════════════════════════════════════════════════
        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['sarane_kharid_weighted'],
            name='خرید حقیقی',
            line=dict(color=COLOR_POSITIVE, width=5),
            hovertemplate='خرید: <b>%{y:.2f}</b><extra></extra>',
            yaxis='y7'
        ), row=7, col=1)

        fig.add_trace(go.Scatter(
            x=df['timestamp'], y=df['sarane_forosh_weighted'],
            name='فروش حقیقی',
            line=dict(color=COLOR_NEGATIVE, width=5),
            hovertemplate='فروش: <b>%{y:.2f}</b><extra></extra>',
            yaxis='y7'
        ), row=7, col=1)

        colors_fill = [
            'rgba(0,230,118,0.75)' if x > 0 else 'rgba(255,23,68,0.75)' if x < 0 else 'rgba(72,79,88,0.75)'
            for x in df['ekhtelaf_sarane_weighted']
        ]

        fig.add_trace(go.Bar(
            x=df['timestamp'], y=df['ekhtelaf_sarane_weighted'],
            name='اختلاف سرانه',
            width=0.9,
            marker=dict(
                color=colors_fill,
                line=dict(color=colors_fill, width=4)
            ),
            hovertemplate='اختلاف: <b>%{y:.2f}</b><extra></extra>',
            yaxis='y14'
        ), row=7, col=1)

        kharid_min = df['sarane_kharid_weighted'].min()
        kharid_max = df['sarane_kharid_weighted'].max()
        forosh_min = df['sarane_forosh_weighted'].min()
        forosh_max = df['sarane_forosh_weighted'].max()

        lines_min = min(kharid_min, forosh_min)
        lines_max = max(kharid_max, forosh_max)
        lines_padding = max(10, (lines_max - lines_min) * 0.15)

        fig.update_yaxes(
            range=[lines_min - lines_padding, lines_max + lines_padding],
            row=7, col=1
        )

        ekhtelaf_min = df['ekhtelaf_sarane_weighted'].min()
        ekhtelaf_max = df['ekhtelaf_sarane_weighted'].max()
        ekhtelaf_padding = max(10, (ekhtelaf_max - ekhtelaf_min) * 0.15)

        fig.update_layout(
            yaxis14=dict(
                overlaying='y7',
                side='right',
                range=[ekhtelaf_min - ekhtelaf_padding, ekhtelaf_max + ekhtelaf_padding],
                showgrid=False,
                showticklabels=False,
                zeroline=False
            )
        )

        # ═══════════════════════════════════════════════════════
        # تنظیمات کلی Layout
        # ═══════════════════════════════════════════════════════
        fig.update_layout(
            height=CHART_HEIGHT + 300,
            paper_bgcolor=COLOR_BACKGROUND,
            plot_bgcolor=COLOR_BACKGROUND,
            font=dict(color='#C9D1D9', family=chart_font_family, size=25),
            hovermode='x unified',
            showlegend=False,
            margin=dict(l=60, r=120, t=120, b=60),
        )

        # عنوان و تاریخ
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

        # ═══════════════════════════════════════════════════════
        # برچسب‌های آخرین مقدار
        # ═══════════════════════════════════════════════════════
        # نمودار 1-3
        fig.add_annotation(
            text=f'<b>{last_gold:,.0f}$</b>',
            x=1.01, y=last_gold, xref='paper', yref='y1',
            xanchor='left', yanchor='middle',
            font=dict(size=28, color=COLOR_GOLD, family=chart_font_family),
            showarrow=False
        )

        dollar_color = COLOR_POSITIVE if last_dollar >= 0 else COLOR_NEGATIVE
        fig.add_annotation(
            text=f'<b>{last_dollar:+.2f}%</b>',
            x=1.01, y=last_dollar, xref='paper', yref='y2',
            xanchor='left', yanchor='middle',
            font=dict(size=28, color=dollar_color, family=chart_font_family),
            showarrow=False
        )

        shams_color = COLOR_POSITIVE if last_shams >= 0 else COLOR_NEGATIVE
        fig.add_annotation(
            text=f'<b>{last_shams:+.2f}%</b>',
            x=1.01, y=last_shams, xref='paper', yref='y3',
            xanchor='left', yanchor='middle',
            font=dict(size=28, color=shams_color, family=chart_font_family),
            showarrow=False
        )

        # نمودار 4
        fund_color = COLOR_POSITIVE if last_fund >= 0 else COLOR_NEGATIVE
        fig.add_annotation(
            text=f'<b>{last_fund:+.2f}%</b>',
            x=1.01, y=last_fund, xref='paper', yref='y4',
            xanchor='left', yanchor='middle',
            font=dict(size=28, color=fund_color, family=chart_font_family),
            showarrow=False
        )

        final_color = '#2196F3'
        min_gap = 0.04
        if abs(last_final - last_fund) < min_gap:
            yshift = -50 if last_final > last_fund else 50
        else:
            yshift = 0

        fig.add_annotation(
            text=f'<b>{last_final:+.2f}%</b>',
            x=1.01, y=last_final, xref='paper', yref='y4',
            xanchor='left', yanchor='middle',
            yshift=yshift,
            font=dict(size=28, color=final_color, family=chart_font_family),
            showarrow=False
        )

        # نمودار 5
        bubble_color = COLOR_POSITIVE if last_bubble >= 0 else COLOR_NEGATIVE
        fig.add_annotation(
            text=f'<b>{last_bubble:+.2f}%</b>',
            x=1.01, y=last_bubble, xref='paper', yref='y5',
            xanchor='left', yanchor='middle',
            font=dict(size=28, color=bubble_color, family=chart_font_family),
            showarrow=False
        )

        # ✅ نمودار 6: پول حقیقی (فرمت سه‌رقم جدا بدون ممیز)
        pol_color = COLOR_POSITIVE if last_pol >= 0 else COLOR_NEGATIVE
        pol_formatted = f"{int(last_pol):+,}".replace(',', '٬')
        fig.add_annotation(
            text=f'<b>{pol_formatted}</b>',
            x=1.01, y=last_pol, xref='paper', yref='y6',
            xanchor='left', yanchor='middle',
            font=dict(size=28, color=pol_color, family=chart_font_family),
            showarrow=False
        )

        # نمودار 7: سرانه - برچسب‌های سمت راست با فرمت مناسب
        ekhtelaf_color = COLOR_POSITIVE if last_ekhtelaf >= 0 else COLOR_NEGATIVE

        # محاسبه موقعیت‌های y برای برچسب‌ها بر اساس محدوده واقعی داده‌ها
        lines_range = lines_max - lines_min
        
        # خرید حقیقی (در بالا)
        kharid_y = lines_max - (lines_range * 0.05)
        
        # فروش حقیقی (در پایین)
        forosh_y = lines_min + (lines_range * 0.05)
        
        # اختلاف (در وسط)
        ekhtelaf_y = (lines_max + lines_min) / 2

        fig.add_annotation(
            text=f'<b>خ: {int(last_kharid):,}</b>'.replace(',', '٬'),
            x=1.01, y=kharid_y, xref='paper', yref='y7',
            xanchor='left', yanchor='middle',
            font=dict(size=28, color=COLOR_POSITIVE, family=chart_font_family),
            showarrow=False
        )

        fig.add_annotation(
            text=f'<b>اخ: {int(last_ekhtelaf):+,}</b>'.replace(',', '٬'),
            x=1.01, y=ekhtelaf_y, xref='paper', yref='y7',
            xanchor='left', yanchor='middle',
            font=dict(size=28, color=ekhtelaf_color, family=chart_font_family),
            showarrow=False
        )

        fig.add_annotation(
            text=f'<b>ف: {int(last_forosh):,}</b>'.replace(',', '٬'),
            x=1.01, y=forosh_y, xref='paper', yref='y7',
            xanchor='left', yanchor='middle',
            font=dict(size=28, color=COLOR_NEGATIVE, family=chart_font_family),
            showarrow=False
        )

        # ═══════════════════════════════════════════════════════
        # تنظیمات محورها
        # ═══════════════════════════════════════════════════════
        df['timestamp'] = pd.to_datetime(df['timestamp'])

        TICK_MINUTES = 30
        start_ts = df['timestamp'].iloc[0]
        end_ts = df['timestamp'].iloc[-1]

        tick_vals = pd.date_range(
            start=start_ts.floor('30min'),
            end=end_ts.ceil('30min'),
            freq='30min'
        ).tolist()

        tick_vals[0] = start_ts
        tick_vals[-1] = end_ts

        logger.info(f"📊 labels: {len(tick_vals)} | interval: 30 min")

        for i in range(1, 8):
            fig.update_xaxes(
                type='date',
                tickmode='array',
                tickvals=tick_vals,
                tickformat='%H:%M',
                tickangle=-45,
                tickfont=dict(size=25),
                gridcolor=COLOR_GRID,
                showgrid=True,
                zeroline=False,
                showline=True,
                linewidth=1,
                linecolor='#30363D',
                row=i, col=1
            )

            fig.update_yaxes(
                tickfont=dict(size=25),
                gridcolor=COLOR_GRID,
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
                fig.add_hline(
                    y=0,
                    line_dash='dot',
                    line_color='#484F58',
                    line_width=2,
                    row=i, col=1
                )

        # ═══════════════════════════════════════════════════════
        # تبدیل به تصویر و واترمارک
        # ═══════════════════════════════════════════════════════
        img_bytes = fig.to_image(
            format='png', 
            width=CHART_WIDTH, 
            height=CHART_HEIGHT + 300,
            scale=CHART_SCALE
        )
        img = Image.open(io.BytesIO(img_bytes)).convert('RGBA')

        try:
            draw = ImageDraw.Draw(img)
            font = ImageFont.truetype(FONT_REGULAR_PATH, 46)
            text = CHANNEL_HANDLE.replace("@", "")
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            x = img.width - w - 25
            y = int(img.height * 0.85)
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

def set_y_range(fig, df, column, row, padding_percent=0.3):
    """تنظیم محدوده محور Y"""
    col_min = df[column].min()
    col_max = df[column].max()
    padding = 0.1 if col_min == col_max else (col_max - col_min) * padding_percent
    fig.update_yaxes(range=[col_min - padding, col_max + padding], row=row, col=1)

def set_y_range_for_series(fig, series, row, padding_percent=0.3):
    """تنظیم محدوده محور Y برای یک Series"""
    col_min = series.min()
    col_max = series.max()
    padding = 0.1 if col_min == col_max else (col_max - col_min) * padding_percent
    fig.update_yaxes(range=[col_min - padding, col_max + padding], row=row, col=1)

def add_conditional_line(fig, df, column, row):
    """رسم خط با تغییر رنگ در محل عبور از صفر"""
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
                mode='lines',
                line=dict(color=color, width=5, shape='spline'),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=1)

            color_next = COLOR_NEGATIVE if next_val < 0 else COLOR_POSITIVE
            fig.add_trace(go.Scatter(
                x=[cross_time, next_time], y=[0, next_val],
                mode='lines',
                line=dict(color=color_next, width=5, shape='spline'),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=1)
        else:
            fig.add_trace(go.Scatter(
                x=[curr_time, next_time], y=[curr_val, next_val],
                mode='lines',
                line=dict(color=color, width=5, shape='spline'),
                showlegend=False,
                hovertemplate='<b>%{y:+.2f}%</b><extra></extra>' if i == 0 else None
            ), row=row, col=1)
