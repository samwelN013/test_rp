import pandas as pd
from pathlib import Path

# import aggtrades
cwd = Path(__file__).resolve()
file_path = cwd.parent/'__input_ag'/'SOLUSDT_ouput_sample.parquet'
# symbol name
SYMBOL = file_path.name.split("-")[0]

file_output_path = cwd.parent/'__output_ag'/f"{SYMBOL}_ouput_sample.parquet"

# load parquet file - note: it's not human readable
df = pd.read_parquet(file_path)

# print(df.info())
print(df.head())


# to save to parquet file
# ------------- EXPORTING the dataframe to parquet using pandas ---------------
df.to_parquet(file_output_path)
