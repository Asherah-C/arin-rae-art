# Release v0.2.0 — Inventory Idempotency & State Pipeline Fixes
### ✨ New Features
* **Direct File Extractions:**  Accepts and by default uses file naming convention for the Inventory Google Sheets and tab names. 
* **Pulled SQL Transforms from Power Query:** Using Pandas/DuckDb to increase performance within Power BI. Prepared `FACT - Event Sales.csv` and `FACT - Inventory History.csv` files for more streamlined loading into Power Bi.
* **Current Inventory Generation:** Automatically generates and updates `DIM - Current Inventory.csv` as new inventory snapshots and sales rows are processed.
* **Event Tracking:** Added event extraction logic to output transformed event records directly to `FACT - Events.csv`.

# Release v0.3.0 Production Runs
### ✨ New Features
* **Process Production into the Inventory Cycle** Accepts new production-focused csv files, and updates `DIM - Current Inventory.csv` and `FACT - Inventory History.csv` to reflect changes in inventory.

### Bug Fixes
* Fixed a bug that set the current inventory to the date the inventory ran. Now sets current inventory date to the latest data.

# Release v0.4.0 Purchasing
### ✨ New Features
* **Purchases Integration** Accepts raw purchases csv for ETL into current inventory and inventory ledger while presnting a cleaner set of data for BI.
* **Running Production Log** Saves and production log as `FACT - Production Ledger.csv`

# 1.0.0 Enhanced Current Inventory!
### ✨ New Features
* **Enhanced Current Inventory** Allows for quick Power BI Dashboard Deployment without excessive latency from calculated tables by integrating multiple tables into a single source.

### Known Bugs & Issues
* **Purchases Functionality requires an empty ledger file to exist.**
* **Append functions are memory intensive as file grows in size. will need to alter code later**
* **Master Item, Stock Level, and Exceptions Tables flags are non-functioning.**