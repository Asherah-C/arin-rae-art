# Arin-Rae-Art Data Cleaning & Transformations

## This package includes:
- main.py
- transforms.py
- validations.py

## This package requires:
- Python 3+
- Pandas
- DuckDb

## Command Syntax
python3 main.py [flag] (option:path) 

## Flags (mutually exclusive)
- -ini : initialize the database (new setup)
- -s : run sales
- -i : set inventory
- -pro: production
- --table: production/Bill of Materials table
- --ledger: production ledger
- --current_inv: current inventory file
- --inv_history: inventory ledger file

## Default sourcefile Paths
-s "Inventory - FACT - Historical Sales.csv"
-i "Inventory - FACT - Inventory Snapshots.csv"
-pro "Inventory - FACT - Production Ledger.csv"
-pur "Inventory - FACT - Puchases.csv"
--table "Inventory - DIM - Production Table.csv"
--master "Inevntory - DIM-Master Item Table.csv"
--stock_lvl ""Inventory - DIM - Item Stock Level.csv"
--stk_exceptions Inventory - DIM - Stock Level Exceptions.csv"
--pro_ledger_processed "FACT - Production Ledger.csv"
--current_inv "DIM - Current Inventory.csv"
--inv_history "FACT - Inventory History.csv"

## Outputs (Default File Names)
- FACT - Event Sales.csv (from sales_filename when -s is used)
- FACT - Events.csv (from sales_filename when -s is used)
- FACT - Inventory History.csv (appended with current inventory, reduced by sales when -s or -i is used)
- FACT - Purchases Ledger.csv (tracks purchases)
- FACT - Production Ledger.csv (tracks production)
- DIM - Current Inventory.csv (Written/Overwritten for all activities that affect current inventory count, including stock levels and production/purchase flags)