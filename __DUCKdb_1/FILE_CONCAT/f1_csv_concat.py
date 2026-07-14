import pandas as pd
from pathlib import Path

# -----  CONCATES CSV FILES IN A FOLDER INTO ONE FILE ----

folder = Path(__file__).resolve().parent.parent/'_inputs'/'crypto_trades'
# csv_files = folder.glob('*.csv')  #  files can be concatinated in unsorted format

# coins concatenated in sorted format
sorted_csv_files = sorted(folder.glob("*.csv"))

# print(folder,'\nFolder Exists :', folder.exists())

# COMBINING THE CSVs
combined_csv_file = pd.concat([pd.read_csv(csv)
                              for csv in sorted_csv_files], ignore_index=True)

# SAVING THE RESULT
combined_csv_file.to_csv(folder/'combined_sol_cv.csv', index=False)
