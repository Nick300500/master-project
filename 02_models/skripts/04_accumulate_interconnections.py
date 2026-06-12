"""
In diesem Skript sollen die Interconnections zwischen den einzelnen Gebotszonen akkumuliert werden,
sodass diese in das PyPSA-Modell gegeben werden können.

Es sollen dabei alle Interconnections einer Gebotszone akkumuliert werden, sowie Interconnections zwischen einzelnen Bereichen
einer Gebotszone exkludiert werden.

Außerdem wird im Ordner ERAA 2022 PEMMDB National Estimates die TY des ausgewählten Jahres transponiert und abgelegt für 
die Weiterverarbeitung
"""

from pathlib import Path
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOURCE_DIR = Path("01_data/03_filtered_data_for_prediction_year/Transfer capacities")
OUTPUT_DIR = Path("01_data/04b_accumulated_data_per_node")

# Globale Gruppierungsregeln für alle Ordner.
# Wert: Mapping von Zielgruppe zu Liste der zusammenzufassenden Gebotszonen.
GROUP_RULES = {
    # Bestimmte Gebietszonen zusammenfassen.
    "adriatic": ["AL", "BA", "HR", "ME", "MK", "RS", "SI"],
    "baltic": ["EE", "LV", "LT"],
    "other eastern european": ["BG", "HU", "RO", "SK"],
}

def normalize_zone(candidate: str) -> str:
    """Normalisiert die Gebotszone, um Inkonsistenzen zu vermeiden (z.B. "DE" vs "DE1")."""
    candidate = candidate.upper()
    if len(candidate) == 4 and candidate[:2].isalpha() and candidate[2:].isdigit():
        return candidate[:2] #Mache aus xx00 --> xx
    if len(candidate) == 2 and candidate.isalpha():
        return candidate #Wenn schon xx: returne xx
    return candidate

def resolve_group(zone: any, rules: dict[str, list[str]]) -> str:
    """Bestimme die Gruppenzugehörigkeit einer Gebotszone anhand der definierten Regeln."""
    zone_str = str(zone).strip().upper() # Rohwert in String umwandeln und bereinigen

    # Normalisiere die Zone mit der dedizierten Funktion
    normalized_zone = normalize_zone(zone_str)

    # Prüfe gegen explizite Gruppierungsregeln
    for group_name, zones in rules.items():
        if normalized_zone in zones:
            return group_name

    # Allgemeine Präfixregel: gleiche Anfangsbuchstaben gruppieren.
    if len(normalized_zone) >= 2 and normalized_zone[:2].isalpha():
        return normalized_zone[:2]

    return normalized_zone # Wenn keine Regel zutrifft, gib die normalisierte Zone zurück

def process_file(csv_path: Path, output_dir: Path):
    """Verarbeitet eine Interconnection-CSV: Gruppierung, Filterung und Summation."""
    logger.info(f"Verarbeite Datei: {csv_path.name}")
    
    # Lade ohne Header, um die ersten 17 Zeilen manuell zu kontrollieren
    df = pd.read_csv(csv_path, header=None, low_memory=False)
    
    # Spalten 0-1 sind Metadaten (Year, Week, etc.)
    meta_cols_df = df.iloc[:, :2]
    data_cols_df = df.iloc[:, 2:]
    
    # In HVAC.csv liegen die Zonen-Namen in Index 16 & 17 (Zeile 17/18)
    from_zones_raw = data_cols_df.iloc[10]
    to_zones_raw = data_cols_df.iloc[11]
    
    # Identifiziere gültige Interconnection-Spalten
    # Eine Spalte ist gültig, wenn sowohl from_zone als auch to_zone nicht UNKNOWN sind
    valid_col_indices = []
    resolved_from_groups = []
    resolved_to_groups = []
    
    for i in range(len(from_zones_raw)):
        g_from = resolve_group(from_zones_raw.iloc[i], GROUP_RULES)
        g_to = resolve_group(to_zones_raw.iloc[i], GROUP_RULES)
        
        if g_from != "UNKNOWN" and g_to != "UNKNOWN":
            valid_col_indices.append(i)
            resolved_from_groups.append(g_from)
            resolved_to_groups.append(g_to)
        else:
            logger.debug(f"  Überspringe Spalte {i} aufgrund unbekannter Zone: Von='{from_zones_raw.iloc[i]}'->'{g_from}', Nach='{to_zones_raw.iloc[i]}'->'{g_to}'")

    if not valid_col_indices:
        logger.warning(f"Keine gültigen Zonenpaare in {csv_path.name} gefunden (alle UNKNOWN).")
        return

    # Filtere numerische Daten, um nur gültige Spalten einzuschließen
    numeric_data_valid_cols = data_cols_df.iloc[18:, valid_col_indices].apply(pd.to_numeric, errors='coerce').fillna(0)
    
    group_pairs = list(zip(resolved_from_groups, resolved_to_groups))
    
    # Trenne Metadaten-Zeilen von den numerischen Daten
    # Die Zeilen 0-17 sind Metadaten, ab Zeile 18 beginnen die numerischen Werte
    
    # Aggregations-Logik
    aggregated_columns = {}
    
    internal_connection_count = 0
    external_connection_count = 0
    
    for i, (g_from, g_to) in enumerate(group_pairs): # Iteriere über bereits gefilterte, gültige Paare
        # Exkludiere interne Verbindungen
        if g_from == g_to:
            internal_connection_count += 1
            logger.debug(f"  Filtere interne Verbindung: ({g_from}, {g_to}) für Spaltenindex {valid_col_indices[i]}")
            continue
            
        external_connection_count += 1
        pair_key = (g_from, g_to)
        
        # Der Index 'i' bezieht sich hier auf den Index innerhalb von `group_pairs` und `numeric_data_valid_cols`
        if i >= numeric_data_valid_cols.shape[1]:
            logger.warning(f"  Spalte {i} für Paar ({g_from}, {g_to}) außerhalb der Grenzen von numeric_data_valid_cols. Überspringe.")
            continue

        col_data = numeric_data_valid_cols.iloc[:, i]
        
        if pair_key in aggregated_columns: # Wenn die Gruppe schon existiert, addiere die Werte
            aggregated_columns[pair_key] += col_data
        else:
            aggregated_columns[pair_key] = col_data.copy() # Ansonsten erstelle neuen Eintrag in dict
            
    logger.info(f"  Zusammenfassung für {csv_path.name}:")
    logger.info(f"    Gesamte Rohspalten in data_cols_df: {data_cols_df.shape[1]}")
    logger.info(f"    Gültige Zonenpaare identifiziert: {len(valid_col_indices)}")
    logger.info(f"    Interne Verbindungen (g_from == g_to) nach Gruppierung: {internal_connection_count}")
    logger.info(f"    Externe Verbindungen nach Filterung gefunden: {external_connection_count}")
    logger.info(f"    Eindeutige aggregierte externe Verbindungen: {len(aggregated_columns)}")

    if not aggregated_columns:
        logger.warning(f"Keine externen Verbindungen in {csv_path.name} nach Gruppierung gefunden.")
        return

    # Baue den neuen Dataframe zusammen
    # 1. Erstelle Header für die neuen Spalten
    new_data_df = pd.DataFrame(aggregated_columns)
    
    # 2. Rekonstruiere die Struktur (Metadaten-Spalten + Aggregierte Spalten)
    # Für die ersten 12 Zeilen der Metadaten-Spalten nehmen wir das Original
    final_meta = df.iloc[:, :2] # Originale Metadaten-Spalten (Datum und Nummer)
    
    # Erstelle die Header-Zeilen für die neuen gruppierten Spalten
    header_rows = pd.DataFrame(index=range(16), columns=new_data_df.columns)
    for pair in new_data_df.columns:
        header_rows.loc[10, [pair]] = pair[0] # From Group
        header_rows.loc[11, [pair]] = pair[1] # To Group
    
    # Verbinde Header und Daten
    combined_data = pd.concat([header_rows, new_data_df], axis=0).reset_index(drop=True)
    
    # Verbinde mit den linken Metadaten-Spalten (Year, Week...)
    final_df = pd.concat([final_meta, combined_data], axis=1)
    
    # Speichern
    rel_path = csv_path.relative_to(SOURCE_DIR)
    out_file = output_dir / "Transfer capacities" / rel_path
    out_file.parent.mkdir(parents=True, exist_ok=True)
    
    final_df.to_csv(out_file, index=False, header=False)
    logger.info(f"  -> Gespeichert: {out_file}")
    
def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Suche alle CSVs in den Transfer capacities Unterordnern
    for csv_path in SOURCE_DIR.rglob("*.csv"):
        process_file(csv_path, OUTPUT_DIR)

if __name__ == "__main__":
    main()