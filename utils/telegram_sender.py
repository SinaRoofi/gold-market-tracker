import io
import logging
import json
import requests
import pytz
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from persiantools.jdatetime import JalaliDateTime
from PIL import Image, ImageDraw, ImageFont
from utils.chart_creator import create_market_charts

logger = logging.getLogger(__name__)

TREEMAP_VERSION = 'matplotlib'


def send_to_telegram(bot_token, chat_id, data, dollar_prices, gold_price, gold_yesterday, gold_time, yesterday_close):
    if data is None:
        logger.error("❌ داده‌های پردازش‌شده (data) مقدار None دارد. ارسال متوقف شد.")
        return False

    try:
        if TREEMAP_VERSION == 'matplotlib':
            img1_bytes = create_combined_image_matplotlib(
                data["Fund_df"], dollar_prices["last_trade"], gold_price,
                gold_yesterday, data["dfp"], yesterday_close
            )
        else:
            img1_bytes = create_combined_image_plotly(
                data["Fund_df"], dollar_prices["last_trade"], gold_price,
                gold_yesterday, data["dfp"], yesterday_close
            )

        img2_bytes = create_market_charts()

        caption = create_simple_caption(
            data, dollar_prices, gold_price, gold_yesterday,
            yesterday_close, gold_time
        )

        if img2_bytes:
            return send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption)
        else:
            logger.warning("⚠️ نمودارها موجود نیست، فقط تصویر اول ارسال می‌شود")
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": ("market_report.png", io.BytesIO(img1_bytes), "image/png")}
            params = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            response = requests.post(url, files=files, data=params, timeout=60)
            return response.status_code == 200

    except Exception as e:
        logger.error(f"❌ خطا در فرآیند ارسال به تلگرام: {e}", exc_info=True)
        return False


def send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption):
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMediaGroup"
        files = {
            'photo1': ('market_treemap.png', io.BytesIO(img1_bytes), 'image/png'),
            'photo2': ('market_charts.png', io.BytesIO(img2_bytes), 'image/png')
        }
        media = [
            {'type': 'photo', 'media': 'attach://photo1', 'caption': caption, 'parse_mode': 'HTML'},
            {'type': 'photo', 'media': 'attach://photo2'}
        ]
        data_payload = {'chat_id': chat_id, 'media': json.dumps(media)}
        response = requests.post(url, files=files, data=data_payload, timeout=60)
        return response.status_code == 200

    except Exception as e:
        logger.error(f"❌ خطا در ارسال Media Group: {e}", exc_info=True)
        return False


def create_combined_image_matplotlib(Fund_df, last_trade, Gold, Gold_yesterday, dfp, yesterday_close):
    import matplotlib.pyplot as plt
    from matplotlib import font_manager
    import squarify
    import numpy as np

    # ⬅⬅⬅ فقط این قسمت اصلاح شد
    try:
        font_path = "assets/fonts/Vazirmatn-Regular.ttf"
        prop_large = font_manager.FontProperties(fname=font_path, size=22, weight='bold')
        prop_medium = font_manager.FontProperties(fname=font_path, size=18)
        prop_small = font_manager.FontProperties(fname=font_path, size=14)
        prop_title = font_manager.FontProperties(fname=font_path, size=28, weight='bold')
    except:
        prop_large = prop_medium = prop_small = prop_title = None

    df_sorted = Fund_df.copy().sort_values("value", ascending=False)

    fig = plt.figure(figsize=(14, 16), facecolor='#000000')
    gs = fig.add_gridspec(3, 1, height_ratios=[2, 1, 0.1], hspace=0.05)

    ax1 = fig.add_subplot(gs[0])
    ax1.set_facecolor('#000000')
    sizes = df_sorted["value"].tolist()

    def get_color_from_change(change_pct):
        normalized = np.clip((change_pct + 10) / 20, 0, 1)
        colorscale = [
            (0.0, "#E57373"), (0.1, "#D85C5C"), (0.2, "#C94444"), (0.3, "#A52A2A"), (0.4, "#6B1A1A"),
            (0.5, "#2C2C2C"),
            (0.6, "#1B5E20"), (0.7, "#2E7D32"), (0.8, "#43A047"), (0.9, "#5CB860"), (1.0, "#66BB6A")
        ]
        for i in range(len(colorscale) - 1):
            if normalized <= colorscale[i + 1][0]:
                t = (normalized - colorscale[i][0]) / (colorscale[i + 1][0] - colorscale[i][0])
                c1, c2 = colorscale[i][1], colorscale[i + 1][1]
                r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
                r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
                r = int(r1 + (r2 - r1) * t)
                g = int(g1 + (g2 - g1) * t)
                b = int(b1 + (b2 - b1) * t)
                return f'#{r:02x}{g:02x}{b:02x}'
        return colorscale[-1][1]

    colors = [get_color_from_change(x) for x in df_sorted["close_price_change_percent"]]

    squarify.plot(
        sizes=sizes, label=None, color=colors, alpha=0.9,
        edgecolor='#1A1A1A', linewidth=3, ax=ax1, text_kwargs={'fontsize': 0}
    )
    ax1.axis('off')

    rects = ax1.patches
    for rect, (idx, row) in zip(rects, df_sorted.iterrows()):
        x = rect.get_x() + rect.get_width() / 2
        y = rect.get_y() + rect.get_height() / 2
        width = rect.get_width()
        height = rect.get_height()
        area = width * height

        name = idx
        price = f"{row['close_price']:,.0f}"
        change = f"({row['close_price_change_percent']:+.2f}%)"
        bubble = f"{row['nominal_bubble']:+.2f}%"

        if area > 0.15:
            ax1.text(x, y + height * 0.12, name, ha='center', va='center',
                     fontproperties=prop_large, color='white')
            ax1.text(x, y, f"{price} {change}", ha='center', va='center',
                     fontproperties=prop_medium, color='white')
            ax1.text(x, y - height * 0.12, bubble, ha='center', va='center',
                     fontproperties=prop_small, color='white')
        elif area > 0.08:
            ax1.text(x, y + height * 0.1, name, ha='center', va='center',
                     fontproperties=prop_medium, color='white', weight='bold')
            ax1.text(x, y - height * 0.08, f"{price} {change}", ha='center', va='center',
                     fontproperties=prop_small, color='white')
        elif area > 0.03:
            ax1.text(x, y, name, ha='center', va='center',
                     fontproperties=prop_small, color='white', weight='bold')

    ax1.text(
        0.5, 1.02,
        '📊 نقشه بازار ۱۰ صندوق طلا با ارزش معاملات بالا',
        transform=ax1.transAxes,
        ha='center', va='bottom',
        fontproperties=prop_title,
        color='#FFD700'
    )

    ax2 = fig.add_subplot(gs[1])
    ax2.axis('off')

    top_10 = df_sorted.head(10)
    table_data = [
        [idx, f"{row['close_price']:,.0f}", f"{row['NAV']:,.0f}", f"{row['close_price_change_percent']:+.2f}%",
         f"{row['nominal_bubble']:+.2f}%", f"{row['ekhtelaf_sarane']:+.2f}",
         f"{row['pol_hagigi']:+,.0f}", f"{row['value']:,.0f}"]
        for idx, row in top_10.iterrows()
    ]

    table = ax2.table(
        cellText=table_data,
        colLabels=["نماد", "قیمت", "NAV", "تغییر %", "حباب %", "اختلاف سرانه", "پول حقیقی", "ارزش معاملات"],
        cellLoc='center',
        loc='center',
        bbox=[0, 0, 1, 1]
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1, 2.5)

    for i in range(len(table_data) + 1):
        for j in range(8):
            cell = table[(i, j)]
            if i == 0:
                cell.set_facecolor('#242F3D')
                cell.set_text_props(weight='bold', color='white', fontproperties=prop_small)
                cell.set_edgecolor('#1A1A1A')
            else:
                cell.set_facecolor('#1C2733')
                cell.set_text_props(color='white')
                cell.set_edgecolor('#1A1A1A')

                if j in [3, 4, 5, 6]:
                    try:
                        val = float(
                            table_data[i - 1][j]
                            .replace('%', '').replace('+', '').replace(',', '')
                        )
                        if val > 0:
                            cell.set_facecolor('#1B5E20')
                        elif val < 0:
                            cell.set_facecolor('#A52A2A')
                    except:
                        pass

    plt.tight_layout()
    output = io.BytesIO()
    plt.savefig(output, format='PNG', facecolor='#000000', dpi=120, bbox_inches='tight')
    plt.close()

    output.seek(0)
    img = Image.open(output).convert("RGBA")
    watermark_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(watermark_layer)

    # ⬅⬅⬅ این قسمت نیز فقط مسیر فونت اصلاح شد
    try:
        font = ImageFont.truetype("assets/fonts/Vazirmatn-Regular.ttf", 70)
    except:
        font = ImageFont.load_default()

    watermark_text = "Gold_Iran_Market"
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    txt_img = Image.new(
        "RGBA",
        (bbox[2] - bbox[0] + 40, bbox[3] - bbox[1] + 40),
        (255, 255, 255, 0)
    )
    txt_draw = ImageDraw.Draw(txt_img)
    txt_draw.text((20, 20), watermark_text, font=font, fill=(255, 255, 255, 90))
    rotated = txt_img.rotate(45, expand=True)
    x = (img.width - rotated.width) // 2
    y = (img.height - rotated.height) // 2
    watermark_layer.paste(rotated, (x, y), rotated)
    img = Image.alpha_composite(img, watermark_layer)

    final_output = io.BytesIO()
    img.save(final_output, format="PNG", optimize=True, quality=90)
    return final_output.getvalue()


def create_combined_image_plotly(Fund_df, last_trade, Gold, Gold_yesterday, dfp, yesterday_close):
    fig = make_subplots(
        rows=2, cols=1,
        row_heights=[0.65, 0.35],
        vertical_spacing=0.02,
        specs=[[{"type": "treemap"}], [{"type": "table"}]]
    )

    df_sorted = Fund_df.copy()
    df_sorted["color_value"] = df_sorted["close_price_change_percent"]
    df_sorted["display_text"] = df_sorted.apply(
        lambda r: f"{r.name}\n{r['close_price']:,.0f} ({r['close_price_change_percent']:+.2f}%)\n{r['nominal_bubble']:+.2f}%",
        axis=1
    )
    df_sorted = df_sorted.sort_values("value", ascending=False)

    colorscale = [
        [0.0, "#E57373"], [0.1, "#D85C5C"], [0.2, "#C94444"], [0.3, "#A52A2A"], [0.4, "#6B1A1A"],
        [0.5, "#2C2C2C"],
        [0.6, "#1B5E20"], [0.7, "#2E7D32"], [0.8, "#43A047"], [0.9, "#5CB860"], [1.0, "#66BB6A"]
    ]

    fig.add_trace(
        go.Treemap(
            labels=df_sorted.index,
            parents=[""] * len(df_sorted),
            values=df_sorted["value"],
            text=df_sorted["display_text"],
            textinfo="text",
            textposition="middle center",
            textfont=dict(size=14, family="Arial", color="white"),
            hoverinfo="skip",
            marker=dict(
                colors=df_sorted["color_value"],
                colorscale=colorscale,
                cmid=0, cmin=-10, cmax=10,
                line=dict(width=3, color="#1A1A1A")
            ),
            pathbar=dict(visible=False)
        ),
        row=1, col=1
    )

    top_10 = df_sorted.head(10)
    table_cells = [
        top_10.index.tolist(),
        [f"{x:,.0f}" for x in top_10["close_price"]],
        [f"{x:,.0f}" for x in top_10["NAV"]],
        [f"{x:+.2f}%" for x in top_10["close_price_change_percent"]],
        [f"{x:+.2f}%" for x in top_10["nominal_bubble"]],
        [f"{x:+.2f}" for x in top_10["ekhtelaf_sarane"]],
        [f"{x:+,.0f}" for x in top_10["pol_hagigi"]],
        [f"{x:,.0f}" for x in top_10["value"]]
    ]

    def col_color(v):
        try:
            x = float(v.replace("%", "").replace("+", "").replace(",", ""))
            return "#1B5E20" if x > 0 else "#A52A2A" if x < 0 else "#2C2C2C"
        except:
            return "#1C2733"

    cell_colors = [["#1C2733"] * len(top_10)] * 3 + [
        [col_color(x) for x in table_cells[i]] for i in [3, 4, 5, 6]
    ] + [["#1C2733"] * len(top_10)]

    fig.add_trace(
        go.Table(
            header=dict(
                values=[f"<b>{h}</b>" for h in ["نماد", "قیمت", "NAV", "تغییر %", "حباب %", "اختلاف سرانه", "پول حقیقی", "ارزش معاملات"]],
                fill_color="#242F3D",
                align="center",
                font=dict(color="white", size=17, family="Vazirmatn-Regular, Arial"),
                height=32
            ),
            cells=dict(
                values=table_cells,
                fill_color=cell_colors,
                align="center",
                font=dict(color="white", size=17, family="Vazirmatn-Regular, Arial"),
                height=35
            )
        ),
        row=2, col=1
    )

    fig.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=1400, width=1400,
        margin=dict(t=90, l=10, r=10, b=10),
        title=dict(
            text="<b>📊 نقشه بازار ۱۰ صندوق طلا با ارزش معاملات بالا </b>",
            font=dict(size=32, color="#FFD700", family="Vazirmatn-Regular, Arial"),
            x=0.5, y=1.0, xanchor="center", yanchor="top"
        ),
        showlegend=False
    )

    img_bytes = fig.to_image(format="png", width=1200, height=1200)
    img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

    watermark_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(watermark_layer)

    # ⬅⬅⬅ فقط مسیر فونت اینجا نیز اصلاح شد
    try:
        font = ImageFont.truetype("assets/fonts/Vazirmatn-Regular.ttf", 60)
    except:
        font = ImageFont.load_default()

    watermark_text = "Gold_Iran_Market"
    bbox = draw.textbbox((0, 0), watermark_text, font=font)
    txt_img = Image.new(
        "RGBA",
        (bbox[2] - bbox[0] + 40, bbox[3] - bbox[1] + 40),
        (255, 255, 255, 0)
    )
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
    tehran_tz = pytz.timezone("Asia/Tehran")
    now = JalaliDateTime.now(tehran_tz)
    current_time = now.strftime("%Y/%m/%d - %H:%M:%S")

    df_funds = data["Fund_df"]
    total_value = df_funds["value"].sum()
    total_pol = df_funds["pol_hagigi"].sum()

    if total_value > 0:
        avg_price_weighted = (df_funds["close_price"] * df_funds["value"]).sum() / total_value
        avg_change_percent_weighted = (df_funds["close_price_change_percent"] * df_funds["value"]).sum() / total_value
        avg_bubble_weighted = (df_funds["nominal_bubble"] * df_funds["value"]).sum() / total_value
    else:
        avg_price_weighted = avg_change_percent_weighted = avg_bubble_weighted = 0

    dollar_change = (
        (dollar_prices["last_trade"] - yesterday_close) / yesterday_close * 100
        if yesterday_close and yesterday_close != 0 else 0
    )
    gold_change = (
        (gold_price - gold_yesterday) / gold_yesterday * 100
        if gold_yesterday and gold_yesterday != 0 else 0
    )

    shams = data["dfp"].loc["شمش-طلا"]
    gold_24 = data["dfp"].loc["طلا-گرم-24-عیار"]
    gold_18 = data["dfp"].loc["طلا-گرم-18-عیار"]
    sekeh = data["dfp"].loc["سکه-امامی-طرح-جدید"]

    def calc_diffs(asset_row, dollar_current, gold_current):
        try:
            d_calc = asset_row["pricing_dollar"]
            d_diff = d_calc - dollar_current
        except:
            d_calc = d_diff = 0
        try:
            o_calc = asset_row["pricing_Gold"]
            o_diff = o_calc - gold_current
        except:
            o_calc = o_diff = 0
        return d_calc, d_diff, o_calc, o_diff

    d_shams, diff_shams, o_shams, diff_o_shams = calc_diffs(
        shams, dollar_prices["last_trade"], gold_price
    )
    d_24, diff_24, _, _ = calc_diffs(
        gold_24, dollar_prices["last_trade"], gold_price
    )
    d_18, diff_18, _, _ = calc_diffs(
        gold_18, dollar_prices["last_trade"], gold_price
    )
    d_sekeh, diff_sekeh, _, _ = calc_diffs(
        sekeh, dollar_prices["last_trade"], gold_price
    )

    gold_24_price = gold_24["close_price"] / 10
    gold_18_price = gold_18["close_price"] / 10
    sekeh_price = sekeh["close_price"] / 10
    pol_to_value_ratio = (total_pol / total_value * 100) if total_value != 0 else 0

    caption = f"""
📅 <b>{current_time}</b>

━━━━━━━━━━━━━━━━━━━━━━━━
<b>💵 دلار</b>
💰 آخرین معامله: <b>{dollar_prices['last_trade']:,} تومان</b> ({dollar_change:+.2f}%)
🟢 خرید: {dollar_prices['bid']:,} | 🔴 فروش: {dollar_prices['ask']:,}
━━━━━━━━━━━━━━━━━━━━━━━━
<b>🔆 اونس طلا </b>
💰 قیمت: <b>${gold_price:,.2f}</b> ({gold_change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━━━━━
<b>📊 آمار صندوق‌های طلا</b>
💰 ارزش معاملات: <b>{total_value:,.0f}</b> میلیارد تومان
💸 ورود پول حقیقی: <b>{total_pol:+,.0f}</b> میلیارد تومان
📊 پول حقیقی به ارزش معاملات: <b>{pol_to_value_ratio:+.0f}%</b>
📈 آخرین قیمت: <b>{avg_price_weighted:,.0f}</b> ({avg_change_percent_weighted:+.2f}%)
🎈 میانگین حباب: <b>{avg_bubble_weighted:+.2f}%</b>
━━━━━━━━━━━━━━━━━━━━━━━━
✨ <b>شمش طلا</b>
💰 قیمت: <b>{shams['close_price']:,}</b> ریال
📊 تغییر: {shams['close_price_change_percent']:+.2f}% | حباب: {shams['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_shams:,.0f} ({diff_shams:+,.0f})
🔆 اونس محاسباتی: ${o_shams:,.0f} ({diff_o_shams:+.0f})

🔸 <b>طلا ۲۴ عیار</b>
💰 قیمت: <b>{gold_24_price:,.0f}</b> تومان
📊 تغییر: {gold_24['close_price_change_percent']:+.2f}% | حباب: {gold_24['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_24:,.0f} ({diff_24:+,.0f})

🔸 <b>طلا ۱۸ عیار</b>
💰 قیمت: <b>{gold_18_price:,.0f}</b> تومان
📊 تغییر: {gold_18['close_price_change_percent']:+.2f}% | حباب: {gold_18['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_18:,.0f} ({diff_18:+,.0f})

🪙 <b>سکه امامی</b>
💰 قیمت: <b>{sekeh_price:,.0f}</b> تومان
📊 تغییر: {sekeh['close_price_change_percent']:+.2f}% | حباب: {sekeh['Bubble']:+.2f}%
💵 دلار محاسباتی: {d_sekeh:,.0f} ({diff_sekeh:+,.0f})
━━━━━━━━━━━━━━━━━━━━━━━━
🔗 <a href='https://t.me/Gold_Iran_Market'>@Gold_Iran_Market</a>
"""
    return caption