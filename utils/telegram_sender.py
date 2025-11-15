"""
ماژول ارسال داده‌ها به تلگرام
یک تصویر بزرگ شامل نمودار همه صندوق‌ها + جدول + کپشن خلاصه
"""

import io
import logging
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from persiantools.jdatetime import JalaliDateTime
import requests

logger = logging.getLogger(__name__)


def send_to_telegram(bot_token, chat_id, data, dollar_prices, gold_price, gold_yesterday, gold_time, yesterday_close):
    """ارسال یک تصویر بزرگ + کپشن به تلگرام"""
    
    # FIXED: بررسی امنیتی برای جلوگیری از خطای NoneType
    if data is None:
        logger.error("❌ داده‌های پردازش‌شده (data) مقدار None دارد. ارسال متوقف شد.")
        return False
        
    try:
        # 1. ایجاد تصویر بزرگ (نمودار همه صندوق‌ها + جدول)
        logger.info("🎨 در حال ساخت تصویر با همه صندوق‌ها...")
        img_bytes = create_combined_image(
            data['Fund_df'],
            dollar_prices['last_trade'],
            gold_price,
            gold_yesterday,
            data['dfp'],
            yesterday_close
        )
        
        # 2. ایجاد کپشن خلاصه
        logger.info("📝 در حال ساخت کپشن...")
        caption = create_caption(
            data,
            dollar_prices,
            gold_price,
            gold_yesterday,
            gold_time,
            yesterday_close
        )
        
        # 3. ارسال تصویر با کپشن
        logger.info("📤 در حال ارسال به تلگرام...")
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        files = {'photo': ('market_report.png', io.BytesIO(img_bytes), 'image/png')}
        params = {
            'chat_id': chat_id,
            'caption': caption,
            'parse_mode': 'HTML'
        }
        
        response = requests.post(url, files=files, data=params, timeout=60)
        
        if response.status_code == 200:
            logger.info("✅ تصویر با موفقیت ارسال شد")
            return True
        else:
            logger.error(f"❌ خطا در ارسال: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطا در ارسال به تلگرام: {e}", exc_info=True)
        return False


def create_combined_image(Fund_df, last_trade, Gold, Gold_yesterday, dfp, yesterday_close):
    """ایجاد یک تصویر بزرگ با نمودار همه صندوق‌ها بالا و جدول 10 تای برتر پایین"""
    
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go
    
    # ایجاد subplot: ردیف بالا نمودار، ردیف پایین جدول
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.68, 0.32],
        vertical_spacing=0.02,
        specs=[[{"type": "treemap"}], [{"type": "table"}]]
    )
    
    # --- بخش 1: نمودار TreeMap با همه صندوق‌ها ---
    df_reset = Fund_df.reset_index()
    df_reset["color_value"] = df_reset["close_price_change_percent"]
    
    # متن داخل مربع‌ها (فقط برای صندوق‌های بزرگ)
    def create_text(row):
        # برای صندوق‌های بزرگ‌تر، متن بیشتر نمایش بده
        if row['value'] > 100:  # بیشتر از 100 میلیارد
            return (f"<b style='font-size:16px'>{row['symbol']}</b><br>"
                    f"<span style='font-size:13px'>{row['close_price']:,}</span><br>"
                    f"<span style='font-size:12px'>{row['close_price_change_percent']:+.2f}%</span><br>"
                    f"<span style='font-size:11px'>حباب: {row['nominal_bubble']:+.2f}%</span>")
        elif row['value'] > 50:  # 50 تا 100 میلیارد
            return (f"<b style='font-size:14px'>{row['symbol']}</b><br>"
                    f"<span style='font-size:12px'>{row['close_price']:,}</span><br>"
                    f"<span style='font-size:11px'>{row['close_price_change_percent']:+.2f}%</span>")
        else:  # کوچک‌تر از 50 میلیارد
            return f"<b style='font-size:13px'>{row['symbol']}</b><br><span style='font-size:11px'>{row['close_price_change_percent']:+.2f}%</span>"
    
    df_reset["display_text"] = df_reset.apply(create_text, axis=1)
    df_sorted = df_reset.sort_values("value", ascending=False)
    
    # رنگ‌بندی
    colorscale = [
        [0.0, "#E57373"], [0.1, "#D85C5C"], [0.2, "#C94444"],
        [0.3, "#A52A2A"], [0.4, "#6B1A1A"], [0.5, "#2C2C2C"],
        [0.6, "#1B5E20"], [0.7, "#2E7D32"], [0.8, "#43A047"],
        [0.9, "#5CB860"], [1.0, "#66BB6A"]
    ]
    
    # اضافه کردن نمودار TreeMap با همه صندوق‌ها
    fig.add_trace(
        go.Treemap(
            labels=df_sorted["symbol"],
            parents=[""] * len(df_sorted),
            values=df_sorted["value"],
            text=df_sorted["display_text"],
            textposition="middle center",
            textfont=dict(size=12, family="Arial", color="white"),
            hoverinfo="skip",
            marker=dict(
                colors=df_sorted["color_value"],
                colorscale=colorscale,
                cmid=0, cmin=-10, cmax=10,
                line=dict(width=2, color="#1A1A1A")
            )
        ),
        row=1, col=1
    )
    
    # --- بخش 2: جدول 10 صندوق برتر ---
    top_10 = df_sorted.head(10)
    
    table_header = ['نماد', 'قیمت', 'تغییر%', 'حباب%', 'ارزش(میلیارد)']
    table_cells = [
        top_10['symbol'].tolist(),
        [f"{x:,}" for x in top_10['close_price']],
        [f"{x:+.2f}%" for x in top_10['close_price_change_percent']],
        [f"{x:+.2f}%" for x in top_10['nominal_bubble']],
        [f"{x:,.0f}" for x in top_10['value']]
    ]
    
    # رنگ‌بندی سلول‌ها
    def get_color(val):
        try:
            v = float(val.replace('%', '').replace('+', '').replace(',', ''))
            if v > 0:
                return '#1B5E20'
            elif v < 0:
                return '#A52A2A'
            else:
                return '#2C2C2C'
        except:
            return '#1C2733'
    
    cell_colors = [
        ['#1C2733'] * len(top_10),
        ['#1C2733'] * len(top_10),
        [get_color(x) for x in table_cells[2]],
        [get_color(x) for x in table_cells[3]],
        ['#1C2733'] * len(top_10),
    ]
    
    fig.add_trace(
        go.Table(
            header=dict(
                values=[f'<b>{h}</b>' for h in table_header],
                fill_color='#242F3D',
                align='center',
                font=dict(color='white', size=15, family='Arial'),
                height=40
            ),
            cells=dict(
                values=table_cells,
                fill_color=cell_colors,
                align='center',
                font=dict(color='white', size=14, family='Arial'),
                height=32
            )
        ),
        row=2, col=1
    )
    
    # تنظیمات کلی
    fig.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=1200,
        width=1400,
        margin=dict(t=90, l=10, r=10, b=10),
        title=dict(
            text=f"<b>📊 نمودار بازار ({len(df_sorted)} صندوق) | 🔝 برترین صندوق‌ها</b>",
            font=dict(size=22, color='#FFD700', family='Arial'),
            x=0.5,
            xanchor='center',
            y=0.325,
            yanchor='top'
        ),
        showlegend=False
    )
    
    # تبدیل به تصویر
    img_bytes = fig.to_image(format="png", width=1400, height=1200)
    return img_bytes


def create_caption(data, dollar_prices, gold_price, gold_yesterday, gold_time, yesterday_close):
    """ایجاد کپشن خلاصه"""
    now = JalaliDateTime.now()
    current_time = now.strftime("%Y/%m/%d - %H:%M:%S")
    
    total_value = data['Fund_df']['value'].sum()
    total_pol = data['Fund_df']['pol_hagigi'].sum()
    
    # تعداد صندوق‌ها
    num_funds = len(data['Fund_df'])
    
    # محاسبه تغییرات
    dollar_change = 0
    dollar_change_emoji = "➖"
    if yesterday_close and yesterday_close > 0:
        dollar_change = ((dollar_prices['last_trade'] - yesterday_close) / yesterday_close) * 100
        dollar_change_emoji = "📈" if dollar_change > 0 else "📉" if dollar_change < 0 else "➖"
    
    gold_change = 0
    gold_change_emoji = "➖"
    if gold_yesterday and gold_yesterday > 0:
        gold_change = ((gold_price - gold_yesterday) / gold_yesterday) * 100
        gold_change_emoji = "📈" if gold_change > 0 else "📉" if gold_change < 0 else "➖"
    
    pol_emoji = "✅" if total_pol > 0 else "❌"
    
    # شمش طلا
    shams_data = data['dfp'].loc['شمش-طلا']
    
    caption = f"""📊 <b>گزارش لحظه‌ای بازار طلا و ارز</b>
🕐 {current_time}
━━━━━━━━━━━━━━━━━━━━

💵 <b>دلار:</b> {dollar_prices['last_trade']:,} تومان {dollar_change_emoji} ({dollar_change:+.2f}%)
    خرید: {dollar_prices['bid']:,} | فروش: {dollar_prices['ask']:,}

🏆 <b>اونس طلا:</b> ${gold_price:,.2f} {gold_change_emoji} ({gold_change:+.2f}%)

━━━━━━━━━━━━━━━━━━━━

📈 <b>تعداد صندوق‌ها:</b> {num_funds} صندوق
💰 <b>ارزش معاملات:</b> {total_value:,.0f} میلیارد تومان
{pol_emoji} <b>پول حقیقی:</b> {total_pol:+,.0f} میلیارد تومان

━━━━━━━━━━━━━━━━━━━━

✨ <b>شمش طلا:</b>
    قیمت: {shams_data['close_price']:,} ({shams_data['close_price_change_percent']:+.2f}%)
    حباب: {shams_data['Bubble']:+.2f}%"""
    
    return caption
