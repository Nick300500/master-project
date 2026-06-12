import pandas as pd
from pathlib import Path

offshore_dir = Path("01_data/03_filtered_data_for_prediction_year/Climate Data/Wind Onshore/PECD_Wind_Onshore_2030_edition 2022.1")
for f in sorted(offshore_dir.glob("*.csv")):
    raw = pd.read_csv(f, header=None, on_bad_lines='skip')
    print(f"{f.name}: {raw.shape}")