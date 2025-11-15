"""
ماژول ارسال داده‌ها به تلگرام
"""

import io
import logging
import plotly.graph_objects as go
from persiantools.jdatetime import JalaliDateTime
import requests

logger = logging.getLogger(__name__)


def send_to_telegram(
    bot_token, chat_id, data, dollar_prices, gold_price, gold_time, yesterday_close
):
    """ارسال داده‌ها و نمودار به تلگرام"""
    try:
        # ایجاد نمودار
        fig = create_market_treemap(
            data["Fund_df"],
            dollar_prices["last_trade"],
            gold_price,
            data.get("gold_yesterday"),
            data["dfp"],
            yesterday_close,
        )

        # ذخیره نمودار به صورت تصویر
        img_bytes = fig.to_image(format="png", width=1400, height=800)

        # متن کپشن
        caption = create_caption(
            data, dollar_prices, gold_price, gold_time, yesterday_close
        )

        # ارسال تصویر با کپشن
        url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
        files = {"photo": ("market_chart.png", io.BytesIO(img_bytes), "image/png")}
        params = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}

        response = requests.post(url, files=files, data=params, timeout=30)

        if response.status_code == 200:
            logger.info("✅ تصویر با موفقیت ارسال شد")

            # ارسال جداول اضافی
            send_tables(bot_token, chat_id, data)

            return True
        else:
            logger.error(f"خطا در ارسال تصویر: {response.text}")
            return False

    except Exception as e:
        logger.error(f"خطا در ارسال به تلگرام: {e}", exc_info=True)
        return False


def create_caption(data, dollar_prices, gold_price, gold_time, yesterday_close):
    """ایجاد متن کپشن"""
    now = JalaliDateTime.now()
    current_time = now.strftime("%Y/%m/%d - %H:%M:%S")

    total_value = data["Fund_df"]["value"].sum()
    total_pol = data["Fund_df"]["pol_hagigi"].sum()

    caption = f"📊 <b>گزارش بازار طلا و ارز</b>\n"
    caption += f"🕐 {current_time}\n"
    caption += f"{'='*40}\n\n"

    # قیمت دلار
    if dollar_prices:
        caption += f"💵 <b>دلار:</b>\n"
        caption += f"   آخرین معامله: {dollar_prices['last_trade']:,} تومان"
        if yesterday_close:
            change_pct = (
                (dollar_prices["last_trade"] - yesterday_close) / yesterday_close
            ) * 100
            emoji = "📈" if change_pct > 0 else "📉" if change_pct < 0 else "➖"
            caption += f" {emoji} ({change_pct:+.2f}%)"
        caption += (
            f"\n   خرید: {dollar_prices['bid']:,} | فروش: {dollar_prices['ask']:,}\n\n"
        )

    # قیمت طلا
    if gold_price:
        caption += f"🏆 <b>اونس طلا:</b> ${gold_price:,.2f}\n\n"

    # خلاصه صندوق‌ها
    caption += f"💰 <b>کل ارزش معاملات:</b> {total_value:,.0f} میلیارد تومان\n"
    pol_emoji = "✅" if total_pol > 0 else "❌"
    caption += f"{pol_emoji} <b>پول حقیقی:</b> {total_pol:+,.0f} میلیارد تومان\n\n"

    # شمش طلا
    shams_data = data["dfp"].loc["شمش-طلا"]
    caption += f"✨ <b>شمش طلا:</b>\n"
    caption += f"   قیمت: {shams_data['close_price']:,} ({shams_data['close_price_change_percent']:+.2f}%)\n"
    caption += f"   حباب: {shams_data['Bubble']:+.2f}%\n"

    return caption


def send_tables(bot_token, chat_id, data):
    """ارسال جداول به صورت متنی"""
    try:
        # جدول برترین صندوق‌ها
        top_funds = data["Fund_df"].head(10)

        message = "🔝 <b>برترین صندوق‌ها:</b>\n<pre>\n"
        message += f"{'نماد':<10} {'قیمت':<12} {'تغییر%':<8} {'حباب%':<8}\n"
        message += "-" * 45 + "\n"

        for symbol, row in top_funds.iterrows():
            message += f"{symbol[:8]:<10} {row['close_price']:>10,} {row['close_price_change_percent']:>6.1f}% {row['nominal_bubble']:>6.1f}%\n"

        message += "</pre>"

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        params = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}

        requests.post(url, data=params, timeout=30)

    except Exception as e:
        logger.error(f"خطا در ارسال جداول: {e}")


def create_market_treemap(
    Fund_df, last_trade, Gold, Gold_yesterday, dfp, yesterday_close
):
    """ایجاد نمودار Treemap"""
    df_reset = Fund_df.reset_index()
    df_reset["color_value"] = df_reset["close_price_change_percent"]
    df_reset["text_color"] = "White"
    df_reset["value_display"] = (df_reset["value"]).apply(
        lambda x: f"{x:,.0f} میلیارد تومان"
    )

    # hover text
    def make_hover(row):
        change_color = (
            "#4CAF50"
            if row["close_price_change_percent"] > 0
            else "#FF5252" if row["close_price_change_percent"] < 0 else "#B0BEC5"
        )
        bubble_color = (
            "#4CAF50"
            if row["nominal_bubble"] > 0
            else "#FF5252" if row["nominal_bubble"] < 0 else "#B0BEC5"
        )
        pol_color = (
            "#4CAF50"
            if row["pol_hagigi"] > 0
            else "#FF5252" if row["pol_hagigi"] < 0 else "#B0BEC5"
        )

        return f"""
<b>{row['symbol']}</b><br>
قیمت: {row['close_price']:,}<br>
NAV: {row['NAV']:,.0f}<br>
ارزش: {row['value_display']}<br>
<span style='color:{pol_color}'>پول حقیقی: {row['pol_hagigi']:,.1f} میلیارد</span><br>
<span style='color:{change_color}'>تغییر: {row['close_price_change_percent']:+.2f}%</span><br>
<span style='color:{bubble_color}'>حباب: {row['nominal_bubble']:+.2f}%</span>
"""

    df_reset["hover_text"] = df_reset.apply(make_hover, axis=1)
    df_reset["display_text"] = df_reset.apply(
        lambda row: f"<b>{row['symbol']}</b><br>{row['close_price']:,} ({row['close_price_change_percent']:+.2f}%)<br>{row['nominal_bubble']:+.2f}% حباب",
        axis=1,
    )

    df_sorted = df_reset.sort_values("value", ascending=False)

    colorscale = [
        [0.0, "#E57373"],
        [0.1, "#D85C5C"],
        [0.2, "#C94444"],
        [0.3, "#A52A2A"],
        [0.4, "#6B1A1A"],
        [0.5, "#2C2C2C"],
        [0.6, "#1B5E20"],
        [0.7, "#2E7D32"],
        [0.8, "#43A047"],
        [0.9, "#5CB860"],
        [1.0, "#66BB6A"],
    ]

    fig = go.Figure(
        go.Treemap(
            labels=df_sorted["symbol"],
            parents=[""] * len(df_sorted),
            values=df_sorted["value"],
            text=df_sorted["display_text"],
            textinfo="text",
            textposition="middle center",
            textfont=dict(
                size=16, family="Arial", color=df_sorted["text_color"], weight="bold"
            ),
            hovertext=df_sorted["hover_text"],
            hoverinfo="text",
            marker=dict(
                colors=df_sorted["color_value"],
                colorscale=colorscale,
                cmid=0,
                cmin=-10,
                cmax=10,
                line=dict(width=2, color="#1A1A1A"),
            ),
        )
    )

    fig.update_layout(
        paper_bgcolor="#000000",
        plot_bgcolor="#000000",
        height=800,
        margin=dict(t=50, l=10, r=10, b=10),
    )

    return fig
