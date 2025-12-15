import pytz
import jdatetime
from datetime import datetime
from config import TIMEZONE

def get_jalali_now_str(fmt='%Y-%m-%d - %H:%M'):
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    return jdatetime.datetime.fromgregorian(datetime=now).strftime(fmt)
