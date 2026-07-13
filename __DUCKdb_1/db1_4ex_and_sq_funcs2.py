import duckdb
import pandas as pd
from pathlib import Path

# FILE PATH
cwd = Path(__file__).resolve()
csvfile = cwd.parent / '_inputs' / 'postcsv.csv'

# Open a private connection sandbox
conn = duckdb.connect()

# ===== TABLE CREATION =====
# FIX: Use an f-string to give duckdb.sql the raw file path, so 'conn' can read it directly!
duckdb.sql(
    f"CREATE TABLE IF NOT EXISTS aggtrades1 AS SELECT * FROM read_csv('{csvfile}')", 
    connection=conn
)

# This will now work beautifully because the table actually exists inside 'conn' now!
aggtrades = duckdb.sql("select price from aggtrades1 limit 7", connection=conn).df()
print("--- Preview from duckdb.sql ---")
print(aggtrades.head())


# ===== READING THE TABLE WITH CONN.EXECUTE =====
# This works perfectly now because 'aggtrades1' was successfully built inside this sandbox!
trades = conn.execute("select * from aggtrades1").df()

print("\n--- Final Print from conn.execute ---")
print(trades.head())