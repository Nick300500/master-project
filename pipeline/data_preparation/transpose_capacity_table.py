"""
Schritt 4: Kapazitätstabelle drehen
===================================
Die ERAA-Tabelle "TY <Zieljahr>.csv" (installierte Kapazitäten) hat die
Technologien in den Zeilen und die Zonen in den Spalten. Dieser Schritt dreht
sie so, dass jede Zone eine Zeile ist ("Bidding Zone" als erste Spalte),
benennt die Speicher-Spalten eindeutig ("... - Energy Storage (MWh)") und
entfernt die doppelte Zonenspalte in der Mitte.

Die Datei wird in config.FILTERED_DIR überschrieben. Ist sie schon gedreht,
passiert nichts. Muss vor den Schritten 5 (Gewichte für Wind/Solar) und 9
laufen.
"""

import logging
from pathlib import Path

import pandas as pd

import config

logger = logging.getLogger(__name__)

SOURCE_DIR = config.FILTERED_DIR / config.NATIONAL_ESTIMATES_DIRNAME
OUTPUT_DIR = SOURCE_DIR


def transpose_ty_file(csv_path: Path, output_dir: Path):
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


def main(year: int = config.TARGET_YEAR):
    csv_full_path = SOURCE_DIR / f"TY {year}.csv"
    if not csv_full_path.exists():
        logger.error(f"Fehler: Datei nicht gefunden unter {csv_full_path}")
        return
    transpose_ty_file(csv_full_path, OUTPUT_DIR)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
