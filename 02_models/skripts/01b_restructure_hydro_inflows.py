import shutil
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Pfade basierend auf deiner Struktur
SOURCE_DIR = Path("01_data/02_processed/Climate Data/Hydro Inflows")
TARGET_BASE_DIR = Path("01_data/02_processed/Climate Data/Hydro Inflows sorted")

def restructure_hydro_inflows():
    """
    Strukturiert Hydro-Inflow Daten um:
    1. Erstellt 5 Ordner basierend auf den Dateitypen (z.B. RoR, Reservoir).
    2. Verschiebt die Dateien dorthin und benennt sie nach dem Schema:
       Länderkürzel_Jahreszahl.csv (z.B. AL00_2030.csv)
    """
    if not SOURCE_DIR.exists():
        logger.error(f"Quellverzeichnis nicht gefunden: {SOURCE_DIR}")
        return

    logger.info(f"Starte Umstrukturierung von {SOURCE_DIR}")

    # Gehe durch jeden Zonen-Unterordner (z. B. PEMMDB_AL00_Hydro Inflow_2030)
    for subfolder in SOURCE_DIR.iterdir():
        if subfolder.is_dir():
            # Extrahiere Länderkürzel und Jahr:
            # 'PEMMDB_AL00_Hydro Inflow_2030' -> 'AL00_2030'
            clean_name = subfolder.name.replace("PEMMDB_", "").replace("_Hydro Inflow", "")
            
            # Verarbeite die 5 CSV-Dateien im Unterordner
            for csv_file in subfolder.glob("*.csv"):
                # Der Name der Datei (z.B. 'RoR') wird zum neuen Unterordner
                tech_category = csv_file.stem
                target_tech_dir = TARGET_BASE_DIR / tech_category
                target_tech_dir.mkdir(parents=True, exist_ok=True)
                
                new_filename = f"{clean_name}{csv_file.suffix}"
                target_path = target_tech_dir / new_filename
                
                shutil.copy2(csv_file, target_path)
                logger.info(f"Kopiert: {subfolder.name}/{csv_file.name} -> {tech_category}/{new_filename}")

    #Lösche den Ordner Hydro Inflows und den Unterordner Blad1
    shutil.rmtree(SOURCE_DIR)
    shutil.rmtree(TARGET_BASE_DIR / "Blad1")
    
    #Rename den neuen Ordner zurück zu Hydro Inflows
    TARGET_BASE_DIR.rename(SOURCE_DIR)
    
    logger.info(f"Fertig! Die sortierten Daten liegen in: {TARGET_BASE_DIR}")

if __name__ == "__main__":
    restructure_hydro_inflows()
    
    

