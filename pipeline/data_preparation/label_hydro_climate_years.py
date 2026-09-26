"""
Schritt 7: Klimajahre in Hydro-Dateien eintragen
================================================
In den ERAA-Hydro-Inflow-Dateien stehen im Tabellenkopf statt der Klimajahre
Platzhalter-Zahlen. Dieser Schritt ersetzt sie in allen Hydro-Dateien unter
config.ACCUMULATED_DIR durch die Jahre 1982-2017, damit das Modell die Spalte
eines Wetterjahrs findet. Mehrfaches Ausführen ist unschädlich.
"""

import csv
import logging

import config

logger = logging.getLogger(__name__)

BASE_DIR = config.ACCUMULATED_DIR
FIRST_YEAR, LAST_YEAR = config.CLIMATE_YEARS_AVAILABLE


def main():
    # Jahre 1982 bis 2017 (insgesamt 36 Spalten pro Block)
    years = [str(y) for y in range(FIRST_YEAR, LAST_YEAR + 1)]

    logger.info(f"Starte Jahr-Ergänzung für Hydro-Dateien in: {BASE_DIR}")

    if not BASE_DIR.exists():
        logger.error("Basisverzeichnis nicht gefunden!")
        return

    processed_files = 0
    for csv_path in BASE_DIR.rglob("*.csv"):
        # Nur Dateien in Ordnern verarbeiten, die "Hydro" enthalten
        if "Hydro" not in str(csv_path):
            continue

        logger.info(f"Verarbeite: {csv_path.relative_to(BASE_DIR)}")

        try:
            with csv_path.open("r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = list(reader)
        except Exception as e:
            logger.error(f"  Fehler beim Lesen: {e}")
            continue

        # Anforderung: Ab Spalte 18 (Index 17), Zeile 14 (Index 13)
        # Wir prüfen zur Sicherheit Zeile 13 und 14 (Index 12 und 13)
        modified = False
        for row_idx in [12, 13]:
            if len(rows) <= row_idx:
                continue

            target_row = rows[row_idx]
            row_modified = False
            i = 17
            while i < len(target_row):
                cell = target_row[i].strip()

                # Robuste Erkennung von Platzhaltern (z.B. "13874" oder "13874.0")
                is_placeholder = False
                try:
                    # Entferne mögliche .0 am Ende und wandle in Float
                    val_f = float(cell.replace(',', '.'))
                    # ERAA Platzhalter-IDs liegen meist zwischen 1000 und 99999
                    if 1000 < val_f < 99999:
                        is_placeholder = True
                except ValueError:
                    pass

                if is_placeholder:
                    for offset, year in enumerate(years):
                        col_idx = i + offset
                        if col_idx < len(target_row):
                            target_row[col_idx] = year
                    row_modified = True
                    i += len(years)  # Sprung zum nächsten Block
                else:
                    i += 1

            if row_modified:
                rows[row_idx] = target_row
                modified = True

        if modified:
            try:
                with csv_path.open("w", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerows(rows)
                processed_files += 1
            except Exception as e:
                logger.error(f"  Fehler beim Schreiben: {e}")

    logger.info(f"Fertig. {processed_files} Dateien wurden mit Jahreszahlen aktualisiert.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
