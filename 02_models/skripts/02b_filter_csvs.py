"""
Einfaches Filter-Skript für CSV-Dateien in 01_data/02_processed.

- Feste Ordner werden komplett kopiert.
- In anderen Ordnern werden nur Dateien übernommen, deren die Jahreszahl im Ordnernamen steht.

Ziel: Kopiere ausgewählte CSVs nach
"01_data/02_processed/03_filtered_data_for_prediction_year".
"""

import logging
import shutil
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOURCE_DIR = Path("01_data/02_processed")
# Ziel: 03_filtered_data_for_prediction_year, damit die Originaldaten in 02_processed unverändert bleiben.
DEST_DIR = Path("01_data/03_filtered_data_for_prediction_year")

# Ordner, die immer komplett unverändert übernommen werden.
COPY_ALL_FOLDERS = [
    "Additional Data/Annex 1 - Input data",
    "ERAA 2022 PEMMDB National Estimates",
]

# Ordner, in denen nur Dateien mit der Jahreszahl im Namen übernommen werden.
YEAR_FILTER_FOLDERS = [
    "Climate Data/Hydro Inflows",
    "Climate Data/PECD_CSP",
    "Climate Data/Solar",
    "Climate Data/Wind onshore",
    "Climate Data/Wind offshore",
    "Demand/Demand Time Series",
    "Demand/Detailed demand (batteries, EVs, HPs)",
    "Transfer capacities"]


def find_csv_files(root_dir):
    root_dir = Path(root_dir)
    return sorted(root_dir.rglob("*.csv"))


def path_matches_folder(relative_path, folder):
    """Prüfe, ob ein relativer Pfad in einem angegebenen Ordner liegt."""
    relative_path = Path(relative_path)
    folder = Path(folder)
    if not folder.parts:
        return False
    return tuple(relative_path.parts[: len(folder.parts)]) == tuple(folder.parts)


def copy_file(csv_path, source_root, dest_root):
    relative_path = csv_path.relative_to(source_root)
    target_path = dest_root / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(csv_path, target_path)
    logger.info(f"Kopiere: {relative_path}")


def main(year):
    source_dir = SOURCE_DIR
    dest_dir = DEST_DIR
    dest_dir.mkdir(parents=True, exist_ok=True)

    csv_files = find_csv_files(source_dir)
    logger.info(f"Gefundene CSV-Dateien: {len(csv_files)}")

    copied = 0
    for csv_path in csv_files:
        rel_path = csv_path.relative_to(source_dir)

        if any(path_matches_folder(rel_path, folder) for folder in COPY_ALL_FOLDERS):
            copy_file(csv_path, source_dir, dest_dir)
            copied += 1
            continue

        if year and any(path_matches_folder(rel_path, folder) for folder in YEAR_FILTER_FOLDERS):
            # Jahreszahl steht im Ordnernamen; prüfe alle Teile des relativen Pfads
            if any(year in part for part in rel_path.parts):
                copy_file(csv_path, source_dir, dest_dir)
                copied += 1
            continue

    logger.info(f"Fertig. Kopiert: {copied} Dateien nach {dest_dir}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", default="2030",
                        help="Zieljahr (Target Year), z.B. 2030 (Default: 2030)")
    args = parser.parse_args()

    main(args.year.strip())
