"""
Skript-Grundgerüst für die Datenakkumulation pro Netz-Knoten.

Dieses Skript soll Daten aus verarbeiteten CSV-Dateien einlesen,
pro Knotengruppe zusammenfassen und als aggregierte Tabelle speichern.

"""

from pathlib import Path
import logging
import re
import csv
import shutil

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)



SOURCE_DIR = Path("01_data/03_filtered_data_for_prediction_year")
OUTPUT_DIR = Path("01_data/04b_accumulated_data_per_node")

def remove_duplicate_files(root_dir: Path):
    """Entferne CSV-Duplikate, die ein '(' im Dateinamen enthalten."""
    removed = 0 #counter
    for csv_path in sorted(root_dir.rglob("*.csv")):
        if "(" in csv_path.stem: #sollte ein ( im Dateinamen sein
            csv_path.unlink() #lösche die Datei
            removed += 1
    logger.info(f"Doppelte Dateien entfernt: {removed}")

# Globale Gruppierungsregeln für alle Ordner.
# Wert: Mapping von Zielgruppe zu Liste der zusammenzufassenden Gebotszonen.
GROUP_RULES = {
    # Bestimmte Gebietszonen zusammenfassen.
    "adriatic": ["AL", "BA", "HR", "ME", "MK", "RS", "SI"],
    "baltic": ["EE", "LV", "LT"],
    "other eastern european": ["BG", "HU", "RO", "SK"],
}

# Ordner, die von der Akkumulation ausgeschlossen werden sollen.
EXCLUDE_FOLDERS = [
    "Additional Data",
    "ERAA 2022 PEMMDB National Estimates",
    "Transfer capacities",
    "Demand", "Hydro Inflows","PECD_CSP","Solar"
]

ZONE_PATTERN = re.compile(r"\b([A-Za-z]{2}\d{0,2})\b")


def is_excluded_folder(relative_folder: Path) -> bool:
    if not relative_folder.parts:
        return False
    return any(part in EXCLUDE_FOLDERS for part in relative_folder.parts) # Wenn in Ausschlussordnern: True zurückgeben, sonst False


def resolve_group(zone: str, rules: dict[str, list[str]]) -> str:
    """Bestimme die Gruppenzugehörigkeit einer Gebotszone anhand der definierten Regeln."""
    for group_name, zones in rules.items(): # Checke nach gruppierten Zonen, z.B. "adriatic"
        if zone in zones:
            return group_name

    # Allgemeine Präfixregel: gleiche Anfangsbuchstaben gruppieren.
    if len(zone) >= 2 and zone[:2].isalpha():
        return zone[:2]

    return zone

###Bis hier hin: ALles klar und passt!

ZONE_CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2}\d{2})(?![A-Za-z0-9])")
ZONE_SHORT_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2})(?![A-Za-z0-9])")


def normalize_zone(candidate: str) -> str: 
    """Normalisiert die Gebotszone, um Inkonsistenzen zu vermeiden (z.B. "DE" vs "DE1")."""
    if pd.isna(candidate):
        return "UNKNOWN"
        
    candidate = str(candidate).upper()
    if len(candidate) == 4 and candidate[:2].isalpha() and candidate[2:].isdigit():
        return candidate[:2] #Mache aus xx00 --> xx
    if len(candidate) == 2 and candidate.isalpha():
        return candidate #Wenn schon xx: returne xx
    return candidate


def extract_zone_from_path(csv_path: Path) -> str:
    """Leite die Gebotszone aus dem CSV-Dateinamen und dem Pfad ab."""
    for part in csv_path.parts:
        for match in ZONE_CODE_PATTERN.findall(part):
            return normalize_zone(match)

    for part in csv_path.parts:
        for match in ZONE_SHORT_PATTERN.findall(part):
            normalized = normalize_zone(match)
            if normalized in {z for zones in GROUP_RULES.values() for z in zones}:
                return normalized

    stem = csv_path.stem
    fallback = stem.split()[0].split("_")[0].upper()
    return normalize_zone(fallback)


def parse_value(value: str):
    text = value.strip()
    if text == "":
        return ""
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return text


def is_numeric_value(value) -> bool:
    """Check if a parsed value is numeric (int or float)."""
    return isinstance(value, (int, float))


def format_value(value):
    if isinstance(value, float):
        return str(value).rstrip("0").rstrip(".") if "." in str(value) else str(value)
    return str(value)


def try_float(value):
    """Try to parse a value as float. Return None if not possible."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if text == "":
            return None
        try:
            return float(text.replace(",", "."))
        except ValueError:
            return None
    return None


import pandas as pd

# ── NEU: p_nom Tabelle einmal global laden ──────────────────────────────────
PNOM_PATH = Path("01_data/03_filtered_data_for_prediction_year/ERAA 2022 PEMMDB National Estimates/TY 2030.csv")

def load_pnom_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    df.index = df.index.map(normalize_zone)
    # Doppelte Zonen (z.B. GR01+GR02 -> GR) aufsummieren
    return df.groupby(df.index).sum()

PNOM_TABLE = load_pnom_table(PNOM_PATH) if PNOM_PATH.exists() else None


# ── NEU: Hilfsfunktion – p_nom einer Zone für eine Technologie ─────────────
def get_pnom_weight(zone: str, folder_name: str) -> float:
    if PNOM_TABLE is None:
        return 1.0
    zone_up = normalize_zone(zone)
    if zone_up not in PNOM_TABLE.index:
        return 1.0
    matching_cols = [c for c in PNOM_TABLE.columns if any(
        keyword in folder_name.lower() for keyword in c.lower().split()
    )]
    if not matching_cols:
        return 1.0
    val = PNOM_TABLE.loc[zone_up, matching_cols[0]]
    # Falls Series (z.B. durch Duplikate im Index): Summe nehmen
    if isinstance(val, pd.Series):
        val = val.sum()
    return float(val) if pd.notna(val) and float(val) > 0 else 1.0

def accumulate_group_files(output_folder: Path, group_name: str, files: list[Path],  folder_name: str = "") -> None:
    """Akkumuliere CSV-Dateien einer Gruppe.

    Basierend auf der Datenstruktur:
    - Zeilen 1-11 und Spalten 1-2: Metadaten, werden aus der ersten Datei übernommen
    - Ab Zeile 12 und Spalte 3: 
        * konventionelle Plants (p_nom): summieren  (bisheriges Verhalten)
        * CF-Zeitreihen (vRES/Hydro):   gewichteter Durchschnitt nach p_nom
    """
    if not files:
        return

    # Store all rows from all files, keyed by (row_index, first_column_value)
    # We'll process them to determine what to keep vs sum
    all_file_rows = []  # list of list of lists (files -> rows -> cells)

    header = None

    file_weights = []
    for csv_path in files:
        zone = extract_zone_from_path(csv_path)
        weight = get_pnom_weight(zone, folder_name)
        file_weights.append(weight)
        logger.info(f"    Gewicht für {csv_path.name} (zone={zone}): {weight:.2f} MW")

    total_weight = sum(file_weights)
    # Normierte Gewichte (0–1, summieren sich zu 1)
    norm_weights = [w / total_weight if total_weight > 0 else 1.0 / len(files)
                    for w in file_weights]

    for csv_path in files:
        with csv_path.open("r", newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            continue
        if header is None:
            header = rows[0]
        all_file_rows.append(rows)

    if not all_file_rows:
        return

    first_file_rows = all_file_rows[0]
    result_rows = [list(first_file_rows[0])]
    max_rows = max(len(f) for f in all_file_rows)

    # ── NEU: Erkenne ob Ordner CF-Zeitreihen enthält (dann gewichten) ───────
    # CF-Ordner: Wind, Solar – diese haben Werte zwischen 0 und 1
    # p_nom-Ordner (PEMMDB) und hydro: diese haben große MW-Werte → summieren
    is_cf_folder = any(keyword in folder_name.lower() for keyword in
                       ["wind", "solar", "pv","capacity factor"])
    is_hydro_folder = any(keyword in folder_name.lower() for keyword in ["hydro", "inflow"])

    for row_idx in range(1, max_rows):
        if row_idx < len(first_file_rows):
            base_row = list(first_file_rows[row_idx])
        else:
            base_row = []

        # Metadaten-Zeilen: unverändert aus erster Datei
        if row_idx <= 11:
            # SONDERFALL HYDRO: Summiere Zeilen 5 und 6 und 7 (Index 5 und 6) NUR Spalte C (Index 2)
            if is_hydro_folder and row_idx in [4, 5, 6]:
                result_row = list(base_row) # Starte mit der Basiszeile, um andere Spalten zu erhalten

                target_col_idx = 2 # Spalte C in Excel (0-indiziert)
                
                # Initialisiere den Wert, der akkumuliert werden soll
                current_sum = try_float(result_row[target_col_idx]) if target_col_idx < len(result_row) else 0.0
                if current_sum is None: # Falls der Startwert nicht numerisch ist, beginne bei 0
                    current_sum = 0.0

                for other_file_rows in all_file_rows[1:]: # Iteriere durch die anderen Dateien
                    if row_idx >= len(other_file_rows): # Prüfe, ob die Zeile in der anderen Datei existiert
                        continue
                    other_row = other_file_rows[row_idx]

                    if target_col_idx < len(other_row): # Prüfe, ob die Zielspalte in der anderen Zeile existiert
                        other_val = try_float(other_row[target_col_idx])
                        if other_val is not None:
                            current_sum += other_val

                # Aktualisiere nur dieses eine Feld in der Zeile
                result_row[target_col_idx] = current_sum
                result_rows.append(result_row)
            else:
                result_rows.append(base_row)
            continue

        result_row = list(base_row)

        if is_cf_folder:
            # ── NEU: Gewichteter Durchschnitt für CF-Werte ──────────────
            # Initialisiere mit 0 für alle numerischen Spalten
            weighted_sums = {}
            for col_idx in range(2, max(len(r) for r in all_file_rows if row_idx < len(r))):
                weighted_val = 0.0
                has_any_value = False
                for file_rows, w in zip(all_file_rows, norm_weights):
                    if row_idx >= len(file_rows):
                        continue
                    row = file_rows[row_idx]
                    # In accumulate_group_files, im is_cf_folder Block:
                    val = try_float(row[col_idx]) if col_idx < len(row) else None
                    if val is not None and not (isinstance(val, float) and val != val):  # kein NaN
                        weighted_val += val * w
                        has_any_value = True
                if has_any_value:
                    weighted_sums[col_idx] = weighted_val

            for col_idx, val in weighted_sums.items():
                if col_idx >= len(result_row):
                    result_row.append(val)
                else:
                    result_row[col_idx] = val

        else:
            # ── Bisheriges Verhalten: Summieren (für p_nom etc.) ─────────
            for other_file_rows in all_file_rows[1:]:
                if row_idx >= len(other_file_rows):
                    continue
                other_row = other_file_rows[row_idx]
                for col_idx in range(2, max(len(result_row), len(other_row))):
                    if col_idx >= len(result_row):
                        result_row.append("")
                    base_val = result_row[col_idx]
                    other_val = other_row[col_idx] if col_idx < len(other_row) else ""
                    base_float = try_float(base_val)
                    other_float = try_float(other_val)
                    if base_float is not None and other_float is not None:
                        result_row[col_idx] = base_float + other_float
                    elif base_float is None and other_float is not None:
                        result_row[col_idx] = other_float

        result_rows.append(result_row)

    out_file = output_folder / f"{group_name}_accumulated.csv"
    with out_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        for row in result_rows:
            writer.writerow([format_value(value) for value in row])

    logger.info(f"  -> Akkumulierte Datei gespeichert in {out_file}")

def accumulate_data_per_node(source_dir: Path, output_dir: Path):
    """Akkumuliere CSV-Daten pro Knotengruppe pro Ordner.
    Für jeden Ordner in source_dir:
    - Alle CSV-Dateien einlesen
    - Zone nur aus dem Dateinamen ableiten
    - Gruppe mittels resolve_group() bestimmen
    - Werte für diese Gruppe akkumulieren
    - Ergebnisse pro Ordner in output_dir speichern"""
    logger.info(f"Starte Akkumulation von Daten in {source_dir}")
    logger.info(f"Zielverzeichnis ist {output_dir}")

    # Suche rekursiv alle Ordner, aber verarbeite nur die Dateien direkt in jedem Ordner.
    for folder in sorted(source_dir.glob("**/")):
        if not folder.is_dir():
            continue

        relative_folder = folder.relative_to(source_dir)

        if is_excluded_folder(relative_folder):
            logger.info(f"  -> Überspringe ausgeschlossenen Ordner: {relative_folder}")
            continue

        csv_paths = sorted(folder.glob("*.csv"))
        if not csv_paths:
            continue

        output_folder = output_dir / relative_folder
        output_folder.mkdir(parents=True, exist_ok=True)
        logger.info(f"Verarbeite Ordner: {relative_folder} (gleiche globale Regeln für alle Ordner)")

        # Nur die CSV-Dateien im aktuellen Ordner, nicht aus Unterordnern.
        group_files: dict[str, list[Path]] = {}
        for csv_path in csv_paths:
            zone = extract_zone_from_path(csv_path)
            group = resolve_group(zone, GROUP_RULES)
            logger.info(f"  - {csv_path.name} -> zone={zone}, group={group}")
            group_files.setdefault(group, []).append(csv_path)

        for group_name, files in sorted(group_files.items()):
            logger.info(f"    Gruppe {group_name}: {len(files)} Dateien")
            accumulate_group_files(output_folder, group_name, files, folder_name=str(relative_folder))

        summary_file = output_folder / "01_group_summary.csv"
        with summary_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["group", "file_count", "files"])
            for group_name, files in sorted(group_files.items()):
                writer.writerow([group_name, len(files), "; ".join(str(p.name) for p in files)])

        logger.info(f"  -> Ergebnisse gespeichert in {summary_file}")


def main():
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    remove_duplicate_files(SOURCE_DIR)
    accumulate_data_per_node(SOURCE_DIR, output_dir)


if __name__ == "__main__":
    main()