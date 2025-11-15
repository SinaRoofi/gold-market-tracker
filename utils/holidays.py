"""
ماژول مدیریت تعطیلات رسمی ایران
"""

from datetime import datetime
import jdatetime


# تعطیلات رسمی 1404 (شمسی)
IRANIAN_HOLIDAYS_1404 = [
    # فروردین
    (1404, 1, 1),
    (1404, 1, 2),
    (1404, 1, 3),
    (1404, 1, 4),  # عید نوروز
    (1404, 1, 12),
    (1404, 1, 13),  # روز طبیعت
    # اردیبهشت
    (1404, 2, 2),  # مبعث
    # خرداد
    (1404, 3, 3),  # شهادت امام علی
    (1404, 3, 14),  # رحلت امام خمینی
    (1404, 3, 15),  # قیام 15 خرداد
    # تیر
    (1404, 4, 6),  # عید فطر
    (1404, 4, 7),  # تعطیل عید فطر
    # مرداد
    # شهریور
    (1404, 6, 11),
    (1404, 6, 12),  # عید قربان
    (1404, 6, 20),  # عید غدیر
    # مهر
    (1404, 7, 8),  # تاسوعا
    (1404, 7, 9),  # عاشورا
    (1404, 7, 17),  # اربعین
    # آبان
    (1404, 8, 7),  # رحلت پیامبر
    (1404, 8, 9),  # شهادت امام رضا
    # آذر
    # دی
    # بهمن
    (1404, 11, 22),  # پیروزی انقلاب
    # اسفند
    (1404, 12, 29),  # ملی شدن نفت
]

# تعطیلات رسمی 1403
IRANIAN_HOLIDAYS_1403 = [
    (1403, 1, 1),
    (1403, 1, 2),
    (1403, 1, 3),
    (1403, 1, 4),
    (1403, 1, 12),
    (1403, 1, 13),
    (1403, 2, 14),
    (1403, 3, 3),
    (1403, 3, 14),
    (1403, 3, 15),
    (1403, 4, 17),
    (1403, 4, 18),
    (1403, 6, 23),
    (1403, 6, 24),
    (1403, 7, 2),
    (1403, 7, 19),
    (1403, 7, 20),
    (1403, 7, 28),
    (1403, 8, 17),
    (1403, 8, 19),
    (1403, 11, 22),
    (1403, 12, 29),
]


def is_iranian_holiday(date_obj):
    """
    بررسی اینکه آیا تاریخ داده شده تعطیل است یا نه

    Args:
        date_obj: datetime object

    Returns:
        bool: True اگر تعطیل باشد
    """
    # تبدیل به تاریخ شمسی
    jalali_date = jdatetime.date.fromgregorian(
        year=date_obj.year, month=date_obj.month, day=date_obj.day
    )

    date_tuple = (jalali_date.year, jalali_date.month, jalali_date.day)

    # بررسی در لیست تعطیلات
    if jalali_date.year == 1404:
        return date_tuple in IRANIAN_HOLIDAYS_1404
    elif jalali_date.year == 1403:
        return date_tuple in IRANIAN_HOLIDAYS_1403

    # برای سال‌های دیگر، فقط جمعه‌ها تعطیل
    # جمعه = 4 در weekday
    gregorian_weekday = date_obj.weekday()
    return gregorian_weekday == 4  # جمعه


def is_working_day(date_obj):
    """
    بررسی اینکه آیا روز کاری است یا نه

    Args:
        date_obj: datetime object

    Returns:
        bool: True اگر روز کاری باشد
    """
    return not is_iranian_holiday(date_obj)
