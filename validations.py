import os
import sys
import pandas as pd

def test_inv(inv_df: pd.DataFrame, inv_history: pd.DataFrame) -> bool:
    latest_inv_date = pd.to_datetime(inv_df["Date of Inventory"]).max()

    if inv_history["Date of Inventory"].notna().any():
        last_inv_date = pd.to_datetime(inv_history["Date of Inventory"]).max()
    else:
        last_inv_date = pd.Timestamp.min

    return latest_inv_date > last_inv_date

def test_sales(sales_df: pd.DataFrame, sales_history: str) -> bool:
    if not os.path.exists(sales_history) or os.path.getsize(sales_history) == 0:
        return True

    sales_history_df = pd.read_csv(sales_history)

    if (sales_history_df.empty or
        "Date of Sales" not in sales_history_df.columns or
        not sales_history_df["Date of Sales"].notna().any()):
        return True

    latest_new_sales = pd.to_datetime(sales_df["Date of Sales"]).max()
    last_hist_sales = pd.to_datetime(sales_history_df["Date of Sales"]).max()

    return latest_new_sales > last_hist_sales

def eval_sales_current (sales_df: pd.DataFrame, current_inv_file: str) -> bool:
    if not os.path.exists(current_inv_file) or os.path.getsize(current_inv_file) == 0:
        print("No Current Inventory File Exists. Cannot Parse Sales Data. Run Inventory first.")
        sys.exit(1)

    current_inv = pd.read_csv(current_inv_file)

    if (current_inv.empty or
        "Date of Inventory" not in current_inv.columns or
        not current_inv["Date of Inventory"].notna().any()):
        print("Current Inventory File contains errors. Cannot Parse Sales Data. Run Inventory first.")
        sys.exit(1)

    latest_new_sales = pd.to_datetime(sales_df["Date of Sales"]).max()
    current_inv_date = pd.to_datetime(current_inv["Date of Inventory"]).max()

    if latest_new_sales <= current_inv_date:
        print("Sales Data is backdated from last conducted inventory. Only 'FACT - Historical Sales.csv' will be updated.")
        return False

    else: # if we make it here, we must have functional files and more recent sales data than our last inventory
        return True

def eval_new_hist_file(hist_path: str) -> bool:
    history_df = pd.read_csv(hist_path)

    if history_df.empty or not history_df["Date of Inventory"].notna().any():
        return True
    else:
        return False


