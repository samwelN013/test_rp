import duckdb
from pathlib import Path

# 1. Setup your file path
cwd = Path(__file__).resolve()
csvfile = cwd.parent / '_inputs' / 'postcsv.csv'

# 2. Open your private connection sandbox
conn = duckdb.connect()

# =====================================================================
# STEP 1: CREATE the table using duckdb.sql()
# CRITICAL TRICK: We pass connection=conn so it builds it inside the sandbox!
# =====================================================================
duckdb.sql(
    f"CREATE TABLE IF NOT EXISTS aggtrades1 AS SELECT * FROM read_csv('{csvfile}')",
    connection=conn
)

# ---- TO return table in SQL  format ----------------------
trades_sq = duckdb.sql("select * from aggtrades1 limit 4", connection=conn)

# ----- To convert the table to pandas dataframe from SQL

# trades_sq = trades_sq.df()
#----- also this works ie 
trades_sq = duckdb.sql("select * from aggtrades1 limit 4", connection=conn).df()

# print(trades_sq)

# =====================================================================
# STEP 2: SELECT from the table using conn.execute()

# This now works perfectly because duckdb.sql put it right in conn's sandbox!
# =====================================================================

# trades_df = conn.execute("SELECT price FROM aggtrades1 LIMIT 7").df()

# Print the result using your pandas dataframe
# print(trades_sq)
