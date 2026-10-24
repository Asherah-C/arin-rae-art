import pandas as pd
import duckdb
#from transforms import backdating_purchases

def prod_table_ref(path:str) -> pd.DataFrame:
    prod_table_df = pd.read_csv(path)

    bill_of_mats_df = (prod_table_df.melt(
        id_vars=['Subcategory'], 
        var_name='Component_Type', 
        value_name='Component_Item'
    ).dropna(subset=['Component_Item']).reset_index(drop=True))

    bill_of_mats_df['Component_Item'] = bill_of_mats_df['Component_Item'].str.strip()

    return bill_of_mats_df

def prod_ref(path:str) -> pd.DataFrame:
    prod_df = pd.read_csv(path)

    return prod_df

def current_inv_ref (path:str) -> tuple[pd.DataFrame,pd.Timestamp]:
    current_inv_df = pd.read_csv(path)
    if current_inv_df["Date of Inventory"].notna().any():
        current_inv_date = pd.to_datetime(current_inv_df["Date of Inventory"]).max()
    else:
        current_inv_date = pd.Timestamp.min

    return current_inv_df, current_inv_date

def update_current_from_prod(prod_df: pd.DataFrame,current_df: pd.DataFrame) ->pd.DataFrame:

    # need to add logic to test if current inventtory was a hand count, if hand count, append only dates after inventory, else, append all dates since last and count (unsure if still needed)
    prod_df_temp = prod_df.copy()
    prod_df_temp["Date_dt"] = pd.to_datetime(prod_df_temp["Date of Production"])
    latest_prod_date = prod_df_temp["Date_dt"].max()

    current_df_temp = current_df.copy()
    current_df_temp["Date_dt"] = pd.to_datetime(current_df_temp["Date of Inventory"])

    # Add Purchase_ID and Batch_IDs to merge data with item


    # group purchased items on purchase_ID, made items on batch_id
    # purchase items have to have a purchase_id (purchased items may also have a batch_id, if they are an input for a final product, but stickers won't, so batch_id is useless here)
    purchased_items = prod_df_temp[prod_df_temp["Purchase_ID"].notna() & (prod_df_temp["Purchase_ID"] !="")]
    purchased_items_group = purchased_items.groupby(["Date of Production", "Inventory Activity", "Item", "Purchase_ID", "Cost"], as_index=False, dropna=False)["Qty Delta"].sum()
    purchased_items_group["Inventory Activity"]

    #made items won't have data in purchase_id and also will have data in batch_id
    made_items = prod_df_temp[(prod_df_temp["Purchase_ID"].isna() | (prod_df_temp["Purchase_ID"] =="")) & (prod_df_temp["Batch_ID"].notna()) & (prod_df_temp["Batch_ID"] !="")]
    made_items_group = made_items.groupby(["Date of Production", "Inventory Activity", "Item", "Batch_ID", "Cost"], as_index=False, dropna=False)["Qty Delta"].sum()
    made_items_group["Inventory Activity"] = "Production"


    prod_summed_df = pd.concat([purchased_items_group,made_items_group],ignore_index=True)

    #Set Timestamp Column to max of original data and fill in any activity blanks with Production
    prod_summed_df["Timestamp"] = prod_df_temp["Timestamp"].max()
    prod_summed_df["Inventory Activity"] = prod_summed_df["Inventory Activity"].fillna("Production")
    prod_summed_df["Purchase_ID"] = pd.to_numeric(prod_summed_df["Purchase_ID"], errors='coerce').astype('Int64')
    prod_summed_df["Batch_ID"] = pd.to_numeric(prod_summed_df["Batch_ID"], errors='coerce').astype('Int64')


    #fill current inventory NAs for merge
    current_df_temp["Purchase_ID"] = pd.to_numeric(current_df_temp["Purchase_ID"], errors='coerce').astype('Int64')
    current_df_temp["Batch_ID"] = pd.to_numeric(current_df_temp["Batch_ID"], errors='coerce').astype('Int64')


    #merge them with current inventory, avoid duplicate column ames with suffixes
    merged_inv = pd.merge(current_df_temp , prod_summed_df, on = ["Item","Purchase_ID","Batch_ID"], how = "outer", suffixes=("_curr","_prod"))

    # update quantity    
    merged_inv["Qty Delta"] = merged_inv["Qty Delta"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"] + merged_inv["Qty Delta"]

    #merge the costs and timestamps into appropriate columns, using production data as base and fill in blanks with last current inv
    merged_inv["Timestamp"] =  merged_inv["Timestamp_prod"].fillna(merged_inv["Timestamp_curr"])
    merged_inv["Cost"] = merged_inv["Cost_prod"].fillna(merged_inv["Cost_curr"])
    merged_inv["Inventory Activity"] = merged_inv["Inventory Activity_prod"].fillna(merged_inv["Inventory Activity_curr"])
    merged_inv["Cost"] = pd.to_numeric(merged_inv["Cost"], errors='coerce').round(2)

    merged_inv["Purchase_ID"] = merged_inv["Purchase_ID"].replace("", pd.NA)
    merged_inv["Batch_ID"] = merged_inv["Batch_ID"].replace("", pd.NA)
    merged_inv["Date of Inventory"] = latest_prod_date
    # merged_inv["Inventory Activity"] = "Production"  # consider eliminating this line to get a more granular/accurate view of what was touched in every day on the inventory history and current inventory

    return merged_inv[[
        "Timestamp",
        "Date of Inventory",
        "Inventory Activity",
        "Item",
        "Purchase_ID",
        "Batch_ID",
        "Qty in Stock",
        "Cost"
    ]]

def calc_current_from_purch(purch:pd.DataFrame, curr_inv:pd.DataFrame) -> pd.DataFrame:
    purch_df = purch.copy()
    curr_df = curr_inv.copy()
    purch_df["Date_dt"] = pd.to_datetime(purch_df["Date of Purchase"])
    current_inv_date = pd.to_datetime(curr_df["Date of Inventory"]).max()
    unprocessed = purch_df[purch_df["Date_dt"] >= current_inv_date].copy()
    if "Timestamp" in curr_df.columns:
        curr_df["Timestamp"] = pd.to_datetime(curr_df["Timestamp"], format="mixed", utc=True, errors="coerce").dt.tz_localize(None)
    if "Timestamp" in unprocessed.columns:
            unprocessed["Timestamp"] = pd.to_datetime(unprocessed["Timestamp"], format="mixed", utc=True, errors="coerce").dt.tz_localize(None)

    # print("curr_inv:")
    # print(curr_df)

    latest_purch_date = unprocessed["Date_dt"].max()

    # Sum on Purchase_ID to maintaian distinct costs, needs to pull every column needed in aggregation. It's gonna be given the Date and make the location
    purch_summed_df = unprocessed.groupby(["Timestamp","Purchase_ID", "Item", "Cost"], as_index=False)["Quantity Bought"].sum()
    # print("purch_summed")
    # print(purch_summed_df)
    #because purchase_IDs will be unique, we want both what current inventory has and what we have.
    
    curr_df["Cost"] = pd.to_numeric(curr_df["Cost"], errors="coerce")
    curr_df["Purchase_ID"]  = pd.to_numeric(curr_df["Purchase_ID"], errors='coerce')
    purch_summed_df["Cost"] = pd.to_numeric(purch_summed_df["Cost"], errors='coerce')
    purch_summed_df["Purchase_ID"] = pd.to_numeric(purch_summed_df["Purchase_ID"], errors='coerce')
    
    merged_inv = pd.merge(curr_inv , purch_summed_df, on = ["Purchase_ID", "Item", "Cost"], how = "outer", suffixes=("_curr","_purch"))

    #fill batch_ids on the merge with NA for the purchased rows, since they don't get one:
    if "Batch_ID" not in merged_inv.columns:
        merged_inv["Batch_ID"]= pd.NA

    #update quantities
    merged_inv["Quantity Bought"] = merged_inv["Quantity Bought"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"] + merged_inv["Quantity Bought"]

    merged_inv["Date of Inventory"] = latest_purch_date
    merged_inv["Inventory Activity"] = "Purchase"

    merged_inv["Timestamp"] = merged_inv["Timestamp_purch"].fillna(merged_inv["Timestamp_curr"])

    return merged_inv[[
        "Timestamp",
        "Date of Inventory",
        "Inventory Activity",
        "Item",
        "Purchase_ID",
        "Batch_ID",
        "Qty in Stock",
        "Cost"
    ]]

#Pulls unique dates from a date column, based on the correct ledger type, possibly obsolete?
def unique_dates(ledger_type:str, dataframe: pd.DataFrame) ->pd.DataFrame:
    if ledger_type == "Sales":
        date_col = "Date of Sales"
    elif ledger_type == "Inventory":
        date_col = "Date of Inventory"
    elif ledger_type == "Purchase":
        date_col = "Date of Purchase"
    elif ledger_type == "Production":
        date_col = "Date of Production"
    elif ledger_type in ["Initialization","Processing"]:
        date_col = "Date"
    else:
        print("Unrecognized ledger_type: Returning None.")
        return None

    raw_data = dataframe.copy()
    dates_query = f"""
    SELECT
        DISTINCT "{date_col}"
    FROM raw_data
    ORDER BY "{date_col}" ASC
    """
    dates_df = duckdb.query(dates_query).df()

    return dates_df

def expand_production_df(bill_of_mats_df: pd.DataFrame, unprocessed_df: pd.DataFrame, expanded_prod_df: pd.DataFrame, lots: pd.DataFrame, batch_start_num: int) -> tuple[pd.DataFrame,pd.DataFrame,pd.DataFrame]:
    new_ledger = unprocessed_df.copy()

    new_ledger["Qty Delta"] = pd.to_numeric(new_ledger["Qty Delta"], errors="coerce").fillna(0)

    # Step 1: Separate rows, add batch IDs
    single_units = new_ledger.loc[new_ledger.index.repeat(new_ledger["Qty Delta"])].reset_index(drop=True)
    single_units["Qty Delta"] = 1
    single_units["Batch_ID"] = range (batch_start_num, batch_start_num + len(single_units))

    # Builds a pivoted table of materials for each line of production
    components_consumed = single_units.merge(bill_of_mats_df, on="Subcategory",how="inner")

    #Unpivot the table on components for each item in production, then remove NaN lines
    component_cols = ["Backboard Size","Plastic Sleeve Size","Matting Size","Frame Size"]
    existing_col = [c for c in component_cols if c in components_consumed.columns]

    components_consumed = components_consumed.melt(
        id_vars=["Timestamp","Date of Production","Batch_ID","Item","Subcategory","Qty Delta"],
        value_vars=existing_col,
        var_name="Component_Type",
        value_name="Component_Item"
    ).dropna(subset=["Component_Item"])

    #Rebuild as a component only ledger
    components_df = pd.DataFrame({
        "Timestamp": components_consumed["Timestamp"],
        "Date of Production": components_consumed["Date of Production"],
        "Batch_ID": components_consumed["Batch_ID"],
        "Item": components_consumed["Component_Item"],
        "Qty Delta": -1,
        "Type": "Consumption"
    })

    #build the art prints component to be consumed based on the original dataframe
    single_units["Print_Suffix"] = single_units["Subcategory"].apply(
        lambda x: "-CSto" if str(x).strip().lower().startswith("card") else "-Prin"
        )

    single_units["Print_Item"] = single_units["Style"].astype(str).str.strip() + single_units["Print_Suffix"]

    art_df = pd.DataFrame({
        "Timestamp": single_units["Timestamp"],
        "Date of Production": single_units["Date of Production"],
        "Batch_ID": single_units["Batch_ID"],
        "Item": single_units["Print_Item"],
        "Qty Delta": -1,
        "Type": "Consumption"
    })

    raw_mats_df = pd.concat([components_df,art_df],ignore_index=True)
    #pull active lots from output purchase ledger
    # print("Printing lots from purchases:")
    # print(lots)
    
    active_lots_df = lots[lots["Status"]=="Active"].copy() #what we have purchased for use with active lots

    print("PRINTING ACTIVE LOTS:")
    print(active_lots_df)
    active_lots_df.to_csv("active_lots_df.csv", header=True, index=False,mode='w')
    active_lots_df["Purchase_ID"] = pd.to_numeric(active_lots_df["Purchase_ID"], errors='coerce').astype('Int64')

    production_log = expanded_prod_df.copy() #historical log of what we've made in the past
    active_lots_df["Purchase_ID"] = pd.to_numeric(active_lots_df["Purchase_ID"], errors='coerce').astype('Int64')
    
    lot_remaining_map  = active_lots_df.set_index("Purchase_ID")["Quantity Bought"].to_dict()
    if not production_log.empty:
        historical_totals = production_log.groupby("Purchase_ID")["Qty Delta"].sum().to_dict()
        for lot_id, delta in historical_totals.items():
            if lot_id in lot_remaining_map:
                lot_remaining_map[lot_id] += delta #delta will be a negative number, reducing the amount available based on prior consumption in production runs
    
    
    new_prod_list_dicts = []

    for _,row in raw_mats_df.iterrows():
        # identify the needed input
        item_needed = row["Item"]
        current_demand = abs(row["Qty Delta"]) #flipping the sign here to make it more understandbale

        print(f"Needed Item = {item_needed}")
        #create a backup point to rerun in case of errors
        while current_demand > 0:
            #restrict the search to only active lots of that item
            masked_lots = active_lots_df[(active_lots_df["Item"]==item_needed) & (active_lots_df["Status"] == "Active")].sort_values(by="Purchase_ID", ascending=True)
            print("Printing masked lots")
            print(masked_lots)
            #exit the loop if there are no active lots for the item
            if masked_lots.empty:
                    print(f"Input Material: {item_needed} is out of stock. Cannot complete production run.")
                    print(f"Exiting without saving...")
                    raise ValueError
            #identify the current FIFO active Lot
            lotID = masked_lots.iloc[0]["Purchase_ID"]

            # print("=====")
            # print(f"Working production against {lotID}")
            # print("=====")
            qty_remaining_in_lot = lot_remaining_map.get(lotID, 0)

            if qty_remaining_in_lot == 0: # if nothing remains in the lot, exhaust and repeat
                active_lots_df.loc[active_lots_df["Purchase_ID"] == lotID, "Status"] = "Exhausted"
                continue

            if qty_remaining_in_lot < 0: 
                print("=================================")
                print(f"Quantity Error reached: Lot_ID: {lotID} Item: {item_needed} has currently available qty: {qty_remaining_in_lot}.")
                active_lots_df.loc[active_lots_df["Purchase_ID"] == lotID, "Status"] = "Exhausted"
                print("=================================")
                continue
            
            units_to_take = min(current_demand,qty_remaining_in_lot) #pull up to the qty remaining from current lot for productio consumption

            row_dict = row.to_dict()
            row_dict["Purchase_ID"] = lotID
            row_dict["Cost"] = active_lots_df.loc[active_lots_df["Purchase_ID"] == lotID, "Price (each)"].iloc[0]
            row_dict["Qty Delta"] = -units_to_take

            new_prod_list_dicts.append(row_dict) #make a new dictionary of the consumption

            lot_remaining_map[lotID] -= units_to_take #declinate the saved state of quantity consumed

            if lot_remaining_map[lotID] == 0:
                active_lots_df.loc[active_lots_df["Purchase_ID"] == lotID, "Status"] = "Exhausted"
            
            current_demand -= units_to_take

            # past_consumed = production_log.loc[production_log["Purchase_ID"]== lotID,"Qty Delta"].sum() #comes as a negative number for consumption!


            # # print(f"Total Consumed before today: {past_consumed}")

            # #determine how many have already been used this run
            # run_consumed = 0
            # for run in new_prod_list_dicts:
            #     if run.get("Purchase_ID") == lotID:
            #         run_consumed += run["Qty Delta"] # a negative number
            # # print("=====")
            # # print(f"Total Consumed today: {run_consumed}")
            # # print("=====")
            
            # #calculate the remaining quantity of items left in the lot
            # qty_bought = masked_lots.loc[masked_lots["Purchase_ID"]==lotID,"Quantity Bought"].iloc[0]
            # current_consumed = row["Qty Delta"]  #also a negative number
            # qty_remaining = qty_bought + past_consumed + run_consumed + current_consumed

            # # print(f"Qty remaining {qty_remaining} for {lotID}")
            # #determine how to process:
            # if qty_remaining >= 0: # Current lot meets the demand
            #     if qty_remaining == 0: # Special case: last one in the lot, turn the lot to exhausted
            #         active_lots_df.loc[active_lots_df["Purchase_ID"] == lotID, "Status"] = "Exhausted"
            #     #append the consumption to the production_log
            #     row_dict = row.to_dict()
            #     row_dict["Purchase_ID"] = lotID
            #     row_dict["Cost"] = active_lots_df.loc[active_lots_df["Purchase_ID"]== lotID,"Price (each)"].iloc[0]

            #     new_prod_list_dicts.append(row_dict) #allows us to update quantity consumed by total in QTy Delta
            #     break
            # else:       #Special Case: the math says there isn't enough here to fill production (i.e. a single unit), the lot must be erroneously active; change and repeat loop
            #     active_lots_df.loc[active_lots_df["Purchase_ID"] == lotID, "Status"] = "Exhausted"


    if new_prod_list_dicts:
        new_production_log = pd.DataFrame(new_prod_list_dicts)

    # print("Printing active_los_df:")
    # print(active_lots_df)
    #make a status map of everything changed in production run
    status_map = active_lots_df.set_index("Purchase_ID")["Status"]

    # After running all of production, update statuses of the lots in the purchases ledger.
    updated_purchase_lots = lots.copy()
    updated_purchase_lots["Purchase_ID"] = pd.to_numeric(updated_purchase_lots["Purchase_ID"],errors='coerce')
    updated_purchase_lots["Status"] = updated_purchase_lots["Purchase_ID"].map(status_map).fillna(updated_purchase_lots["Status"])
                    
    finished_goods_df = pd.DataFrame({
        "Timestamp": single_units["Timestamp"],
        "Date of Production": single_units["Date of Production"],
        "Batch_ID": single_units["Batch_ID"],
        "Item": single_units["Item"],
        "Qty Delta": 1,
        "Type": "Production"
    })
    #prep production log for math because pandas doesn't like currency
    new_production_log["Cost"] = (new_production_log["Cost"].astype(str).str.replace(r"[$,]", "", regex=True))
    new_production_log["Cost"] = pd.to_numeric(new_production_log["Cost"], errors="coerce").fillna(0.0)

    # Calculate Cost of Good produced based on the production log, referencing the Batch_ID, append to log and to a new production lots df
    batch_costs = new_production_log.groupby("Batch_ID")["Cost"].sum().round(2)
    finished_goods_df["Purchase_ID"] = pd.NA #needs to be blank, but an existing column for dataframe concate
    finished_goods_df["Cost"] = finished_goods_df["Batch_ID"].map(batch_costs)

    #Append to log
    new_production_log = pd.concat([new_production_log,finished_goods_df], ignore_index=True)
    new_production_log = new_production_log[["Batch_ID","Timestamp","Date of Production","Item","Purchase_ID","Type","Qty Delta","Cost"]]

    # print("NEW PRODUCTION LOG:")
    # print(new_production_log)
    #prep new production lots & format
    production_lots = finished_goods_df.copy()
    production_lots["Qty"] = production_lots["Qty Delta"]
    production_lots["Status"]  = "Active"
    production_lots = production_lots.drop(columns=["Purchase_ID","Qty Delta","Type"])

    return updated_purchase_lots, new_production_log, production_lots

def calc_sales_df(next_Sales_ID: int, sales_df: pd.DataFrame, updated_purchase_lots: pd.DataFrame, updated_production_lots: pd.DataFrame, sales_history_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    sales_df_temp = sales_df.copy()
    sales_df_temp["Date_dt"] = pd.to_datetime(sales_df_temp["Date of Sales"])

    #remove unsold lines
    sales_df_temp = sales_df_temp[sales_df_temp["Qty Sold"] > 0]
    # Pull apart stickers (are simply resold from purchase) and production items (everything else sold)
    sticker_sales = sales_df_temp[sales_df_temp["Subcategory"]== 'Sticker']
    production_sales = sales_df_temp[sales_df_temp["Subcategory"]!='Sticker']
    
    stickers_by_lot = []
    produced_sales_by_lot = []
    sales_updated_purchase_lots = updated_purchase_lots.copy()
    sales_updated_purchase_lots.rename(columns={"Quantity Bought": "Qty"}, inplace=True)
    sales_updated_production_lots = updated_production_lots.copy()


    def stock_depletion(category,updated_lots: pd.DataFrame, sales_df: pd.DataFrame, sales_history_df: pd.DataFrame) ->tuple[list[dict], pd.DataFrame]:
        #set column name to be called
        if category == "Sticker":
            col_name = "Purchase_ID"

            if isinstance(sales_history_df, pd.DataFrame) and not sales_history_df.empty:
                prior_sold_map = sales_history_df.groupby(col_name)["Qty Sold"].sum()
                prior_sold_map = prior_sold_map.to_dict()
            elif not isinstance(sales_history_df, pd.DataFrame):
                print("Unrecognized sales history data format.")
                print(f"Exiting without saving...")
                raise ValueError
            elif sales_history_df.empty:
                prior_sold_map = {}
        elif category == "Produced":
            col_name = "Batch_ID"
            prior_sold_map = {}
        else:
            print("Unrecognized sales category.")
            print(f"Exiting without saving...")
            raise ValueError
        
        #Ensure there is data to parse, otherwise error
        if isinstance(updated_lots, pd.DataFrame) and not updated_lots.empty:
            lots_df = updated_lots.copy()
        else:
            print(f"{category} sales anamoly. Cannot parse sales where there is no current inventory.")
            print(f"Exiting without saving...")
            raise ValueError

        exhausted_lots = []
        #Make a dictory of a list of dictionaries of active lots by item: lot_ID as key, qty available as value pair, multiple of them are lists as a value where the key is the item name (omfg. whyyyyy)
        lots_df = lots_df.sort_values(by=col_name, ascending=True)

        item_lots = {}
        for _,lot_row in lots_df.iterrows():
            if lot_row["Status"] == "Active":
                prior_sales = prior_sold_map.get(lot_row[col_name],0)
                item_name = lot_row["Item"]

                if lot_row["Qty"] > prior_sales:
                    
                    if not item_name in item_lots:
                        item_lots[item_name] = []

                    item_lots[item_name].append({"id":lot_row[col_name], "Qty": lot_row["Qty"]-prior_sales})
                elif lot_row["Qty"] == prior_sales:
                    lot_row["Status"] = "Exhausted"
                    exhausted_lots.append(lot_row[col_name])
                else: #prior on lot > lot
                    print(f"ERROR: {item_name} with {col_name} : {lot_row[col_name]} has recorded sales greater than original quantity.")
                    print(f"Exiting without saving...")
                    raise ValueError

        #for each row, check to make sure there is enough in stock to sell| sum across all purchase_ID that are "Active" for the Item being sold
        sales_by_lot = []
  
        for _,row in sales_df.iterrows():
                item_needed = row["Item"]
                qty_needed = row["Qty Sold"]

                #verify the needed item in the monstrosity
                if item_needed not in item_lots:
                    print(f"ERROR: Sales for {item_needed} has no active lots.")
                    print(f"Exiting without saving...")
                    raise ValueError

                #parse the monstrosity dictionary into a list of dictionaries
                active_lots = item_lots[item_needed]
                summed_qty_avail = 0
                for id in active_lots:
                    summed_qty_avail += id["Qty"]

                
                #error out if sales exceed inventory
                if qty_needed > summed_qty_avail:
                    print(f"ERROR: Sales for {item_needed} exceed inventory quantity available. Qty Sold:{qty_needed}; Qty available: {summed_qty_avail}.")
                    print(f"Exiting without saving...")
                    raise ValueError

                #iteratively deplete each ID until the order is complete
                while qty_needed > 0:
                    current_ID = active_lots[0]["id"]
                    current_qty = active_lots[0]["Qty"]
                    #if ID does not get depeleted, just subtract sales from the lot and exit loop
                    if qty_needed < current_qty:
                        sales_by_lot.append({
                            **row.to_dict(),
                            col_name: current_ID,
                            "Qty": qty_needed
                        })
                        active_lots[0]["Qty"] = current_qty - qty_needed
                        break

                    # otherwise, ID gets depleted by qty_needed. Turn Status to Exhausted and subtract quantity needed by qty in stock in the lot.
                    qty_needed = qty_needed - current_qty
                    exhausted_lots.append(current_ID)
                    active_lots.pop(0)

                    #append the purchase fulfillent for this purchase_ID into the sales_by_lot dataframe
                    sales_by_lot.append({
                        **row.to_dict(),
                        col_name: current_ID,
                        "Qty": current_qty
                    })
        #update the lots statii
        lots_df.loc[lots_df[col_name].isin(exhausted_lots),"Status"] = "Exhausted"

        #bring forward the costs of each thing sold byy id
        cost_map = updated_lots.set_index(col_name)["Cost"].to_dict()
        for row in sales_by_lot:
            row["Cost"] = cost_map.get(row[col_name],0.0)

        return sales_by_lot, lots_df

    if not sticker_sales.empty:
        
        stickers_by_lot, sales_updated_purchase_lots = stock_depletion("Sticker", sales_updated_purchase_lots, sticker_sales, sales_history_df)
    

    if not production_sales.empty:
        produced_sales_by_lot, sales_updated_production_lots = stock_depletion("Produced",updated_production_lots, production_sales, sales_history_df)
  
    sales_by_lot = stickers_by_lot + produced_sales_by_lot
    sales_by_lot = pd.DataFrame(sales_by_lot)
    for id_col in ["Purchase_ID", "Batch_ID"]:
        if id_col not in sales_by_lot.columns:
            sales_by_lot[id_col] = pd.NA
    sales_by_lot = sales_by_lot.sort_values(
        by=["Date of Sales","Event Name","Item"]
    )
    sales_by_lot["Sales_ID"] = range(next_Sales_ID, next_Sales_ID + len(sales_by_lot))
        
    sales_updated_purchase_lots.rename(columns={"Qty": "Quantity Bought"}, inplace=True)
    #we now need to return the sales data, along with the most updated purchase and production lots
    return sales_by_lot, sales_updated_purchase_lots, sales_updated_production_lots

def calc_curr_from_sales (sales_df: pd.DataFrame, current_df: pd.DataFrame):
    #    1. Pre-aggregate sales if sales_df can have multiple rows per ID
    sales_cols = ["Timestamp", "Date of Sales", "Activity", "Qty Sold"]

    # print("Printing sales to calc current inv")
    # print(sales_df)
    sales_df["Batch_ID"] = pd.to_numeric(sales_df["Batch_ID"],errors='coerce')
    sales_df["Purchase_ID"] = pd.to_numeric(sales_df["Purchase_ID"], errors='coerce') # error here
    current_df["Batch_ID"] = pd.to_numeric(current_df["Batch_ID"],errors='coerce')
    current_df["Purchase_ID"] = pd.to_numeric(current_df["Purchase_ID"], errors='coerce')

    sales_batch = (sales_df[sales_df["Batch_ID"].notna()].groupby("Batch_ID", as_index=False)[sales_cols].last()) # Retains latest metadata; use .agg({'Qty Sold': 'sum'}) if Qty needs summing
    sales_purch = (sales_df[sales_df["Purchase_ID"].notna()].groupby("Purchase_ID", as_index=False)[sales_cols].last())

    # 2. Split inventory into batch vs. purchase subsets
    is_batch = current_df["Batch_ID"].notna()
    curr_batches = current_df[is_batch].copy()
    curr_purchases = current_df[~is_batch].copy()

    def merging_sales(column,sales, current_part):
        if current_part.empty:
            return current_part
        
        merged_inv = current_part.merge(sales[[column, "Timestamp","Date of Sales","Qty Sold","Activity"]], on=column, how = "left", suffixes=("","_sales"))

        if "Timestamp_sales" in merged_inv.columns:
            merged_inv["Timestamp"] = merged_inv["Timestamp_sales"].combine_first(merged_inv["Timestamp"])
        if "Date of Sales" in merged_inv.columns:
            merged_inv["Date of Inventory"] = merged_inv["Date of Sales"].combine_first(merged_inv["Date of Inventory"])
        if "Activity" in merged_inv.columns:
            merged_inv["Inventory Activity"] = merged_inv["Activity"].combine_first(merged_inv["Inventory Activity"])
        merged_inv["Qty Sold"] = merged_inv["Qty Sold"].fillna(0)
        merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"] - merged_inv["Qty Sold"]

        merged_inv = merged_inv.drop(columns=["Timestamp_sales","Date of Sales","Qty Sold","Activity"])
        return merged_inv

    merged_batches = merging_sales("Batch_ID",sales_batch,curr_batches)
    merged_purchases = merging_sales("Purchase_ID",sales_purch, curr_purchases)

    new_curr = pd.concat([merged_purchases, merged_batches]).sort_index()

    final_cols = ["Timestamp","Date of Inventory","Inventory Activity","Item","Style","Subcategory","Category","Final Product","Input Product","Purchase_ID","Batch_ID","Qty in Stock","Cost"]

    return new_curr[final_cols]