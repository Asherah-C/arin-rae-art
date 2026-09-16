import pandas as pd
import duckdb
from transforms import backdating_purchases

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

#def purch_ledger_ref(path:str)-> tuple[pd.DataFrame,pd.Timestamp]:
    purch_ledger = pd.read_csv(path)
    if purch_ledger["Date of Purchase"].notna().any():
        last_purch_date = pd.to_datetime(purch_ledger["Date of Purchase"]).max()
    else:
        last_purch_date = pd.Timestamp.min

    return purch_ledger,last_purch_date

def current_inv_ref (path:str) -> tuple[pd.DataFrame,pd.Timestamp]:
    current_inv_df = pd.read_csv(path)
    if current_inv_df["Date of Inventory"].notna().any():
        current_inv_date = pd.to_datetime(current_inv_df["Date of Inventory"]).max()
    else:
        current_inv_date = pd.Timestamp.min

    return current_inv_df, current_inv_date

# def calc_production_df(bill_of_mats_df: pd.DataFrame, unprocessed_df: pd.DataFrame) -> pd.DataFrame:
    new_ledger = unprocessed_df.copy()
    new_ledger["Qty Delta"] = pd.to_numeric(new_ledger["Qty Delta"], errors="coerce").fillna(0)

    components_consumed = new_ledger.merge(bill_of_mats_df, on="Subcategory",how="inner")

    raw_paper_sizes = {"5x7", "8x10", "Card", "11x14", "13x19"}

    components_consumed = components_consumed[
        ~components_consumed["Component_Item"].astype(str).str.strip().isin(raw_paper_sizes)
    ]
    components_df = pd.DataFrame({
        "Date of Production": components_consumed["Date of Production"],
        "Item": components_consumed["Component_Item"],
        "Qty Delta": -1 * components_consumed["Qty Delta"],
        "Type": "Component Consumption"
    })

    new_ledger["Print_Suffix"] = new_ledger["Subcategory"].apply(
        lambda x: "-CSto" if str(x).strip().lower().startswith("card") else "-Prin"
    )

    new_ledger["Print_Item"] = new_ledger["Style"].astype(str).str.strip() + new_ledger["Print_Suffix"]

    art_df = pd.DataFrame({
        "Date of Production": new_ledger["Date of Production"],
        "Item": new_ledger["Print_Item"],
        "Qty Delta": -1 * new_ledger["Qty Delta"],
        "Type": "Style art/card stock Consumption"
    })

    finished_goods_df = pd.DataFrame({
        "Date of Production": new_ledger["Date of Production"],
        "Item": new_ledger["Item"],
        "Qty Delta": new_ledger["Qty Delta"],
        "Type": "Finished Goods Production"
    })

    production_delta_df = pd.concat(
        [components_df, art_df, finished_goods_df],
        ignore_index=True
    )

    aggregated_df = (
        production_delta_df.groupby(["Date of Production","Item","Type"], as_index=False)["Qty Delta"].sum()
    )

    return aggregated_df.sort_values(by=["Date of Production","Item"], ignore_index=True)

def update_current_from_prod(prod_df: pd.DataFrame,current_df: pd.DataFrame) ->pd.DataFrame:

    # need to add logic to test if current inventtory was a hand count, if hand count, append only dates after inventory, else, append all dates since last and count
    prod_df_temp = prod_df.copy()
    prod_df_temp["Date_dt"] = pd.to_datetime(prod_df_temp["Date of Production"])
    latest_prod_date = prod_df_temp["Date_dt"].max()
    prod_summed_df = prod_df_temp.groupby("Item", as_index=False)["Qty Delta"].sum()

    current_df_temp = current_df.copy()
    current_df_temp["Date_dt"] = pd.to_datetime(current_df_temp["Date of Inventory"])

    merged_inv = pd.merge(current_df_temp , prod_summed_df, on = "Item", how = "outer")
    merged_inv["Qty Delta"] = merged_inv["Qty Delta"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"] + merged_inv["Qty Delta"]

    merged_inv["Date of Inventory"] = latest_prod_date
    merged_inv["Inventory Location"] = "Calculated"

    return merged_inv[[
            "Timestamp",
            "Date of Inventory",
            "Inventory Location",
            "Item",
            "Qty in Stock"
    ]]

# def pull_purch_ledger(path:str) -> tuple[pd.DataFrame,pd.Timestamp]:
    ledger = pd.read_csv(path)
    if ledger["Date of Purchase"].notna().any():
        last_purch_date = pd.to_datetime(ledger["Date of Purchase"]).max()
    else:
        last_purch_date = pd.Timestamp.min
    
    return ledger,last_purch_date

def calc_current_from_purch(purch:pd.DataFrame, curr_inv:pd.DataFrame) -> pd.DataFrame:
    purch_df = purch.copy()
    purch_df["Date_dt"] = pd.to_datetime(purch_df["Date of Purchase"])
    current_inv_date = pd.to_datetime(curr_inv["Date of Inventory"]).max()
    unprocessed = purch_df[purch_df["Date_dt"] > current_inv_date].copy()

    latest_purch_date = unprocessed["Date_dt"].max()
    
    purch_summed_df = unprocessed.groupby("Item", as_index=False)["Quantity Bought"].sum()

    merged_inv = pd.merge(curr_inv , purch_summed_df, on = "Item", how = "left")
    merged_inv["Quantity Bought"] = merged_inv["Quantity Bought"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"] + merged_inv["Quantity Bought"]

    merged_inv["Date of Inventory"] = latest_purch_date
    merged_inv["Inventory Location"] = "Calculated"

    return merged_inv[[
        "Timestamp",
        "Date of Inventory",
        "Inventory Location",
        "Item",
        "Qty in Stock"
    ]]

#Pulls unique dates from a date column, based on the correct ledger type
def unique_dates(ledger_type:str, dataframe: pd.DataFrame) ->pd.DataFrame:
    if ledger_type == "Sales":
        date_col = "Date of Sales"
    elif ledger_type == "Inventory":
        date_col = "Date of Inventory"
    elif ledger_type == "Purchase":
        date_col = "Date of Purchase"
    elif ledger_type == "Production":
        date_col = "Date of Production"
    elif ledger_type == "Initialization" or "Processing":
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

def test():
    bill_of_mats = "Inventory - DIM - Production Table.csv"
    production_ledger_path = "Inventory - FACT - Production Ledger.csv"
    purchase_path = "Inventory - FACT - Purchases.csv"
    expanded_prod_ledger_path = "FACT - Production Ledger.csv" 
    purch_ledger_path = "DIM - Purchases Ledger.csv"

    bill_of_mats_df = pd.read_csv(bill_of_mats)
    unprocessed_df = pd.read_csv(production_ledger_path)
    purch_ledger_df = pd.read_csv(purchase_path)
    expanded_prod_df = pd.read_csv(expanded_prod_ledger_path)

    purch_ledger_df = purch_ledger_df.drop(columns=["Item / Style","Category(for styles only; leave blank for packaging and inputs)"])
    lots = backdating_purchases("Purchases", purch_ledger_df,purch_ledger_path)
    next_batch_num = 1 if expanded_prod_df.empty else int(expanded_prod_df["Batch_ID"].max()) + 1

    print("testing expand_production_df")
    purch_log, production_log = expand_production_df(bill_of_mats_df,unprocessed_df,expanded_prod_df,lots,next_batch_num)

    purch_log.to_csv(purch_ledger_path, header=True, index=False)
    production_log.to_csv(expanded_prod_ledger_path, mode='a', header=False, index=False)


def expand_production_df(bill_of_mats_df: pd.DataFrame, unprocessed_df: pd.DataFrame, expanded_prod_df: pd.DataFrame, lots: pd.DataFrame, batch_start_num: int) -> pd.DataFrame:
    new_ledger = unprocessed_df.copy()

    #Temp line while testing
    new_ledger["Qty Delta"] = new_ledger["Qty Made"]
    new_ledger["Item"] = new_ledger["Item Made"]
    #-end temp line

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
    #pull active lots from outtput purchase ledger
    active_lots_df = lots[lots["Status"]=="Active"].copy()
    production_log = expanded_prod_df.copy()

    for _,row in raw_mats_df.iterrows():
        # identify the needed input
        item_needed = row["Item"]

        #create a backup point to rerun in case of errors
        while True:
            #restrict the search to only active lots of that item
            masked_lots = active_lots_df[(active_lots_df["Item"]==item_needed) & (active_lots_df["Status"] == "Active")]

            #exit the loop if there are no active lots for the item
            if masked_lots.empty:
                    print(f"Input Material: {item_needed} is out of stock. Cannot complete production run.")
                    print(f"Exiting without saving...")
                    raise ValueError
            #identify the current FIFO active Lot
            lotID = masked_lots["Purchase_ID"].min()

            #calculate the remaining quantity of items left in the lot
            qty_bought = masked_lots.loc[masked_lots["Purchase_ID"]==lotID,"Quantity Bought"].iloc[0]
            qty_consumed = (production_log["Purchase_ID"] == lotID).sum()
            qty_remaining = qty_bought - qty_consumed

            #verify it should be active, if not change to "exhausted" and restart loop
            if qty_remaining > 0:
                #if the last one, change to exhausted
                if qty_remaining == 1:
                    active_lots_df.loc[active_lots_df["Purchase_ID"] == lotID, "Status"] = "Exhausted"
                #append the consumption to the production_log
                row["Purchase_ID"] = lotID
                row["Cost"] = active_lots_df.loc[active_lots_df["Purchase_ID"]== lotID,"Price (each)"].iloc[0]
                
                production_log = pd.concat([production_log, pd.DataFrame([row])], ignore_index=True)

                break
            else:
                active_lots_df.loc[active_lots_df["Purchase_ID"] == lotID, "Status"] = "Exhausted"


    #make a status map of everything changed in production run
    status_map = active_lots_df.set_index("Purchase_ID")["Status"]

    # After running all of production, update statuses of the lots in the purchases ledger.
    updated_lots = lots.copy()
    updated_lots["Status"] = updated_lots["Purchase_ID"].map(status_map).fillna(updated_lots["Status"])
                    
    finished_goods_df = pd.DataFrame({
        "Timestamp": single_units["Timestamp"],
        "Date of Production": single_units["Date of Production"],
        "Batch_ID": single_units["Batch_ID"],
        "Item": single_units["Item"],
        "Qty Delta": 1,
        "Type": "Production"
    })
    #prep production log for math because pandas doesn't like currency
    production_log["Cost"] = (production_log["Cost"].astype(str).str.replace(r"[$,]", "", regex=True))
    production_log["Cost"] = pd.to_numeric(production_log["Cost"], errors="coerce").fillna(0.0)

    # Calculate Cost of Good produced based on the production log, referencing the Batch_ID
    for _,row in finished_goods_df.iterrows():
        row_batch = row["Batch_ID"]
        row["Purchase_ID"] = pd.NA #needs to be blank, but an existing column for dataframe concate
        row["Cost"] = production_log.loc[production_log["Batch_ID"]== row_batch,"Cost"].sum()

        production_log = pd.concat([production_log,pd.DataFrame([row])], ignore_index=True)

    return updated_lots, production_log

