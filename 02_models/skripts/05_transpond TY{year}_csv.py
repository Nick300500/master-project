'''Transponiere eine Date des folders ERAA 2022 PEMMDB National Estimates zur weiterverarbeitung
Dass die Datei weiterverwendet werden kann die wie anderen, müssen außerdem diverse Umbenennungen etc vorgenommen werden

Unter anderem wird die .csv durch eine Spalte getrennt, in der erneut die Zonenname angegeben werden, diese wurde
unter anderem entfernt
'''

import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOURCE_DIR = Path("01_data/03_filtered_data_for_prediction_year/ERAA 2022 PEMMDB National Estimates") # Dies sollte das Ausgabeverzeichnis von 05_filter_and_accu_PEMMCD_National_Estimates.py sein
OUTPUT_DIR = Path("01_data/03_filtered_data_for_prediction_year/ERAA 2022 PEMMDB National Estimates")

def transpose_ty_file(csv_path: Path, output_dir: Path, year: str): # 'year' als Parameter hinzugefügt
    """Transponiert die TY-Datei für das ausgewählte Jahr."""
    logger.info(f"Verarbeite Datei: {csv_path.name}")
    
    df = pd.read_csv(csv_path, low_memory=False)
    
    #Checke, ob Datei bereits transponiert ist
    if "Bidding Zone" in df.columns:
        logger.info(f"Die Datei {csv_path.name} scheint bereits transponiert zu sein. Überspringe Verarbeitung.")
        return
    # Transponiere das ganze dataframe
    ty_file_transposed = df.transpose()
    
    # Lösche die erste Zeile über die Position 
    ty_file_transposed = ty_file_transposed.iloc[0:]
    ty_file_transposed = ty_file_transposed.iloc[:,2:]
    
    #Bennene erste Spalte in Bidding Zone um
    ty_file_transposed.rename(columns={ty_file_transposed.columns[0]: "Bidding Zone"}, inplace=True)
    
    #Benenne Spalte 2 bis 35 nach dem ersten Eintrag der Spalte um
    ty_file_transposed.columns = ["Bidding Zone"] + list(ty_file_transposed.iloc[0, 1:])
    #Lösche die erste Zeile des Frames
    ty_file_transposed = ty_file_transposed.iloc[1:, :]
    #Adde zum Namen von Spalte 29 bis 33 "Energy Storage (MWh)"
    ty_file_transposed.columns = [col if i < 28 or i > 33 else f"{col} - Energy Storage (MWh)" for i, col in enumerate(ty_file_transposed.columns)]
    #Lösche Spalte 29
    ty_file_transposed.drop(columns=ty_file_transposed.columns[27], inplace=True)
    
    # Speichere die transponierte Datei  
    output_filename = f"{csv_path.stem}.csv"
    output_path = output_dir / output_filename
    ty_file_transposed.to_csv(output_path, index=False)
    logger.info(f"Transponierte Datei gespeichert: {output_path}")
    
if __name__ == "__main__":
    year = input("Geben Sie das Jahr ein (z.B. 2030): ").strip()
    
    csv_full_path = SOURCE_DIR / f"TY {year}.csv"

    if not csv_full_path.exists():
        logger.error(f"Fehler: Datei nicht gefunden unter {csv_full_path}")
    else:
        transpose_ty_file(csv_full_path, OUTPUT_DIR, year) # 'year' an die Funktion übergeben
