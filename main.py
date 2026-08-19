import os
import pandas as pd
import duckdb
import sys
import argparse
from transforms import path_to_df, exclude_columns, sales_transform, inv_transform, event_transform, create_current_inv, append_to_inv,create_current_from_inv,append_to_purch_ledger, current_inv_enrichment, production_query, purchase_query
from validations import test_inv, test_sales, eval_sales_current, eval_new_hist_file
from calculations import prod_table_ref, prod_ref, current_inv_ref, calc_production_df, update_current_from_prod, calc_current_from_purch, purch_table_ref, pull_purch_ledger

default_inv = "Inventory - FACT - Inventory Snapshots.csv"
default_sales = "Inventory - FACT - Historical Sales.csv"
prod_table = "Inventory - DIM - Production Table.csv"
prod_ledger_source = "Inventory - FACT - Production Ledger.csv"
purch_ledger = "Inventory - FACT - Puchases.csv"
master_table_path = "Inventory - DIM-Master Item Table.csv"
stock_lvl_path = "Inventory - DIM - Item Stock Level.csv"
stock_exceptions_path = "Inventory - DIM - Stock Level Exceptions.csv"

transformed_inv_file = "FACT - Inventory History.csv"
transformed_sales = "FACT - Event Sales.csv"
current_inventory_file = "DIM - Current Inventory.csv"
purchases_ledger_file = "FACT - Purchases Ledger.csv"
prod_ledger = "FACT - Production Ledger.csv"



def process_sales (path: str):
    sales = path_to_df(path)
    query= exclude_columns(sales)
    sales_transformed = sales_transform(sales,query)
    events = event_transform(sales,query)

    return path, sales_transformed, events

def save_salesevents (path, sales, events):
    sales_filename = transformed_sales
    sales.to_csv(sales_filename, index= False)
    print(f"{path} transformed to: {sales_filename}. {len(sales)} rows saved.")
    event_filename = "FACT - Events.csv"
    events.to_csv(event_filename, index=False)
    print(f"{path} transformed to: {event_filename}. {len(events)} rows saved.")

def process_inv (path):
    inv = path_to_df(path)
    query= exclude_columns(inv)
    inv_transformed = inv_transform(inv,query)

    return path, inv_transformed

def process_current_inv (sales_df, inv_df):
    current_inv = create_current_inv(sales_df,inv_df)
    return current_inv

def write_current_inv(current_inv: pd.DataFrame):
    current_filename = current_inventory_file
    current_inv.to_csv(current_filename, index= False)
    print(f"{current_filename} Overwitten with current data. {len(current_inv)} rows saved.")

def write_new_inventory(inv_df: pd.DataFrame) -> pd.DataFrame:
    inv_filename = transformed_inv_file
    inv_df.to_csv(inv_filename, index = False)
    print(f"{inv_filename} Created with current data. {len(inv_df)} rows saved.")

def append_current_inv(inventory: pd.DataFrame,current_inv: pd.DataFrame):
    updated_inv = append_to_inv(inventory,current_inv)
    inv_filename = transformed_inv_file
    updated_inv.to_csv(inv_filename, index= False)
    print(f"Current inventory appended to: {inv_filename}. {len(current_inv)} rows added.")

def append_purch_ledger(ledger: pd.DataFrame,purch_to_process: pd.DataFrame):
    updated_ledger = append_to_purch_ledger(purch_to_process,ledger)
    purch_filename = purchases_ledger_file
    updated_ledger.to_csv(purch_filename, index= False)
    print(f"New data appended to: { purch_filename}. {len(updated_ledger)} rows added.")

def append_to_prod_ledger(prod_ledger: str, prod_to_process: pd.DataFrame) -> pd.DataFrame:
    file_exists = os.path.exists(prod_ledger)

    prod_to_process.to_csv(
        prod_ledger,
        mode="a",
        header= not file_exists,
        index=False
    )
    print(f"{prod_ledger} appended. {len(prod_to_process)} rows added.")

def enhanced_current_inv(current_inv:pd.DataFrame):

    enriched = current_inv_enrichment(current_inv, master_table_path)
    prod  = production_query(enriched,stock_lvl_path,stock_exceptions_path)
    purch = purchase_query(prod)
    write_current_inv(purch)

def inventory_processing(args, inv_history):
    print("Processing inventory data...")

    _,inv_df = process_inv(args.inventory)
    new_hist = eval_new_hist_file(transformed_inv_file)

    if test_inv(inv_df,inv_history):
        print("New Inventory Data found. Updating DIM - Current Inventory.csv and appending FACT - Inventory History.csv")
        current_inv = create_current_from_inv (inv_df)
        enhanced_current_inv (current_inv)

        if new_hist:
            write_new_inventory(inv_df)
        else:
            append_current_inv(inv_history, current_inv)
        print("All inventory files updated.")

    else:
        print("No new inventory data found. No changes made.")

def sales_processing(args):
    print("Processing sales data...")

    path_sales, sales_df,events_df = process_sales(args.sales)

    if test_sales(sales_df,transformed_sales):
        save_salesevents (path_sales, sales_df, events_df)

        if eval_sales_current(sales_df,current_inventory_file):
            inv_df = pd.read_csv(current_inventory_file)
            current_inv_df = process_current_inv(sales_df,inv_df)

            enhanced_current_inv(current_inv_df)
            inv_hist = pd.read_csv(transformed_inv_file)
            append_current_inv(inv_hist, current_inv_df)
    else:
        print("Supplied Sales Data is up-to-date. No action required.")

def production_processing(args):
    print("Processing Production Data...")
    ledger_path = args.production
    bill_of_mats_path = args.prod_table
    current_inv_path= args.current_inv
    inv_hist_path = args.inv_history
    prod_ledger_path = args.prod_ledger_processed
    

    # Run Validation Checks of Fail out

    inv_df = pd.read_csv(inv_hist_path)
    bom_table = prod_table_ref(bill_of_mats_path)
    ledger = prod_ref(ledger_path)
    current_inv, date = current_inv_ref(current_inv_path)
    production_table = calc_production_df(bom_table,ledger,date)

    append_to_prod_ledger(prod_ledger_path,production_table)
    new_current_inv = update_current_from_prod(production_table,current_inv)

    enhanced_current_inv(new_current_inv)
    append_current_inv(inv_df,new_current_inv)
    

def purchases_processing(args):
    print("Processing Purchases Data...")
    current_inv_path = args.current_inv
    ledger_path = args.purch_ledger
    inv_hist_path = args.inv_history
    purchase_path = args.purchases

    # Run Validation Checks

    purch_ledger, ledger_date = pull_purch_ledger(ledger_path)
    purch_to_process = purch_table_ref(purchase_path,ledger_date)
    append_purch_ledger(purch_ledger,purch_to_process)


    print(f"Updating {current_inv_path} and {inv_hist_path} with new purchases data.")
    curr_inv, curr_date = current_inv_ref(current_inv_path)
    new_curr_inv = calc_current_from_purch(purch_to_process,curr_inv,curr_date)

    inventory_df = pd.read_csv(inv_hist_path)

    enhanced_current_inv(new_curr_inv)
    append_current_inv(inventory_df,new_curr_inv)

def main():
    parser = argparse.ArgumentParser(
        description = "Transform sales and inventory CSVs into pivoted BI format."
    )

    group = parser.add_mutually_exclusive_group(required = True)

    group.add_argument(
        "-s",
        "--sales",
        nargs = "?",
        const = default_sales,
        default = None,
        metavar = "FILE",
        help = "path to sales CSV file",
    )
    group.add_argument(
        "-i",
        "--inventory",
        nargs = "?",
        const = default_inv,
        default = None,
        metavar = "FILE",
        help = "Path to inventory CSV file",
    )
    group.add_argument(
        "-pro",
        "--production",
        nargs = "?",
        const = prod_ledger_source,
        default = None,
        metavar = "FILE",
        help = "Path to source production ledger CSV file",
    )
    group.add_argument(
            "-pur",
            "--purchases",
            nargs = "?",
            const = purch_ledger,
            default = None,
            metavar = "FILE",
            help = "Path to raw purchases ledger CSV file",
        )
    parser.add_argument(
        "--prod_table",
        default = prod_table,
        metavar = "FILE",
        help = "Path to production/ Bill of materials table CSV file"
    )
    parser.add_argument(
        "--current_inv",
        default = current_inventory_file,
        metavar = "FILE",
        help = "Path to current inventory table CSV file"
    )
    parser.add_argument(
        "--inv_history",
        default = transformed_inv_file,
        metavar = "FILE",
        help = "Path to inventory history table CSV file"
    )
    parser.add_argument(
        "--purch_ledger",
        default = purchases_ledger_file,
        metavar = "FILE",
        help = "Path to most recently prepared purchases ledger table CSV file"
    )
    parser.add_argument(
        "--prod_ledger_processed",
        default = prod_ledger,
        metavar = "FILE",
        help = "Path to finished production ledger CSV file"
    )
    parser.add_argument(
        "--master",
        default = master_table_path,
        metavar = "FILE",
        help = "Path to master item table CSV file"
    )
    parser.add_argument(
        "--stock_lvl",
        default = stock_lvl_path,
        metavar = "FILE",
        help = "Path to stock level table CSV file"
    )
    parser.add_argument(
        "--stk_exceptions",
        default = stock_exceptions_path,
        metavar = "FILE",
        help = "Path to stock level exceptions table CSV file"
    )
    args = parser.parse_args()

    if not os.path.exists(transformed_inv_file):
        print(f"Error: Required history file '{transformed_inv_file}' not found.")
        print("Please run an initial inventory snapshot before processing sales.")
        # force the exit error so the engineer must touch <filename> or import data, depending on project state
        sys.exit(1)

    if args.sales:
        sales_processing(args)

    if args.inventory:
        inv_history = pd.read_csv(transformed_inv_file)
        inventory_processing(args, inv_history)

    if args.production:
        production_processing(args)

    if args.purchases:
        purchases_processing(args)

if __name__ == "__main__":
    main()