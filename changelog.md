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
* Move to Timestamps
* Production adds all in ledger, not just applicable dates. It creates the dataset based on what needs to be added to the ledger and adds it to current inventory, including any dates that are captured by the latest handcount.
* Change "Add to Purchase Order" logic to be IF AND "Add to Production Queue" for prints and cards, else FALSE, skip logic for inputs/supplies
* Add cannibalism logic to Production

# 1.2.0 Release

### ✨ New Features
* Initialization feature now populates all ledgers (inventory, purchases, production, events, and sales) with historical information accurately by date and then creates a current inventory file.
* Processing feature now handles all activities at once, with backdating and activity prioritization! (inventory, purchases, production, sales)
* Timestamps now integrated (but not utilized yet, pending owner-level manual clean).
* New Flags for all files (sources and outputs).

### Resolved Bugs
* **Resolved "Add to Purchase Order" logic** by eliminating additional OR clause. Now, items will only be added to purchase order as needed to cover production queues.
* **Resolved multiple bugs**  by implementing processing logic.
- - ~~Need to recalculate/overwrite current inventory when a newer inventory that predates current inventory arrives. calc all purchases, production, and sales based on that newest inventory date, going forward.~~
- - ~~Loading by activity will fail to maintain an accurate telling of events unless they are loaded in order, as they happen.~~
- - ~~Production adds all in ledger, not just applicable dates. It creates the dataset based on what needs to be added to the ledger and adds it to current inventory, including any dates that are captured by the latest handcount.~~
* **Timestamps integrated for future iterations.**

### Under the Hood
* **Initialization.py** New file to handle the initialization of a new database fullly, loading all data chronologically and from all sources simultaneously. This initialization will become a large feature of rolling out a unifed data ETL process, built on timestamps and not merely dates.
* **processing.py**
* **Code Cleaning: Unification of args and flags** slowly bringing all code into a single standard, beginning with unified args references to help reduce confusion of coders to aid in troubleshooting.

### Known Bugs and Issues
* Needs a way to build-in spot check inventories (possible Power BI function over python?)
* No price or expenses data is ETLed at this time.
* Add cannibalism logic to Production
* Add Joins of Production Tables

# 1.2.1 Release

### ✨ New Features
No new main features. Back end prep for Purchase /Production logic for cost analysis.

### Known Bugs and Issues
* Needs a way to build-in spot check inventories (possible Power BI function over python?)
* No price or expenses data is ETLed at this time.
* Add cannibalism logic to Production
* Add Joins of Production Tables

# 1.2.2 Patch Notes


### Resolved Bugs
* Fixed a pair of errors that caused purchases to not be parsed correctly. Reinitialization and running recommended.
* Resolved an errror where the code was not expecting the new "Location (City)" Column from Historical sales.csv

### Known Bugs and Issues
* Needs a way to build-in spot check inventories (possible Power BI function over python?)
* No price or expenses data is ETLed at this time.
* Add cannibalism logic to Production
* Add Joins of Production Tables

# 1.2.3 Patch Notes

### Resolved Bugs
* Fixed a calculation error where initialization files were double calculated.

### Known Bugs and Issues
* Needs a way to build-in spot check inventories (possible Power BI function over python?)
* No price or expenses data is ETLed at this time.
* Add cannibalism logic to Production
* Add Joins of Production Tables
* Inventory Enrichment turns all activities into "Calculated"

# 1.2.3-1 Commit to Main before Branch
### Known Bugs and Issues
* Needs a way to build-in spot check inventories (possible Power BI function over python?)
* No price or expenses data is ETLed at this time.
* Add cannibalism logic to Production
* Add Joins of Production Tables
* Inventory Enrichment turns all activities into "Calculated"

# 2.0 Costs of Good Sold BETA

### New Features
* Purchase Lot Enforcement:
-   Assigns Purchase_ID to each item-qty purchased
-   Tracks Active vs Exhausted lots to ensure First-In-First-Out accounting
* Production Batching:
-   Derives individual cost of good produced by building each item individually from available inputs
-   Uses First-In, First-Out production accounting
* Added new columns:
-   Input Purchase Ledger Columns: Purchase_ID (autocalc)
-   Ouput Purchase Ledger Columns: Purchase_ID, Status (Active or Exhausted)
-   Output Production Ledger Columns: Batch_ID (autocalc by single qty item produced), Purchase_ID (for inputs only), Cost
-   DIM - Current Inventory: added Purchase_ID, Batch_ID, and Cost columsn; cost of item (ea) per appropriate ID
-   FACT - Event Sales.csv now assigns sales by Purchase or Batch ID (looks much more exploded);
*  New Output Table!
- DIM - Production Lots.csv tracks production batch log, cost per unit assembled and status.

## Removed Features
* To maintain consistent granularity of items across inventory, we removed the sumprint production logic, as well as purchase production logic. these will need to be implemented in a BI feature push to retain function for end-user.
* Current Inventory no longer sums up total counts on item, but now on Purchase_ID or Batch_ID, whichever is appropriate. Full aggregation will need to be implemented in BI feature push to retain function of end-user.
* Event Sales no longer aggreated on item; Full aggregation will need to be implemented in BI feature push to retain function of end-user.

### Resolved Issues
* Renamed flags for consistency
* Changed Inventory Location to Inventory Activity to avoid ambiguity and increase granualarity of data

# 2.0.1 Costs of Good Sold BETA - Hotfix
### Resolved Issues
* FACT - Event Sales.csv was missing Subcategory Column

# 2.0.2 Costs of Good Sold BETA - Patch
### Additional Features
* Inventory History Run Tracking
-   Run_ID column in inventory_history.csv to differentiate exact snapshots for backdating activity and provide clear date-captured snapshot, where the snapshot date = max(Date of Inventory) for each Run_ID

* !!! IMAGED DATA !!!
- The program now successfully zips all output files together upon successful completion of a data ETL process.
- Files saved as "{Date of Activity} | {Activity}.zip" within a directory called "Imaged Data by default."
- Default directory can be renamed using args flag --image-dir.

* By-Activity Processing
- The program now processes new activities one at a time by date first, and activity priority (still inventory, purchase, production, sales) individually.
- This increases granularity of data output, in case backdated data is later discovered, as well as ensures more accurate backups.

### Resolved Issues
* Removed an errroneous args flag (raw-mats-ledger).

### Under the Hood
* Eliminated several functions through streamlining, many of which caused errors in
* Removed validations.py from program. No longer used.

### Known Bugs and Issues
* Needs a way to build-in spot check inventories (possible Power BI function over python?)
* No price data is ETLed at this time. Slated for future feature release.
* Add cannibalism logic to Production
* Add Joins of Production Tables

### Dev Log
* 10/9/2026:    To Do - Upstream cast column types on pd.read_csv()
* 10/21/2026:   Consider production, (stock qty), Master Item Table tables in .zip file?
-               Inventory largely untested. Will wish to see how it iteracts with program.             

# 2.0.3 Cost of Goods Sold BETA - Hotfix
### Resolved Issues
* Identified that the Production processing overwrote, not appended, production lots.
* Identified a bug that caused cascading errors in the Sales data.


