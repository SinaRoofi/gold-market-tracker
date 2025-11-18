import io
import logging
import pytz
import requests
from PIL import Image, ImageDraw, ImageFont
from persiantools.jdatetime import JalaliDateTime

# Import نسبی از chart_creator
from .chart_creator import create_market_charts, create_combined_image

logger = logging.getLogger(__name__)

def send_to_telegram(
    bot_token,
    chat_id,
    data,
    dollar_prices,
    gold_price,
    gold_yesterday,
    gold_time,
    yesterday_close,
):
    if data is None:
        logger.error("❌ داده‌های پردازش‌شده (data) مقدار None دارد. ارسال متوقف شد.")
        return False

    try:
        # ایجاد تصویر اول (Treemap + جدول)
        img1_bytes = create_combined_image(
            data["Fund_df"],
            dollar_prices["last_trade"],
            gold_price,
            gold_yesterday,
            data["dfp"],
            yesterday_close,
        )

        # ایجاد تصویر دوم (نمودارها)
        img2_bytes = create_market_charts()

        # ایجاد کپشن
        caption = create_simple_caption(
            data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
        )

        # ارسال به صورت Media Group (آلبوم)
        if img2_bytes:
            return send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption)
        else:
            # اگر نمودار نبود، فقط تصویر اول رو بفرست
            logger.warning("⚠️ نمودارها موجود نیست، فقط تصویر اول ارسال می‌شود")
            url = f"https://api.telegram.org/bot{bot_token}/sendPhoto"
            files = {"photo": ("market_report.png", io.BytesIO(img1_bytes), "image/png")}
            params = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            response = requests.post(url, files=files, data=params, timeout=60)
            if response.status_code == 200:
                return True
            else:
                logger.error(f"❌ خطا در ارسال: {response.text}")
                return False

    except Exception as e:
        logger.error(f"❌ خطا در ارسال به تلگرام: {e}", exc_info=True)
        return False


def send_media_group(bot_token, chat_id, img1_bytes, img2_bytes, caption):
    """ارسال 2 عکس + کپشن به صورت Media Group"""
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
        data = {'chat_id': chat_id, 'media': str(media).replace("'", '"')}
        response = requests.post(url, files=files, data=data, timeout=60)
        if response.status_code == 200:
            logger.info("✅ Media Group ارسال شد")
            return True
        else:
            logger.error(f"❌ خطا در ارسال Media Group: {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ خطا در ارسال Media Group: {e}", exc_info=True)
        return False


def create_simple_caption(
    data, dollar_prices, gold_price, gold_yesterday, yesterday_close, gold_time
):
    tehran_tz = pytz.timezone("Asia/Tehran")
    now = JalaliDateTime.now(tehran_tz)
    current_time = now.strftime("%Y/%m/%d - %H:%M:%S")
    try:
        dollar_time = gold_time.strftime("%H:%M") if gold_time else "نامشخص"
    except:
        dollar_time = "نامشخص"

    total_value = data["Fund_df"]["value"].sum()
    total_pol = data["Fund_df"]["pol_hagigi"].sum()
    avg_price = data["Fund_df"]["close_price"].mean()
    avg_change_percent = data["Fund_df"]["close_price_change_percent"].mean()

    dollar_change = ((dollar_prices["last_trade"] - yesterday_close) / yesterday_close * 100) if yesterday_close else 0
    gold_change = ((gold_price - gold_yesterday) / gold_yesterday * 100) if gold_yesterday else 0

    shams = data["dfp"].loc["شمش-طلا"]
    gold_24 = data["dfp"].loc["طلا-گرم-24-عیار"]
    gold_18 = data["dfp"].loc["طلا-گرم-18-عیار"]
    sekeh = data["dfp"].loc["سکه-امامی-طرح-جدید"]

    try:
        dollar_calc = shams["pricing_dollar"]
        dollar_diff = dollar_calc - dollar_prices["last_trade"]
    except:
        dollar_calc = 0
        dollar_diff = 0

    try:
        ounce_calc = shams["pricing_Gold"]
        ounce_diff = ounce_calc - gold_price
    except:
        ounce_calc = 0
        ounce_diff = 0

    gold_24_price = gold_24["close_price"] / 10
    gold_18_price = gold_18["close_price"] / 10
    sekeh_price = sekeh["close_price"] / 10

    min_bubble_row = data["Fund_df"].loc[data["Fund_df"]["nominal_bubble"].idxmin()]
    max_bubble_row = data["Fund_df"].loc[data["Fund_df"]["nominal_bubble"].idxmax()]
    top_value5 = data["Fund_df"].sort_values("value", ascending=False).head(5)
    min_bubble_top5 = top_value5.loc[top_value5["nominal_bubble"].idxmin()]
    data["Fund_df"]["pol_ratio"] = data["Fund_df"]["pol_hagigi"] / data["Fund_df"]["value"] * 100
    top_pol = data["Fund_df"].sort_values("pol_ratio", ascending=False).head(3)

    caption = f"""
📅 <b>{current_time}</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>💵 بازار ارز</b>
💰 آخرین معامله: <b>{dollar_prices['last_trade']:,} تومان ({dollar_change:+.2f}%)</b> 
🟢 خرید: {dollar_prices['bid']:,} | 🔴 فروش: {dollar_prices['ask']:,}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>🔆 اونس طلا</b>
<b>قیمت:</b> ${gold_price:,.2f} ({gold_change:+.2f}%)
━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>📊 آمار معاملات صندوق‌های طلا</b>
💰 ارزش معاملات: {total_value:,.0f} میلیارد تومان
💸 ورود پول حقیقی: {total_pol:+,.0f} میلیارد تومان
📈 آخرین قیمت: {avg_price:,.0f} ({avg_change_percent:+.2f}%)

💎 حباب صندوق‌ها:
کمترین حباب: {min_bubble_row.name} ({min_bubble_row['nominal_bubble']:+.2f}%)
بیشترین حباب: {max_bubble_row.name} ({max_bubble_row['nominal_bubble']:+.2f}%)

💹 <b>ورود پول به ارزش معامله (۳ رتبه اول)</b>:
"""
    for _, row in top_pol.iterrows():
        caption += f"{row.name} ({row['pol_ratio']:+.0f}% | اختلاف سرانه: {row['ekhtelaf_sarane']:+,.0f})\n"

    caption += "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    caption += f"""
📈 <b>✨ شمش طلا</b>
<b>قیمت:</b> {shams['close_price']:,}
تغییر: {shams['close_price_change_percent']:+.2f}% | حباب: {shams['Bubble']:+.2f}%
💵 دلار محاسباتی: {dollar_calc:,.0f} ({dollar_diff:+,.0f})
🔆 اونس محاسباتی: ${ounce_calc:,.0f} ({ounce_diff:+.0f})

🔸 <b>طلا ۲۴ عیار</b>
<b>قیمت:</b> {gold_24_price:,.0f}
تغییر: {gold_24['close_price_change_percent']:+.2f}% | حباب: {gold_24['Bubble']:+.2f}%

🔸 <b>طلا ۱۸ عیار</b>
<b>قیمت:</b> {gold_18_price:,.0f}
تغییر: {gold_18['close_price_change_percent']:+.2f}% | حباب: {gold_18['Bubble']:+.2f}%

🪙 <b>سکه امامی طرح جدید</b>
<b>قیمت:</b> {sekeh_price:,.0f}
تغییر: {sekeh['close_price_change_percent']:+.2f}% | حباب: {sekeh['Bubble']:+.2f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔗 <a href='https://t.me/Gold_Iran_Market'>@Gold_Iran_Market</a>
"""
    return caption
