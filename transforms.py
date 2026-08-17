import pandas as pd
import duckdb
import os


def path_to_df(path :str):
    datafile = pd.read_csv(path)

    return datafile

def exclude_columns(datafile:  pd.DataFrame):
    query = """
    SELECT * EXCLUDE (Timestamp) FROM datafile
    """
    return query

def sales_transform(datafile:  pd.DataFrame,query) -> pd.DataFrame:
    exc_col_query = duckdb.query(query).df()

    unpivot = """
        WITH unpivoted as (
            FROM  exc_col_query
            UNPIVOT INCLUDE NULLS (
                qty_sold FOR Item IN (
                    COLUMNS (* EXCLUDE(
                        "Email Address",
                        "Date of Sales",
                        "Name of Event/ Venue", 
                        "Total Sales($)",
                        "(Total) Tabling and Additional Costs ($)", 
                        "Event Notes (weather, etc)"
                )))
            )
        )
        SELECT 
            "Date of Sales",
            "Name of Event/ Venue",
            Item,
            -- If value is null, empty string, or non-numeric, default to 0
            COALESCE(TRY_CAST(qty_sold AS DOUBLE), 0) AS "Qty Sold"
        FROM unpivoted
        ORDER BY "Date of Sales", Item
    """
    return duckdb.query(unpivot).df()

def inv_transform(datafile: pd.DataFrame,query) -> pd.DataFrame:
    exc_col_query = duckdb.query(query).df()

    unpivot = """
        WITH unpivoted as (
            FROM  exc_col_query
            UNPIVOT INCLUDE NULLS (
                stock_qty FOR Item IN (
                    COLUMNS (* EXCLUDE(
                    "Date of Inventory",
                    "Inventory Location",
                    "Notes"
                )))
            )
        )
    -- Step 3: Select metadata + item_key, converting missing values to 0
        SELECT 
            "Date of Inventory",
            "Inventory Location",
            Item,
            COALESCE(TRY_CAST(stock_qty AS DOUBLE), 0) AS "Qty in Stock"
        FROM unpivoted
        ORDER BY "Date of Inventory", Item
    """

    return duckdb.query(unpivot).df()

def event_transform(datafile:  pd.DataFrame,query) ->  pd.DataFrame:
    exc_col_query = duckdb.query(query).df()

    event_query = """
        SELECT "Date of Sales", "Total Sales($)","(Total) Tabling and Additional Costs ($)","Event Notes (weather, etc)" FROM datafile
    """

    return duckdb.query(event_query).df()

def create_current_inv(sales_df: pd.DataFrame,inv_df: pd.DataFrame) ->pd.DataFrame:
    latest_inv_date = pd.to_datetime(inv_df["Date of Inventory"]).max()

    sales_df_temp = sales_df.copy()
    sales_df_temp["Date_dt"] = pd.to_datetime(sales_df_temp["Date of Sales"])

    filtered_sales = sales_df_temp[sales_df_temp["Date_dt"] >= latest_inv_date]

    aggregated_sales = (filtered_sales.groupby("Item", as_index = False)["Qty Sold"].sum()) # a positive number

    inv_df_temp = inv_df.copy()
    inv_df_temp["Date_dt"] = pd.to_datetime(inv_df_temp["Date of Inventory"])
    last_inv = inv_df_temp[inv_df_temp["Date_dt"] == latest_inv_date].drop(columns=["Date_dt"])

    merged_inv = pd.merge(last_inv , aggregated_sales, on = "Item", how = "left")
    merged_inv["Qty Sold"] = merged_inv["Qty Sold"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"] - merged_inv["Qty Sold"]
    merged_inv = merged_inv.drop(columns=["Qty Sold"])

    merged_inv["Date of Inventory"] = sales_df_temp["Date_dt"].max().strftime("%m/%d/%Y")
    merged_inv["Inventory Location"] = "Calculated"

    return merged_inv[[
            "Date of Inventory",
            "Inventory Location",
            "Item",
            "Qty in Stock"
    ]]

def create_current_from_inv(inv_df: pd.DataFrame,) -> pd.DataFrame:
    latest_inv_date = pd.to_datetime(inv_df["Date of Inventory"]).max()
    inv_df_temp = inv_df.copy()
    inv_df_temp["Date_dt"] = pd.to_datetime(inv_df_temp["Date of Inventory"])
    last_inv = inv_df_temp[inv_df_temp["Date_dt"] == latest_inv_date].drop(columns=["Date_dt"])

    return last_inv [[
        "Date of Inventory",
        "Inventory Location",
        "Item",
        "Qty in Stock"
    ]]


# problematic code below: overwrites the whole file in lieu of just appending
def append_to_inv(hist_df: pd.DataFrame,current_inv: pd.DataFrame) -> pd.DataFrame:      
    appended_history = pd.concat([hist_df, current_inv], ignore_index = True)

    return appended_history.sort_values(by=["Date of Inventory", "Item"], ignore_index = True)

def append_to_purch_ledger(purch:pd.DataFrame,purch_ledger: pd.DataFrame) -> pd.DataFrame:
    appended = pd.concat([purch_ledger,purch], ignore_index = True)

    return appended.sort_values(by=["Date of Purchase","Item"], ignore_index=True)
# ------

