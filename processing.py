import pandas as pd
import duckdb

from transforms import append_to_inv, transform_sales, transform_inv, transform_purchase, transform_production, create_current_from_inv, current_inv_enrichment, backdating_sales_events, transform_events, backdating_purchases
from calculations import expand_production_df, calc_current_from_purch, update_current_from_prod, unique_dates, calc_sales_df, calc_curr_from_sales

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
    raw_sales_df["Date of Sales"]= pd.to_datetime(raw_sales_df["Date of Sales"].astype(str).str.strip(), format='%m/%d/%Y')
    raw_inv_df["Date of Inventory"]= pd.to_datetime(raw_inv_df["Date of Inventory"].astype(str).str.strip(), format='%m/%d/%Y')
    raw_purch_df["Date of Purchase"]= pd.to_datetime(raw_purch_df["Date of Purchase"].astype(str).str.strip(), format='%m/%d/%Y')
    raw_prod_df["Date of Production"]= pd.to_datetime(raw_prod_df["Date of Production"].astype(str).str.strip(), format='%m/%d/%Y')

    events_sales_df["Date of Sales"]= pd.to_datetime(events_sales_df["Date of Sales"].astype(str).str.strip(), format='ISO8601')
    inv_history_df["Date of Inventory"]= pd.to_datetime(inv_history_df["Date of Inventory"].astype(str).str.strip(), format='ISO8601')
    current_inv_df["Date of Inventory"]= pd.to_datetime(current_inv_df["Date of Inventory"].astype(str).str.strip(), format='ISO8601')
    purchase_ledger_df["Date of Purchase"]= pd.to_datetime(purchase_ledger_df["Date of Purchase"].astype(str).str.strip(), format='ISO8601')
    expanded_production_df["Date of Production"]= pd.to_datetime(expanded_production_df["Date of Production"].astype(str).str.strip(), format='ISO8601')

    #Step 1.2 Create dataframes of activity dates that exist in raw data but not in output data  | pulling the dataset direct from dates that are missing means i no longer have to guess about what dates are needed to be added
    #Step 1.2a Pull unique dates of Inventory History that have Hand Count Inventory Activities already processed
    processed_hand_count_inventory_dates = inv_history_df[inv_history_df["Inventory Activity"]=="Hand Count"]["Date of Inventory"].unique()

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

    print(loaded_dict)
    # 1.2b: Exits out if here is no new data
    if all(df.empty for df in loaded_dict.values()):
            print("No new data. System is up to date. Exiting.")
            return

    dates = []

   #if not empty, pull date for each activity row missing
    for activity, dataframe in loaded_dict.items():
        if dataframe.empty:
            continue

        #parsed by date of individual date in the activity's row
        date_col = f"Date of {activity}"

        # run each dataframe, adding dates for each row of activity, as applicable
        if date_col in dataframe.columns:
            valid_dates = pd.to_datetime(dataframe[date_col], errors="coerce").dropna()
            #find the earliest date of each dataframe, save in valid_dates list
            if not valid_dates.empty:
                dates.append(valid_dates.min())

    #if there are dates to process, find the earliest date to process
    if dates:
        earliest_date_to_process = min(dates)

    #Step 1.4 Determine if any inventory history data needs to be overwritten, process accordingly

    current_inv_date = pd.to_datetime(current_inv_df["Date of Inventory"]).max()

    if earliest_date_to_process > current_inv_date :
        # all data falls after the last performed run
        print("New data falls after current iventory date. Appending data to approriate ledgers and updating inventory history.")
        activity_to_load_df, updated_purchase_lots, prepped_prod_df, production_lots = merge_raw_data_for_processing(args,loaded_dict)
        backdated_data = False

    else:
        # some data falls earlier than last run, so we need to rewrite inventory histry ledger for all activities on and after the earliest date
        print("We've found backdated data. We're going to need to clean the existing data first.")
        inventory_to_reset_current = drop_inventory_history_rows(args, inv_history_df,earliest_date_to_process)
        set_backdated_current_inv(args, inventory_to_reset_current)
        print("Beginning repopulation of inventory history.")

        print(f"Pulling additional data from all activities on or after {earliest_date_to_process}.")
        updated_loaded_dict = additional_activity_pull(raw_sales_df, raw_prod_df, raw_purch_df, raw_inv_df, loaded_dict, earliest_date_to_process)
        activity_to_load_df, updated_purchase_lots, prepped_prod_df, production_lots = merge_raw_data_for_processing(args,updated_loaded_dict)
        backdated_data = True

    if not activity_to_load_df.empty:
        populate_inventory_history(args, activity_to_load_df, backdated_data)
        print("Testing to see if activity is empty. It is not.")

    if not all(df.empty for df in loaded_dict.values()):
        append_ledgers(args, loaded_dict, prepped_prod_df, updated_purchase_lots, production_lots)
        #overwrites purchase lots statuses post-production
        
  

# Step 2 (Optional, when earliest predates current inventory date) Wipe Inventory History file of rows on and after earliest date
def drop_inventory_history_rows(args, inv_history_df: pd.DataFrame, earliest_date: pd.Timestamp)->pd.DataFrame:
    inv_history_path = args.inv_history

    inv_hist = inv_history_df.copy()
    print(inv_hist)
    inv_hist["Date of Inventory"] = pd.to_datetime(inv_hist["Date of Inventory"])
    print(inv_hist["Date of Inventory"].min())
    rows = len(inv_hist) - len(inv_hist[pd.to_datetime(inv_hist["Date of Inventory"]) < earliest_date])
    inv_hist = inv_hist[pd.to_datetime(inv_hist["Date of Inventory"]) < earliest_date]

    print(f"Deleting {rows} from {inv_history_path} to update all records on and after {earliest_date}")
    inv_hist.to_csv(inv_history_path, index=False)

    # Find latest date of the known good inventory history, pull all rows of that date
    inv_hist["Date of Inventory"] = pd.to_datetime(inv_hist["Date of Inventory"])
    inv_history_maxdate = inv_hist["Date of Inventory"].max()
    to_backdate_current_inv_df = inv_hist[inv_hist["Date of Inventory"] == inv_history_maxdate]

    return(to_backdate_current_inv_df)

# Set the current inventory sheet to the back in time via pull of inventory history on last known good date
def set_backdated_current_inv(args, inv_to_backdate: pd.DataFrame):
    current_inventory_path = args.current_inv
    master_table_path = args.master_item
    stock_levels_path = args.stock_levels
    stock_exceptions_path = args.stock_exceptions

    print("Resetting current inventory to last known good inventory before backdate.")
    enriched = current_inv_enrichment(inv_to_backdate, master_table_path)
    #prod  = production_query(enriched,stock_levels_path,stock_exceptions_path)
    #finished_curr = purchase_query(prod)
    #current_inventory = finished_curr
    # enriched.to_csv("testpulloutcurrent.csv", index=False,date_format='%Y-%m-%dT%H:%M:%S')
    enriched.to_csv(current_inventory_path, index= False,date_format='%Y-%m-%dT%H:%M:%S')
    
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
def merge_raw_data_for_processing(args, loaded_dict: dict[str:pd.DataFrame]) -> pd.DataFrame:
    bill_of_mats = args.bill_of_mats
    expanded_prod_ledger_path = args.expanded_production
    purch_ledger_path = args.purchases_output
    master_table_path = args.master_table_output
    bill_of_mats_df = pd.read_csv(bill_of_mats)
    master_table_df = pd.read_csv(master_table_path)
    # Loop over the dictionary and pull the dataframe out, append to a new list
    prepped_dfs = []
    updated_purchase_lots = pd.DataFrame()
    prepped_prod_df = pd.DataFrame()
    production_lots = pd.DataFrame()

    #is this strictly necessary? Maybe yes, maybe no
    def pending_purchases(purch_ledger_path: str,loaded_dict: dict) -> pd.DataFrame: # returns a daily up-to-date purchase ledger in case a downstream activity needs purchase data before it is proccessed
        purch_ledger_df = pd.read_csv(purch_ledger_path)
        pending_purch = pd.DataFrame()
        #check for pending purchases, if true, load them into memory for processing
        if "Purchase" in loaded_dict and not loaded_dict["Purchase"].empty:
            pending_purch = transform_purchase(loaded_dict["Purchase"])
            pending_purch["Status"] = "Active"
        if not pending_purch.empty and "Purchase_ID" in purch_ledger_df.columns:
            existing_ids= set(purch_ledger_df["Purchase_ID"].dropna())
            pending_purch = pending_purch[~pending_purch["Purchase_ID"].isin(existing_ids)]
        if not pending_purch.empty:
            purch_ledger_df = pd.concat([purch_ledger_df,pending_purch], ignore_index=True)

        return purch_ledger_df

    for activity, raw_df in loaded_dict.items():
        if raw_df.empty:
            print(f"No {activity} data to process. Skipping....")
            continue

        print(f"Working on {activity} data...")

    
    # Step 2.2b: transform Inventory Data
        if activity == "Inventory":
            prepped = transform_inv(raw_df)
            prepped["Activity"] = "Inventory"
            prepped = prepped.rename(columns={"Qty in Stock":"Qty","Date of Inventory":"Date"})
            print(f"{len(prepped)} rows of Hand Count Inventory Data prepared for load.")
            print(prepped)

    # Step 2.2c: transform Purchase Data
        elif activity == "Purchase":
            prepped = transform_purchase(raw_df)
            prepped["Activity"] = "Purchase"
            prepped = prepped.rename(columns={"Quantity Bought":"Qty","Date of Purchase":"Date"})
            print(f"{len(prepped)} rows of {activity} Data prepared for load.")
            print(prepped)

    # Step 2.2d: transform Production Data
        elif activity == "Production":
            compressed_prod = transform_production(raw_df)
            expanded_prod_df = pd.read_csv(expanded_prod_ledger_path)
            # get an up-to-date purchase ledger, even if there is loaded but not applied purchase activity today
            purch_ledger_df = pending_purchases(purch_ledger_path,loaded_dict)

            next_batch_num = 1 if expanded_prod_df.empty else int(expanded_prod_df["Batch_ID"].max()) + 1
            updated_purchase_lots, prepped, production_lots = expand_production_df(bill_of_mats_df,compressed_prod,expanded_prod_df,purch_ledger_df,next_batch_num)

            prepped["Activity"] = "Production"
            prepped = prepped.rename(columns={"Qty Delta":"Qty","Date of Production":"Date"})
            prepped_prod_df = prepped.copy()
            print(f"{len(prepped)} rows of {activity} Data prepared for load:")
            print(prepped_prod_df)

    # Step 2.2a: transform Sales Data
        elif activity == "Sales":
            prepped= transform_sales(raw_df, master_table_df)
           
            events_sales_path = args.sales_output
            sales_history_df = pd.read_csv(events_sales_path)

            # get an up-to-date purchase ledger, even if there is loaded but not applied purchase activity today
            purch_ledger_df = pending_purchases(purch_ledger_path,loaded_dict)

            #if production was also run today, use its processed purchase lots instead of the original
            if not updated_purchase_lots.empty:
                purch_ledger_df = updated_purchase_lots

            #limit memory to only "Active" Lots
            purch_ledger_df = purch_ledger_df[purch_ledger_df["Status"]=="Active"]

            #Load production lots from most up to date source
            if not production_lots.empty:
                updated_production_lots = production_lots.copy()
            else:
                production_lots_path = args.prod_lots_output
                updated_production_lots = pd.read_csv(production_lots_path)

            #Process Sales by item, assigning lots to each item sold
            prepped, updated_purchase_lots, production_lots = calc_sales_df(prepped,purch_ledger_df,updated_production_lots,sales_history_df)

            prepped["Activity"] = "Sales"
            prepped.rename(columns={"Date of Sales":"Date"}, inplace=True)


        prepped_dfs.append(prepped)

   
    
    #Step 2.3 Merge Data into a single dataframe to be parsed
    if not prepped_dfs:
        print("No data to process.")
        activity_df = pd.DataFrame()
    else:
        activity_df = pd.concat(prepped_dfs, ignore_index=True)
        if "Timestamp" in activity_df.columns:
            activity_df["Timestamp"] = pd.to_datetime(activity_df["Timestamp"], format="mixed", utc=True, errors="coerce").dt.tz_localize(None)
        if isinstance(updated_purchase_lots, pd.DataFrame) and not updated_purchase_lots.empty:
            updated_purchase_lots["Timestamp"] = pd.to_datetime(updated_purchase_lots["Timestamp"], format="mixed", utc=True, errors="coerce").dt.tz_localize(None)
        if isinstance(prepped_prod_df, pd.DataFrame) and not prepped_prod_df.empty:
            prepped_prod_df["Timestamp"] = pd.to_datetime(prepped_prod_df["Timestamp"], format="mixed", utc=True, errors="coerce").dt.tz_localize(None)

    
    return activity_df, updated_purchase_lots, prepped_prod_df,production_lots

# Run each Date through the Current Inventory and create a inventory log based on the activity type; this populates the inventory ledger for all data after the initialized current inventory date
def populate_inventory_history(args, activity_ledger: pd.DataFrame, backdated_data: bool):
    inv_history_path = args.inv_history
    current_inventory_path = args.current_inv
    master_table_path = args.master_item
    stock_levels_path = args.stock_levels
    stock_exceptions_path = args.stock_exceptions

    print("Printing Activity Ledger")
    print(activity_ledger)

    activity_order = ["Inventory","Purchase","Production","Sales"]

    #Create a List of Dates to Parse over from the full activity log
    all_dates = unique_dates("Processing",activity_ledger)
    all_dates["Date"] = pd.to_datetime(all_dates["Date"])

    inventory_initialization_date = pd.to_datetime("2024-12-31")
    valid_dates = all_dates[all_dates["Date"] > inventory_initialization_date]
    
    activity_ledger["Date"] = pd.to_datetime(activity_ledger["Date"])
    current_inventory = pd.read_csv(current_inventory_path)

    print("Printing Current Inventory path")
    print (current_inventory_path)

    print("Printing activity ledger")
    print(activity_ledger)
    #Guards against Column errors
    for col in ["Purchase_ID", "Batch_ID"]:
        if col not in activity_ledger.columns:
            activity_ledger[col] = pd.NA

    #Iterate over every date in the dates dataframe (i.e., unique dates from the activity ledger that fall after the initialization of the inventory)
    for unique_date in valid_dates["Date"]:
        print(f"Pulling data from {unique_date}...")
        date_log_query="""
        SELECT
        Timestamp,
            Date,
            Activity,
            Item,
            Qty,
            Batch_ID,
            Purchase_ID,
            Cost
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
            activity_df["Inventory Activity"] = activity

            # Based on each activity, execute relevant functions
            if activity == "Inventory":
                activity_df = activity_df.rename(columns={"Qty":"Qty in Stock","Date": "Date of Inventory"})
                activity_df["Inventory Activity"] = "Hand Count"
                curr_inv = create_current_from_inv (activity_df)
                current_inventory = current_inv_enrichment(curr_inv, master_table_path)
                # prod  = production_query(enriched,stock_levels_path,stock_exceptions_path)
                # finished_curr = purchase_query(prod)
                # current_inventory = finished_curr
                append_to_inv(inv_history_path,current_inventory)
            elif activity == "Purchase":
                activity_df = activity_df.rename(columns={"Qty":"Quantity Bought","Date": "Date of Purchase"})
                #new code line to populate purchases
                print("Activity dataframe:")
                print(activity_df)
                print("Current Inventory:")
                print(current_inventory)
                curr_inv = calc_current_from_purch(activity_df,current_inventory)
                current_inventory = current_inv_enrichment(curr_inv, master_table_path)
                # prod  = production_query(enriched,stock_levels_path,stock_exceptions_path)
                # finished_curr = purchase_query(prod)
                # current_inventory = finished_curr
                append_to_inv(inv_history_path,current_inventory)
            elif activity == "Production":
                activity_df = activity_df.rename(columns={"Qty":"Qty Delta","Date": "Date of Production"})
                curr_inv = update_current_from_prod(activity_df,current_inventory)
                current_inventory = current_inv_enrichment(curr_inv, master_table_path)
                # prod  = production_query(enriched,stock_levels_path,stock_exceptions_path)
                # finished_curr = purchase_query(prod)
                # current_inventory = finished_curr
                append_to_inv(inv_history_path,current_inventory)
            elif activity == "Sales":
                activity_df = activity_df.rename(columns={"Qty":"Qty Sold","Date": "Date of Sales"})
                curr_inv = calc_curr_from_sales(activity_df,current_inventory)
                current_inventory = current_inv_enrichment(curr_inv, master_table_path)
                # prod  = production_query(enriched,stock_levels_path,stock_exceptions_path)
                # finished_curr = purchase_query(prod)
                # current_inventory = finished_curr
                append_to_inv(inv_history_path,current_inventory)
            else:
                print(f"{activity} Not Recognized. Skipping....")

    
    current_inventory.to_csv(current_inventory_path, header= True, index= False, date_format='%Y-%m-%dT%H:%M:%S')
    print(f"{current_inventory_path} overwitten with current data. {len(current_inventory)} rows saved.")

# Populate the Power-BI ledgers with data
def append_ledgers(args, loaded_dict,prepped_prod_df: pd.DataFrame, purch_activity_update: pd.DataFrame, production_lots: pd.DataFrame):


    expanded_prod_ledger_path = args.expanded_production 
    purch_ledger_path = args.purchases_output
    events_sales_path = args.sales_output
    events_path = args.events
    bill_of_mats = args.bill_of_mats
    master_table_path = args.master_table_output
    production_lots_path = args.prod_lots_output

    #Step 4.1 : Unpack the Dataframes
    raw_sales_to_append = loaded_dict["Sales"]
    raw_purch_to_append = loaded_dict["Purchase"]

    bill_of_mats_df = pd.read_csv(bill_of_mats)
    master_table_df = pd.read_csv(master_table_path)

    #Step 4.2 Populate Sales and Events Ledgers, test for empty
    if isinstance(raw_sales_to_append,pd.DataFrame) and not raw_sales_to_append.empty:
        sales = transform_sales(raw_sales_to_append, master_table_df)
        events = transform_events(raw_sales_to_append)
        dates_df = unique_dates("Sales", sales)

        backdating_sales_events("Sales",dates_df, sales, events_sales_path)
        backdating_sales_events("Events",dates_df, events, events_path)

    #4.3 Populate Purchase Ledger
    if isinstance(raw_purch_to_append,pd.DataFrame) and not raw_purch_to_append.empty:
        purchases = transform_purchase(raw_purch_to_append)
        backdating_purchases("Purchase",purchases,purch_ledger_path)

    #4.4 Populate the expanded production ledger
    if isinstance(prepped_prod_df,pd.DataFrame)and not prepped_prod_df.empty:
        prepped_prod_df = prepped_prod_df.drop(columns="Activity")
        backdating_purchases("Production",prepped_prod_df,expanded_prod_ledger_path)

        if isinstance(purch_activity_update,pd.DataFrame) and not purch_activity_update.empty:
            purch_activity_update.to_csv(purch_ledger_path, header=True, index=False,date_format='%Y-%m-%dT%H:%M:%S')

        if isinstance(production_lots, pd.DataFrame) and not production_lots.empty:
            production_lots.to_csv(production_lots_path, header = True, index=False, date_format='%Y-%m-%dT%H:%M:%S')

    
