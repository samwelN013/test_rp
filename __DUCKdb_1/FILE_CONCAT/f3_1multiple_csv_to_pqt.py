import pandas as pd
from pathlib import Path
import duckdb

# -----  CONVERTING MULTIPLE CSV FILE TO MULTIPLE PARQUET FILES ----

folder = Path(__file__).resolve().parent.parent/'_inputs'/'crypto_trades'
# csv_files = folder.glob('*.csv')  #  files can be concatinated in unsorted format

# coins concatenated in sorted format
sorted_csv_files_source = sorted(folder.glob("*.csv"))

# destination folder
pqt_folder = Path(__file__).resolve().parent.parent/'_inputs'/'pqt_folder'
pqt_folder.mkdir(parents=True, exist_ok=True)

