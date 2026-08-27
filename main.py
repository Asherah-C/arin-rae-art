import os
import pathlib as Path
import pandas as pd
import duckdb
import sys
import argparse
from transforms import initialize_current_inv_query , path_to_df, exclude_columns, sales_transform, inv_transform, event_transform, create_current_inv, append_to_inv,create_current_from_inv, current_inv_enrichment, production_query, purchase_query, backdating_inventory, backdating_sales_events, backdating_purchases, purch_transform, prod_transform, unprocessed_table
from validations import  test_dates_vs_current, compare_dates
from calculations import prod_table_ref, prod_ref, current_inv_ref, calc_production_df, update_current_from_prod, calc_current_from_purch, pull_purch_ledger
from initialization import initialize_outputs, pull_initial_data, initialize_inventory_history, initialize_ledgers

# Raw Data Files Paths -- to delete after calls are redirected
default_inv = "Inventory - FACT - Inventory Snapshots.csv"
default_sales = "Inventory - FACT - Historical Sales.csv"
prod_table = "Inventory - DIM - Production Table.csv"
prod_ledger_source = "Inventory - FACT - Production Ledger.csv"
purchases = "Inventory - FACT - Puchases.csv"
master_table_path = "Inventory - DIM-Master Item Table.csv"
stock_lvl_path = "Inventory - DIM - Item Stock Level.csv"
stock_exceptions_path = "Inventory - DIM - Stock Level Exceptions.csv"

# Processed data File Paths -- to delete after calls are redirected
transformed_inv_file = "FACT - Inventory History.csv"
events_sales_ledger = "FACT - Event Sales.csv"
current_inventory_file = "DIM - Current Inventory.csv"
purchases_ledger = "FACT - Purchases Ledger.csv"
prod_ledger = "FACT - Production Ledger.csv"
events_path = "FACT - Events.csv"
master_table_output = "DIM-Master Item Table.csv"

# Unified Path Variables
master_table_path = "Inventory - DIM-Master Item Table.csv"
stock_levels_path = "Inventory - DIM - Item Stock Level.csv"
stock_exceptions_path = "Inventory - DIM - Stock Level Exceptions.csv"
inv_path = "Inventory - FACT - Inventory Snapshots.csv"
purchase_path = "Inventory - FACT - Puchases.csv"
production_ledger_path = "Inventory - FACT - Production Ledger.csv"
bill_of_mats = "Inventory - DIM - Production Table.csv"
raw_sales_path = "Inventory - FACT - Historical Sales.csv"

expanded_prod_ledger_path = "FACT - Production Ledger.csv"  
inv_history_path = "FACT - Inventory History.csv"
purch_ledger_path = "FACT - Purchases Ledger.csv"
events_sales_path = "FACT - Event Sales.csv"
events_path = "FACT - Events.csv"
current_inventory_path = "DIM - Current Inventory.csv"
master_table_output = "DIM-Master Item Table.csv"



### ----------- ARGS Quick Reference -----------
#    expanded_prod_ledger_path = args.expanded_production 
#    inv_history_path = args.inv_history
#    purch_ledger_path = args.purchases_output
#    events_sales_path = args.sales_output
#    events_path = args.events
#    current_inventory_path = args.current_inv
#    master_table_output = args.master_table_output
#
#    master_table_path = args.master_item
#    stock_levels_path = args.stock_levels
#    stock_exceptions_path = args.stock_exceptions
#    inv_path = args.inventory_path
#    purchase_path = args.purchases_source
#    production_ledger_path = args.production_path
#    bill_of_mats = args.bill_of_mats
#    raw_sales_path = args.sales_source
# ------------------------------------------------


# Database Initialization
def initialize_db(args):
    initialize_outputs(args)
    initialize_inventory_history(args)
    initialize_ledgers(args)

def save_salesevents (path, sales, events):
 
    sales.to_csv(events_sales_ledger, index= False)
    print(f"{path} transformed to: {events_sales_ledger}. {len(sales)} rows saved.")
  
    events.to_csv(events_path, index=False)
    print(f"{path} transformed to: {events_path}. {len(events)} rows saved.")

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
    print(f"{current_filename} overwitten with current data. {len(current_inv)} rows saved.")

def write_new_inventory(inv_df: pd.DataFrame) -> pd.DataFrame:
    inv_filename = transformed_inv_file
    inv_df.to_csv(inv_filename, index = False)
    print(f"{inv_filename} Created with current data. {len(inv_df)} rows saved.")

# def append_current_inv(inventory: pd.DataFrame,current_inv: pd.DataFrame):
#    updated_inv, rows = append_to_inv(inventory,current_inv)
#    inv_filename = transformed_inv_file
#    updated_inv.to_csv(inv_filename, index= False)
#    print(f"Current inventory appended to: {inv_filename}. {rows} rows added.")

# def append_purch_ledger(ledger: pd.DataFrame,purch_to_process: pd.DataFrame):
#    updated_ledger = append_to_purch_ledger(purch_to_process,ledger)
#    purch_filename = purchases_ledger
#    updated_ledger.to_csv(purch_filename, index= False)
#    print(f"New data appended to: { purch_filename}. {len(updated_ledger)} rows added.")

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

    return purch

# Proccessing functions
def inventory_processing(args, inv_history):
    print("Processing inventory data...")
    hist_path = args.inv_history
    _,inv_df = process_inv(args.inventory)

    query_type= "inv"
    all_dates, dates_df =  compare_dates(query_type, inv_df,inv_history)
 
    if not all_dates:
        print("New Inventory Data found...")
        print("Comparing to Current Inventory...")

        current_path = args.current_inv
        current_df = pd.read_csv(current_path)
        if test_dates_vs_current(dates_df, current_df):
            "New inventory data is most current. Updating current inventory..."
            curr_inv = create_current_from_inv (inv_df)
            current_inv = enhanced_current_inv (curr_inv)
            append_to_inv(hist_path,current_inv)
        else:
            print("Associated inventory data predates current inventory.")

            # TO ADD : FUNCTIONALITY TO REBUILD MOST ACCURATE CURRENT INVENTORY FROM MOST RECENT (BUT OLD) RAW INVENTORY FILE

        print("Appending missing data to inventory history.")
        backdating_inventory(dates_df,inv_df,hist_path)

        print("All inventory files updated.")

    else:
        print("No new inventory data found. No changes made.")

def sales_processing(args):
    print("Processing sales data...")
    sales_path = args.sales
    hist_path = args.inv_history

    sales_df = path_to_df(sales_path)
    query= exclude_columns(sales_df)
    sales_transformed = sales_transform(sales_df,query)
    events = event_transform(sales_df,query)

    sales_history = pd.read_csv(events_sales_ledger)
    events_history = pd.read_csv(events_path) 

    query_type = "sales"
    sales_all_dates, dates_df = compare_dates(query_type, sales_transformed, sales_history)
    

    if not sales_all_dates:
        print("New sales data found....")
        print("Comparing to current inventory....")

        current_path = args.current_inv
        current_df = pd.read_csv(current_path)
        if test_dates_vs_current(dates_df, current_df):
            "New sales data is most current. Updating current inventory..."
            curr_inv = create_current_inv (sales_transformed,current_df)
            current_inv = enhanced_current_inv (curr_inv)
            append_to_inv(hist_path,current_inv)
        else:
            print("Associated sales data predates current inventory.")

            # TO ADD : FUNCTIONALITY TO REBUILD MOST ACCURATE CURRENT INVENTORY FROM MOST RECENT DATA FOLLOWING LATEST INVENTORY

        print("Appending Missing Sales Data....")
        backdating_sales_events(query_type, dates_df, sales_transformed, events_sales_ledger)
    else:
        print("Sales data is current and up-to-date.")

    events_transformed = event_transform(sales_df,query)
    events_all_dates, events_dates_df = compare_dates(query_type, events_transformed, events_history)

    if not events_all_dates:
        print("Updating events table....")
        type="event"
        backdating_sales_events(type,events_dates_df,events_transformed, events_path)
    else:
        "Events table is up-to-date."

def production_processing(args):
    print("Processing Production Data...")
    prod_path = args.production
    bill_of_mats_path = args.prod_table
    current_inv_path= args.current_inv
    inv_hist_path = args.inv_history
    prod_hist_path = args.prod_ledger_processed
    
    query_type = "production"
    production_raw = pd.read_csv(prod_path)
    production_df = prod_transform(production_raw)
    prod_hist_df = pd.read_csv(prod_hist_path)

    all_dates, dates_df = compare_dates(query_type,production_df,prod_hist_df)

    if not all_dates:
        print("New Production Data found....")
        print("Building itemized production inventory changes table....")
        prod_to_process = unprocessed_table(query_type,dates_df,production_df)
        bom_table = prod_table_ref(bill_of_mats_path)

        production_table = calc_production_df(bom_table,prod_to_process)
        print(f"New production data unpivoted. {len(production_table)} rows need updating.")

        print("Comparing to Current Inventory")
        current_df = pd.read_csv(current_inv_path)
        if test_dates_vs_current(dates_df,current_df):
            print("New Data is most current. Updating Current Inventory...")
            new_curr_inv = update_current_from_prod(production_table,current_df)
            current_inv = enhanced_current_inv(new_curr_inv)
            append_to_inv(inv_hist_path,current_inv)
        else:
            print("Associated purchases data predates current inventory.")

            # TO ADD: FUNCTIONALITY TO REBUILD CURRENT INVENTORY WHEN DATES FALL BETTWEN CURRENT INVENTORY AND PREVIOUS HAND COUNT

        print("Appending missing sales data....")
        backdating_purchases(query_type,production_table,prod_hist_path)
    else:
        print("Purchases Data up-to-date.")                

def purchases_processing(args):
    print("Processing Purchases Data...")
    current_inv_path = args.current_inv
    purch_ledger_path = args.purch_ledger
    inv_hist_path = args.inv_history
    purchases_path = args.purchases

    query_type = "purchases"
    purchases_raw = pd.read_csv(purchases_path)
    purchases_df = purch_transform(purchases_raw)
    purch_hist_df = pd.read_csv(purch_ledger_path)

    all_dates, dates_df = compare_dates(query_type, purchases_df, purch_hist_df)

    if not all_dates:
        print("New Purchases Data found....")
        print("Comparing to Current Inventory")
        current_df = pd.read_csv(current_inv_path)
        purch_to_process = unprocessed_table(query_type,dates_df,purchases_df)
        if test_dates_vs_current(dates_df,current_df):
            print("New Data is most current. Updating Current Inventory...")
            new_curr_inv = calc_current_from_purch(purch_to_process,current_df)
            current_inv = enhanced_current_inv(new_curr_inv)
            append_to_inv(inv_hist_path,current_inv)
        else:
            print("Associated purchases data predates current inventory.")

            # TO ADD: FUNCTIONALITY TO REBUILD CURRENT INVENTORY WHEN DATES FALL BETTWEN CURRENT INVENTORY AND PREVIOUS HAND COUNT

        print("Appending missing sales data....")
        backdating_purchases(query_type,purch_to_process,purch_ledger_path)
    else:
        print("Purchases Data up-to-date.")

def main():
    parser = argparse.ArgumentParser(
        description = "Transform sales and inventory CSVs into pivoted BI format."
    )

    group = parser.add_mutually_exclusive_group(required = True)

    group.add_argument(
        "-sales",
        "--sales",
        nargs = "?",
        const = default_sales,
        default = None,
        metavar = "FILE",
        help = "path to sales CSV file",
    )
    group.add_argument(
        "-inv",
        "--inventory",
        nargs = "?",
        const = default_inv,
        default = None,
        metavar = "FILE",
        help = "Path to inventory CSV file",
    )
    group.add_argument(
        "-prod",
        "--production",
        nargs = "?",
        const = prod_ledger_source,
        default = None,
        metavar = "FILE",
        help = "Path to source production ledger CSV file",
    )
    group.add_argument(
            "-purch",
            "--purchases",
            nargs = "?",
            const = purchases,
            default = None,
            metavar = "FILE",
            help = "Path to raw purchases ledger CSV file",
        )
    group.add_argument(
            "-ini",
            "--initialize",
            nargs = "?",
            const = master_table_path,
            default = None,
            metavar = "FILE",
            help = "Path to raw purchases ledger CSV file",
        )

    parser.add_argument(
        "--master-item", 
        type=str,
        default = master_table_path,
        metavar = "FILE",
        help = "Path to source master item table CSV file"
    )
    parser.add_argument(
        "--stock-levels",
        default = stock_levels_path,
        metavar = "FILE",
        help = "Path to source stock level table CSV file"
    )
    parser.add_argument(
        "--stock-exceptions",
        default = stock_exceptions_path,
        metavar = "FILE",
        help = "Path to source stock level exceptions table CSV file"
    )
    parser.add_argument(
        "--inventory-path",
        default = inv_path,
        metavar = "FILE",
        help = "Path to source hand count inventory table CSV file"
    )
    parser.add_argument(
        "--purchases-source",
        default = purchase_path,
        metavar = "FILE",
        help = "Path to source purchases ledger CSV file"
    )
    parser.add_argument(
        "--production-path",
        default = production_ledger_path,
        metavar = "FILE",
        help = "Path to source (unexpanded) production ledger CSV file"
    )
    parser.add_argument(
        "--bill-of-mats",
        default = bill_of_mats,
        metavar = "FILE",
        help = "Path to Bill of materials table CSV file"
    )
    parser.add_argument(
        "--sales-source",
        default = raw_sales_path,
        metavar = "FILE",
        help = "Path to source (pivoted) sales table CSV file"
    )
    parser.add_argument(
        "--current_inv",
        default = current_inventory_path,
        metavar = "FILE",
        help = "Path to output current inventory table CSV file"
    )
    parser.add_argument(
        "--inv_history",
        default = inv_history_path,
        metavar = "FILE",
        help = "Path to output inventory history table CSV file"
    )
    parser.add_argument(
        "--expanded-production",
        default = expanded_prod_ledger_path,
        metavar = "FILE",
        help = "Path to output production ledger CSV file"
    )
    parser.add_argument(
        "--sales-output",
        default = events_sales_path,
        metavar = "FILE",
        help = "Path to output sales ledger CSV file"
    )
    parser.add_argument(
        "--events",
        default = events_path,
        metavar = "FILE",
        help = "Path to output events ledger CSV file"
    )
    parser.add_argument(
        "--purchases-output",
        default = purch_ledger_path,
        metavar = "FILE",
        help = "Path to output purchases ledger CSV file"
    )
    parser.add_argument(
        "--master-table-output",
        default = master_table_output,
        metavar = "FILE",
        help = "Path to outputMaster Item Table CSV file"
    )

    args = parser.parse_args()

    if not args.initialize:
        if not os.path.exists(inv_history_path):
            print(f"Error: Required history file '{inv_history_path}' not found.")
            print("Please run an initial inventory snapshot before processing sales.")
            # force the exit error so the engineer must touch <filename> or import data, depending on project state
            sys.exit(1)


    if args.initialize:
        initialize_db(args)
    if args.sales:
        sales_processing(args)

    if args.inventory:
        # changed from inv_history due to confusion with unified args;
        inv_df = pd.read_csv(inv_path)
        inventory_processing(args, inv_df)

    if args.production:
        production_processing(args)

    if args.purchases:
        purchases_processing(args)

if __name__ == "__main__":
    main()