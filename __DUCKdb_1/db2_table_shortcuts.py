import pandas as pd
import duckdb

# connection to database
conn = duckdb.connect()

# A) :1  ----------------------------SCHEMA INFO ---------------------------
# Ask DuckDB to list all tables inside your connection sandbox
tables = duckdb.sql("SHOW TABLES", connection=conn)
print(tables)

# A) :2   -------------------------------------------------------------------
# Ask DuckDB to list all tables outside your connection sandbox / GLOBALLY
tables = duckdb.sql("SHOW TABLES")  # YOU remove the connection argument
print(tables)


# ======================================== TABLE INFO =========================================

# B) : 1
# Get a beautiful breakdown of your table's structure
# u rmv conn if db exist globally outside the sandbox
table_info = duckdb.sql("DESCRIBE aggtrades1", connection=conn)
print(table_info)

#  B) : 2 =========== TABLE INFO QUERY =============== : this is the long route postgresql related option for  same result as B) 1.
info = duckdb.sql(
    "SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'aggtrades1' ")
# print(info)
# ------------------------------------------------------ ---------------------------------------------
