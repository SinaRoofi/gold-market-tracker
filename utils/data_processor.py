"""
ماژول پردازش و تحلیل داده‌های بازار
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)
pd.set_option('future.no_silent_downcasting', True)
pd.options.display.float_format = "{:,.2f}".format


def process_market_data(
    market_data, gold_price, last_trade, yesterday_close=None, gold_yesterday=None
):
    """
    پردازش داده‌های بازار و محاسبه شاخص‌ها

    Returns:
        dict: شامل dfp و Fund_df
    """
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
                "entity_id",
                "type",
                "asset_id",
                "short_name",
                "intrinsic_value",
                "price_bubble",
                "price_bubble_percent",
                "calculated_usdirr",
                "name",
            ],
            axis=1,
            inplace=True,
            errors="ignore",
        )
        assets_df.set_index("slug", inplace=True)

        warehouse_df.drop(
            [
                "entity_id",
                "type",
                "asset_id",
                "short_name",
                "intrinsic_value",
                "price_bubble",
                "price_bubble_percent",
                "calculated_usdirr",
                "trade_symbol",
                "name",
                "value",
                "volume",
            ],
            axis=1,
            inplace=True,
            errors="ignore",
        )
        warehouse_df.set_index("slug", inplace=True)

        funds_df.drop(
            [
                "entity_id",
                "type",
                "asset_id",
                "short_name",
                "trade_symbol",
                "name",
                "other_weight",
                "bullion_weight",
                "coin_weight",
                "real_bubble_percent",
                "real_bubble",
                "intrinsic_bubble_percent",
                "intrinsic_bubble",
                "nominal_bubble_percent",
                "sum_nav",
                "intrinsic_price",
            ],
            axis=1,
            inplace=True,
            errors="ignore",
        )
        funds_df.set_index("slug", inplace=True)

        funds_df.sort_values(by="value", ascending=False, inplace=True)
        funds_df["close_price"] = pd.to_numeric(
            funds_df["close_price"], errors="coerce"
        )
        funds_df["nav"] = pd.to_numeric(funds_df["nav"], errors="coerce")
        funds_df["value"] = (
            pd.to_numeric(funds_df["value"], errors="coerce") / 10_000_000_000
        )
        funds_df["nominal_bubble"] = (
            (funds_df["close_price"] - funds_df["nav"])
            / funds_df["nav"].replace(0, pd.NA)
        ) * 100
        funds_df["last_trade_time"] = funds_df["last_trade_time"].str[11:19]
        funds_df["close_price_change_percent"] = (
            pd.to_numeric(funds_df["close_price_change_percent"], errors="coerce") * 100
        )
        funds_df["close_price_change_percent"] = funds_df[
            "close_price_change_percent"
        ].round(2)
        funds_df["nominal_bubble"] = funds_df["nominal_bubble"].round(2)
        funds_df = funds_df[
            [
                "close_price",
                "nav",
                "nominal_bubble",
                "close_price_change",
                "close_price_change_percent",
                "value",
                "last_trade_time",
            ]
        ]

        Fund_df = process_traders_data(traders_data)

        dfp = pd.concat([warehouse_df, assets_df])

        dfp["trade_date"] = dfp["last_trade_time"].str[:10]
        dfp["last_trade_time"] = dfp["last_trade_time"].str[11:19]

        dfp["close_price_change_percent"] = (
            pd.to_numeric(dfp["close_price_change_percent"], errors="coerce") * 100
        )
        dfp["close_price_change_percent"] = dfp[
            "close_price_change_percent"
        ].round(2)

        dd = [
            "طلا-گرم-18-عیار",
            "طلا-گرم-24-عیار",
            "شمش-طلا",
            "سطلا",
            "سکه-امامی-طرح-جدید",
            "سکه-بهار-آزادی-طرح-قدیم",
            "طلا-مظنه-آبشده-تهران",
            "سکه0312پ01",
            "سکه0411پ05",
            "سکه0412پ03",
            "نیم-سکه",
            "ربع-سکه",
            "سکه-1-گرمی",
        ]

        dfp = dfp.reindex(dd)
        dfp.insert(1, "Value", np.nan)
        dfp["pricing_dollar"] = np.nan
        dfp["pricing_Gold"] = np.nan

        calculate_values(dfp, gold_price, last_trade)

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
    columns = [
        "id",
        "symbol",
        "volume",
        "value",
        "col5",
        "col6",
        "col7",
        "col8",
        "price1",
        "price1_change",
        "price2",
        "price2_change",
        "price3",
        "price3_change",
        *[f"col{i}" for i in range(14, 49)],
        "category",
    ]

    Fund_df = pd.DataFrame(data, columns=columns)

    Fund_df = Fund_df.rename(
        columns={
            "price2": "close_price",
            "col40": "NAV",
            "col41": "nominal_bubble",
            "price2_change": "close_price_change_percent",
            "col16": "sarane_kharid",
            "col17": "sarane_forosh",
            "col19": "pol_hagigi",
        }
    )

    Fund_df = Fund_df.set_index("symbol")
    Fund_df["value"] = Fund_df["value"] / 10_000_000_000
    Fund_df["sarane_kharid"] = Fund_df["sarane_kharid"] / 10_000_000
    Fund_df["sarane_forosh"] = Fund_df["sarane_forosh"] / 10_000_000
    Fund_df["ekhtelaf_sarane"] = Fund_df["sarane_kharid"] - Fund_df["sarane_forosh"]
    Fund_df["pol_hagigi"] = Fund_df["pol_hagigi"] / 10_000_000_000
    Fund_df.sort_values(by="value", ascending=False, inplace=True)

    Fund_df = Fund_df[
        [
            "close_price",
            "NAV",
            "nominal_bubble",
            "close_price_change_percent",
            "sarane_kharid",
            "sarane_forosh",
            "ekhtelaf_sarane",
            "pol_hagigi",
            "value",
        ]
    ]

    return Fund_df


def calculate_values(dfp, Gold, last_trade):
    dfp.loc[dfp.index[0], "Value"] = (((last_trade * Gold) / 31.1034768) * 0.75) * 10
    dfp.loc[dfp.index[1], "Value"] = ((((last_trade * Gold) / 31.1034768)) * 0.995) * 10
    dfp.loc[dfp.index[2], "Value"] = (((last_trade * Gold) / 31.1034768)) * 0.995
    dfp.loc[dfp.index[3], "Value"] = (
        ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 * 10
    )
    dfp.loc[dfp.index[4], "Value"] = (
        ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 * 10
    )
    dfp.loc[dfp.index[5], "Value"] = (
        ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 * 10
    )
    dfp.loc[dfp.index[6], "Value"] = (
        ((0.705 * (last_trade * Gold)) / 31.1034768) * 4.6083 * 10
    )
    dfp.loc[dfp.index[7], "Value"] = (
        ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 / 100
    )
    dfp.loc[dfp.index[8], "Value"] = (
        ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 / 100
    )
    dfp.loc[dfp.index[9], "Value"] = (
        ((0.9 * (last_trade * Gold)) / 31.1034768) * 8.133 / 100
    )
    dfp.loc[dfp.index[10], "Value"] = (
        ((0.9 * (last_trade * Gold)) / 31.1034768) * 4.0665 * 10
    )
    dfp.loc[dfp.index[11], "Value"] = (
        ((0.9 * (last_trade * Gold)) / 31.1034768) * 2.03225 * 10
    )
    dfp.loc[dfp.index[12], "Value"] = (((0.9 * (last_trade * Gold)) / 31.1034768)) * 10

    dfp["Bubble"] = ((dfp["close_price"] - dfp["Value"]) / dfp["Value"]) * 100

    for i in range(len(dfp)):
        if i < 5:
            factor = [0.75, 0.995, 0.995, 7.3197, 7.3197][i]
            multiplier = [10, 10, 1, 10, 10][i]
            dfp.loc[dfp.index[i], "pricing_dollar"] = (
                (dfp.loc[dfp.index[i], "close_price"] * 31.1034768)
                / (Gold * factor)
                / multiplier
            )
            dfp.loc[dfp.index[i], "pricing_Gold"] = (
                ((dfp.loc[dfp.index[i], "close_price"] / factor) * 31.1034768)
                / last_trade
                / multiplier
            )

    cols = ["Value", "close_price", "pricing_dollar", "pricing_Gold"]

    # حذف FutureWarning مربوط به downcasting
    dfp = dfp.copy()
    dfp[cols] = dfp[cols].fillna(0).infer_objects().astype(int)

    dfp = dfp[
        [
            "close_price",
            "Value",
            "Bubble",
            "close_price_change_percent",
            "pricing_dollar",
            "pricing_Gold",
            "trade_date",
            "last_trade_time",
        ]
    ]

    return dfp