import pandas as pd
import duckdb

from transforms import append_to_inv, transform_sales, transform_inv, transform_purchase, transform_production, create_current_from_inv, current_inv_enrichment, production_query,purchase_query, create_current_inv, backdating_sales_events, transform_events, backdating_purchases
from calculations import expand_production_df, calc_current_from_purch,update_current_from_prod, unique_dates

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


# Step 1: Create a dataset of all activities that need to be appended to relevant ledger 
def find_unprocessed_data(args) -> list[pd.Timestamp, pd.Timestamp, dict]:
    # Output Data
    expanded_prod_ledger_path = args.expanded_production 
    inv_history_path = args.inv_history
    purch_ledger_path = args.purchases_output
    events_sales_path = args.sales_output
    current_inventory_path = args.current_inv

    # Raw Data
    inv_path = args.inventory_path
    purchase_path = args.purchases_source
    production_ledger_path = args.production_path
    raw_sales_path = args.sales_source

    #Step 1.1 - Pull DataFrames
    expanded_production_df = pd.read_csv(expanded_prod_ledger_path)
    inv_history_df = pd.read_csv(inv_history_path)
    purchase_ledger_df = pd.read_csv(purch_ledger_path)
    events_sales_df = pd.read_csv(events_sales_path)
    current_inv_df = pd.read_csv(current_inventory_path)

    raw_inv_df = pd.read_csv(inv_path)
    raw_purch_df = pd.read_csv(purchase_path)
    raw_prod_df = pd.read_csv(production_ledger_path)
    raw_sales_df = pd.read_csv(raw_sales_path)

    #Set Date Format correctly
    raw_sales_df["Date of Sales"]= pd.to_datetime(raw_sales_df["Date of Sales"], errors='coerce').dt.date
    raw_inv_df["Date of Inventory"]= pd.to_datetime(raw_inv_df["Date of Inventory"], errors='coerce').dt.date
    raw_purch_df["Date of Purchase"]= pd.to_datetime(raw_purch_df["Date of Purchase"], errors='coerce').dt.date
    raw_prod_df["Date of Production"]= pd.to_datetime(raw_prod_df["Date of Production"], errors='coerce').dt.date

    events_sales_df["Date of Sales"]= pd.to_datetime(events_sales_df["Date of Sales"], errors='coerce').dt.date
    inv_history_df["Date of Inventory"]= pd.to_datetime(inv_history_df["Date of Inventory"], errors='coerce').dt.date
    current_inv_df["Date of Inventory"]= pd.to_datetime(current_inv_df["Date of Inventory"], errors='coerce').dt.date
    purchase_ledger_df["Date of Purchase"]= pd.to_datetime(purchase_ledger_df["Date of Purchase"], errors='coerce').dt.date
    expanded_production_df["Date of Production"]= pd.to_datetime(expanded_production_df["Date of Production"], errors='coerce').dt.date

    #Step 1.2 Create dataframes of activity dates that exist in raw data but not in output data  | pulling the dataset direct from dates that are missing means i no longer have to guess about what dates are needed to be added
    #Step 1.2a Pull unique dates of Inventory History that have Hand Count Inventory Locations already processed
    processed_hand_count_inventory_dates = inv_history_df[inv_history_df["Inventory Location"]=="Hand Count"]["Date of Inventory"].unique()

    missing_inventories_df = raw_inv_df[~raw_inv_df["Date of Inventory"].isin(processed_hand_count_inventory_dates)]
    missing_purchases_df = raw_purch_df[~raw_purch_df["Date of Purchase"].isin(purchase_ledger_df["Date of Purchase"])]
    missing_sales_df = raw_sales_df[~raw_sales_df["Date of Sales"].isin(events_sales_df["Date of Sales"])]
    missing_production_df = raw_prod_df[~raw_prod_df["Date of Production"].isin(expanded_production_df["Date of Production"])]

    loaded_dict = {
        "Inventory": missing_inventories_df,
        "Purchase": missing_purchases_df,
        "Production": missing_production_df,
        "Sales": missing_sales_df
    }

    # 1.2b: Exits out if here is no new data
    if all(df.empty for df in loaded_dict.values()):
            print("No new data. System is up to date. Exiting.")
            return

    dates = []
   
    for activity, dataframe in loaded_dict.items():
        if dataframe.empty:
            continue

        date_col = f"Date of {activity}"

        if date_col in dataframe.columns:
            valid_dates = pd.to_datetime(dataframe[date_col], errors="coerce").dropna()
            if not valid_dates.empty:
                dates.append(valid_dates.min())
        
    if dates:
        earliest_date_to_process = min(dates)
        

    #Step 1.4 Determine if any inventory history data needs to be overwritten, process accordingly

    current_inv_date = pd.to_datetime(current_inv_df["Date of Inventory"]).max()

    if earliest_date_to_process > current_inv_date :
        # all data falls after the last performed run
        print("New data falls after current iventory date. Appending data to approriate ledgers and updating inventory history.")
        activity_to_load_df = merge_raw_data_for_processing(args,loaded_dict)
        backdated_data = False

    else:
        # some data falls earlier than last run, so we need to rewrite inventory histry ledger for all activities on and after the earliest date
        print("We've found backdated data. We're going to need to clean the existing data first.")
        drop_inventory_history_rows(args, inv_history_df,earliest_date_to_process)
        print("Beginning repopulation of inventory history.")

        print(f"Pulling additional data from all activities on or after {earliest_date_to_process}.")
        updated_loaded_dict = additional_activity_pull(raw_sales_df, raw_prod_df, raw_purch_df, raw_inv_df, loaded_dict, earliest_date_to_process)
        activity_to_load_df = merge_raw_data_for_processing(args,updated_loaded_dict)
        backdated_data = True

    if not activity_to_load_df.empty:
        populate_inventory_history(args, activity_to_load_df, backdated_data)
        print("Testing to see if activity is empty. It is not.")

    if not all(df.empty for df in loaded_dict.values()):
        append_ledgers(args, loaded_dict)

  

# Step 2 (Optional, when earliest predates current inventory date) Wipe Inventory History file of rows on and after earliest date
def drop_inventory_history_rows(args, inv_history_df: pd.DataFrame, earliest_date: pd.Timestamp)->pd.DataFrame:
    inv_history_path = args.inv_history

    inv_hist = inv_history_df.copy()
    rows = len(inv_hist) - len(inv_hist[pd.to_datetime(inv_hist["Date of Inventory"]) < earliest_date])
    inv_hist = inv_hist[pd.to_datetime(inv_hist["Date of Inventory"]) < earliest_date]

    print(f"Deleting {rows} from {inv_history_path} to update all records on and after {earliest_date}")
    inv_hist.to_csv(inv_history_path, index=False)
    
# Step 2.1 (optional, when earliest predates current inventory date) Pull additional rows from earliest date forward from raw data files
def additional_activity_pull(raw_sales: pd.DataFrame, raw_prod: pd.DataFrame, raw_purch: pd.DataFrame, raw_hist:pd.DataFrame, loaded_dict: dict, earliest_date: pd.Timestamp) -> dict:
    reloaded_dict= loaded_dict.copy()
    raw_map = {
        "Inventory": raw_hist,
        "Sales": raw_sales,
        "Purchase": raw_purch,
        "Production": raw_prod
    }

    for activity, dataframe in reloaded_dict.items():
        if activity not in raw_map:
            continue

        raw_df = raw_map[activity]
        date_col = f"Date of {activity}"

        filtered_raw = raw_df[pd.to_datetime(raw_df[date_col]) >= earliest_date]

        reloaded_dict[activity] = pd.concat([reloaded_dict[activity], filtered_raw],ignore_index=True).drop_duplicates()

    return reloaded_dict
        
# Pull dataframes of all relevant data, convert into single table to analyze
def merge_raw_data_for_processing(args, loaded_dict: pd.DataFrame) -> pd.DataFrame:
    bill_of_mats = args.bill_of_mats

    bill_of_mats_df = pd.read_csv(bill_of_mats)

    # Loop over the dictionary and pull the dataframe out, append to a new list
    prepped_dfs = []

    for activity, raw_df in loaded_dict.items():
        if raw_df.empty:
            print(f"No {activity} data to process. Skipping....")
            continue

        print(f"Working on {activity} data...")
    # Step 2.2a: transform Sales Data
        if activity == "Sales":
            prepped= transform_sales(raw_df)
            prepped["Activity"] = "Sales"
            prepped= prepped.rename(columns={"Qty Sold":"Qty","Date of Sales":"Date"})
            print(f"{len(prepped)} rows of {activity} Data prepared for load.")
    
    # Step 2.2b: transform Inventory Data
        elif activity == "Inventory":
            prepped = transform_inv(raw_df)
            prepped["Activity"] = "Inventory"
            prepped = prepped.rename(columns={"Qty in Stock":"Qty","Date of Inventory":"Date"})
            print(f"{len(prepped)} rows of Hand Count Inventory Data prepared for load.")

    # Step 2.2c: transform Purchases Data
        elif activity == "Purchase":
            prepped = transform_purchase(raw_df)
            prepped["Activity"] = "Purchase"
            prepped = prepped.rename(columns={"Quantity Bought":"Qty","Date of Purchase":"Date"})
            print(f"{len(prepped)} rows of {activity} Data prepared for load.")

    # Step 2.2d: transform Production Data
        elif activity == "Production":
            compressed_prod = transform_production(raw_df)
            prepped = expand_production_df(bill_of_mats_df,compressed_prod)
            prepped["Activity"] = "Production"
            prepped = prepped.rename(columns={"Qty Delta":"Qty","Date of Production":"Date"})
            print(f"{len(prepped)} rows of {activity} Data prepared for load.")

        prepped_dfs.append(prepped)
    
    #Step 2.3 Merge Data into a single dataframe to be parsed
    if not prepped_dfs:
        print("No data to process.")
        activity_df = pd.DataFrame()
    else:
        activity_df = pd.concat(prepped_dfs, ignore_index=True)
    print("Printing consolidated activity dataframe...")
    print(activity_df)
    return activity_df

# Run each Date through the Current Inventory and create a inventory log based on the activity type; this populates the inventory ledger for all data after the initialized current inventory date
def populate_inventory_history(args, activity_ledger: pd.DataFrame, backdated_data: bool):
    inv_history_path = args.inv_history
    current_inventory_path = args.current_inv
    master_table_path = args.master_item
    stock_levels_path = args.stock_levels
    stock_exceptions_path = args.stock_exceptions

    activity_order = ["Inventory","Purchase","Production","Sales"]

    #Create a List of Dates to Parse over from the full activity log
    all_dates = unique_dates("Processing",activity_ledger)
    all_dates["Date"] = pd.to_datetime(all_dates["Date"])

    inventory_initialization_date = pd.to_datetime("2024-12-31")
    valid_dates = all_dates[all_dates["Date"] > inventory_initialization_date]
    
    activity_ledger["Date"] = pd.to_datetime(activity_ledger["Date"])
    current_inventory = pd.read_csv(current_inventory_path)

    #Iterate over every date in the dates dataframe (i.e., unique dates from the activity ledger that fall after the initialization of the inventory)
    for unique_date in valid_dates["Date"]:
        print(f"Pulling data from {unique_date}...")
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
            print(f"Working on {activity} data for {unique_date}")
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
            elif activity == "Purchase":
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

# Populate the Power-BI ledgers with data
def append_ledgers(args, loaded_dict):


    expanded_prod_ledger_path = args.expanded_production 
    purch_ledger_path = args.purchases_output
    events_sales_path = args.sales_output
    events_path = args.events
    bill_of_mats = args.bill_of_mats

    #Step 4.1 : Unpack the Dataframes
    raw_sales_to_append = loaded_dict["Sales"]
    raw_purch_to_append = loaded_dict["Purchase"]
    raw_prod_to_append = loaded_dict["Production"]

    bill_of_mats_df = pd.read_csv(bill_of_mats)

    #Step 4.2 Populate Sales and Events Ledgers
    sales = transform_sales(raw_sales_to_append)
    events = transform_events(raw_sales_to_append)
    dates_df = unique_dates("Sales", sales)

    backdating_sales_events("Sales",dates_df, sales, events_sales_path)
    backdating_sales_events("Events",dates_df, events, events_path)

    #4.3 Populate Purchases Ledger
    purchases = transform_purchase(raw_purch_to_append)
    backdating_purchases("Purchases",purchases,purch_ledger_path)

    #4.4 Populate the expanded production ledger
    production = transform_production(raw_prod_to_append)
    expanded = expand_production_df(bill_of_mats_df,production)
    backdating_purchases("Production",expanded,expanded_prod_ledger_path)

    
