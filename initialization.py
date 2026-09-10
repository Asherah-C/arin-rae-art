import pandas as pd
import duckdb
import os

from transforms import initialize_current_inv_query, append_to_inv, transform_sales, transform_inv, transform_purchase, transform_production, create_current_from_inv, current_inv_enrichment, production_query,purchase_query, create_current_inv, backdating_sales_events, transform_events, backdating_purchases
from calculations import expand_production_df, calc_current_from_purch,update_current_from_prod, unique_dates

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


    inv_ledger_headers = ["Timestamp","Date of Inventory","Inventory Location","Item","Qty in Stock"]
    purch_ledger_headers = ["Timestamp","Date of Purchase", "Invoice / Purchase Orders","Item","Quantity Bought","Price (each)","Subtotal"]
    prod_ledger_headers = ["Timestamp","Date of Production", "Item", "Type", "Delta Qty"]
    sales_headers = ["Timestamp","Date of Sales","Event Name","Item","Qty Sold"]
    events_headers = ["Timestamp","Date of Sales","Event Name","Total Sales($)","(Total) Tabling and Additional Costs ($)","Event Notes (weather, etc)"]

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

    if not os.path.exists(expanded_prod_ledger_path):
        prod_df = pd.DataFrame(columns = prod_ledger_headers)
        prod_df.to_csv(expanded_prod_ledger_path, index = False)
        print(f"Sales Events file initialized as {expanded_prod_ledger_path}.")

    else:
        print(f"{expanded_prod_ledger_path} already exists.")

    if not os.path.exists(expanded_prod_ledger_path):
        prod_df = pd.DataFrame(columns = prod_ledger_headers)
        prod_df.to_csv(expanded_prod_ledger_path, index = False)
        print(f"Production ledger file initialized as {expanded_prod_ledger_path}.")

    else:
        print(f"{expanded_prod_ledger_path} already exists.")

# Step 2 Pull dataframes of raw data, convert into single table to analyze
def pull_initial_data(args) -> pd.DataFrame:
    inv_path = args.inventory_path
    purchase_path = args.purchases_source
    production_ledger_path = args.production_path
    bill_of_mats = args.bill_of_mats
    raw_sales_path = args.sales_source


    raw_sales_df = pd.read_csv(raw_sales_path)
    inventories_df = pd.read_csv(inv_path)
    purchases_df = pd.read_csv(purchase_path)
    production_df = pd.read_csv(production_ledger_path)
    bill_of_mats_df = pd.read_csv(bill_of_mats)

    #Set Date Format correctly
    raw_sales_df["Date of Sales"]= pd.to_datetime(raw_sales_df["Date of Sales"], errors='coerce').dt.strftime("%Y-%m-%d")
    inventories_df["Date of Inventory"]= pd.to_datetime(inventories_df["Date of Inventory"], errors='coerce').dt.strftime("%Y-%m-%d")
    purchases_df["Date of Purchase"]= pd.to_datetime(purchases_df["Date of Purchase"], errors='coerce').dt.strftime("%Y-%m-%d")
    production_df["Date of Production"]= pd.to_datetime(production_df["Date of Production"], errors='coerce').dt.strftime("%Y-%m-%d")
    # stock_lvl_df = pd.read_csv(stock_levels_path)
    #stk_exceptions_df = pd.read_csv(stock_exceptions_path)

    # Step 2.1: transform Sales Data
    prepped_sales = transform_sales(raw_sales_df)
    prepped_sales["Activity"] = "Sales"
    prepped_sales = prepped_sales.rename(columns={"Qty Sold":"Qty","Date of Sales":"Date"})
    
    # Step 2.2: transform Inventory Data
    prepped_inv = transform_inv(inventories_df)
    prepped_inv["Activity"] = "Inventory"
    prepped_inv = prepped_inv.rename(columns={"Qty in Stock":"Qty","Date of Inventory":"Date"})

    # Step 2.3: transform Purchases Data
    prepped_purch = transform_purchase(purchases_df)
    prepped_purch["Activity"] = "Purchases"
    prepped_purch = prepped_purch.rename(columns={"Qty Bought":"Qty","Date of Purchase":"Date"})

    # Step 2.4: transform Production Data
    compressed_prod_df = transform_production(production_df)
    expanded_prod_df = expand_production_df(bill_of_mats_df,compressed_prod_df)
    expanded_prod_df["Activity"] = "Production"
    expanded_prod_df = expanded_prod_df.rename(columns={"Qty Delta":"Qty","Date of Production":"Date"})
 
    #Step 2.5 Merge Data into a single dataframe to be parsed
    activity_df = pd.concat(
        [prepped_sales,prepped_inv,prepped_purch,expanded_prod_df],
        ignore_index=True
    )

    return activity_df

#Step 3: Run each Date through the Current Inventory and create a inventory log based on the activity type; this populates the inventory ledger for all data after the initialized current inventory date
def initialize_inventory_history(args):
    inv_history_path = args.inv_history
    current_inventory_path = args.current_inv
    master_table_path = args.master_item
    stock_levels_path = args.stock_levels
    stock_exceptions_path = args.stock_exceptions

    activity_ledger = pull_initial_data(args)

    activity_order = ["Inventory","Purchases","Production","Sales"]

    #Step 3.1 Create a List of Dates to Parse over from the full activity log
    dates = unique_dates("Initialization",activity_ledger)

    #Step 3.2 Ensure Date values are treated as dates in Pandas
    dates["Date"] = pd.to_datetime(dates["Date"])
    activity_ledger["Date"] = pd.to_datetime(activity_ledger["Date"])
    current_inventory = pd.read_csv(current_inventory_path)

    #Step 3.3 Iterate over every date in the dates dataframe (i.e., unique dates from the activity ledger)
    for unique_date in dates["Date"]:
        #3.3.1 Check the current inventory date

        current_inventory["Date of Inventory"] = pd.to_datetime(current_inventory["Date of Inventory"])
        current_inv_date = pd.to_datetime(current_inventory["Date of Inventory"]).max()

        print(unique_date,current_inv_date)
        #3.3.2 Check to see if the activity occurs before the current inventory date, we are looking for only activities after the initialization date.
        if unique_date <= current_inv_date:
            pass # skip dates before the current inventory date
        else: # Pull the activity from the iterated date
            print(f"Pulling data from{unique_date}")
            date_log_query="""
            SELECT
                Timestamp,
                Date,
                Activity,
                Item,
                Qty
            FROM activity_ledger
            WHERE Date = $unique_date
            ORDER BY Activity,Item
            """
            date_log = duckdb.query(date_log_query, params={"unique_date": unique_date}).df()

            #3.3.2.a Determine activities performed on the date, determine number and order of passes
            unique_activities = date_log["Activity"].unique()
            passes = [act for act in activity_order if act in unique_activities]

            #3.3.2.b process each activity
            for activity in passes:
                activity_df = date_log[date_log["Activity"] == activity].sort_values(by="Item")
                activity_df["Inventory Location"] = "Calculated"

                # Based on each activity, execute relevant functions
                if activity == "Inventory":
                    activity_df = activity_df.rename(columns={"Qty":"Qty in Stock","Date": "Date of Inventory"})
                    activity_df["Inventory Location"] = "Hand Count"
                    curr_inv = create_current_from_inv (activity_df)
                    enriched = current_inv_enrichment(curr_inv, master_table_path)
                    prod  = production_query(enriched,stock_levels_path,stock_exceptions_path)
                    finished_curr = purchase_query(prod)
                    current_inventory = finished_curr
                    append_to_inv(inv_history_path,finished_curr)
                elif activity == "Purchases":
                    activity_df = activity_df.rename(columns={"Qty":"Quantity Bought","Date": "Date of Purchase"})
                    curr_inv = calc_current_from_purch(activity_df,current_inventory)
                    enriched = current_inv_enrichment(curr_inv, master_table_path)
                    prod  = production_query(enriched,stock_levels_path,stock_exceptions_path)
                    finished_curr = purchase_query(prod)
                    current_inventory = finished_curr
                    append_to_inv(inv_history_path,finished_curr)
                elif activity == "Production":
                    activity_df = activity_df.rename(columns={"Qty":"Qty Delta","Date": "Date of Production"})
                    curr_inv = update_current_from_prod(activity_df,current_inventory)
                    enriched = current_inv_enrichment(curr_inv, master_table_path)
                    prod  = production_query(enriched,stock_levels_path,stock_exceptions_path)
                    finished_curr = purchase_query(prod)
                    current_inventory = finished_curr
                    append_to_inv(inv_history_path,finished_curr)
                elif activity == "Sales":
                    activity_df = activity_df.rename(columns={"Qty":"Qty Sold","Date": "Date of Sales"})
                    curr_inv = create_current_inv (activity_df,current_inventory)
                    enriched = current_inv_enrichment(curr_inv, master_table_path)
                    prod  = production_query(enriched,stock_levels_path,stock_exceptions_path)
                    finished_curr = purchase_query(prod)
                    current_inventory = finished_curr
                    append_to_inv(inv_history_path,finished_curr)
                else:
                    print(f"{activity} Not Recognized. Skipping....")

    
    current_inventory.to_csv(current_inventory_path, index= False)
    print(f"{current_inventory_path} overwitten with current data. {len(current_inventory)} rows saved.")

# Step 4 Populate the Power-BI ledgers with data
def initialize_ledgers(args):
    expanded_prod_ledger_path = args.expanded_production 
    purch_ledger_path = args.purchases_output
    events_sales_path = args.sales_output
    events_path = args.events
    purchase_path = args.purchases_source
    production_ledger_path = args.production_path
    bill_of_mats = args.bill_of_mats
    raw_sales_path = args.sales_source


    #Step 4.1 : Pull files into memory
    raw_sales_df = pd.read_csv(raw_sales_path)
    purchases_df = pd.read_csv(purchase_path)
    production_df = pd.read_csv(production_ledger_path)
    bill_of_mats_df = pd.read_csv(bill_of_mats)

    #Set Date Format correctly
    raw_sales_df["Date of Sales"]= pd.to_datetime(raw_sales_df["Date of Sales"], errors='coerce').dt.strftime("%Y-%m-%d")
    purchases_df["Date of Purchase"]= pd.to_datetime(purchases_df["Date of Purchase"], errors='coerce').dt.strftime("%Y-%m-%d")
    production_df["Date of Production"]= pd.to_datetime(production_df["Date of Production"], errors='coerce').dt.strftime("%Y-%m-%d")


    #4.2 Populate Purchases Ledger
    purchases = transform_purchase(purchases_df)
    backdating_purchases("Purchases",purchases,purch_ledger_path)

    #4.3 Populate the expanded production ledger
    production = transform_production(production_df)
    expanded = expand_production_df(bill_of_mats_df,production)
    backdating_purchases("Production",expanded,expanded_prod_ledger_path)

    #Step 4.4 Populaate Sales and Events Ledgers
    sales = transform_sales(raw_sales_df)
    events = transform_events(raw_sales_df)
    dates_df = unique_dates("Sales", sales)

    backdating_sales_events("Sales",dates_df, sales, events_sales_path)
    backdating_sales_events("Events",dates_df, events, events_path)