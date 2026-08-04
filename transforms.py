import pandas as pd
import duckdb


def get_sales(sales_path :str):
    datafile = pd.read_csv(sales_path)

    return datafile

def exclude_columns(datafile):
    query = """
    SELECT * EXCLUDE (Timestamp,"Email Address") FROM datafile
    """
    return query

def sales_transform(datafile,query):
    exc_col_query = duckdb.query(query).df()

    unpivot = """
        WITH unpivoted as (
            FROM  exc_col_query
            UNPIVOT INCLUDE NULLS (
                qty_sold FOR item_key IN (
                    COLUMNS (* EXCLUDE(
                        "Date of Sales", 
                        "Name of Event/ Venue", 
                        "Total Sales($)", 
                        "Event Notes (weather, etc)"
                )))
            )
        )
        PIVOT unpivoted
        ON "Date of Sales"
        USING COALESCE(SUM(qty_sold),0)
        GROUP BY item_key
        ORDER BY item_key 
    """

    return duckdb.query(unpivot).df()