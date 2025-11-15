"""
ماژول ارسال داده‌ها به تلگرام
یک تصویر بزرگ: نقشه بازار + جدول 10 صندوق اول + کپشن بهبود یافته
"""

import io
import logging
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from persiantools.jdatetime import JalaliDateTime
import pytz
import requests

logger = logging.getLogger(__name__)


def send_to_telegram(bot_token, chat_id, data, dollar_prices, gold_price, gold_yesterday, gold_time, yesterday_close):
    """ارسال یک تصویر بزرگ + کپشن بهبود یافته به تلگرام"""
    
    if data is None:
        logger.error("❌ داده‌های پردازش‌شده (data) مقدار None دارد. ارسال متوقف شد.")
        return False
        
    try:
        # 1. ایجاد تصویر بزرگ
        logger.info("🎨 در حال ساخت تصویر...")
        img_bytes = create_combined_image(
            data['Fund_df'],
            dollar_prices['last_trade'],
            gold_price,
            gold_yesterday,
            data['dfp'],
            yesterday_close
        )
        
        # 2. ایجاد کپشن بهبود یافته
        logger.info("📝 در حال ساخت کپشن...")
        caption = create_simple_caption(
            data,
            dollar_prices,
            gold_price,
            gold_yesterday,
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
    """ایجاد تصویر: نقشه بازار بالا + جدول 10 صندوق اول (با NAV) پایین"""
    
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.02,
        specs=[[{"type": "treemap"}], [{"type": "table"}]]
    )
    
    # --- بخش 1: نقشه بازار (TreeMap) - همه صندوق‌ها ---
    df_reset = Fund_df.reset_index()
    df_reset["color_value"] = df_reset["close_price_change_percent"]
    
    # متن داخل مربع‌ها
    def create_text(row):
        if row['value'] > 100:
            return (f"<b style='font-size:16px'>{row['symbol']}</b><br>"
                   f"<span style='font-size:13px'>{row['close_price']:,}</span><br>"
                   f"<span style='font-size:12px'>{row['close_price_change_percent']:+.2f}%</span><br>"
                   f"<span style='font-size:11px'>حباب: {row['nominal_bubble']:+.2f}%</span>")
        elif row['value'] > 50:
            return (f"<b style='font-size:14px'>{row['symbol']}</b><br>"
                   f"<span style='font-size:12px'>{row['close_price']:,}</span><br>"
                   f"<span style='font-size:11px'>{row['close_price_change_percent']:+.2f}%</span>")
        else:
            return f"<b style='font-size:13px'>{row['symbol']}</b><br><span style='font-size:11px'>{row['close_price_change_percent']:+.2f}%</span>"
    
    df_reset["display_text"] = df_reset.apply(create_text, axis=1)
    df_sorted = df_reset.sort_values("value", ascending=False)
    
    colorscale = [
        [0.0, "#E57373"], [0.1, "#D85C5C"], [0.2, "#C94444"],
        [0.3, "#A52A2A"], [0.4, "#6B1A1A"], [0.5, "#2C2C2C"],
        [0.6, "#1B5E20"], [0.7, "#2E7D32"], [0.8, "#43A047"],
        [0.9, "#5CB860"], [1.0, "#66BB6A"]
    ]
    
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
    
    # --- بخش 2: جدول فقط 10 صندوق اول با NAV ---
    top_10_funds = df_sorted.head(10)
    
    table_header = ['نماد', 'قیمت', 'NAV', 'تغییر%', 'حباب%', 'ارزش(میلیارد)']
    table_cells = [
        top_10_funds['symbol'].tolist(),
        [f"{x:,}" for x in top_10_funds['close_price']],
        [f"{x:,}" for x in top_10_funds['NAV']],
        [f"{x:+.2f}%" for x in top_10_funds['close_price_change_percent']],
        [f"{x:+.2f}%" for x in top_10_funds['nominal_bubble']],
        [f"{x:,.0f}" for x in top_10_funds['value']]
    ]
    
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
        ['#1C2733'] * len(top_10_funds),  # نماد
        ['#1C2733'] * len(top_10_funds),  # قیمت
        ['#1C2733'] * len(top_10_funds),  # NAV
        [get_color(x) for x in table_cells[3]],  # تغییر%
        [get_color(x) for x in table_cells[4]],  # حباب%
        ['#1C2733'] * len(top_10_funds),  # ارزش
    ]
    
    fig.add_trace(
        go.Table(
            header=dict(
                values=[f'<b>{h}</b>' for h in table_header],
                fill_color='#242F3D',
                align='center',
                font=dict(color='white', size=14, family='Arial'),
                height=35
            ),
            cells=dict(
                values=table_cells,
                fill_color=cell_colors,
                align='center',
                font=dict(color='white', size=12, family='Arial'),
                height=30
            )
        ),
        row=2, col=1
    )
    
    # تنظیمات کلی با عنوان جدید در بالای نقشه
    fig.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=1400,
        width=1400,
        margin=dict(t=80, l=10, r=10, b=10),
        title=dict(
            text=f"<b>📊 نقشه بازار و ۱۰ صندوق با ارزش معامله بالا</b>",
            font=dict(size=22, color='#FFD700', family='Arial'),
            x=0.5,
            xanchor='center',
            y=1.0,
            yanchor='top'
        ),
        showlegend=False
    )
    
    img_bytes = fig.to_image(format="png", width=1400, height=1400)
    return img_bytes


def create_simple_caption(data, dollar_prices, gold_price, gold_yesterday, yesterday_close):
    """کپشن بهبود یافته با ساعت تهران و فرمت بهتر"""
    
    # استفاده از timezone تهران
    tehran_tz = pytz.timezone('Asia/Tehran')
    now = JalaliDateTime.now(tehran_tz)
    current_time = now.strftime("%Y/%m/%d - %H:%M:%S")
    
    total_value = data['Fund_df']['value'].sum()
    total_pol = data['Fund_df']['pol_hagigi'].sum()
    
    # محاسبه تغییرات دلار
    dollar_change = 0
    if yesterday_close and yesterday_close > 0:
        dollar_change = ((dollar_prices['last_trade'] - yesterday_close) / yesterday_close) * 100
    
    # محاسبه تغییرات طلا
    gold_change = 0
    if gold_yesterday and gold_yesterday > 0:
        gold_change = ((gold_price - gold_yesterday) / gold_yesterday) * 100
    
    # دریافت اطلاعات از dfp
    try:
        gold_18 = data['dfp'].loc['طلا-گرم-18-عیار']
        gold_24 = data['dfp'].loc['طلا-گرم-24-عیار']
        shams = data['dfp'].loc['شمش-طلا']
        sekeh = data['dfp'].loc['سکه-امامی-طرح-جدید']
    except:
        logger.warning("⚠️ برخی داده‌های dfp موجود نیست")
        return f"📊 {current_time}\n💵 دلار: {dollar_prices['last_trade']:,}\n🏆 طلا: ${gold_price:,.2f}"
    
    # کپشن با فرمت بهبود یافته - اطلاعات طلا در خطوط جداگانه
    caption = f"""📅 {current_time}

💵 آخرین معامله: {dollar_prices['last_trade']:,} ({dollar_change:+.2f}%)
💵 خرید: {dollar_prices['bid']:,} | فروش: {dollar_prices['ask']:,}
🏆 اونس طلا: ${gold_price:,.2f} ({gold_change:+.2f}%)

💰 ارزش معاملات: {total_value:,.0f} میلیارد
💸 ورود پول حقیقی: {total_pol:+,.0f} میلیارد

🔸 طلا ۱۸ عیار: {gold_18['close_price']:,}
   تغییر: {gold_18['close_price_change_percent']:+.2f}% | حباب: {gold_18['Bubble']:+.2f}%

🔸 طلا ۲۴ عیار: {gold_24['close_price']:,}
   تغییر: {gold_24['close_price_change_percent']:+.2f}% | حباب: {gold_24['Bubble']:+.2f}%

🪙 سکه امامی: {sekeh['close_price']:,}
   تغییر: {sekeh['close_price_change_percent']:+.2f}% | حباب: {sekeh['Bubble']:+.2f}%

✨ شمش طلا: {shams['close_price']:,}
   تغییر: {shams['close_price_change_percent']:+.2f}% | حباب: {shams['Bubble']:+.2f}%"""
    
    return caption
