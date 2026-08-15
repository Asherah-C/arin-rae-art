# Arin-Rae-Art Data Cleaning & Transformations

## This package includes:
- main.py
- transforms.py

## This package requires:
- Python 3+
- Pandas
- DuckDb

## Command Syntax
python3 main.py [flag] (option:path) 

## Flags (mutually exclusive)
- -s : run sales
- -i : set inventory

## Default sourcefile Paths
-s "Inventory - FACT - Historical Sales.csv"
-i "Inventory - FACT - Inventory Snapshots.csv"

Required file: "FACT - Inventory History.csv" (import or touch to begin a new instance) NOTE: if you create a new file, be sure to have the following columns placed, or a pandas EmptyDataError occurs: "Date of Inventory,Inventory Location,Item,Qty in Stock"

## Outputs (Default File Names)
- FACT - Event Sales.csv (from sales_filename when -s is used)
- FACT - Events.csv (from sales_filename when -s is used)
- FACT - Inventory History.csv (appended with current inventory, reduced by sales when -s or -i is used)
- DIM - Current Inventory.csv (Written/Overwritten when -s or -i used)