import io
import logging
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from persiantools.jdatetime import JalaliDateTime
import pytz
import requests
from PIL import Image, ImageDraw, ImageFont

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
            yesterday_close,
            gold_time
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

    df_reset = Fund_df.reset_index()
    df_reset["color_value"] = df_reset["close_price_change_percent"]

    FONT_BIG = 19

    def create_text(row):
        if row['value'] > 100:
            return (f"<b style='font-size:{FONT_BIG+3}px'>{row.name}</b><br>"
                    f"<span style='font-size:{FONT_BIG}px'>{row['close_price']:,}</span><br>"
                    f"<span style='font-size:{FONT_BIG-1}px'>{row['close_price_change_percent']:+.2f}%</span><br>"
                    f"<span style='font-size:{FONT_BIG-2}px'>حباب: {row['nominal_bubble']:+.2f}%</span>")
        elif row['value'] > 50:
            return (f"<b style='font-size:{FONT_BIG+1}px'>{row.name}</b><br>"
                    f"<span style='font-size:{FONT_BIG-1}px'>{row['close_price']:,}</span><br>"
                    f"<span style='font-size:{FONT_BIG-2}px'>{row['close_price_change_percent']:+.2f}%</span>")
        else:
            return f"<b style='font-size:{FONT_BIG}px'>{row.name}</b><br><span style='font-size:{FONT_BIG-2}px'>{row['close_price_change_percent']:+.2f}%</span>"

    df_reset["display_text"] = df_reset.apply(create_text, axis=1)
    df_sorted = df_reset.sort_values("value", ascending=False)

    colorscale = [
        [0.0, "#E57373"], [0.1, "#D85C5C"], [0.2, "#C94444"], [0.3, "#A52A2A"], 
        [0.4, "#6B1A1A"], [0.5, "#2C2C2C"], [0.6, "#1B5E20"], [0.7, "#2E7D32"], 
        [0.8, "#43A047"], [0.9, "#5CB860"], [1.0, "#66BB6A"]
    ]
    
    fig.add_trace(
        go.Treemap(
            labels=df_sorted.index,
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

    top_10 = df_sorted.head(10)
    table_header = ['نماد', 'قیمت', 'NAV', 'تغییر %', 'حباب %', 'اختلاف سرانه', 'پول حقیقی(م.ت)', 'ارزش معاملات(م.ت)']
    table_cells = [
        top_10.index.tolist(),
        [f"{x:,}" for x in top_10['close_price']],
        [f"{x:,}" for x in top_10['NAV']],
        [f"{x:+.2f}%" for x in top_10['close_price_change_percent']],
        [f"{x:+.2f}%" for x in top_10['nominal_bubble']],
        [f"{x:+.3f}" for x in top_10['ekhtelaf_sarane']],
        [f"{x:+,.0f}" for x in top_10['pol_hagigi']],
        [f"{x:,.0f}" for x in top_10['value']]
    ]

    def col_color(v):
        try:
            x = float(v.replace("%", "").replace("+", "").replace(",", ""))
            return "#1B5E20" if x > 0 else "#A52A2A" if x < 0 else "#2C2C2C"
        except:
            return "#1C2733"

    cell_colors = [
        ['#1C2733'] * len(top_10),
        ['#1C2733'] * len(top_10),
        ['#1C2733'] * len(top_10),
        [col_color(x) for x in table_cells[3]],
        [col_color(x) for x in table_cells[4]],
        [col_color(x) for x in table_cells[5]],
        [col_color(x) for x in table_cells[6]],
        ['#1C2733'] * len(top_10),
    ]

    fig.add_trace(
        go.Table(
            header=dict(
                values=[f"<b>{h}</b>" for h in table_header],
                fill_color='#242F3D',
                align='center',
                font=dict(color='white', size=FONT_BIG-3, family="Vazirmatn, Arial"),
                height=32
            ),
            cells=dict(
                values=table_cells,
                fill_color=cell_colors,
                align='center',
                font=dict(color='white', size=FONT_BIG-3, family="Vazirmatn, Arial"),
                height=35
            )
        ),
        row=2, col=1
    )

    fig.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=1400,
        width=1400,
        margin=dict(t=90, l=10, r=10, b=10),
        title=dict(
            text="<b>📊 نقشه بازار و ۱۰ صندوق طلا با ارزش معاملات بالا </b>",
            font=dict(size=32, color='#FFD700', family="Vazirmatn, Arial"),
            x=0.5,
            y=1.0,
            xanchor="center",
            yanchor="top"
        ),
        showlegend=False
    )

    img_bytes = fig.to_image(format="png", width=1200, height=1200)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    
    watermark_layer = Image.new('RGBA', img.size, (255, 255, 255, 0))
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
    txt_img = Image.new('RGBA', (textwidth + 40, textheight + 40), (255, 255, 255, 0))
    txt_draw = ImageDraw.Draw(txt_img)
    txt_draw.text((20, 20), watermark_text, font=font, fill=(255, 255, 255, 100))
    rotated = txt_img.rotate(45, expand=True)
    x = (img.width - rotated.width) // 2
    y = (img.height - rotated.height) // 2
    watermark_layer.paste(rotated, (x, y), rotated)
    img = Image.alpha_composite(img, watermark_layer)

    output = io.BytesIO()
    img.save(output, format="PNG", optimize=True, quality=85)
    return output.getvalue()


def create_simple_caption(data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time):
    tehran_tz = pytz.timezone('Asia/Tehran')
    now = JalaliDateTime.now(tehran_tz)
    current_time = now.strftime("%Y/%m/%d - %H:%M:%S")
    
    try:
        dollar_time = gold_time.strftime("%H:%M") if gold_time else "نامشخص"
    except:
        dollar_time = "نامشخص"

    total_value = data['Fund_df']['value'].sum()
    total_pol = data['Fund_df']['pol_hagigi'].sum()
    
    avg_price = data['Fund_df']['close_price'].mean()
    avg_change_percent = data['Fund_df']['close_price_change_percent'].mean()

    dollar_change = ((dollar_prices['last_trade'] - yesterday_close) / yesterday_close * 100) if yesterday_close else 0
    gold_change = ((gold_price - gold_yesterday) / gold_yesterday * 100) if gold_yesterday else 0

    shams = data['dfp'].loc['شمش-طلا']
    gold_24 = data['dfp'].loc['طلا-گرم-24-عیار']
    gold_18 = data['dfp'].loc['طلا-گرم-18-عیار']
    sekeh = data['dfp'].loc['سکه-امامی-طرح-جدید']
    
    try:
        dollar_calc = shams['pricing_dollar']
        dollar_diff = dollar_calc - dollar_prices['last_trade']
    except:
        dollar_calc = 0
        dollar_diff = 0
    
    try:
        ounce_calc = shams['pricing_Gold']
        ounce_diff = ounce_calc - gold_price
    except:
        ounce_calc = 0
        ounce_diff = 0

    gold_24_price = gold_24['close_price'] / 10
    gold_18_price = gold_18['close_price'] / 10
    sekeh_price = sekeh['close_price'] / 10

    caption = f"""
📅 <b>{current_time}</b>

💵 <b>بازار ارز</b>
💰 آخرین معامله: <b>{dollar_prices['last_trade']:,} تومان ({dollar_change:+.2f}%)</b> 
🟢 خرید: {dollar_prices['bid']:,} | 🔴 فروش: {dollar_prices['ask']:,}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔆 <b>اونس طلا</b>
<b>قیمت:</b> ${gold_price:,.2f} ({gold_change:+.2f}%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 <b>آمار صندوق‌های طلا</b>

💰 ارزش معاملات: {total_value:,.0f} میلیارد تومان
💸 ورود پول حقیقی: {total_pol:+,.0f} میلیارد تومان
📈 آخرین قیمت: {avg_price:,.0f} تومان
📊 درصد آخرین قیمت: {avg_change_percent:+.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━
📈 <b style='font-size:18px'>✨ شمش طلا</b>
<b>قیمت:</b> {shams['close_price']:,}
تغییر: {shams['close_price_change_percent']:+.2f}% | حباب: {shams['Bubble']:+.2f}%
💵 دلار محاسباتی: {dollar_calc:,.0f} ({dollar_diff:+,.0f})
🔆 اونس محاسباتی: ${ounce_calc:,.0f} ({ounce_diff:+.0f})

🔸 <b style='font-size:18px'>طلا ۲۴ عیار</b>
<b>قیمت:</b> {gold_24_price:,.0f}
تغییر: {gold_24['close_price_change_percent'] :+.2f}% | حباب: {gold_24['Bubble'] :+.2f}%

🔸 <b style='font-size:18px'>طلا ۱۸ عیار</b>
<b>قیمت:</b> {gold_18_price:,.0f}
تغییر: {gold_18['close_price_change_percent'] :+.2f}% | حباب: {gold_18['Bubble'] :+.2f}%

🪙 <b style='font-size:18px'>سکه امامی طرح جدید</b>
<b>قیمت:</b> {sekeh_price:,.0f}
تغییر: {sekeh['close_price_change_percent'] :+.2f}% | حباب: {sekeh['Bubble'] :+.2f}%

━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 <a href='https://t.me/Gold_Iran_Market'>@Gold_Iran_Market</a>"""

    return caption


