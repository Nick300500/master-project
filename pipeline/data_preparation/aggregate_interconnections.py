"""
Schritt 8: Leitungskapazitäten je Zonenpaar aggregieren
=======================================================
Liest HVAC.csv und HVDC.csv (stündliche NTC-Werte je ERAA-Grenze) aus
config.FILTERED_DIR/Transfer capacities, fasst Grenzen zwischen denselben
Modellzonen zusammen (Summe), entfernt Leitungen innerhalb einer Modellzone
(z.B. HR-SI innerhalb "adriatic") und schreibt das Ergebnis nach
config.ACCUMULATED_DIR/Transfer capacities.

Bekannter Rohdatenfehler (HVDC, TY2030): Finnland-Estland steht zweimal als
"EE00 -> FI00" in der Datei, die Gegenrichtung fehlt. Wird automatisch
korrigiert (Warnung im Log).

"Max limit.csv" wird nicht verändert; die Kopie aus Schritt 6 wird direkt
vom Modell gelesen (pipeline/model/max_limits.py).
"""

import logging
from pathlib import Path

import pandas as pd

import config

logger = logging.getLogger(__name__)

SOURCE_DIR = config.FILTERED_DIR / "Transfer capacities"
OUTPUT_DIR = config.ACCUMULATED_DIR


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

    # Spalten 0-1 sind Metadaten (Year, Week, etc.), ab Spalte 2 die Grenzen
    data_cols_df = df.iloc[:, 2:]

    # Zeile 11/12 (Index 10/11) der Datenspalten: From-/To-Zone jeder Grenze
    from_zones_raw = data_cols_df.iloc[10].copy()
    to_zones_raw = data_cols_df.iloc[11].copy()

    # ── Duplikate auf granularer Zonenebene erkennen ──
    # Bekannter Fehler in den ERAA-Rohdaten (HVDC TY2030): Die Verbindung
    # FI-EE (EstLink) steht in zwei Spalten, beide als "EE00 -> FI00"
    # beschriftet; die Rückrichtung "FI00 -> EE00" fehlt. Fehlt zu einem
    # doppelt vorkommenden Paar die Gegenrichtung in der ganzen Datei, wird
    # die zweite Spalte als Rückrichtung umgedreht. Andernfalls (Gegenrichtung
    # vorhanden) ist es ein echtes Duplikat und wird ausgeschlossen.
    def _pair(i):
        return (str(from_zones_raw.iloc[i]).strip().upper(),
                str(to_zones_raw.iloc[i]).strip().upper())

    all_raw_pairs = {_pair(i) for i in range(len(from_zones_raw))}
    seen_raw_pairs = set()
    duplicate_indices = set()
    for i in range(len(from_zones_raw)):
        raw_pair = _pair(i)
        if raw_pair in seen_raw_pairs:
            reverse_pair = (raw_pair[1], raw_pair[0])
            if reverse_pair not in all_raw_pairs:
                from_val, to_val = from_zones_raw.iloc[i], to_zones_raw.iloc[i]
                from_zones_raw.iloc[i], to_zones_raw.iloc[i] = to_val, from_val
                seen_raw_pairs.add(reverse_pair)
                all_raw_pairs.add(reverse_pair)
                logger.warning(f"  {csv_path.name}: Rohspalte {i} doppelt beschriftet "
                                f"als {raw_pair}, Gegenrichtung fehlt - "
                                f"wird als {reverse_pair} gewertet")
            else:
                duplicate_indices.add(i)
                logger.warning(f"  {csv_path.name}: doppelte Rohspalte {i} für "
                                f"Zonenpaar {raw_pair} - wird übersprungen")
        else:
            seen_raw_pairs.add(raw_pair)

    valid_col_indices = []
    resolved_from_groups = []
    resolved_to_groups = []

    for i in range(len(from_zones_raw)):
        if i in duplicate_indices:
            continue
        g_from = resolve_group(from_zones_raw.iloc[i], config.ZONE_GROUPS)
        g_to = resolve_group(to_zones_raw.iloc[i], config.ZONE_GROUPS)

        if g_from != "UNKNOWN" and g_to != "UNKNOWN":
            valid_col_indices.append(i)
            resolved_from_groups.append(g_from)
            resolved_to_groups.append(g_to)
        else:
            logger.debug(f"  Überspringe Spalte {i} aufgrund unbekannter Zone: "
                          f"Von='{from_zones_raw.iloc[i]}'->'{g_from}', "
                          f"Nach='{to_zones_raw.iloc[i]}'->'{g_to}'")

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
    # Nur die Leitungs-Dateien aggregieren. "Max limit.csv" (Länder-Obergrenzen)
    # hat ein anderes Layout und wird unverändert von max_limits.py gelesen.
    for csv_path in SOURCE_DIR.rglob("*.csv"):
        if csv_path.name not in ("HVAC.csv", "HVDC.csv"):
            logger.info(f"Überspringe {csv_path.name} (keine HVAC/HVDC-Datei)")
            continue
        process_file(csv_path, OUTPUT_DIR)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
