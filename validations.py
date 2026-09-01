import pandas as pd
import duckdb

# def test_inv(inv_df: pd.DataFrame, inv_history: pd.DataFrame) -> bool:
#    latest_inv_date = pd.to_datetime(inv_df["Date of Inventory"]).max()
#
#    if inv_history["Date of Inventory"].notna().any():
#        last_inv_date = pd.to_datetime(inv_history["Date of Inventory"]).max()
#    else:
#        last_inv_date = pd.Timestamp.min
#
#    return latest_inv_date > last_inv_date

#ef test_sales(sales_df: pd.DataFrame, sales_history: str) -> bool:
    # if not os.path.exists(sales_history) or os.path.getsize(sales_history) == 0:
    #    return True

#   sales_history_df = pd.read_csv(sales_history)

#   if (sales_history_df.empty or
#       "Date of Sales" not in sales_history_df.columns or
#       not sales_history_df["Date of Sales"].notna().any()):
#       return True

#   latest_new_sales = pd.to_datetime(sales_df["Date of Sales"]).max()
#   last_hist_sales = pd.to_datetime(sales_history_df["Date of Sales"]).max()

#   return latest_new_sales > last_hist_sales

# def eval_sales_current (sales_df: pd.DataFrame, current_inv_file: str) -> bool:
#    if not os.path.exists(current_inv_file) or os.path.getsize(current_inv_file) == 0:
#        print("No Current Inventory File Exists. Cannot Parse Sales Data. Run Inventory first.")
#        sys.exit(1)

#    current_inv = pd.read_csv(current_inv_file)

#    if (current_inv.empty or
#        "Date of Inventory" not in current_inv.columns or
#        not current_inv["Date of Inventory"].notna().any()):
#        print("Current Inventory File contains errors. Cannot Parse Sales Data. Run Inventory first.")
#        sys.exit(1)

#    latest_new_sales = pd.to_datetime(sales_df["Date of Sales"]).max()
#    current_inv_date = pd.to_datetime(current_inv["Date of Inventory"]).max()

#    if latest_new_sales <= current_inv_date:
#        print("Sales Data is backdated from last conducted inventory. Only 'FACT - Historical Sales.csv' will be updated.")
#        return False

#    else: # if we make it here, we must have functional files and more recent sales data than our last inventory
#        return True

# def eval_new_hist_file(hist_path: str) -> bool:
#    history_df = pd.read_csv(hist_path)
#
#    if history_df.empty or not history_df["Date of Inventory"].notna().any():
#        return True
#    else:
#        return False


# compares every date in raw inventory data to see if it is in the history. If not, it adds it to a table of dates, ascending
# def inv_compare_dates (inv_df: pd.DataFrame, inv_history: pd.DataFrame) ->[bool, pd.DataFrame]:
#    query = """
#    WITH raw_dates AS(
#    SELECT
#        DISTINCT "Date of Inventory" as inv_date
#    FROM inv_df
#    ),
#    hist_dates AS(
#    SELECT
#        DISTINCT "Date of Inventory" as inv_date
#    FROM inv_history
#    WHERE "Inventory Location" = 'Home Office'
#    )
#    SELECT
#        inv_date
#    FROM raw_dates
#    WHERE
#        inv_date NOT IN (SELECT inv_date FROM hist_dates)
#    ORDER BY strptime(inv_date, '%m/%d/%Y') ASC
#"""

#    return(len(duckdb.query(query).df())==0,duckdb.query(query).df())

# compares every date in raw sales data to see if it is in the ledger. If not, it adds it to a table of dates, ascending
def compare_dates (query_type: str, new_df: pd.DataFrame, history_df: pd.DataFrame) -> tuple[bool, pd.DataFrame]:
    col_name = str
    if query_type == "inv":
        col_name = "Date of Inventory"
        where_clause = "WHERE \"Inventory Location\" = 'Home Office'"
    if query_type == "sales":
        col_name = "Date of Sales"
        where_clause = ""
    if query_type =="purchases":
        col_name = "Date of Purchase"
        where_clause = ""
    if query_type =="production":
        col_name = "Date of Production"
        where_clause = ""

    query = f"""
    WITH raw_dates AS(
    SELECT
        DISTINCT "{col_name}" as date
    FROM new_df
    ),
    hist_dates AS(
    SELECT
        DISTINCT "{col_name}" as date
    FROM history_df
    {where_clause}
    )
    SELECT
        date
    FROM raw_dates
    WHERE
        date NOT IN (SELECT date FROM hist_dates)
    ORDER BY strptime(date, '%Y%m-%d) ASC
"""
    dates = duckdb.query(query).df() 

    return(len(dates)==0,dates)

# checks to see if the latest raw date to be added into a ledger is newer than the current inventory.
def test_dates_vs_current(dates_df: pd.DataFrame, current_df: pd.DataFrame) -> bool:
    latest_inv_date = pd.to_datetime(dates_df["date"]).max()
    last_inv_date = pd.to_datetime(current_df[f"Date of Inventory"]).max()

    return latest_inv_date > last_inv_date