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
    if data is None:
        logger.error("❌ داده‌های پردازش‌شده (data) مقدار None دارد. ارسال متوقف شد.")
        return False
        
    try:
        img_bytes = create_combined_image(
            data['Fund_df'],
            dollar_prices['last_trade'],
            gold_price,
            gold_yesterday,
            data['dfp'],
            yesterday_close
        )

        caption = create_simple_caption(
            data,
            dollar_prices,
            gold_price,
            gold_yesterday,
            yesterday_close
        )

        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        files = {'photo': ('market_report.png', io.BytesIO(img_bytes), 'image/png')}
        params = {'chat_id': chat_id, 'caption': caption, 'parse_mode': 'HTML'}
        
        response = requests.post(url, files=files, data=params, timeout=60)
        
        if response.status_code == 200:
            return True
        else:
            logger.error(f"❌ خطا در ارسال: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"❌ خطا در ارسال به تلگرام: {e}", exc_info=True)
        return False



def create_combined_image(Fund_df, last_trade, Gold, Gold_yesterday, dfp, yesterday_close):
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.02,
        specs=[[{"type": "treemap"}], [{"type": "table"}]]
    )

    # ------------- TreeMap ----------------
    df_reset = Fund_df.reset_index()
    df_reset["color_value"] = df_reset["close_price_change_percent"]

    # فونت ۲ واحد بزرگ‌تر
    FONT_BIG = 19

    def create_text(row):
        if row['value'] > 100:
            return (f"<b style='font-size:{FONT_BIG+3}px'>{row['symbol']}</b><br>"
                    f"<span style='font-size:{FONT_BIG}px'>{row['close_price']:,}</span><br>"
                    f"<span style='font-size:{FONT_BIG-1}px'>{row['close_price_change_percent']:+.2f}%</span><br>"
                    f"<span style='font-size:{FONT_BIG-2}px'>حباب: {row['nominal_bubble']:+.2f}%</span>")
        elif row['value'] > 50:
            return (f"<b style='font-size:{FONT_BIG+1}px'>{row['symbol']}</b><br>"
                    f"<span style='font-size:{FONT_BIG-1}px'>{row['close_price']:,}</span><br>"
                    f"<span style='font-size:{FONT_BIG-2}px'>{row['close_price_change_percent']:+.2f}%</span>")
        else:
            return f"<b style='font-size:{FONT_BIG}px'>{row['symbol']}</b><br><span style='font-size:{FONT_BIG-2}px'>{row['close_price_change_percent']:+.2f}%</span>"

    df_reset["display_text"] = df_reset.apply(create_text, axis=1)
    df_sorted = df_reset.sort_values("value", ascending=False)

    colorscale = [
        [0.0, "#E57373"], [0.1, "#D85C5C"], [0.2, "#C94444"], [0.3, "#A52A2A"], 
        [0.4, "#6B1A1A"], [0.5, "#2C2C2C"], [0.6, "#1B5E20"], [0.7, "#2E7D32"], 
        [0.8, "#43A047"], [0.9, "#5CB860"], [1.0, "#66BB6A"]
    ]
    
    fig.add_trace(
        go.Treemap(
            labels=df_sorted["symbol"],
            parents=[""] * len(df_sorted),
            values=df_sorted["value"],
            text=df_sorted["display_text"],
            textinfo="text",
            textposition="middle center", 
            textfont=dict(size=FONT_BIG, family="Vazirmatn, Arial", color="white"),
            hoverinfo="skip",
            marker=dict(
                colors=df_sorted["color_value"],
                colorscale=colorscale,
                cmid=0, cmin=-10, cmax=10,
                line=dict(width=2, color="#1A1A1A")
            ),
        ),
        row=1, col=1
    )

    # ------------- جدول 10 صندوق -------------

    top_10 = df_sorted.head(10)

    table_header = ['نماد', 'قیمت', 'NAV', 'تغییر %', 'حباب %', 'ارزش معاملات(م.ت)']
    
    table_cells = [
        top_10['symbol'].tolist(),
        [f"{x:,}" for x in top_10['close_price']],
        [f"{x:,}" for x in top_10['NAV']],
        [f"{x:+.2f}%" for x in top_10['close_price_change_percent']],
        [f"{x:+.2f}%" for x in top_10['nominal_bubble']],
        [f"{x:,.0f}" for x in top_10['value']]
    ]

    def col_color(v):
        try:
            x = float(v.replace("%", "").replace("+", ""))
            return "#1B5E20" if x > 0 else "#A52A2A" if x < 0 else "#2C2C2C"
        except:
            return "#1C2733"

    cell_colors = [
        ['#1C2733'] * len(top_10),
        ['#1C2733'] * len(top_10),
        ['#1C2733'] * len(top_10),
        [col_color(x) for x in table_cells[3]],
        [col_color(x) for x in table_cells[4]],
        ['#1C2733'] * len(top_10),
    ]

    fig.add_trace(
        go.Table(
            header=dict(
                values=[f"<b>{h}</b>" for h in table_header],
                fill_color='#242F3D',
                align='center',
                font=dict(color='white', size=FONT_BIG, family="Vazirmatn, Arial"),
                height=32
            ),
            cells=dict(
                values=table_cells,
                fill_color=cell_colors,
                align='center',
                font=dict(color='white', size=FONT_BIG, family="Vazirmatn, Arial"),
                height=35
            )
        ),
        row=2, col=1
    )

    # -------- عنوان + بزرگ‌تر شدن ۴ واحد --------
    fig.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=1400,
        width=1400,
        margin=dict(t=90, l=10, r=10, b=10),
        title=dict(
            text="<b>📊 نقشه بازار و ۱۰ صندوق طلا با ارزش معاملات بالا </b>",
            font=dict(size=32, color='#FFD700', family="Vazirmatn, Arial"),  # بزرگ‌تر شده
            x=0.5,
            y=1.0,
            xanchor="center",
            yanchor="top"
        ),
        showlegend=False
    )

    return fig.to_image(format="png", width=1400, height=1400)



def create_simple_caption(data, dollar_prices, gold_price, gold_yesterday, yesterday_close):
    tehran_tz = pytz.timezone('Asia/Tehran')
    now = JalaliDateTime.now(tehran_tz)
    current_time = now.strftime("%Y/%m/%d - %H:%M:%S")

    total_value = data['Fund_df']['value'].sum()
    total_pol = data['Fund_df']['pol_hagigi'].sum()

    dollar_change = ((dollar_prices['last_trade'] - yesterday_close) / yesterday_close * 100) if yesterday_close else 0
    gold_change = ((gold_price - gold_yesterday) / gold_yesterday * 100) if gold_yesterday else 0

    # ترتیب جدید: شمش → ۲۴ → ۱۸ → سکه
    shams = data['dfp'].loc['شمش-طلا']
    gold_24 = data['dfp'].loc['طلا-گرم-24-عیار']
    gold_18 = data['dfp'].loc['طلا-گرم-18-عیار']
    sekeh = data['dfp'].loc['سکه-امامی-طرح-جدید']

    caption = f"""📅 {current_time}

💵 آخرین معامله دلار: {dollar_prices['last_trade']:,} ({dollar_change:+.2f}%)
🟢 خرید: {dollar_prices['bid']:,} |🔴 فروش: {dollar_prices['ask']:,}

🔆 اونس جهانی: ${gold_price:,.2f} ({gold_change:+.2f}%)

💰 ارزش معاملات: {total_value:,.0f}  میلیارد تومان
💸 ورود پول حقیقی: {total_pol:+,.0f} میلیارد تومان

✨ شمش طلا: {shams['close_price']:,}
  تغییر: {shams['close_price_change_percent']:+.2f}% | حباب: {shams['Bubble']:+.2f}%

🔸 طلا ۲۴ عیار: {gold_24['close_price']:,}
  تغییر: {gold_24['close_price_change_percent']:+.2f}% | حباب: {gold_24['Bubble']:+.2f}%

🔸 طلا ۱۸ عیار: {gold_18['close_price']:,}
  تغییر: {gold_18['close_price_change_percent']:+.2f}% | حباب: {gold_18['Bubble']:+.2f}%

🪙 سکه امامی: {sekeh['close_price']:,}
  تغییر: {sekeh['close_price_change_percent']:+.2f}% | حباب: {sekeh['Bubble']:+.2f}%"""

    return caption



