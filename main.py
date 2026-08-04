import pandas as pd
import duckdb
import sys
from transforms import get_sales, exclude_columns, sales_transform

def main (path: str):
    sales = get_sales(path)
    query= exclude_columns(sales)
    sales_transformed = sales_transform(sales,query)
    sales_filename = "transformed_sales.csv"

    sales_transformed.to_csv(sales_filename, index= False)
    print(f"{sys.argv[1]} transformed to: {sales_filename}. {len(sales_transformed)} rows saved.")

main(sys.argv[1])