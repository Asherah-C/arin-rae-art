import pandas as pd
import duckdb

def initialize_current_inv_query (master_df : pd.DataFrame, stock_lvl_path : str, stock_exceptions_path : str ) -> pd.DataFrame:
    master_table = master_df.copy()


    #Date 12/31/2024 is set arbitrarily based on manual data pull. Future iterations may desire a change, depending on initialization functions behavior. See initializations.initializw_inventory_history() for more info.
    query = """
    WITH master_inv AS (
    SELECT
        '2024-12-31T23:59:59-07:00' AS Timestamp,
        '2024-12-31' AS "Date of Inventory",
        'Initiziation' AS "Inventory Location",
        Key AS Item,
        Style,
        Subcategory,
        Category,
        "Final Product",
        "Input Product",
        0 AS "Qty in Stock",
        0 AS "Stock Level",
        0 AS "Inventory Shortfall"
    FROM master_table
    ),
    combined_print AS (
    SELECT
        NULL AS Timestamp,
        '2024-12-31' AS "Date of Inventory",
        'Initiziation' AS "Inventory Location",
        Style || '-SumP' AS Item,
        Style,
        'SumPrint' AS Subcategory,
        'Print' AS Category,
        TRUE AS "Final Product",
        FALSE AS "Input Product",
        0 AS "Qty in Stock",
        0 AS "Stock Level",
        0 AS "Inventory Shortfall"
    FROM master_inv
    WHERE Category = 'Print'
    AND "Final Product" = TRUE
    GROUP BY Style
    )
    SELECT * FROM master_inv
    UNION ALL
    SELECT * from combined_print
    ORDER BY Item

"""

    initial_inv = duckdb.query(query).df()

    initial_inv_prod = production_query(initial_inv,stock_lvl_path,stock_exceptions_path)

    full_ini_current_inv = purchase_query(initial_inv_prod)

    return(full_ini_current_inv)


def create_current_inv(sales_df: pd.DataFrame,inv_df: pd.DataFrame) ->pd.DataFrame:
    latest_inv_date = pd.to_datetime(inv_df["Date of Inventory"]).max()

    sales_df_temp = sales_df.copy()
    sales_df_temp["Date_dt"] = pd.to_datetime(sales_df_temp["Date of Sales"])

    filtered_sales = sales_df_temp[sales_df_temp["Date_dt"] > latest_inv_date]

    aggregated_sales = (filtered_sales.groupby("Item", as_index = False)["Qty Sold"].sum()) # a positive number

    inv_df_temp = inv_df.copy()
    inv_df_temp["Date_dt"] = pd.to_datetime(inv_df_temp["Date of Inventory"])
    last_inv = inv_df_temp[inv_df_temp["Date_dt"] == latest_inv_date].drop(columns=["Date_dt"])

    merged_inv = pd.merge(last_inv , aggregated_sales, on = "Item", how = "left")
    merged_inv["Qty Sold"] = merged_inv["Qty Sold"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"] - merged_inv["Qty Sold"]
    merged_inv = merged_inv.drop(columns=["Qty Sold"])

    merged_inv["Date of Inventory"] = sales_df_temp["Date_dt"].max().strftime("%Y-%m-%d")
    merged_inv["Inventory Location"] = "Calculated"

    return merged_inv[[
            "Timestamp",
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
        "Timestamp",
        "Date of Inventory",
        "Inventory Location",
        "Item",
        "Qty in Stock"
    ]]

# cleaner data append from current to inventory history
def append_to_inv(hist_path: pd.DataFrame,current_inv: pd.DataFrame):

    query ="""
    SELECT
        Timestamp,
        "Date of Inventory",
        "Inventory Location",
        Item,
        "Qty in Stock"
    FROM current_inv AS c
    WHERE Subcategory != 'SumPrint'
    ORDER BY Item
"""
    trimmed_current = duckdb.query(query).df()
    trimmed_current['Date of Inventory'] = pd.to_datetime(trimmed_current['Date of Inventory']).dt.strftime('%Y-%m-%d')
    rows = len(trimmed_current)
    trimmed_current.to_csv(hist_path, mode='a', header=False, index=False)
    print(f"Current inventory appended to: {hist_path}. {rows} rows added.")

def backdating_inventory (dates_df: pd.DataFrame, raw_df: pd.DataFrame, hist_path:str):
    query = """
    SELECT
        r.*
    FROM dates_df AS d
    LEFT JOIN raw_df AS r
        ON d.date = r."Date of Inventory"
    ORDER BY r."Date of Inventory", r.Item
    """

    inv_count_to_append = duckdb.query(query).df()
    rows = len(inv_count_to_append)
    inv_count_to_append.to_csv(hist_path, mode='a', header=False, index=False)
    print(f"Inventory history updated with new data: {hist_path} updated with {rows} new rows.")

def backdating_sales_events (table_type,dates_df: pd.DataFrame, raw_df: pd.DataFrame, hist_path:str):
    order_clause = str
    if table_type == "Sales":
        order_clause = "ORDER BY r.\"Date of Sales\" ASC, r.Item ASC"
    if table_type == "Events":
        order_clause = "ORDER BY r.\"Date of Sales\" ASC, r.\"Event Name\" ASC"

    #changed d.date to d."Date of Sales"; if something fails here we need to add clauses; (changed due to initialize_ledgers call)
    query = f"""
    SELECT
        r.*
    FROM dates_df AS d
    LEFT JOIN raw_df AS r

        ON d."Date of Sales" = r."Date of Sales"
    {order_clause}
    """

    sales_to_append = duckdb.query(query).df()
    rows = len(sales_to_append)
    sales_to_append.to_csv(hist_path, mode='a', header=False, index=False)
    print(f"{table_type} history updated with new data: {hist_path} updated with {rows} new rows.")
    
def backdating_purchases(query_type: str, purch_to_process: pd.DataFrame, hist_path:str):
    rows = len(purch_to_process)
    purch_to_process.to_csv(hist_path, mode='a', header=False, index=False)
    print(f"{query_type} history updated with new data: {hist_path} updated with {rows} new rows.")


# --- Enhancing Current Inventory for additional logistics 
def current_inv_enrichment(current_df: pd.DataFrame, master_table_path: str) ->pd.DataFrame:
    master_df = pd.read_csv(master_table_path)

    enriched_query = """
    WITH enriched_inv as (
    SELECT
        c.Timestamp,
        c."Date of Inventory",
        c."Inventory Location",
        c.Item,
        m.Style,
        m.Subcategory,
        m.Category,
        m."Final Product",
        m."Input Product",
        c."Qty in Stock"
    FROM master_df as m
    INNER JOIN current_df as c
        ON c.Item = m.Key
    ) 
    , combined_print as(
        SELECT
            MAX(Timestamp) AS Timestamp,
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
    WITH prod_update AS(
    SELECT
        e.Timestamp, 
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
        THEN e."Qty in Stock" < COALESCE(x."Stock Level",s."Reorder Stock Level",0)
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
    )
    SELECT
        c.Timestamp, 
        c."Date of Inventory",
        c."Inventory Location",
        c.Item,
        c.Style,
        c.Subcategory,
        c.Category,
        c."Final Product",
        c."Input Product",
        c."Qty in Stock",
        p."Stock Level",
        p."Inventory Shortfall",
        p."Add to Production Queue"
    FROM enriched_inv AS c
    LEFT JOIN prod_update AS  p
        ON c.Item = p.Item
    ORDER BY c.Item
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
        p.Timestamp,
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
        THEN d."Add to Production Queue" = TRUE AND (p."Qty in Stock" - p."Stock Level") < d."Inventory Shortfall"
        WHEN p.Subcategory = 'CStock'
        THEN c."Add to Production Queue" = TRUE AND (p."Qty in Stock" - p."Stock Level") < c."Inventory Shortfall"
        WHEN p.Category = 'Supplies'
        THEN "Qty in Stock" < "Stock Level"
        WHEN p.Category = 'Sticker'
        THEN "Qty in Stock" < "Stock Level"
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

# New transforms to include Timestamps
def transform_sales(datafile:  pd.DataFrame) -> pd.DataFrame:
    unpivot = """
        WITH unpivoted as (
            FROM  datafile
            UNPIVOT INCLUDE NULLS (
                qty_sold FOR Item IN (
                    COLUMNS (* EXCLUDE(
                        Timestamp,
                        "Email Address",
                        "Date of Sales",
                        "Name of Event/ Venue",
                        "Location (City)", 
                        "Total Sales($)",
                        "(Total) Tabling and Additional Costs ($)", 
                        "Event Notes (weather, etc)"
                )))
            )
        )
        SELECT 
            Timestamp,
            "Date of Sales",
            "Name of Event/ Venue" AS "Event Name",
            Item,
            -- If value is null, empty string, or non-numeric, default to 0
            COALESCE(TRY_CAST(qty_sold AS DOUBLE), 0) AS "Qty Sold"
        FROM unpivoted
        ORDER BY "Date of Sales", Item
    """

    sales = duckdb.query(unpivot).df()

    return sales

def transform_inv(datafile: pd.DataFrame) -> pd.DataFrame:
    unpivot = """
        WITH unpivoted as (
            FROM  datafile
            UNPIVOT INCLUDE NULLS (
                stock_qty FOR Item IN (
                    COLUMNS (* EXCLUDE(
                    Timestamp,
                    "Date of Inventory",
                    "Inventory Location",
                    "Notes"
                )))
            )
        )
    -- Step 3: Select metadata + item_key, converting missing values to 0
        SELECT
            Timestamp, 
            "Date of Inventory",
            "Inventory Location",
            Item,
            COALESCE(TRY_CAST(stock_qty AS DOUBLE), 0) AS "Qty in Stock"
        FROM unpivoted
        ORDER BY "Date of Inventory", Item
    """

    return duckdb.query(unpivot).df()

def transform_purchase(dataframe) -> pd.DataFrame:
    query = """
    SELECT
        Timestamp, 
        "Date of Purchase",
        "Invoice / Purchase Orders",
        "Item",
        "Quantity Bought",
        "Price (each)",
        "Subtotal"
    FROM dataframe
    ORDER BY "Date of Purchase" ASC
    """
    ex_col = duckdb.query(query).df()
    return ex_col

def transform_production(dataframe) -> pd.DataFrame:
    query = """
    SELECT
        Timestamp, 
        "Date of Production",
        "Item Made" AS "Item",
        "Style",
        "Subcategory",
        "Qty Made" as "Qty Delta"
    FROM dataframe
    ORDER BY "Date of Production" ASC
    """
    ex_col = duckdb.query(query).df()
    return ex_col

def transform_events(datafile:  pd.DataFrame) ->  pd.DataFrame:
    event_query = """
        SELECT
            Timestamp,
            "Date of Sales",
            "Name of Event/ Venue" AS "Event Name",
            "Location (City)",
            "Total Sales($)",
            "(Total) Tabling and Additional Costs ($)",
            "Event Notes (weather, etc)"
        FROM datafile
        ORDER by "Date of Sales" ASC
    """

    return duckdb.query(event_query).df()