"""
prepare_data.py
===============
Datenaufbereitung: ERAA-2022-Excel-Rohdaten (config.RAW_DIR) -> Zwischenformat
je Modellzone (config.ACCUMULATED_DIR), die einzige Eingabe von
main/run_simulation.py.

Führt die zehn Schritte in pipeline/data_preparation/ in der vorgeschriebenen
Reihenfolge aus. Muss nach einer Änderung von TARGET_YEAR / ZONE_GROUPS in
config.py erneut laufen.

Beispiele (aus dem Projekt-Root):
    python main/prepare_data.py                      # alle Schritte
    python main/prepare_data.py --list               # Schritte anzeigen
    python main/prepare_data.py --from aggregate_climate_data
    python main/prepare_data.py --only aggregate_interconnections
    python main/prepare_data.py --force              # Excel-Dateien neu konvertieren
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from pipeline.data_preparation import (
    aggregate_climate_data,
    aggregate_demand_data,
    aggregate_interconnections,
    aggregate_national_estimates,
    copy_no_hydro_files,
    excel_to_csv,
    filter_target_year,
    label_hydro_climate_years,
    sort_hydro_inflows,
    transpose_capacity_table,
)

logger = logging.getLogger(__name__)

# Reihenfolge ist verbindlich: jeder Schritt liest die Ausgabe der vorherigen.
STEPS = [
    ("excel_to_csv",                 excel_to_csv,                 "01_raw -> 02_processed: eine CSV pro Excel-Reiter"),
    ("sort_hydro_inflows",           sort_hydro_inflows,           "Hydro-Inflows nach Technologie statt nach Zone ordnen"),
    ("filter_target_year",           filter_target_year,           "02_processed -> 03_filtered: nur Dateien des Zieljahrs"),
    ("transpose_capacity_table",     transpose_capacity_table,     "Kapazitätstabelle TY <Jahr>.csv drehen (Zonen als Zeilen)"),
    ("aggregate_climate_data",       aggregate_climate_data,       "Wind/Solar/Hydro je Modellzone -> 04b"),
    ("aggregate_demand_data",        aggregate_demand_data,        "Last je Modellzone -> 04b, Additional Data + Leitungen kopieren"),
    ("label_hydro_climate_years",    label_hydro_climate_years,    "Klimajahre 1982-2017 in Hydro-Spaltenköpfe schreiben"),
    ("aggregate_interconnections",   aggregate_interconnections,   "HVAC/HVDC je Zonenpaar aggregieren -> 04b"),
    ("aggregate_national_estimates", aggregate_national_estimates, "Kapazitäten, DSR etc. je Modellzone -> 04b"),
    ("copy_no_hydro_files",          copy_no_hydro_files,          "Norwegen-Hydro-Excel (NO-Hydro-Fix) -> 04b"),
]
STEP_NAMES = [name for name, _, _ in STEPS]


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--from", dest="start", choices=STEP_NAMES, metavar="SCHRITT",
                       help="ab diesem Schritt bis zum Ende ausführen")
    group.add_argument("--only", choices=STEP_NAMES, metavar="SCHRITT",
                       help="nur diesen einen Schritt ausführen")
    parser.add_argument("--list", action="store_true", help="Schritte anzeigen und beenden")
    parser.add_argument("--force", action="store_true",
                        help="Schritt excel_to_csv: bereits vorhandene CSVs neu schreiben")
    args = parser.parse_args()

    if args.list:
        for i, (name, _, desc) in enumerate(STEPS, 1):
            print(f"{i}. {name:30s} {desc}")
        return

    # Windows-Konsolen (cp1252) können z.B. '→' nicht darstellen: ersetzen statt abbrechen
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    if args.only:
        selected = [s for s in STEPS if s[0] == args.only]
    elif args.start:
        selected = STEPS[STEP_NAMES.index(args.start):]
    else:
        selected = STEPS

    logger.info("Zieljahr: %s | Rohdaten: %s | Ausgabe: %s",
                config.TARGET_YEAR, config.RAW_DIR, config.ACCUMULATED_DIR)

    for name, module, desc in selected:
        logger.info("=" * 60)
        logger.info("Schritt %d/%d: %s (%s)", STEP_NAMES.index(name) + 1, len(STEPS), name, desc)
        logger.info("=" * 60)
        if module is excel_to_csv:
            module.main(skip_existing=not args.force)
        else:
            module.main()

    logger.info("Datenaufbereitung abgeschlossen: %s", config.ACCUMULATED_DIR)


if __name__ == "__main__":
    main()
