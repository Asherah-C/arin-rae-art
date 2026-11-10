import pandas as pd
import duckdb
import os
import zipfile
import glob

from transforms import append_to_inv, transform_raw_sales, transform_inv, transform_purchase, transform_production, create_current_from_inv, current_inv_enrichment, backdating_sales_events, transform_events, backdating_purchases, transform_sales_by_lot_df
from calculations import expand_production_df, calc_current_from_purch, update_current_from_prod, unique_dates, calc_sales_df, calc_curr_from_sales, calc_cannibalism, calc_inventory

### ----------- ARGS Quick Reference -----------
#    expanded_prod_ledger_path = args.expanded_production 
#    inv_history_path = args.inv_history
#    purch_ledger_path = args.purchases_output
#    events_sales_path = args.sales_output
#    events_path = args.events
#    current_inventory_path = args.current_inv
#    master_table_output = args.master_table_output
#    production_lots_path = args.prod_lots_output
#    cannibal_input_path = args.cannibal_input
#    spot_check_input = args.spot_check_input

#    spot_check_output = args.spot_check_output
#    master_table_path = args.master_item
#    stock_levels_path = args.stock_levels
#    stock_exceptions_path = args.stock_exceptions
#    inv_path = args.inventory_path
#    purchase_path = args.purchases_source
#    production_ledger_path = args.production_path
#    bill_of_mats = args.bill_of_mats
#    raw_sales_path = args.sales_source
#    image_dir = args.image_dir
#    cannibal_ledger_out_path = args.cannibal_ledger_output
# ------------------------------------------------


# Step 1: Create a dataset of all activities that need to be appended to relevant ledger 
def find_unprocessed_data(args) -> list[pd.Timestamp, pd.Timestamp, dict]:
    # Output Data
    expanded_prod_ledger_path = args.expanded_production 
    inv_history_path = args.inv_history
    purch_ledger_path = args.purchases_output
    events_sales_path = args.sales_output
    current_inventory_path = args.current_inv
    image_dir = args.image_dir
    cannibal_ledger_output = args.cannibal_ledger_output
    spot_check_output = args.spot_check_output

    # Raw Data
    #   inv_path = args.inventory_path
    purchase_path = args.purchases_source
    production_ledger_path = args.production_path
    raw_sales_path = args.sales_source
    cannibal_input_path = args.cannibal_input
    spot_check_input = args.spot_check_input

    #Step 1.1 - Pull DataFrames
    expanded_production_df = pd.read_csv(expanded_prod_ledger_path)
    inv_history_df = pd.read_csv(inv_history_path,dtype={'Run_ID': 'int64'})
    purchase_ledger_df = pd.read_csv(purch_ledger_path)
    events_sales_df = pd.read_csv(events_sales_path)
    current_inv_df = pd.read_csv(current_inventory_path)
    cannibal_ledger_output_df = pd.read_csv(cannibal_ledger_output)
    spot_check_output_df = pd.read_csv(spot_check_output)

    raw_spot_check_input_df = pd.read_csv(spot_check_input)
    raw_cannibal_input_df = pd.read_csv(cannibal_input_path)
    #   raw_inv_df = pd.read_csv(inv_path)
    raw_purch_df = pd.read_csv(purchase_path)
    raw_prod_df = pd.read_csv(production_ledger_path)
    raw_sales_df = pd.read_csv(raw_sales_path)

    #Set Date Format correctly
    raw_sales_df["Date of Sales"]= pd.to_datetime(raw_sales_df["Date of Sales"].astype(str).str.strip(), format='%m/%d/%Y')
    #   raw_inv_df["Date of Inventory"]= pd.to_datetime(raw_inv_df["Date of Inventory"].astype(str).str.strip(), format='%m/%d/%Y')
    raw_spot_check_input_df["Date of Inventory"]= pd.to_datetime(raw_spot_check_input_df["Date of Inventory"].astype(str).str.strip(), format='%m/%d/%Y')
    raw_purch_df["Date of Purchase"]= pd.to_datetime(raw_purch_df["Date of Purchase"].astype(str).str.strip(), format='%m/%d/%Y')
    raw_prod_df["Date of Production"]= pd.to_datetime(raw_prod_df["Date of Production"].astype(str).str.strip(), format='%m/%d/%Y')
    raw_cannibal_input_df["Date of Cannibalization"]= pd.to_datetime(raw_cannibal_input_df["Date of Cannibalization"].astype(str).str.strip(), format='%m/%d/%Y')

    events_sales_df["Date of Sales"]= pd.to_datetime(events_sales_df["Date of Sales"].astype(str).str.strip(), format='ISO8601')
    inv_history_df["Date of Inventory"]= pd.to_datetime(inv_history_df["Date of Inventory"].astype(str).str.strip(), format='ISO8601')
    current_inv_df["Date of Inventory"]= pd.to_datetime(current_inv_df["Date of Inventory"].astype(str).str.strip(), format='ISO8601')
    purchase_ledger_df["Date of Purchase"]= pd.to_datetime(purchase_ledger_df["Date of Purchase"].astype(str).str.strip(), format='ISO8601')
    expanded_production_df["Date of Production"]= pd.to_datetime(expanded_production_df["Date of Production"].astype(str).str.strip(), format='ISO8601')
    cannibal_ledger_output_df["Date of Cannibalization"]= pd.to_datetime(cannibal_ledger_output_df["Date of Cannibalization"].astype(str).str.strip(), format='ISO8601')
    spot_check_output_df["Date of Inventory"]= pd.to_datetime(spot_check_output_df["Date of Inventory"].astype(str).str.strip(), format='ISO8601')

    #Step 1.2 Create dataframes of activity dates that exist in raw data but not in output data  | pulling the dataset direct from dates that are missing means i no longer have to guess about what dates are needed to be added
    #Step 1.2a Pull unique dates of Inventory History that have Hand Count Inventory Activities already processed
    processed_hand_count_inventory_dates = inv_history_df[inv_history_df["Inventory Activity"]=="Hand Count"]["Date of Inventory"].unique()
    processed_spot_check_dates = spot_check_output_df[spot_check_output_df["Inventory Activity"]=="Spot Inventory"]["Date of Inventory"].unique()

    #   missing_inventories_df = raw_inv_df[~raw_inv_df["Date of Inventory"].isin(processed_hand_count_inventory_dates)]
    missing_spot_checks_df = raw_spot_check_input_df[~raw_spot_check_input_df["Date of Inventory"].isin(processed_spot_check_dates)]
    missing_purchases_df = raw_purch_df[~raw_purch_df["Date of Purchase"].isin(purchase_ledger_df["Date of Purchase"])]
    missing_sales_df = raw_sales_df[~raw_sales_df["Date of Sales"].isin(events_sales_df["Date of Sales"])]
    missing_production_df = raw_prod_df[~raw_prod_df["Date of Production"].isin(expanded_production_df["Date of Production"])]
    missing_cannibalism_df = raw_cannibal_input_df[~raw_cannibal_input_df["Date of Cannibalization"].isin(cannibal_ledger_output_df["Date of Cannibalization"])]

    loaded_dict = {
        #   "Inventory": missing_inventories_df,
        "Spot Check": missing_spot_checks_df,
        "Purchase": missing_purchases_df,
        "Production": missing_production_df,
        "Cannibalization": missing_cannibalism_df,
        "Sales": missing_sales_df
    }

    # 1.2b: Exits out if here is no new data
    if all(df.empty for df in loaded_dict.values()):
            print("No new data. System is up to date. Exiting.")
            return

    # we're creating a dictionary of {Date:[activities-as-dataframes]} to quickly parse every activity to determine how to proceed; this combination also saves us trouble in trying to image each date-activity for backdating references
    date_activity_dict = {}

   #if not empty, pull date for each activity row missing in order to do activity by date
    for activity, dataframe in loaded_dict.items():
        if dataframe.empty:
            continue

        #parsed by date of individual date in the activity's row
        date_col = f"Date of {activity}"

        for date, date_activity_df in dataframe.groupby(date_col):
            if date not in date_activity_dict:
                date_activity_dict[date] = {}

            date_activity_dict[date][activity] = date_activity_df

    #if there are dates to process, find the earliest date to process
    if date_activity_dict:
        print(f"{date_activity_dict.keys()}")
        earliest_date_to_process = min(date_activity_dict.keys())
    else:
        "No data to process. Exiting program."
        return

    #Step 1.4 Determine if any inventory history data needs to be overwritten, process accordingly
    #helper function for the final step that is the same activity for both future conditions (backdated data vs current data only)
    def saving_files(args, activity_to_load_df: pd.DataFrame ,backdated_data :bool, activity_dict : dict, prepped_prod_df: pd.DataFrame, updated_purchase_lots_dict: dict, production_lots_append: pd.DataFrame, updated_prod_lots_dict: dict, cannibal_output: pd.DataFrame, prepped_sales_df: pd.DataFrame, date, activity):
      
        if not activity_to_load_df.empty:
            populate_inventory_history(args, activity_to_load_df, backdated_data)                                                   # This is no longer robust enough for complex work, as cannibalizism has unqiue + production activity; need to update (but it's working 95% now?? See dev notes for details)

        if not all(df.empty for df in loaded_dict.values()):
            if activity == "Spot Check":
                activity_dict["Spot Check"] = activity_to_load_df
            append_ledgers(args, activity, activity_dict, prepped_prod_df, updated_purchase_lots_dict, production_lots_append, updated_prod_lots_dict, cannibal_output, prepped_sales_df)
            image_run(args, date, activity)

        vars_to_clean = [
            'activity_to_load_df', 'updated_purchase_lots_dict', 'prepped_prod_df', 'changed_prod_df', 'production_lots_append', 'updated_prod_lots_dict', 'prepped_sales_df', 'cannibal_output'                
        ]
        for var_name in vars_to_clean:
            if var_name in locals():
                del locals()[var_name]
        
        # 2. Force Python's garbage collector to release the memory immediately
        import gc
        gc.collect()
            


    current_inv_date = pd.to_datetime(current_inv_df["Date of Inventory"]).max()
    priority_order = [
        #   "Inventory",
        "Spot Check",
        "Purchase",
        "Production",
        "Cannibalization",
        "Sales"
        ]

    #build a logic set that makes sure the incoming data is in chronolical to prior runs
    chronological_data = False
    if earliest_date_to_process > current_inv_date: # loop out fast if the date is newer than last run date
        chronological_data = True
    elif earliest_date_to_process == current_inv_date:
        for i in range(0, len(priority_order)): #we're going to find the highest priority activity in the dataset to load from the earliest date
            if priority_order[i] in date_activity_dict[earliest_date_to_process].keys():
                ref_activity = priority_order[i]
                break
        if ref_activity and ref_activity == "Inventory":
            chronological_data = False #if we are looking at the same day as current inventory, and we are trying to load an inventory dataset, we need to backdate instead.
        elif ref_activity is not None: # here, we need to determine if our data to load is higher in priority than the prior run daa, using our images to determing it. since wwe have current inventory on this date, we know for a fact there should be an associated zip file
            ref_date = earliest_date_to_process
            if isinstance(ref_date, (pd.Timestamp, pd.DatetimeTZDtype)):
                ref_date = ref_date.strftime('%Y-%m-%d')
            else:
                ref_date = str(ref_date).replace('/','-')
            

            priority_map = {act: idx for idx,act in enumerate(priority_order)}
            target_priority_idx = priority_map.get(ref_activity, -1)

            best_activity = None
            max_priority = None
            search_pattern = os.path.join(image_dir, f"{ref_date} | *.zip")
            for zip_file in glob.glob(search_pattern):
                try:
                    base_name = os.path.basename(zip_file)
                    name_without_ext = base_name.replace(".zip","")
                    parts = name_without_ext.split(" | ") # a tuple of (date, activity)

                    if len(parts) == 2:
                        _, file_activity = parts[0], parts[1]
                        file_priority_idx  = priority_map.get(file_activity,-1)

                        if file_priority_idx != -1: # so long as the file isn't a weird name, check it out to compare
                            if file_priority_idx <= target_priority_idx:
                                if max_priority is None or file_priority_idx > max_priority:
                                    max_priority = file_priority_idx
                                    best_activity = file_activity
                except Exception:
                    pass
            if best_activity is None:  # should only happen on an error of the above
                chronological_data = True
            else:
                best_activity_idx = priority_map.get(best_activity,-1)
                if best_activity_idx < target_priority_idx:
                    chronological_data = True
                else:
                    chronological_data = False
        else:
            chronological_data = False
    else:
        chronological_data = False

    if chronological_data:
        # all data falls after the last performed run, we can just append new data       
        backdated_data = False
        for date in sorted(date_activity_dict.keys()):
            activities_by_date = date_activity_dict[date]
            for activity in priority_order:
                if activity in activities_by_date.keys():
                    df_to_load = {}
                    df_to_load[activity] = date_activity_dict[date][activity]
                    activity_dict = df_to_load[activity]
                    print(loaded_dict)
                    print("======= Activity Dict =====")
                    print(activity_dict)

                    print(f"Running {activity} data for {date} in merge_raw_data_for processing....")
                    activity_to_load_df, updated_purchase_lots_dict, prepped_prod_df, production_lots_append, updated_prod_lots_dict, cannibal_output, prepped_sales_df = merge_raw_data_for_processing(args,df_to_load)                         #   Need output df for cannibalization here

                    saving_files(args, activity_to_load_df, backdated_data, activity_dict, prepped_prod_df, updated_purchase_lots_dict, production_lots_append, updated_prod_lots_dict, cannibal_output, prepped_sales_df, date, activity)        #   Need above output as input here


    if not chronological_data:
        # some data falls earlier than last run, so we need to rewrite inventory histry ledger for all activities on and after the earliest date
             
        #first step is to set the absolute latest parameter we will look for in the image directory.
        earliest_activities = date_activity_dict[earliest_date_to_process]
        image_date = earliest_date_to_process
        image_activity = next((act for act in priority_order if act in earliest_activities), None)
        for i in range(0, len(priority_order)):
            if priority_order[i] in earliest_activities.keys():
                if i > 0:
                    # if it's not an inventory, we go hunting for the next higher priority activity
                    image_date = earliest_date_to_process
                    image_activity = priority_order[i-1]
                else:
                    # if it was an inventory, our most late target must be Yesterday's Sales
                    image_date = earliest_date_to_process - pd.Timedelta(days=1)
                    image_activity = "Sales"
                break

        if isinstance(image_date, (pd.Timestamp, pd.DatetimeTZDtype)):
            image_date = image_date.strftime('%Y-%m-%d')
        else:
            image_date = str(image_date).replace('/','-')

        possible_zip_path = f"{image_date} | {image_activity}.zip"
        possible_zip_path = os.path.join(image_dir,possible_zip_path)

        #if it exists, overwrite all output data with the image
        if os.path.exists(possible_zip_path):
            with zipfile.ZipFile(possible_zip_path, "r") as zip_ref:
                zip_ref.extractall()
        else:
            # need to go searching for the most recent image that exists before the possible zip file
            priority_map = {act: idx for idx,act in enumerate(priority_order)}
            target_date_dt = pd.to_datetime(image_date)
            target_priority_idx = priority_map.get(image_activity, -1)

            best_zip_path = None
            max_checkpoint_tuple = None
            search_pattern = os.path.join(image_dir, "* | *.zip")
            for zip_file in glob.glob(search_pattern):
                try:
                    base_name = os.path.basename(zip_file)
                    name_without_ext = base_name.replace(".zip","")
                    parts = name_without_ext.split(" | ") # a tuple of (date, activity)

                    if len(parts) == 2:
                        file_date_str, file_activity = parts[0], parts[1]
                        file_date_dt = pd.to_datetime(file_date_str)
                        file_priority_idx  = priority_map.get(file_activity,-1)

                        if file_priority_idx != -1: # so long as the file isn't a weird name, check it out to compare
                            checkpoint_tuple = (file_date_dt,file_priority_idx)
                            if checkpoint_tuple <= (target_date_dt, target_priority_idx):
                                if max_checkpoint_tuple is None or checkpoint_tuple > max_checkpoint_tuple:
                                    max_checkpoint_tuple = checkpoint_tuple
                                    best_zip_path = zip_file
                except:
                    continue
            if best_zip_path and os.path.exists(best_zip_path):
                with zipfile.ZipFile(best_zip_path, "r") as zip_ref:
                    zip_ref.extractall()
         
        # 1. Explicitly delete the local DataFrame references holding stale data
        vars_to_clean = [                                                                                   #   Need to define cannibalization variables and then load them here for cleaning too!
            'current_inv_df', 'inv_history_df', 'raw_sales_df', 'raw_prod_df', 
            'raw_purch_df', 'raw_inv_df', 'loaded_dict', 'earliest_activities', 
            'date_activity_dict', 'missing_inventories_df', 'missing_purchases_df', 
            'missing_sales_df', 'missing_production_df'
        ]
        for var_name in vars_to_clean:
            if var_name in locals():
                del locals()[var_name]
        
        # 2. Force Python's garbage collector to release the memory immediately
        import gc
        gc.collect()
        
        # 3. Trigger recursion (make sure your function is designed to re-load from disk at the start!)
        return find_unprocessed_data(args)

        
# Pull dataframes of all relevant data, convert into single table to analyze
def merge_raw_data_for_processing(args, loaded_dict: dict[str:pd.DataFrame]) -> tuple[pd.DataFrame, dict, pd.DataFrame, pd.DataFrame, dict, pd.DataFrame]:

    bill_of_mats = args.bill_of_mats
    expanded_prod_ledger_path = args.expanded_production
    purch_ledger_path = args.purchases_output
    master_table_path = args.master_table_output
    bill_of_mats_df = pd.read_csv(bill_of_mats)
    master_table_df = pd.read_csv(master_table_path)
    # Loop over the dictionary and pull the dataframe out, append to a new list
    prepped_dfs = []
    prepped_prod_df = pd.DataFrame()
    production_lots_append = pd.DataFrame()
    prepped_sales_df= pd.DataFrame()
    updated_purchase_lots_dict = {}
    updated_prod_lots_dict = {}

    for activity, raw_df in loaded_dict.items():
        if raw_df.empty:
            # print(f"No {activity} data to process. Skipping....")
            continue

        print(f"Working on {activity} data...")

    
    # Step 2.2a: transform Inventory Data
        # if activity == "Inventory":
        #     prepped = transform_inv(raw_df)                                                     #   Only Needed for Full Inventories (pivoted data)
        #     prepped["Activity"] = " Full Inventory"
        #     prepped = prepped.rename(columns={"Qty in Stock":"Qty","Date of Inventory":"Date"})
        #     print(f"{len(prepped)} rows of Hand Count Inventory Data prepared for load.")
        #     # print(prepped)

    # Step 2.2b: transform Spot Checks
        if activity == "Spot Check":
            prepped, updated_purchase_lots_dict, updated_prod_lots_dict = calc_inventory(args, raw_df)
            prepped["Activity"] = "Spot Inventory"
            prepped = prepped.rename(columns={"Qty in Stock":"Qty","Date of Inventory":"Date"})
            print(f"{len(prepped)} rows of Hand Count Inventory Data prepared for load.")

    # Step 2.2c: transform Purchase Data
        elif activity == "Purchase":
            prepped = transform_purchase(raw_df)
            prepped["Activity"] = "Purchase"
            prepped = prepped.rename(columns={"Quantity Bought":"Qty","Date of Purchase":"Date"})
            print(f"{len(prepped)} rows of {activity} Data prepared for load.")
            # print(prepped)

    # Step 2.2d: transform Production Data
        elif activity == "Production":
            purch_ledger_df = pd.read_csv(purch_ledger_path)
            compressed_prod = transform_production(raw_df)
            expanded_prod_df = pd.read_csv(expanded_prod_ledger_path)
            next_batch_num = 1 if expanded_prod_df.empty else int(expanded_prod_df["Batch_ID"].max()) + 1
            updated_purchase_lots_dict, prepped, production_lots_append = expand_production_df(bill_of_mats_df,compressed_prod,expanded_prod_df,purch_ledger_df,next_batch_num)

            prepped["Activity"] = "Production"
            prepped = prepped.rename(columns={"Qty Delta":"Qty","Date of Production":"Date"})
            prepped_prod_df = prepped.copy()
            print(f"{len(prepped)} rows of {activity} Data prepared for load:")
            # print(prepped_prod_df)

    # Step 2.2e: transform Cannibalism Data
        elif activity == "Cannibalization":
            cannibal_output, prepped, updated_purchase_lots_dict, production_lots_append, updated_prod_lots_dict = calc_cannibalism(args,raw_df)
            prepped["Activity"] = "Cannibalization"
            prepped_prod_df = prepped.copy()
            prepped = prepped.rename(columns={"Qty Delta":"Qty","Date of Production":"Date"})
            print(f"{len(prepped)} rows of {activity} Data prepared for load:")


    # Step 2.2f: transform Sales Data
        elif activity == "Sales":
            purch_ledger_df = pd.read_csv(purch_ledger_path)
            prepped= transform_raw_sales(raw_df, master_table_df)
           
            events_sales_path = args.sales_output
            sales_history_df = pd.read_csv(events_sales_path)
            next_sales_ID = max(sales_history_df["Sales_ID"], default=0)+1

            production_lots_path = args.prod_lots_output
            updated_production_lots = pd.read_csv(production_lots_path)

            #Process Sales by item, assigning lots to each item sold
            prepped, updated_purchase_lots_dict, updated_prod_lots_dict = calc_sales_df(next_sales_ID,prepped,purch_ledger_df,updated_production_lots,sales_history_df)

            # print(prepped)
            prepped_sales_df = prepped.copy()
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
        if isinstance(prepped_prod_df, pd.DataFrame) and not prepped_prod_df.empty:
            prepped_prod_df["Timestamp"] = pd.to_datetime(prepped_prod_df["Timestamp"], format="mixed", utc=True, errors="coerce").dt.tz_localize(None)

    
    return activity_df, updated_purchase_lots_dict, prepped_prod_df, production_lots_append, updated_prod_lots_dict, cannibal_output, prepped_sales_df

# Run each Date through the Current Inventory and create a inventory log based on the activity type; this populates the inventory ledger for all data after the initialized current inventory date
def populate_inventory_history(args, activity_ledger: pd.DataFrame, backdated_data: bool):
    inv_history_path = args.inv_history
    current_inventory_path = args.current_inv
    master_table_path = args.master_item
    stock_levels_path = args.stock_levels
    stock_exceptions_path = args.stock_exceptions

    activity_order = ["Inventory","Spot Check", "Purchase","Production", "Cannibalization","Sales"]

    #Create a List of Dates to Parse over from the full activity log
    all_dates = unique_dates("Processing",activity_ledger)
    all_dates["Date"] = pd.to_datetime(all_dates["Date"])

    inventory_initialization_date = pd.to_datetime("2024-12-31")
    valid_dates = all_dates[all_dates["Date"] > inventory_initialization_date]
    
    activity_ledger["Date"] = pd.to_datetime(activity_ledger["Date"])
    current_inventory = pd.read_csv(current_inventory_path)

    #Guards against Column errors
    for col in ["Purchase_ID", "Batch_ID"]:
        if col not in activity_ledger.columns:
            activity_ledger[col] = pd.NA

    #Iterate over every date in the dates dataframe (i.e., unique dates from the activity ledger that fall after the initialization of the inventory)
    for unique_date in valid_dates["Date"]:
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
            # if activity == "Inventory":
            #     activity_df = activity_df.rename(columns={"Qty":"Qty in Stock","Date": "Date of Inventory"})
            #     activity_df["Inventory Activity"] = "Full Inventory"
            #     curr_inv = create_current_from_inv (activity_df)                                            #   Only Valid for full inventory
            #     current_inventory = current_inv_enrichment(curr_inv, master_table_path)

            #     append_to_inv(inv_history_path,current_inventory)

            if activity == "Spot Check":
                activity_df = activity_df.rename(columns={"Qty":"Qty in Stock","Date": "Date of Inventory"})
                current_inventory = activity_df.copy()
                append_to_inv(inv_history_path,current_inventory)

            elif activity == "Purchase":
                activity_df = activity_df.rename(columns={"Qty":"Quantity Bought","Date": "Date of Purchase"})

                curr_inv = calc_current_from_purch(activity_df,current_inventory)
                current_inventory = current_inv_enrichment(curr_inv, master_table_path)

                append_to_inv(inv_history_path,current_inventory)
            elif activity == "Production":
                activity_df = activity_df.rename(columns={"Qty":"Qty Delta","Date": "Date of Production"})
                curr_inv = update_current_from_prod(activity_df,current_inventory)
                current_inventory = current_inv_enrichment(curr_inv, master_table_path)

                append_to_inv(inv_history_path,current_inventory)
            elif activity == "Cannibalization":                                                                         #   2 Options: Cannibalism is unique vs Cannibalism is special form of production. If production, we just need to ensure output shape aligns with input into production-> curr inv
                activity_df = activity_df.rename(columns={"Qty":"Qty Delta","Date": "Date of Production"})             #   Shape Changes? Or do we push the expanded_production

                curr_inv =  update_current_from_prod(activity_df,current_inventory)
                current_inventory = current_inv_enrichment(curr_inv,master_table_path)
                append_to_inv(inv_history_path, current_inventory)  
            elif activity == "Sales":
                activity_df = activity_df.rename(columns={"Qty":"Qty Sold","Date": "Date of Sales"})
                curr_inv = calc_curr_from_sales(activity_df,current_inventory)
                current_inventory = current_inv_enrichment(curr_inv, master_table_path)

                append_to_inv(inv_history_path,current_inventory)
            else:
                print(f"{activity} Not Recognized. Skipping....")

    
    current_inventory.to_csv(current_inventory_path, header= True, index= False, date_format='%Y-%m-%dT%H:%M:%S')
    print(f"{current_inventory_path} overwitten with current data. {len(current_inventory)} rows saved.")

# Populate the Power-BI ledgers with data
def append_ledgers(args, activity, activity_dict, prepped_prod_df: pd.DataFrame, updated_purchase_lots_dict: dict, production_lots: pd.DataFrame, updated_prod_lots_dict: dict,cannibalism_to_output: pd.DataFrame, prepped_sales_df: pd.DataFrame):
    
    expanded_prod_ledger_path = args.expanded_production 
    purch_ledger_path = args.purchases_output
    events_sales_path = args.sales_output
    events_path = args.events
    bill_of_mats = args.bill_of_mats
    master_table_path = args.master_table_output
    production_lots_path = args.prod_lots_output
    cannibalism_ledger_out_path = args.cannibal_ledger_output

    def change_lot_status(args, file_type: str, updated_lots_dict: dict):
        if file_type == "Production":
            path = args.prod_lots_output
            col_name = "Batch_ID"
        elif file_type == "Purchase":
            path = args.purchases_output
            col_name = "Purchase_ID"
        else:
            print("ERROR: dictionary type not recognized. Cannot parse into correct file.")
            print(f"{file_type} dictionary not recognized. Must be either a production or purchase lots dictionary.")
            raise ValueError

        ledger = pd.read_csv(path)
        ledger[col_name] = pd.to_numeric(ledger[col_name], errors='coerce')
        if "Timestamp" in ledger.columns:
            ledger["Timestamp"] = pd.to_datetime(ledger["Timestamp"], errors='coerce')

        mask = ledger[col_name].isin(updated_lots_dict.keys())
        ledger.loc[mask, "Status"] = ledger.loc[mask, col_name].map(updated_lots_dict)
        ledger.loc[mask, "Timestamp"] = pd.Timestamp.now()

        ledger.to_csv(path, header = True, index=False, date_format='%Y-%m-%dT%H:%M:%S', mode='w')

    def run_production_changes(args, prepped_prod_df: pd.DataFrame, production_lots: pd.DataFrame, updated_purchase_lots_dict: dict):
        if isinstance(prepped_prod_df,pd.DataFrame)and not prepped_prod_df.empty:
            prepped_prod_df = prepped_prod_df.drop(columns="Activity")
            backdating_purchases(activity,prepped_prod_df,expanded_prod_ledger_path)

            #When we run production, we need to append the new lots to the current production lots file
            if isinstance(production_lots, pd.DataFrame) and not production_lots.empty:
                production_lots.to_csv(production_lots_path, header = False, index=False, date_format='%Y-%m-%dT%H:%M:%S', mode='a')

            # finally, we update purchase lots with an over write, if needed
            if updated_purchase_lots_dict:
                change_lot_status(args,"Purchase", updated_purchase_lots_dict)

    if activity == "Purchase":
        raw_purch_to_append = activity_dict
        if isinstance(raw_purch_to_append,pd.DataFrame) and not raw_purch_to_append.empty:
            purchases = transform_purchase(raw_purch_to_append)
            backdating_purchases("Purchase",purchases,purch_ledger_path)

    if activity == "Production":
        #4.4 Populate the expanded production ledger; automatically handles production side of cannibalism, less the cannibalism output itself
        run_production_changes(args, prepped_prod_df, production_lots, updated_purchase_lots_dict)

    if activity == "Cannibalization":

        #   for cannibalism, do we need to append AND write, strictly write, or just append. We have changed production statuses (new function) AND added new rows in production (like in production), and need to change statuses in purchases (like in sales)
        if isinstance(cannibalism_to_output,pd.DataFrame) and not cannibalism_to_output.empty:
            # Step 1 Append the Cannibalism Ledger
            cannibalism_to_output.to_csv(cannibalism_ledger_out_path, header = False, index=False, date_format='%Y-%m-%dT%H:%M:%S', mode='a')

            #Step 2: Write the production changes we performed; This appends new lines to production and updates/overwrites purchase lots as needed
            run_production_changes(args, prepped_prod_df, production_lots, updated_purchase_lots_dict)

            # Step 3 handle cannibalism of production lots explicitly
            if updated_prod_lots_dict:
                change_lot_status(args, "Production", updated_prod_lots_dict)
    
    if activity == "Sales":
        if isinstance(prepped_sales_df,pd.DataFrame) and not prepped_sales_df.empty:
                sales = transform_sales_by_lot_df(prepped_sales_df)
                events = transform_events(activity_dict)
        
                #I believe these are broken now....
                dates_df = unique_dates("Sales", sales)
        
                backdating_sales_events("Sales",dates_df, sales, events_sales_path)                                 # appends
                backdating_sales_events("Events",dates_df, events, events_path)                                     # appends

                if updated_purchase_lots_dict:
                    change_lot_status(args,"Purchase",updated_purchase_lots_dict)

                if updated_prod_lots_dict:
                    change_lot_status(args,"Production", updated_prod_lots_dict)
            

    # When/how to update?
    bill_of_mats_df = pd.read_csv(bill_of_mats)
    master_table_df = pd.read_csv(master_table_path)

def image_run(args,date: str,activity: str):
    expanded_prod_ledger_path = args.expanded_production 
    inv_history_path = args.inv_history
    purch_ledger_path = args.purchases_output
    events_sales_path = args.sales_output
    events_path = args.events
    current_inventory_path = args.current_inv
    master_table_output = args.master_table_output
    production_lots_path = args.prod_lots_output
    cannibalism_ledger_out_path = args.cannibal_ledger_output
    image_dir = args.image_dir

    file_list = (expanded_prod_ledger_path, inv_history_path, purch_ledger_path,events_sales_path, events_path, current_inventory_path, master_table_output,production_lots_path, cannibalism_ledger_out_path)
    
    if isinstance(date, (pd.Timestamp, pd.DatetimeTZDtype)):
        date_str = date.strftime('%Y-%m-%d')
    else:
        date_str = str(date).replace('/','-')

    zip_filename = f"{date_str} | {activity}.zip"

    zip_filename = os.path.join(image_dir,zip_filename)
    
    with zipfile.ZipFile(zip_filename, "w", compression=zipfile.ZIP_DEFLATED) as zip_ref:
        for file in file_list:
            if os.path.exists(file):               
                zip_ref.write(file)
            else:
                print(f"Error: Output file ///{file}/// does not exist. Skipping.")

