"""
Schritt 1: Excel -> CSV
=======================
Liest alle Excel-Dateien aus config.RAW_DIR und schreibt jeden Reiter (Sheet)
als eigene CSV nach config.PROCESSED_DIR. Die Ordnerstruktur bleibt erhalten:
    01_raw/.../Datei.xlsx  ->  02_processed/.../Datei/<Reiter>.csv

Bereits vorhandene CSVs werden übersprungen (Neu-Konvertierung mit
`python main/prepare_data.py --force`).
"""

import logging
from pathlib import Path

import pandas as pd

import config

logger = logging.getLogger(__name__)


def find_excel_files(root_dir): #Input: Oberknoten, welcher durchsucht werden soll
    """
    Gibt Excel-Dateien im Verzeichnis-Tree zurück

    Args:
        root_dir: Oberknoten, dessen Äste bis in die Leafs durchsucht werden sollen

    Returns:
        list: Liste der gefundenen Excel-Dateien
    """

    root_dir = Path(root_dir)
    #listet alle global gefundenen Excel-files auf
    excel_files = list(root_dir.rglob("*.xlsx")) + list(root_dir.rglob("*.xls"))
    return sorted(set(excel_files))


def convert_excel_to_csv(excel_file, output_dir, skip_existing=True):
    """
    Konvertiert eine Excel-Datei mit mehreren Reitern in einzelne CSVs.
    Hier wird eine einzelne Datei mit x-Reitern un x-.csv-Files aufgeteilt

    Args:
        excel_file (Path): Pfad zur Excel-Datei
        output_dir (Path): Zielverzeichnis für CSVs
        skip_existing (bool): Vorhandene CSV-Dateien überspringen

    Returns:
        dict: Dictionary mit Sheet-Namen und entsprechenden DataFrames
    """
    try:
        excel_file = Path(excel_file) #Pfad-Name --> Pfad-Objekt
        xls = pd.ExcelFile(excel_file) #Excel-Datei wird geöffner

        logger.info(f"Lese Datei: {excel_file.name}")
        logger.info(f"Gefundene Reiter: {xls.sheet_names}") #Liste aller Sheet-Namen

        dataframes = {} #Dictionary wird erstellt, in welches Name und DF jedes sheets gelegt wird

        for sheet_name in xls.sheet_names: #Für jedes Sheet in der Namens-Liste
            safe_name = sheet_name.replace('/', '_').replace('\\', '_') #Umwandlung in gültige Zeichen
            output_file = output_dir / f"{safe_name}.csv" #Pfad, in dem .csv gelegt werden soll

            if skip_existing and output_file.exists(): #Wenn Datei schon existiert wird skipped
                logger.info(f"  - '{sheet_name}': bereits vorhanden, überspringe")
                try:
                    df = pd.read_csv(output_file) #Laden von vorhandener File
                    dataframes[sheet_name] = df #wird dann ins dictionary übernommen
                except Exception as e: # (standard exception call) Falls das nicht funktioniert, wird versucht sheet separat neu zu laden
                    logger.warning(f"  ! Fehler beim Lesen vorhandener CSV '{output_file.name}': {e}")
                    df = pd.read_excel(excel_file, sheet_name=sheet_name) #Lies Excel ein
                    df.to_csv(output_file, index=False) #Mach Excel to .csv
                    dataframes[sheet_name] = df #Adde to dictionary
                    logger.info(f"    Erneut geschrieben: {output_file.name}")
                continue

            try:
                df = pd.read_excel(excel_file, sheet_name=sheet_name) #Lies Excel ein
                dataframes[sheet_name] = df #Adde Excel to dict
                output_file.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(output_file, index=False) #Mache Excel --> .csv
                logger.info(f"  ✓ '{sheet_name}': {len(df)} Zeilen → {output_file.name}")
            except Exception as e:
                logger.error(f"  ✗ Fehler bei Sheet '{sheet_name}': {e}")

        return dataframes #Gib das dict mit allen .csv Dateien zurück
    except Exception as e:
        logger.error(f"Fehler beim Lesen von {excel_file}: {e}")
        return {}

def process_all_excel_files(raw_dir, processed_dir, skip_existing=True):
    """
    Verarbeitet alle Excel-Dateien in einem Verzeichnis.
    Notwendig, um durch einen ganzen Ordner durchzugehen und jede Excel-File zu laden,
    um daraufhin die Excel-Reiter --> .csv-Files zu transformieren

    Args:
        raw_dir (Path): Verzeichnis mit Excel-Dateien
        processed_dir (Path): Zielverzeichnis für CSVs
        skip_existing (bool): Vorhandene CSV-Dateien überspringen

    Returns:
        dict: Alle DataFrames organisiert nach Datei und Sheet
    """
    all_dataframes = {} #New dict für alle Excel-Files

    if not raw_dir.exists(): #Falls dict nicht vorhanden ist: Fehlermeldung
        logger.error(f"Verzeichnis nicht gefunden: {raw_dir}")
        return all_dataframes

    excel_files = find_excel_files(raw_dir) #Gib alle Excel-files in angegebenem VErzeichnis aus

    if not excel_files: #Falls Keine Excel vorhanden: Fehlermeldung
        logger.warning(f"Keine Excel-Dateien in {raw_dir} und Unterordnern gefunden")
        return all_dataframes

    logger.info(f"Gefundene Dateien: {len(excel_files)}\n") #Info: Anzahl Excel-Files gefunden

    for excel_file in excel_files: #Erstellt im Zielordner gleiche Ordnerstruktur wie im Stammordner
        relative_parent = excel_file.relative_to(raw_dir).parent #Pfad von Excel relativ von Ausgangsordner
        file_output_dir = processed_dir / relative_parent / excel_file.stem #Neuer Ausgangsordner für .csv-Files
        file_output_dir.mkdir(parents=True, exist_ok=True) #Falls Ausgabeordner nicht existiert: Erstelle neu

        #Nimmt nun jede Excel-Datei und wandelt sie in .csv um
        dataframes = convert_excel_to_csv(excel_file, file_output_dir, skip_existing=skip_existing)
        all_dataframes[str(excel_file.relative_to(raw_dir))] = dataframes
        #Speichert Dataframes in selbiger Struktur wie Ausgangsordner

    return all_dataframes

def main(skip_existing=True, raw_dir=config.RAW_DIR, processed_dir=config.PROCESSED_DIR):
    """Hauptfunktion: Startet die Konvertierung."""
    processed_dir.mkdir(parents=True, exist_ok=True)
    logger.info("=" * 60)
    logger.info("EXCEL ZU CSV KONVERTIERUNG")
    logger.info("=" * 60 + "\n")

    #Startet mit der Verarbeitung aller Excel-Dateien
    # In Process... werden alle Excel Files gefunden und in einem For-Loop dann in .csv gewandelt
    all_data = process_all_excel_files(raw_dir, processed_dir, skip_existing=skip_existing)

    logger.info("\n" + "=" * 60) #Logger-Stuff für übersichtlichere Darstellung
    logger.info("ZUSAMMENFASSUNG")
    logger.info("=" * 60)
    logger.info(f"Verarbeitete Dateien: {len(all_data)}")
    for file_name, sheets in all_data.items():
        logger.info(f"  {file_name}: {len(sheets)} Sheets")
    logger.info(f"\nAlle CSVs gespeichert in: {processed_dir}")

    return all_data

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
