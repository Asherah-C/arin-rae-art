import pandas as pd
import duckdb


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

def purch_ledger_ref(path:str)-> tuple[pd.DataFrame,pd.Timestamp]:
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

def pull_purch_ledger(path:str) -> tuple[pd.DataFrame,pd.Timestamp]:
    ledger = pd.read_csv(path)
    if ledger["Date of Purchase"].notna().any():
        last_purch_date = pd.to_datetime(ledger["Date of Purchase"]).max()
    else:
        last_purch_date = pd.Timestamp.min
    
    return ledger,last_purch_date

#def purch_table_ref(dates_df:pd.DataFrame, raw_df: pd.DataFrame) ->pd.DataFrame:
#    query = """
#    SELECT r.*
#    FROM dates_df as d
#    LEFT JOIN raw_df as r
#        ON d.date = r."Date of Purchase"
#    """
#    purch_to_process = duckdb.query(query).df()
#
#    return purch_to_process

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

# Reworks to include Timestamp
def expand_production_df(bill_of_mats_df: pd.DataFrame, unprocessed_df: pd.DataFrame) -> pd.DataFrame:
    new_ledger = unprocessed_df.copy()
    new_ledger["Qty Delta"] = pd.to_numeric(new_ledger["Qty Delta"], errors="coerce").fillna(0)

    # Builds a pivoted table of materials for each line of production
    components_consumed = new_ledger.merge(bill_of_mats_df, on="Subcategory",how="inner")

    #Unpivot the table on components for each item in production, then remove NaN lines
    component_cols = ["Backboard Size","Plastic Sleeve Size","Matting Size","Frame Size"]
    existing_col = [c for c in component_cols if c in components_consumed.columns]

    components_consumed = components_consumed.melt(
        id_vars=["Timestamp","Date of Production","Item","Subcategory","Qty Delta"],
        value_vars=existing_col,
        var_name="Component_Type",
        value_name="Component_Item"
    ).dropna(subset=["Component_Item"])

    #Rebuild as a component only ledger
    components_df = pd.DataFrame({
        "Timestamp": components_consumed["Timestamp"],
        "Date of Production": components_consumed["Date of Production"],
        "Item": components_consumed["Component_Item"],
        "Qty Delta": -1 * components_consumed["Qty Delta"],
        "Type": "Component Consumption"
    })

    #build the art prints component to be consumed based on the original dataframe
    new_ledger["Print_Suffix"] = new_ledger["Subcategory"].apply(
        lambda x: "-CSto" if str(x).strip().lower().startswith("card") else "-Prin"
    )

    new_ledger["Print_Item"] = new_ledger["Style"].astype(str).str.strip() + new_ledger["Print_Suffix"]

    art_df = pd.DataFrame({
        "Timestamp": new_ledger["Timestamp"],
        "Date of Production": new_ledger["Date of Production"],
        "Item": new_ledger["Print_Item"],
        "Qty Delta": -1 * new_ledger["Qty Delta"],
        "Type": "Style art/card stock Consumption"
    })

    finished_goods_df = pd.DataFrame({
        "Timestamp": new_ledger["Timestamp"],
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
            production_delta_df.groupby(["Timestamp","Date of Production","Item","Type"], as_index=False)["Qty Delta"].sum()
        )
    print("Expanded Production Activity:")
    print(aggregated_df)
    return aggregated_df.sort_values(by=["Date of Production","Item"], ignore_index=True)