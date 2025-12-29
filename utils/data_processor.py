# utils/data_processor.py
"""ماژول پردازش و تحلیل داده‌های بازار"""

import pandas as pd
import numpy as np
import logging
from config import ASSET_ORDER

pd.set_option('future.no_silent_downcasting', True)
logger = logging.getLogger(__name__)

pd.options.display.float_format = "{:,.2f}".format


def process_market_data(
    market_data, gold_price, last_trade, yesterday_close=None, gold_yesterday=None
):
    try:
        rahavard_data = market_data["rahavard_data"]["data"]
        traders_data = market_data["traders_data"]

        assets_df = pd.DataFrame(rahavard_data["assets"])
        warehouse_df = pd.DataFrame(rahavard_data["warehouse_receipt_systems"])
        funds_df = pd.DataFrame(rahavard_data["funds"]["values"])

        assets_df = flatten_entities(assets_df, "related_entities")
        warehouse_df = flatten_entities(warehouse_df, "related_entities")
        funds_df = flatten_entities(funds_df, "related_entities")

        # ✅ حذف امن ستون‌ها (اگر وجود نداشت، خطا نمی‌دهد)
        assets_df.drop(
            [
                "entity_id", "type", "asset_id", "short_name", 
                "intrinsic_value", "price_bubble", "price_bubble_percent",
                "calculated_usdirr", "name",
            ],
            axis=1,
            inplace=True,
            errors="ignore",
        )
        assets_df.set_index("slug", inplace=True)

        warehouse_df.drop(
            [
                "entity_id", "type", "asset_id", "short_name",
                "intrinsic_value", "price_bubble", "price_bubble_percent",
                "calculated_usdirr", "trade_symbol", "name",
                "value", "volume",
            ],
            axis=1,
            inplace=True,
            errors="ignore",
        )
        warehouse_df.set_index("slug", inplace=True)

        funds_df.drop(
            [
                "entity_id", "type", "asset_id", "short_name",
                "trade_symbol", "name", "other_weight", "bullion_weight",
                "coin_weight", "real_bubble_percent", "real_bubble",
                "intrinsic_bubble_percent", "intrinsic_bubble",
                "nominal_bubble_percent", "sum_nav", "intrinsic_price",
            ],
            axis=1,
            inplace=True,
            errors="ignore",
        )
        funds_df.set_index("slug", inplace=True)

        funds_df.sort_values(by="value", ascending=False, inplace=True)
        funds_df["close_price"] = pd.to_numeric(funds_df["close_price"], errors="coerce")
        funds_df["nav"] = pd.to_numeric(funds_df["nav"], errors="coerce")
        funds_df["value"] = pd.to_numeric(funds_df["value"], errors="coerce") / 10_000_000_000

        funds_df["nominal_bubble"] = (
            (funds_df["close_price"] - funds_df["nav"]) / funds_df["nav"].replace(0, pd.NA)
        ) * 100

        funds_df["last_trade_time"] = funds_df["last_trade_time"].str[11:19]
        funds_df["close_price_change_percent"] = (
            pd.to_numeric(funds_df["close_price_change_percent"], errors="coerce") * 100
        ).round(2)
        funds_df["nominal_bubble"] = funds_df["nominal_bubble"].round(2)

        # ✅ فقط ستون‌هایی که وجود دارند را انتخاب می‌کنیم
        required_columns = [
            "close_price", "nav", "nominal_bubble",
            "close_price_change", "close_price_change_percent",
            "value", "last_trade_time",
        ]
        available_columns = [col for col in required_columns if col in funds_df.columns]
        funds_df = funds_df[available_columns]

        Fund_df = process_traders_data(traders_data)

        dfp = pd.concat([warehouse_df, assets_df])
        dfp = dfp[~dfp.index.duplicated(keep='first')]

        dfp["trade_date"] = dfp["last_trade_time"].str[:10]
        dfp["last_trade_time"] = dfp["last_trade_time"].str[11:19]

        dfp["close_price_change_percent"] = (
            pd.to_numeric(dfp["close_price_change_percent"], errors="coerce") * 100
        ).round(2)

        dfp = dfp.reindex(ASSET_ORDER)
        dfp.insert(1, "Value", np.nan)
        dfp["pricing_dollar"] = np.nan
        dfp["pricing_Gold"] = np.nan

        dfp = calculate_values(dfp, gold_price, last_trade)

        return {
            "dfp": dfp,
            "Fund_df": Fund_df,
            "gold_price": gold_price,
            "last_trade": last_trade,
            "yesterday_close": yesterday_close,
            "gold_yesterday": gold_yesterday,
        }

    except Exception as e:
        logger.error(f"خطا در پردازش داده‌ها: {e}", exc_info=True)
        return None


def flatten_entities(df, list_col="related_entities"):
    if list_col in df.columns:
        df_flat = pd.json_normalize(
            df.to_dict(orient="records"),
            list_col,
            meta=[col for col in df.columns if col != list_col],
            errors="ignore",
        )
        return df_flat
    else:
        return df


def process_traders_data(data):
    """پردازش داده‌های تریدرز آرنا با مدیریت انعطاف‌پذیر ستون‌ها"""
    
    try:
        # ✅ ابتدا DataFrame بدون نام ستون می‌سازیم
        Fund_df = pd.DataFrame(data)
        
        actual_column_count = len(Fund_df.columns)
        logger.info(f"📊 تعداد ستون‌های واقعی traders_data: {actual_column_count}")
        
        # ✅ نام‌گذاری پویای ستون‌ها
        column_names = []
        column_names.extend(["id", "symbol", "volume", "value"])
        column_names.extend([f"col{i}" for i in range(5, 14)])  # col5 تا col13
        column_names.extend(["price1", "price1_change", "price2", "price2_change", "price3", "price3_change"])
        
        # ✅ ادامه ستون‌ها تا آخر
        current_col = 20
        while len(column_names) < actual_column_count - 1:  # -1 برای category
            column_names.append(f"col{current_col}")
            current_col += 1
        
        column_names.append("category")
        
        # ✅ اگر هنوز کم داریم، ستون‌های extra اضافه می‌کنیم
        while len(column_names) < actual_column_count:
            column_names.append(f"extra_col{len(column_names)}")
        
        # ✅ اگر زیاد داریم، کم می‌کنیم
        column_names = column_names[:actual_column_count]
        
        Fund_df.columns = column_names
        
        logger.info(f"✅ نام‌گذاری {len(column_names)} ستون انجام شد")
        
        # ✅ نام‌گذاری ستون‌های اصلی
        rename_map = {
            "price2": "close_price",
            "price3_change": "final_price_change",
            "price2_change": "close_price_change_percent",
        }
        
        # ✅ mapping ستون‌های شناخته شده
        column_mapping = {
            "col16": "sarane_kharid",
            "col17": "sarane_forosh",
            "col19": "pol_hagigi",
            "col31": "avg_monthly_value",
            "col32": "value_to_avg_ratio",
            "col35": "weekly_return",
            "col36": "monthly_return",
            "col37": "3_month_return",
            "col38": "net_asset",
            "col40": "NAV",
            "col41": "nominal_bubble",
            "col42": "NAV_change_percent",
        }
        
        # ✅ فقط ستون‌هایی که وجود دارند را rename می‌کنیم
        for old_name, new_name in column_mapping.items():
            if old_name in Fund_df.columns:
                rename_map[old_name] = new_name
        
        Fund_df = Fund_df.rename(columns=rename_map)
        Fund_df = Fund_df.set_index("symbol")

        # ✅ پردازش ستون‌های اصلی
        Fund_df["value"] = pd.to_numeric(Fund_df["value"], errors="coerce") / 10_000_000_000
        
        # ✅ تابع کمکی برای پردازش ستون‌ها
        def safe_process_column(df, col_name, divisor=1, default_value=0):
            if col_name in df.columns:
                df[col_name] = (
                    df[col_name]
                    .replace("-", pd.NA)
                    .pipe(pd.to_numeric, errors="coerce")
                    / divisor
                )
            else:
                df[col_name] = default_value
            return df
        
        Fund_df = safe_process_column(Fund_df, "sarane_kharid", divisor=10_000_000)
        Fund_df = safe_process_column(Fund_df, "sarane_forosh", divisor=10_000_000)
        Fund_df = safe_process_column(Fund_df, "pol_hagigi", divisor=10_000_000_000)
        Fund_df = safe_process_column(Fund_df, "avg_monthly_value", divisor=10_000_000_000, default_value=pd.NA)
        Fund_df = safe_process_column(Fund_df, "net_asset", divisor=10_000_000_000)
        
        # ✅ پردازش ستون‌های درصدی
        for col in ["NAV_change_percent", "weekly_return", "monthly_return", "3_month_return", "value_to_avg_ratio"]:
            if col in Fund_df.columns:
                Fund_df[col] = pd.to_numeric(Fund_df[col], errors="coerce").round(2)
            else:
                Fund_df[col] = 0

        # ✅ محاسبات مشتق شده
        Fund_df["ekhtelaf_sarane"] = Fund_df["sarane_kharid"] - Fund_df["sarane_forosh"]

        Fund_df["pol_to_value_ratio"] = (
            (Fund_df["pol_hagigi"] / Fund_df["avg_monthly_value"].replace(0, pd.NA)) * 100
        ).round(2)

        Fund_df["final_price_change"] = pd.to_numeric(
            Fund_df["final_price_change"], errors="coerce"
        ).round(2)

        Fund_df.sort_values(by="value", ascending=False, inplace=True)

        # ✅ انتخاب ستون‌های نهایی (فقط آنهایی که وجود دارند)
        final_columns = [
            "close_price", "NAV", "nominal_bubble", "NAV_change_percent",
            "close_price_change_percent", "final_price_change",
            "weekly_return", "monthly_return", "3_month_return", "net_asset",
            "sarane_kharid", "sarane_forosh", "ekhtelaf_sarane",
            "pol_hagigi", "pol_to_value_ratio",
            "value", "avg_monthly_value", "value_to_avg_ratio",
        ]
        
        available_final_columns = [col for col in final_columns if col in Fund_df.columns]
        Fund_df = Fund_df[available_final_columns]

        logger.info(f"✅ Fund_df پردازش شد - {len(Fund_df)} صندوق با {len(Fund_df.columns)} ستون")

        return Fund_df
        
    except Exception as e:
        logger.error(f"❌ خطا در پردازش داده‌های traders: {e}", exc_info=True)
        return None


def calculate_values(dfp, Gold, last_trade):
    dfp.loc[dfp.index[0], "Value"] = (((last_trade * Gold) / 31.1034768) * 0.75) * 10
    dfp.loc[dfp.index[1], "Value"] = ((((last_trade * Gold) / 31.1034768)) * 0.995) * 10
    dfp.loc[dfp.index[2], "Value"] = (((last_trade * Gold) / 31.1034768)) * 0.995
    dfp.loc[dfp.index[3], "Value"] = ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 * 10
    dfp.loc[dfp.index[4], "Value"] = ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 * 10
    dfp.loc[dfp.index[5], "Value"] = ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 * 10
    dfp.loc[dfp.index[6], "Value"] = ((0.705 * (last_trade * Gold)) / 31.1034768) * 4.6083 * 10
    dfp.loc[dfp.index[7], "Value"] = ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 / 100
    dfp.loc[dfp.index[8], "Value"] = ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 / 100
    dfp.loc[dfp.index[9], "Value"] = ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 / 100
    dfp.loc[dfp.index[10], "Value"] = ((0.9 * (last_trade * Gold)) / 31.1034768) * 4.0665 * 10
    dfp.loc[dfp.index[11], "Value"] = ((0.9 * (last_trade * Gold)) / 31.1034768) * 2.03225 * 10
    dfp.loc[dfp.index[12], "Value"] = (((0.9 * (last_trade * Gold)) / 31.1034768)) * 10

    dfp["Bubble"] = ((dfp["close_price"] - dfp["Value"]) / dfp["Value"]) * 100

    for i in range(min(5, len(dfp))):
        factor = [0.75, 0.995, 0.995, 7.3197, 7.3197][i]
        multiplier = [10, 10, 1, 10, 10][i]

        dfp.loc[dfp.index[i], "pricing_dollar"] = (
            (dfp.loc[dfp.index[i], "close_price"] * 31.1034768) / 
            (Gold * factor) / multiplier
        )
        dfp.loc[dfp.index[i], "pricing_Gold"] = (
            ((dfp.loc[dfp.index[i], "close_price"] / factor) * 31.1034768) / 
            last_trade / multiplier
        )

    cols = ["Value", "close_price", "pricing_dollar", "pricing_Gold"]
    dfp = dfp.copy()
    dfp[cols] = dfp[cols].fillna(0).astype(int)

    # ✅ فقط ستون‌هایی که وجود دارند را انتخاب می‌کنیم
    required_columns = [
        "close_price", "Value", "Bubble",
        "close_price_change_percent",
        "pricing_dollar", "pricing_Gold",
        "trade_date", "last_trade_time",
    ]
    available_columns = [col for col in required_columns if col in dfp.columns]
    dfp = dfp[available_columns]

    return dfp
