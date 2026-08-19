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


# --- Enhancing Current Inventory for additional logistics 
def current_inv_enrichment(current_df: pd.DataFrame, master_table_path: str) ->pd.DataFrame:
    master_df = pd.read_csv(master_table_path)

    enriched_query = """
    WITH enriched_inv as (
    SELECT
        c."Date of Inventory",
        c."Inventory Location",
        c.Item,
        m.Style,
        m.Subcategory,
        m.Category,
        m."Final Product",
        m."Input Product",
        c."Qty in Stock"
    FROM current_df as c
    INNER JOIN master_df as m
        ON c.Item = M.Key
    ) 
    , combined_print as(
        SELECT
            MAX("Date of Inventory") AS "Date of Inventory",
            'Calculated' AS "Inventory Location",
            Style || '-SumP' AS Item,
            Style,
            'SumPrint' AS Subcategory,
            'Print' AS Category,
            TRUE AS "Final Product",
            FALSE AS "Input Product",
            SUM("Qty in Stock") AS "Qty in Stock"
        FROM enriched_inv
        WHERE Category = 'Print'
        AND "Final Product" = TRUE
        GROUP BY Style
    )

    SELECT * FROM enriched_inv
    UNION ALL
    SELECT * from combined_print
    ORDER BY Item
    """

    return duckdb.query(enriched_query).df()

def production_query(current_inv_enriched: pd.DataFrame,stock_lvl_path: str, stock_exceptions_path: str) ->pd.DataFrame:

    enriched_inv = current_inv_enriched.copy()
    stock_lvl_df = pd.read_csv(stock_lvl_path)
    stock_exc_df = pd.read_csv(stock_exceptions_path)
    
    production_query = """
    SELECT 
        e."Date of Inventory",
        e."Inventory Location",
        e.Item,
        e.Style,
        e.Subcategory,
        e.Category,
        e."Final Product",
        e."Input Product",
        e."Qty in Stock",
    COALESCE(x."Stock Level", s."Reorder Stock Level", 0) AS "Stock Level",
    GREATEST(0, COALESCE(x."Stock Level",s."Reorder Stock Level",0)- e."Qty in Stock") AS "Inventory Shortfall",
    CASE
        WHEN e."Final Product" = TRUE
        AND e.Category != 'Sticker'
        THEN e."Qty in Stock" <= COALESCE(x."Stock Level",s."Reorder Stock Level",0)
        ELSE NULL
    END AS "Add to Production Queue"
    FROM enriched_inv as e
    LEFT JOIN stock_lvl_df as s
        ON e.Category = s.Category
    LEFT JOIN stock_exc_df as x
        ON e.Style = x.Style
        AND e.Category = x.Category
    WHERE e.Subcategory IN ('SumPrint', 'Card, Greeting', 'Sticker')
            OR e."Input Product" = TRUE
    ORDER BY e.Item

    """

    return duckdb.query(production_query).df()

def purchase_query(production_query: pd.DataFrame) ->pd.DataFrame:

    production_queue = production_query.copy()

    purchase_order = """
    WITH check_prints AS(
    SELECT
        Style,
        Category,
        "Inventory Shortfall",
        "Add to Production Queue"
    FROM  production_queue
    WHERE Subcategory = 'SumPrint'
    AND "Add to Production Queue" = TRUE
    ), check_cards AS(
        SELECT
            Style,
            Category,
            "Inventory Shortfall",
            "Add to Production Queue"
        FROM  production_queue
        WHERE Subcategory = 'Cards, Greeting'
        AND "Add to Production Queue" = TRUE
        )
    
    SELECT
        p."Date of Inventory",
        p."Inventory Location",
        p.Item,
        p.Style,
        p.Subcategory,
        p.Category,
        p."Final Product",
        p."Input Product",
        p."Qty in Stock",
        p."Stock Level",
    CASE
        WHEN p.Subcategory = 'CStock'
            AND c."Add to Production Queue" = TRUE
        THEN GREATEST(0, c."Inventory Shortfall" - (p."Qty in Stock" - p."Stock Level"))
        WHEN p.Subcategory = 'Print'
            AND d."Add to Production Queue" = TRUE
        THEN GREATEST(0, d."Inventory Shortfall" - (p."Qty in Stock" - p."Stock Level"))  
        ELSE p."Inventory Shortfall"
    END AS "Inventory Shortfall",
        p."Add to Production Queue",
    CASE
        WHEN p.SubCategory = 'Print'
        THEN p."Qty in Stock" <= p."Stock Level"
            OR
            d."Add to Production Queue" = TRUE AND (p."Qty in Stock" - p."Stock Level") <= d."Inventory Shortfall"
        WHEN p.Subcategory = 'CStock'
        THEN p."Qty in Stock" <= p."Stock Level"
            OR
            d."Add to Production Queue" = TRUE AND (p."Qty in Stock" - p."Stock Level") <= d."Inventory Shortfall"
        WHEN p.Category = 'Supplies'
        THEN "Qty in Stock" <= "Stock Level"
        WHEN p.Category = 'Sticker'
        THEN "Qty in Stock" <= "Stock Level"
        ELSE NULL
    END AS "Add to Purchase Order"
    FROM production_queue as p
    LEFT JOIN check_prints as d
        ON p.Style = d.Style
        AND p.Category = d.Category
    LEFT JOIN check_cards as c
        ON p.Style = c.Style
        AND p.Category = c.Category
    ORDER BY p."Item"
    """

    query_table = duckdb.query(purchase_order).df()

    return query_table
# ------