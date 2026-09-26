"""
Schritt 5: Klimadaten je Modellzone aggregieren
===============================================
Fasst die Zeitreihen aus config.FILTERED_DIR/Climate Data (Wind, Solar, CSP,
Hydro-Inflows) von ERAA-Zonen (z.B. DE00, HR00, NOM1) auf Modellzonen
zusammen (config.ZONE_GROUPS, sonst Ländercode) und schreibt je Zone eine
Datei "<Zone>_accumulated.csv" nach config.ACCUMULATED_DIR.

- Wind/Solar (Kapazitätsfaktoren): mit der installierten Leistung der
  Teilzonen gewichteter Mittelwert (Gewichte aus der in Schritt 4 gedrehten
  Kapazitätstabelle).
- Alles andere (Hydro-Inflows in GWh): Summe.

Pro Ordner entsteht zusätzlich "01_group_summary.csv" (welche Dateien in
welche Zone eingegangen sind).
"""

import csv
import logging
import re
from pathlib import Path

import pandas as pd

import config

logger = logging.getLogger(__name__)

SOURCE_DIR = config.FILTERED_DIR
OUTPUT_DIR = config.ACCUMULATED_DIR
PNOM_PATH = SOURCE_DIR / config.NATIONAL_ESTIMATES_DIRNAME / f"TY {config.TARGET_YEAR}.csv"

def remove_duplicate_files(root_dir: Path):
    """Entferne CSV-Duplikate, die ein '(' im Dateinamen enthalten."""
    removed = 0
    for csv_path in sorted(root_dir.rglob("*.csv")):
        if "(" in csv_path.stem:
            csv_path.unlink()
            removed += 1
    logger.info(f"Doppelte Dateien entfernt: {removed}")

# Ordner, die hier nicht aggregiert werden (andere Schritte zuständig)
EXCLUDE_FOLDERS = [
    "Additional Data",
    config.NATIONAL_ESTIMATES_DIRNAME,
    "Transfer capacities",
    "Demand",
]


def is_excluded_folder(relative_folder: Path) -> bool:
    if not relative_folder.parts:
        return False
    return any(part in EXCLUDE_FOLDERS for part in relative_folder.parts)


def resolve_group(zone: str, rules: dict[str, list[str]]) -> str:
    for group_name, zones in rules.items():
        if zone in zones:
            return group_name
    if len(zone) >= 2 and zone[:2].isalpha():
        return zone[:2]
    return zone


ZONE_CODE_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2}\d{2})(?![A-Za-z0-9])")
ZONE_SHORT_PATTERN = re.compile(r"(?<![A-Za-z0-9])([A-Z]{2})(?![A-Za-z0-9])")


def normalize_zone(candidate: str) -> str:
    if pd.isna(candidate):
        return "UNKNOWN"
    candidate = str(candidate).upper()
    if len(candidate) == 4 and candidate[:2].isalpha() and candidate[2:].isdigit():
        return candidate[:2]
    if len(candidate) == 2 and candidate.isalpha():
        return candidate
    return candidate


def extract_zone_from_path(csv_path: Path) -> str:
    for part in csv_path.parts:
        for match in ZONE_CODE_PATTERN.findall(part):
            return normalize_zone(match)
    for part in csv_path.parts:
        for match in ZONE_SHORT_PATTERN.findall(part):
            normalized = normalize_zone(match)
            if normalized in {z for zones in config.ZONE_GROUPS.values() for z in zones}:
                return normalized
    stem = csv_path.stem
    fallback = stem.split()[0].split("_")[0].upper()
    return normalize_zone(fallback)


def format_value(value):
    if isinstance(value, float):
        return str(value).rstrip("0").rstrip(".") if "." in str(value) else str(value)
    return str(value)


def try_float(value):
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


# ── p_nom-Tabelle (Gewichte für Wind/Solar), wird in main() geladen ─────────
PNOM_TABLE = None


def load_pnom_table(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0)
    df.index = df.index.map(normalize_zone)
    return df.groupby(df.index).sum()


def get_pnom_weight(zone: str, folder_name: str) -> float:
    """
    Gibt p_nom-Gewicht einer Zone für die passende Technologie zurück.
    Nur für Wind Onshore, Wind Offshore und Solar aktiv.
    Alle anderen Ordner → 0.0 (werden im else-Zweig summiert, Gewicht egal).
    Zonen mit p_nom = 0 → 0.0 → werden beim gewichteten Mittel ignoriert.
    """
    if PNOM_TABLE is None:
        return 1.0

    zone_up = normalize_zone(zone)
    if zone_up not in PNOM_TABLE.index:
        return 0.0

    # Explizites Mapping: Ordner-Keyword → exakter Spaltenname in TY2030
    tech_map = {
        "wind onshore" : "Wind Onshore",
        "wind offshore": "Wind Offshore",
        "solar"        : "Solar (Photovoltaic)",
    }

    folder_lower = folder_name.lower()
    col = None
    for keyword, tech_col in tech_map.items():
        if keyword in folder_lower and tech_col in PNOM_TABLE.columns:
            col = tech_col
            break

    if col is None:
        return 0.0  # Kein Match → kein Gewicht → Fallback in accumulate_group_files

    val = PNOM_TABLE.loc[zone_up, col]
    if isinstance(val, pd.Series):
        val = val.sum()

    # p_nom = 0 → Zone hat keine Kapazität → Gewicht 0 → wird beim Mittelwert ignoriert
    return float(val) if pd.notna(val) and float(val) > 0 else 0.0


def accumulate_group_files(output_folder: Path, group_name: str, files: list[Path], folder_name: str = "") -> None:
    """Akkumuliere CSV-Dateien einer Gruppe.

    - Zeilen 1-11, Spalten 1-2: Metadaten aus erster Datei
    - Ab Zeile 12, Spalte 3:
        * Wind/Solar (is_cf_folder): kapazitätsgewichteter Durchschnitt nach p_nom
          Zonen mit p_nom=0 gehen nicht in Zähler/Nenner ein
        * Alle anderen: summieren
    """
    if not files:
        return

    all_file_rows = []
    header = None

    # Gewichte berechnen
    file_weights = []
    for csv_path in files:
        zone = extract_zone_from_path(csv_path)
        weight = get_pnom_weight(zone, folder_name)
        file_weights.append(weight)
        logger.info(f"    Gewicht für {csv_path.name} (zone={zone}): {weight:.2f} MW")

    total_weight = sum(file_weights)
    if total_weight == 0:
        # Fallback: gleichgewichtet (tritt auf bei Hydro/CSP wo get_pnom_weight 0.0 zurückgibt)
        # Spielt keine Rolle da diese Ordner sowieso summiert werden (is_cf_folder=False)
        norm_weights = [1.0 / len(files)] * len(files)
    else:
        norm_weights = [w / total_weight for w in file_weights]

    for csv_path in files:
        with csv_path.open("r", newline="", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            rows = list(reader)
        if not rows:
            continue
        if header is None:
            header = rows[0]
        all_file_rows.append(rows)

    # ── NEU: Alle Dateien auf gleiche maximale Spaltenanzahl normieren ──
    if all_file_rows:
        max_cols = max(len(row) for file_rows in all_file_rows
                       for row in file_rows if row)
        normalized_all = []
        for file_rows in all_file_rows:
            normalized = []
            for row in file_rows:
                if len(row) < max_cols:
                    row = row + [''] * (max_cols - len(row))
                normalized.append(row)
            normalized_all.append(normalized)
        all_file_rows = normalized_all

    if not all_file_rows:
        return

    first_file_rows = all_file_rows[0]
    result_rows = [list(first_file_rows[0])]
    max_rows = max(len(f) for f in all_file_rows)

    # Erkenne Ordnertyp
    is_cf_folder   = any(keyword in folder_name.lower() for keyword in
                         ["wind", "solar", "pv", "capacity factor"])
    is_hydro_folder = any(keyword in folder_name.lower() for keyword in
                          ["hydro", "inflow"])

    for row_idx in range(1, max_rows):
        if row_idx < len(first_file_rows):
            base_row = list(first_file_rows[row_idx])
        else:
            base_row = []

        # Metadaten-Zeilen
        if row_idx <= 11:
            if is_hydro_folder and row_idx in [4, 5, 6]:
                result_row = list(base_row)
                target_col_idx = 2
                current_sum = try_float(result_row[target_col_idx]) if target_col_idx < len(result_row) else 0.0
                if current_sum is None:
                    current_sum = 0.0
                for other_file_rows in all_file_rows[1:]:
                    if row_idx >= len(other_file_rows):
                        continue
                    other_row = other_file_rows[row_idx]
                    if target_col_idx < len(other_row):
                        other_val = try_float(other_row[target_col_idx])
                        if other_val is not None:
                            current_sum += other_val
                result_row[target_col_idx] = current_sum
                result_rows.append(result_row)
            else:
                result_rows.append(base_row)
            continue

        result_row = list(base_row)

        if is_cf_folder:
            # ── Kapazitätsgewichteter Durchschnitt für Wind/Solar ────────
            # Zonen mit Gewicht 0 gehen nicht in Zähler/Nenner ein,
            # weil norm_weights[i] = 0 für diese Zonen.
            weighted_sums = {}

            for col_idx in range(2, max(len(r) for r in all_file_rows if row_idx < len(r))):
                weighted_val = 0.0
                weight_sum   = 0.0
                has_any_value = False

                for file_rows, w in zip(all_file_rows, norm_weights):
                    if row_idx >= len(file_rows):
                        continue
                    row = file_rows[row_idx]
                    val = try_float(row[col_idx]) if col_idx < len(row) else None
                    # NaN und None ignorieren; w=0 trägt sowieso nichts bei
                    if val is not None and not (isinstance(val, float) and val != val):
                        weighted_val += val * w
                        weight_sum   += w
                        has_any_value = True

                if has_any_value and weight_sum > 0:
                    # Renormieren falls nicht alle Zonen Daten hatten
                    weighted_sums[col_idx] = weighted_val / weight_sum
                elif has_any_value:
                    weighted_sums[col_idx] = weighted_val

            for col_idx, val in weighted_sums.items():
                if col_idx >= len(result_row):
                    result_row.append(val)
                else:
                    result_row[col_idx] = val

        else:
            # ── Summieren (für alle anderen Ordner) ──────────────────────
            for other_file_rows in all_file_rows[1:]:
                if row_idx >= len(other_file_rows):
                    continue
                other_row = other_file_rows[row_idx]
                for col_idx in range(2, max(len(result_row), len(other_row))):
                    if col_idx >= len(result_row):
                        result_row.append("")
                    base_val  = result_row[col_idx]
                    other_val = other_row[col_idx] if col_idx < len(other_row) else ""
                    base_float  = try_float(base_val)
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
    logger.info(f"Starte Akkumulation von Daten in {source_dir}")
    logger.info(f"Zielverzeichnis ist {output_dir}")

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
        logger.info(f"Verarbeite Ordner: {relative_folder}")

        group_files: dict[str, list[Path]] = {}
        for csv_path in csv_paths:
            zone  = extract_zone_from_path(csv_path)
            group = resolve_group(zone, config.ZONE_GROUPS)
            logger.info(f"  - {csv_path.name} -> zone={zone}, group={group}")
            group_files.setdefault(group, []).append(csv_path)

        for group_name, files in sorted(group_files.items()):
            logger.info(f"    Gruppe {group_name}: {len(files)} Dateien")
            accumulate_group_files(output_folder, group_name, files,
                                   folder_name=str(relative_folder))

        summary_file = output_folder / "01_group_summary.csv"
        with summary_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["group", "file_count", "files"])
            for group_name, files in sorted(group_files.items()):
                writer.writerow([group_name, len(files),
                                  "; ".join(str(p.name) for p in files)])

        logger.info(f"  -> Ergebnisse gespeichert in {summary_file}")


def main():
    global PNOM_TABLE
    if PNOM_PATH.exists():
        PNOM_TABLE = load_pnom_table(PNOM_PATH)
    else:
        logger.warning(f"{PNOM_PATH} fehlt - Wind/Solar werden ungewichtet gemittelt. "
                       f"Schritt 4 (transpose_capacity_table) vorher ausführen.")
    output_dir = OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)
    remove_duplicate_files(SOURCE_DIR)
    accumulate_data_per_node(SOURCE_DIR, output_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
