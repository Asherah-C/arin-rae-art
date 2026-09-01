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
- -ini      initialize the database (new setup)
- -proc     process additional ativities, after initialization

## Optional Flags, Default Sourcefile Paths, and Descriptions

### Source Files
--master-table-path             "Inventory - DIM-Master Item Table.csv"             Source Master Item Table
--stock-levels-path             "Inventory - DIM - Item Stock Level.csv"            Source Standard Item Stock Levels Table
--stock-exceptions-path         "Inventory - DIM - Stock Level Exceptions.csv"      Source Exceptions to Standard Item Stock Level Table
--inv-path                      "Inventory - FACT - Inventory Snapshots.csv"        Source Hand Counted Inventory Log (Pivotted)
--purchase-path                 "Inventory - FACT - Purchases.csv"                  Source Purchases Ledger
--production-ledger-path        "Inventory - FACT - Production Ledger.csv"          Source Production Ledger (unexpanded)
--bill-of-mats                  "Inventory - DIM - Production Table.csv"            Source Bill of Materials used in Production (Pivotted)
--raw-sales-path                "Inventory - FACT - Historical Sales.csv"           Source Event Sales (Pivotted)
### Output Files
--expanded-production           "FACT - Production Ledger.csv"                      Output Expanded Production Ledger
--inv-history                   "FACT - Inventory History.csv"                      Output unpivotted Inventory history
--purchases-output              "FACT - Purchases Ledger.csv"                       Output Purchases Ledger
--sales-output                  "FACT - Event Sales.csv"                            Output Unpivoted Sales Data
--events                        "FACT - Events.csv"                                 Output Event Data
--current-inv                   "DIM - Current Inventory.csv"                       Output Current Inventory (Merged and Calculated)
--master-table-output           "DIM-Master Item Table.csv"                         Output Master Item Table copy
