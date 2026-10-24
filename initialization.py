import pandas as pd
import duckdb
import os

from transforms import initialize_current_inv_query, append_to_inv, transform_raw_sales, transform_inv, transform_purchase, transform_production, create_current_from_inv, current_inv_enrichment, backdating_sales_events, transform_events, backdating_purchases
from calculations import expand_production_df, calc_current_from_purch,update_current_from_prod, unique_dates

### ----------- ARGS Quick Reference -----------
#    expanded_prod_ledger_path = args.expanded_production 
#    inv_history_path = args.inv_history
#    purch_ledger_path = args.purchases_output
#    events_sales_path = args.sales_output
#    events_path = args.events
#    current_inventory_path = args.current_inv
#    master_table_output = args.master_table_output
#    raw_mats_ledger_path = args.raw_mats_output
#    production_lots_path = args.prod_lots_output
#
#    master_table_path = args.master_item
#    stock_levels_path = args.stock_levels
#    stock_exceptions_path = args.stock_exceptions
#    inv_path = args.inventory_path
#    purchase_path = args.purchases_source
#    production_ledger_path = args.production_path
#    bill_of_mats = args.bill_of_mats
#    raw_sales_path = args.sales_source
#    image_dir = args.image_dir
# ------------------------------------------------


# Step 1: touch output files and set up columns
def initialize_outputs(args):
    expanded_prod_ledger_path = args.expanded_production 
    inv_history_path = args.inv_history
    purch_ledger_path = args.purchases_output
    events_sales_path = args.sales_output
    events_path = args.events
    current_inventory_path = args.current_inv
    master_table_output = args.master_table_output
    master_table_path = args.master_item
    stock_levels_path = args.stock_levels
    stock_exceptions_path = args.stock_exceptions
    production_lots_path = args.prod_lots_output
    image_dir = args.image_dir


    inv_ledger_headers = ["Run_ID","Timestamp","Date of Inventory","Inventory Activity","Item", "Purchase_ID", "Batch_ID", "Qty in Stock", "Cost"]
    purch_ledger_headers = [ "Purchase_ID", "Timestamp","Date of Purchase", "Invoice / Purchase Orders","Item","Quantity Bought","Cost","Price (each)","Subtotal","Status"]
    prod_ledger_headers = ["Batch_ID","Timestamp","Date of Production", "Item", "Purchase_ID", "Type", "Qty Delta", "Cost"]
    sales_headers = ["Sales_ID","Timestamp","Event_ID","Date of Sales","Event Name","Item","Subcategory", "Qty Sold", "Purchase_ID", "Batch_ID", "Cost (ea)"]
    events_headers = ["Event_ID","Timestamp","Date of Sales","Event Name","Location (City)", "Total Sales($)","(Total) Tabling and Additional Costs ($)","Event Notes (weather, etc)"]
    production_lots_headers = ["Timestamp","Date of Production","Batch_ID","Item","Cost","Qty", "Status"]

    # Check for output files. If they do not exist, set them up, otherwise skip.
    # Do we want a sys.exit(0) here, since initialization will be writing data?
    if not os.path.exists(inv_history_path):
        inv_df = pd.DataFrame(columns = inv_ledger_headers)
        inv_df.to_csv(inv_history_path, index = False)
        print(f"Inventory history initialized as {inv_history_path}.")

    else:
        print(f"{inv_history_path} already exists.")
        
    if not os.path.exists(purch_ledger_path):
        purch_df = pd.DataFrame(columns = purch_ledger_headers)
        purch_df.to_csv(purch_ledger_path, index = False)
        print(f"Purchasing history initialized as {purch_ledger_path}.")

    else:
        print(f"{purch_ledger_path} already exists.")

    if not os.path.exists(expanded_prod_ledger_path):
        prod_df = pd.DataFrame(columns = prod_ledger_headers)
        prod_df.to_csv(expanded_prod_ledger_path, index = False)
        print(f"Productioon file initialized as {expanded_prod_ledger_path}.")

    else:
        print(f"{expanded_prod_ledger_path} already exists.")

    if not os.path.exists(events_sales_path):
        sales_df = pd.DataFrame(columns = sales_headers)
        sales_df.to_csv(events_sales_path, index = False)
        print(f"Sales Events file initialized as {events_sales_path}.")

    else:
        print(f"{events_sales_path} already exists.")

    if not os.path.exists(events_path):
        events_df = pd.DataFrame(columns = events_headers)
        events_df.to_csv(events_path, index = False)
        print(f"Sales Events file initialized as {events_path}.")

    else:
        print(f"{events_sales_path} already exists.")

    if not os.path.exists(current_inventory_path):
        master_df = pd.read_csv(master_table_path)

        if not os.path.exists(master_table_output):
            master_df.to_csv(master_table_output, index=False)
        else:
            print(f"{master_table_output} already exists.")

        current_inv = initialize_current_inv_query(master_df,stock_levels_path,stock_exceptions_path)
        append_to_inv(inv_history_path,current_inv)
        current_inv.to_csv(current_inventory_path, index= False)
        print(f"{current_inventory_path} written with zeroed data. {len(current_inv)} rows saved.")

    else:
        print(f"{current_inventory_path} already exists.")

    if not os.path.exists(production_lots_path):
        prod_lots_df = pd.DataFrame(columns = production_lots_headers)
        prod_lots_df.to_csv(production_lots_path, index = False)
        print(f"Productioon file initialized as {production_lots_path}.")

    else:
        print(f"{production_lots_path} already exists.")

    os.makedirs(image_dir,exist_ok=True)
    print(f"Created directed for zip files as {image_dir}/")
