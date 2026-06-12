'''Filter die Dateien des Ordners PEMMCD National Estimates nach dem gewünschten Jahr und gruppiere nach den
Gruppenregeln, wie für die vorherigen Datensätze.'''

import pandas as pd
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


SOURCE_DIR = Path("01_data/03_filtered_data_for_prediction_year/ERAA 2022 PEMMDB National Estimates")
OUTPUT_DIR = Path("01_data/04b_accumulated_data_per_node/ERAA 2022 PEMMDB National Estimates")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Globale Gruppierungsregeln für alle Ordner.
# Wert: Mapping von Zielgruppe zu Liste der zusammenzufassenden Gebotszonen.
GROUP_RULES = {
    # Bestimmte Gebietszonen zusammenfassen.
    "adriatic": ["AL", "BA", "HR", "ME", "MK", "RS", "SI"],
    "baltic": ["EE", "LV", "LT"],
    "other eastern european": ["BG", "HU", "RO", "SK"],
}

FILE_NAMES = ["Capacity Derated.csv", "Explicit DSR.csv", "Forced Outage Rates.csv", "Must-run Capacities.csv",
              "Reserve Requirements.csv", "TY 2030.csv"] #Hier TY 2030.csv alternativ anpassen


#Filtere alle Zeilen nach dem Jahr, welches später im Terminal angegeben wird
def filter_by_year(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """Filtert die Zeilen eines DataFrames nach einem bestimmten Jahr."""
    if "TY" not in df.columns:
        logger.warning("Die Spalte 'TY' ist im DataFrame nicht vorhanden. Keine Filterung möglich.")
        return df
    filtered_df = df[df["TY"] == year]
    logger.info(f"Gefiltert nach Jahr {year}: {len(filtered_df)} Zeilen übrig von ursprünglich {len(df)}.")
    return filtered_df

def normalize_zone(candidate: str) -> str:
    """Normalisiert die Gebotszone, um Inkonsistenzen zu vermeiden (z.B. "DE" vs "DE1")."""
    candidate = candidate.upper()
    if len(candidate) == 4 and candidate[:2].isalpha() and candidate[2:].isdigit():
        return candidate[:2] #Mache aus xx00 --> xx
    if len(candidate) == 4 and candidate[:3].isalpha() and candidate[3:].isalpha():
        return candidate[:2] #Mache aus xxY0 --> xx
    if len(candidate) == 2 and candidate.isalpha():
        return candidate #Wenn schon xx: returne xx
    else:
        return candidate[:2]
    return candidate

def group_zone(zone: str, rules: dict[str, list[str]]) -> str:
    """Gruppiert eine Gebotszone basierend auf den definierten Regeln."""
    for group_name, zones in rules.items():
        if zone in zones:
            return group_name
    return zone # Wenn keine Regel zutrifft, gib die ursprüngliche Zone zurück

#Gehe jede Zeile einer .csv durch und wende normalize_zone an, um die Gebotszone zu normalisieren
def process_file(csv_path: Path, output_dir: Path):
    """Verarbeitet eine CSV: Filterung"""
    logger.info(f"Verarbeite Datei: {csv_path.name}")
    
    df = pd.read_csv(csv_path, low_memory=False)
    
    # Überprüfe, ob die Spalte 'TY' vorhanden ist, bevor du filterst
    if "TY" in df.columns:
        df = filter_by_year(df, 2030) #Hier das gewünschte Jahr angeben
    
    #Neben Bidding Zone ist auch Bidding Zone* als Spaltenname angegeben, dieses soll umbenannt werden in Bidding Zone
    if "Bidding Zone*" in df.columns:
        df.rename(columns={"Bidding Zone*": "Bidding Zone"}, inplace=True)
    # Normalisiere die Gebotszonen in der Spalte 'Zone' (oder wie auch immer sie heißt)
    if "Bidding Zone" in df.columns:
        df["Normalized_Zone"] = df["Bidding Zone"].apply(normalize_zone)
        logger.info(f"Gebotszonen normalisiert. Beispielwerte: {df['Normalized_Zone'].unique()[:5]}")
        df["Bidding Zone"] = df["Normalized_Zone"].apply(lambda z: group_zone(z, GROUP_RULES))
    else:
        logger.warning("Die Spalte 'Bidding Zone' ist im DataFrame nicht vorhanden. Keine Normalisierung möglich.")

    # Summiere jede Zeile der csv nach Bidding Zone und ggf. TY/Technology auf
    if "Bidding Zone" in df.columns:
        df = df.drop(columns=["Normalized_Zone"], errors="ignore")

        group_cols = ["Bidding Zone"]
        if "TY" in df.columns:
            group_cols.append("TY")
        if "Technology" in df.columns:
            group_cols.append("Technology")

        df = df.groupby(group_cols, as_index=False).sum()
        logger.info(f"Nach {', '.join(group_cols)} gruppiert. Beispielwerte: {df['Bidding Zone'].unique()[:5]}")
        
    # Speichere die verarbeitete Datei im Output-Verzeichnis
    output_path = output_dir / csv_path.name
    df.to_csv(output_path, index=False)
    logger.info(f"Verarbeitete Datei gespeichert: {output_path}")
    
    
def main():
    for file_name in FILE_NAMES:
        csv_path = SOURCE_DIR / file_name
        if csv_path.exists():
            process_file(csv_path, OUTPUT_DIR)
        else:
            logger.warning(f"Datei nicht gefunden: {csv_path}")
        

if __name__ == "__main__":
    main()

    