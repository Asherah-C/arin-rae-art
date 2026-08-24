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
* **Production and Purchas Algo needs to be strictly less, not less or equal to.** Flags items erroneously for production when exactly the stock level is reached.
* **Current Inventory is destructive at the moment, causing lost data to fall off when not touched by current activity.**

# 1.1.0 Initialization and Standardization
* **Standardized and initialization of database** Eliminates the echo/touch manual entry with -ini

### Resolved Bugs
* Production Runs Dropped Current Inventory Rows. This helps resolve one source of current inventory destruction.
* Master, Stock, and stock exception flags are functioning.

### Known Bugs & Issues
* **Append functions are memory intensive as file grows in size. will need to alter code later**
* **Current Inventory is destructive at the moment, causing lost data to fall off when not touched by current activity.**

# 1.1.1 PATCH NOTES

### ✨ New Features
* All output files created with correct headers and 0 rows using initialize flag.

### Resolved Bugs
* Resolved Purchase and production algos to be strictly less than, eliminating erroneous TRUE for purchasing and production.
* Append to Inventordy History now strictly appends, not a full reconstruction, saving memory as data grows.
* Removed resolved bugs that were left in queue but had been resolved by 1.1 rollout.
* Appends do strict appends, reducing memory while preserving data historicity.
* Current Inventory now appends all active items to inventory history.

### Known Bugs & Issues
* NEW - Need to correct/overwrite current inventory between inventories when new purchasing, production, and sales data arrives between current inventory date and last hand count date.
* NEW - Need to recalculate/overwrite current inventory when a newer inventory that predates current inventory arrives. calc all purchases, production, and sales based on that newest inventory date, going forward.
* NEW - Needs a way to build-in spot check inventories (possible Power BI function over python?)
* Loading by activity will fail to maintain an accurate telling of events unless they are loaded in order, as they happen.
* No price or expenses data is ETLed at this time.