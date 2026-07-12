import duckdb
import pandas as pd
from pathlib import Path
# pip install polars
import polars

# FILE PATH
cwd = Path(__file__).resolve()
csvfile = cwd.parent/'_inputs'/'postcsv.csv'