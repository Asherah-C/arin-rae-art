import pandas as pd
import duckdb
import sys


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

def calc_production_df(bill_of_mats_df: pd.DataFrame, prod_ledger_df: pd.DataFrame, curr_inv_date:pd.Timestamp) -> pd.DataFrame:
    ledger = prod_ledger_df.copy()
    ledger["Date of Production"] = pd.to_datetime(ledger["Date of Production"])

    unprocessed = ledger[ledger["Date of Production"] > curr_inv_date].copy()

    if unprocessed.empty:
        return pd.DataFrame(columns=["Date", "Item", "Qty Delta", "Type"])

    unprocessed["Qty Made"] = pd.to_numeric(unprocessed["Qty Made"], errors="coerce").fillna(0)

    components_consumed = unprocessed.merge(bill_of_mats_df, on="Subcategory",how="inner")

    raw_paper_sizes = {"5x7", "8x10", "Card", "11x14", "13x19"}

    components_consumed = components_consumed[
        ~components_consumed["Component_Item"].astype(str).str.strip().isin(raw_paper_sizes)
    ]
    components_df = pd.DataFrame({
        "Date": components_consumed["Date of Production"],
        "Item": components_consumed["Component_Item"],
        "Qty Delta": -1 * components_consumed["Qty Made"],
        "Type": "Component Consumption"
    })

    unprocessed["Print_Suffix"] = unprocessed["Subcategory"].apply(
        lambda x: "-CSto" if str(x).strip().lower().startswith("card") else "-Prin"
    )

    unprocessed["Print_Item"] = unprocessed["Style"].astype(str).str.strip() + unprocessed["Print_Suffix"]

    art_df = pd.DataFrame({
        "Date": unprocessed["Date of Production"],
        "Item": unprocessed["Print_Item"],
        "Qty Delta": -1 * unprocessed["Qty Made"],
        "Type": "Style art/card stock Consumption"
    })

    finished_goods_df = pd.DataFrame({
        "Date": unprocessed["Date of Production"],
        "Item": unprocessed["Item Made"],
        "Qty Delta": unprocessed["Qty Made"],
        "Type": "Finished Goods Production"
    })

    production_delta_df = pd.concat(
        [components_df, art_df, finished_goods_df],
        ignore_index=True
    )

    aggregated_df = (
        production_delta_df.groupby(["Date","Item","Type"], as_index=False)["Qty Delta"].sum()
    )

    return aggregated_df.sort_values(by=["Date","Item"], ignore_index=True)

def update_current_from_prod(prod_df: pd.DataFrame,inv_df: pd.DataFrame) ->pd.DataFrame:

    prod_df_temp = prod_df.copy()
    prod_df_temp["Date_dt"] = pd.to_datetime(prod_df_temp["Date"])
    latest_prod_date = prod_df_temp["Date_dt"].max()
    prod_summed_df = prod_df_temp.groupby("Item", as_index=False)["Qty Delta"].sum()

    inv_df_temp = inv_df.copy()
    inv_df_temp["Date_dt"] = pd.to_datetime(inv_df_temp["Date of Inventory"])

    merged_inv = pd.merge(inv_df_temp , prod_summed_df, on = "Item", how = "outer")
    merged_inv["Qty Delta"] = merged_inv["Qty Delta"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"].fillna(0)
    merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"] + merged_inv["Qty Delta"]

    merged_inv["Date of Inventory"] = latest_prod_date.strftime("%m/%d/%Y")
    merged_inv["Inventory Location"] = "Calculated"

    return merged_inv[[
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

def purch_table_ref(path:str,ledger_date: pd.Timestamp) ->pd.DataFrame:
    purch_table = pd.read_csv(path)
    purch_table["Date_dt"] = pd.to_datetime(purch_table["Date of Purchase"])

    unprocessed = purch_table[purch_table["Date_dt"] > ledger_date].copy()

    if unprocessed.empty:
        print("No new purchases to process. Exiting....")
        sys.exit(0)

    else:
        return unprocessed[[
            "Date of Purchase",
            "Invoice / Purchase Orders",
            "Item",
            "Quantity Bought",
            "Price (each)",
            "Subtotal",
            "Date_dt"
        ]]

def calc_current_from_purch(purch:pd.DataFrame, curr_inv:pd.DataFrame,curr_date: pd.Timestamp) -> pd.DataFrame:
    purch_df = purch.copy()

    unprocessed = purch_df[purch_df["Date_dt"] > curr_date].copy()

    if unprocessed.empty:
        print("Inventory is current. Exiting.")
        sys.exit(0)

    else:
        latest_purch_date = unprocessed["Date_dt"].max()
        print(latest_purch_date)
    
        purch_summed_df = unprocessed.groupby("Item", as_index=False)["Quantity Bought"].sum()

        merged_inv = pd.merge(curr_inv , purch_summed_df, on = "Item", how = "outer")
        merged_inv["Quantity Bought"] = merged_inv["Quantity Bought"].fillna(0)
        merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"].fillna(0)
        merged_inv["Qty in Stock"] = merged_inv["Qty in Stock"] + merged_inv["Quantity Bought"]

        merged_inv["Date of Inventory"] = latest_purch_date.strftime("%m/%d/%Y")
        merged_inv["Inventory Location"] = "Calculated"

        return merged_inv[[
            "Date of Inventory",
            "Inventory Location",
            "Item",
            "Qty in Stock"
        ]]
