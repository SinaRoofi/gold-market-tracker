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

        funds_df = funds_df[
            [
                "close_price", "nav", "nominal_bubble",
                "close_price_change", "close_price_change_percent",
                "value", "last_trade_time",
            ]
        ]

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
    """پردازش داده‌های traders با mapping مستقیم index‌ها - بولت‌پروف"""
    
    if not data or len(data) == 0:
        logger.warning("⚠️ داده traders_data خالی است")
        return pd.DataFrame()
    
    actual_columns = len(data[0])
    logger.info(f"📊 تعداد ستون‌های دریافتی: {actual_columns}")
    
    # ✅ Mapping مستقیم: index -> نام ستون مورد نیاز
    column_mapping = {
        0: "id",
        1: "symbol",
        2: "volume",
        3: "value",
        4: "first_price",
        5: "first_price_change_percent",
        6: "high_price",
        7: "high_price_change_percent",
        8: "low_price",
        9: "low_price_change_percent",
        10: "close_price",
        11: "close_price_change_percent",
        12: "final_price",
        13: "final_price_change_percent",
        14: "close_final_diff",
        15: "volitility",
        16: "sarane_kharid",
        17: "sarane_forosh",
        18: "buy_power",
        19: "pol_hagigi",
        20: "buy_order_value",
        21: "sell_order_value",
        22: "buy_sell_order_sum",
        23: "5day_avg_pol_hagigi",
        24: "20day_avg_pol_hagigi",
        25: "60day_avg_pol_hagigi",
        26: "5day_pol_hagigi",
        27: "20day_pol_hagigi",
        28: "60day_pol_hagigi",
        29: "5day_buy_power",
        30: "20day_buy_power",
        31: "avg_monthly_value",
        32: "value_to_avg_ratio",
        35: "weekly_return",
        36: "monthly_return",
        37: "3_month_return",
        38: "net_asset",
        40: "NAV",
        41: "nominal_bubble",
        42: "NAV_change_percent",
        49: "category",
        50: "isin",
    }
    
    # ✅ ساخت DataFrame با استخراج ستون‌های مورد نیاز
    extracted_data = []
    for row in data:
        extracted_row = {}
        for idx, col_name in column_mapping.items():
            if idx < len(row):
                extracted_row[col_name] = row[idx]
            else:
                extracted_row[col_name] = None
                logger.warning(f"⚠️ ستون {idx} ({col_name}) در دیتا وجود ندارد")
        extracted_data.append(extracted_row)
    
    Fund_df = pd.DataFrame(extracted_data)
    Fund_df = Fund_df.set_index("symbol")
    
    # ✅ پردازش عددی ستون‌ها
    Fund_df["value"] = pd.to_numeric(Fund_df["value"], errors="coerce") / 10_000_000_000
    Fund_df["sarane_kharid"] = pd.to_numeric(Fund_df["sarane_kharid"], errors="coerce") / 10_000_000
    Fund_df["sarane_forosh"] = pd.to_numeric(Fund_df["sarane_forosh"], errors="coerce") / 10_000_000
    Fund_df["pol_hagigi"] = pd.to_numeric(Fund_df["pol_hagigi"], errors="coerce") / 10_000_000_000

    Fund_df["avg_monthly_value"] = (
        Fund_df["avg_monthly_value"]
        .replace("-", pd.NA)
        .pipe(pd.to_numeric, errors="coerce")
        / 10_000_000_000
    )

    Fund_df["NAV_change_percent"] = pd.to_numeric(
        Fund_df["NAV_change_percent"], errors="coerce"
    ).round(2)

    for col in ["weekly_return", "monthly_return", "3_month_return"]:
        if col in Fund_df.columns:
            Fund_df[col] = pd.to_numeric(Fund_df[col], errors="coerce").round(2)

    Fund_df["net_asset"] = (
        Fund_df["net_asset"]
        .replace("-", pd.NA)
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
        / 10_000_000_000
    )

    Fund_df["ekhtelaf_sarane"] = Fund_df["sarane_kharid"] - Fund_df["sarane_forosh"]

    Fund_df["pol_to_value_ratio"] = (
        (Fund_df["pol_hagigi"] / Fund_df["avg_monthly_value"].replace(0, pd.NA)) * 100
    ).round(2)

    # ✅ نام ستون در main.py به عنوان "final_price_change" استفاده میشه
    Fund_df["final_price_change"] = pd.to_numeric(
        Fund_df["final_price_change_percent"], errors="coerce"
    ).round(2)

    Fund_df["value_to_avg_ratio"] = pd.to_numeric(
        Fund_df["value_to_avg_ratio"], errors="coerce"
    ).round(2)

    Fund_df.sort_values(by="value", ascending=False, inplace=True)

    # ✅ انتخاب ستون‌های نهایی (فقط آنهایی که وجود دارند)
    final_columns = [
        "close_price", "NAV", "nominal_bubble", "NAV_change_percent",
        "close_price_change_percent", "final_price_change",
        "weekly_return", "monthly_return", "3_month_return", "net_asset",
        "sarane_kharid", "sarane_forosh", "ekhtelaf_sarane",
        "pol_hagigi", "pol_to_value_ratio", "value",
        "avg_monthly_value", "value_to_avg_ratio",
    ]
    
    existing_columns = [col for col in final_columns if col in Fund_df.columns]
    Fund_df = Fund_df[existing_columns]

    logger.info(f"✅ Fund_df پردازش شد - {len(Fund_df)} صندوق با {len(Fund_df.columns)} ستون")

    return Fund_df


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

    dfp = dfp[
        [
            "close_price", "Value", "Bubble",
            "close_price_change_percent",
            "pricing_dollar", "pricing_Gold",
            "trade_date", "last_trade_time",
        ]
    ]

    return dfp
