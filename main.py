import os
import sys
import argparse
from initialization import initialize_outputs, initialize_inventory_history, initialize_ledgers
from processing import find_unprocessed_data

# Unified Path Variables
master_table_path = "Inventory - DIM-Master Item Table.csv"
stock_levels_path = "Inventory - DIM - Item Stock Level.csv"
stock_exceptions_path = "Inventory - DIM - Stock Level Exceptions.csv"
inv_path = "Inventory - FACT - Inventory Snapshots.csv"
purchase_path = "Inventory - FACT - Purchases.csv"
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
#    initialize_ledgers(args)
    find_unprocessed_data(args)

# Process New Data after initialization
def run_processing(args):
    find_unprocessed_data(args)

def main():
    parser = argparse.ArgumentParser(
        description = "Transform sales, purchases, production and inventory CSVs into pivoted BI format."
    )

    group = parser.add_mutually_exclusive_group(required = True)

    group.add_argument(
        "-proc",
        "--process",
        nargs = "?",
        const = master_table_path,
        default = None,
        metavar = "FILE",
        help = "process all activities after initialization.",
    )
#    group.add_argument(
#        "-sales",
#        "--sales",
#        nargs = "?",
#        const = default_sales,
#        default = None,
#        metavar = "FILE",
#        help = "path to sales CSV file",
#    )
#    group.add_argument(
#        "-inv",
#        "--inventory",
#        nargs = "?",
#        const = default_inv,
#        default = None,
#        metavar = "FILE",
#        help = "Path to inventory CSV file",
#    )
#    group.add_argument(
#        "-prod",
#        "--production",
#        nargs = "?",
#        const = prod_ledger_source,
#        default = None,
#        metavar = "FILE",
#        help = "Path to source production ledger CSV file",
#    )
#    group.add_argument(
#            "-purch",
#            "--purchases",
#            nargs = "?",
#            const = purchases,
#            default = None,
#            metavar = "FILE",
#            help = "Path to raw purchases ledger CSV file",
#        )
    group.add_argument(
            "-ini",
            "--initialize",
            nargs = "?",
            const = master_table_path,
            default = None,
            metavar = "FILE",
            help = "Initialize new business activity",
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
    if args.process:
        run_processing(args)

if __name__ == "__main__":
    main()