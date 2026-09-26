"""
Schritt 9: Kapazitäten und DSR je Modellzone aggregieren
========================================================
Liest die Tabellen aus config.FILTERED_DIR/<ERAA 2022 PEMMDB National Estimates>
(installierte Kapazitäten "TY <Zieljahr>.csv" aus Schritt 4, Explicit DSR,
Must-run, ...), filtert auf das Zieljahr, fasst ERAA-Zonen zu Modellzonen
zusammen (config.ZONE_GROUPS, Summe) und schreibt sie nach
config.ACCUMULATED_DIR/<ERAA 2022 PEMMDB National Estimates>.
"""

import logging
from pathlib import Path

import pandas as pd

import config

logger = logging.getLogger(__name__)

SOURCE_DIR = config.FILTERED_DIR / config.NATIONAL_ESTIMATES_DIRNAME
OUTPUT_DIR = config.ACCUMULATED_DIR / config.NATIONAL_ESTIMATES_DIRNAME


def file_names_for(year: int) -> list[str]:
    return ["Capacity Derated.csv", "Explicit DSR.csv", "Forced Outage Rates.csv",
            "Must-run Capacities.csv", "Reserve Requirements.csv", f"TY {year}.csv"]


#Filtere alle Zeilen nach dem Zieljahr
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
    return candidate[:2]

def group_zone(zone: str, rules: dict[str, list[str]]) -> str:
    """Gruppiert eine Gebotszone basierend auf den definierten Regeln."""
    for group_name, zones in rules.items():
        if zone in zones:
            return group_name
    return zone # Wenn keine Regel zutrifft, gib die ursprüngliche Zone zurück

#Gehe jede Zeile einer .csv durch und wende normalize_zone an, um die Gebotszone zu normalisieren
def process_file(csv_path: Path, output_dir: Path, year: int = config.TARGET_YEAR):
    """Verarbeitet eine CSV: Filterung"""
    logger.info(f"Verarbeite Datei: {csv_path.name}")

    df = pd.read_csv(csv_path, low_memory=False)

    # Überprüfe, ob die Spalte 'TY' vorhanden ist, bevor du filterst
    if "TY" in df.columns:
        df = filter_by_year(df, year)

    #Neben Bidding Zone ist auch Bidding Zone* als Spaltenname angegeben, dieses soll umbenannt werden in Bidding Zone
    if "Bidding Zone*" in df.columns:
        df.rename(columns={"Bidding Zone*": "Bidding Zone"}, inplace=True)
    # Normalisiere die Gebotszonen in der Spalte 'Zone' (oder wie auch immer sie heißt)
    if "Bidding Zone" in df.columns:
        df["Normalized_Zone"] = df["Bidding Zone"].apply(normalize_zone)
        logger.info(f"Gebotszonen normalisiert. Beispielwerte: {df['Normalized_Zone'].unique()[:5]}")
        df["Bidding Zone"] = df["Normalized_Zone"].apply(lambda z: group_zone(z, config.ZONE_GROUPS))
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


def main(year: int = config.TARGET_YEAR):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for file_name in file_names_for(year):
        csv_path = SOURCE_DIR / file_name
        if csv_path.exists():
            process_file(csv_path, OUTPUT_DIR, year)
        else:
            logger.warning(f"Datei nicht gefunden: {csv_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
