"""
Schritt 10: Norwegen-Hydro-Dateien bereitstellen
================================================
Der NO-Hydro-Fix (--no-hydro-fix flow / flow+level) liest wöchentliche
Erzeugungs- und Füllstandsgrenzen direkt aus den ERAA-Excel-Dateien der drei
norwegischen Gebotszonen (PEMMDB_NOM1/NON1/NOS0_Hydro Inflow_<Zieljahr>.xlsx).
Dieser Schritt kopiert sie unverändert aus den Rohdaten nach
config.ACCUMULATED_DIR/Climate Data/Hydro Inflows/NO constraint approach/.
"""

import logging
import shutil

import config
from pipeline.model.no_hydro_fix import NO_BZONE_CODES

logger = logging.getLogger(__name__)

SOURCE_DIR = config.RAW_DIR / "Climate Data" / "Hydro Inflows"
OUTPUT_DIR = config.ACCUMULATED_DIR / "Climate Data" / "Hydro Inflows" / "NO constraint approach"


def main(year: int = config.TARGET_YEAR):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for code in NO_BZONE_CODES:
        source = SOURCE_DIR / f"PEMMDB_{code}_Hydro Inflow_{year}.xlsx"
        if not source.exists():
            logger.warning(f"Datei nicht gefunden: {source} - NO-Hydro-Fix ist ohne sie nicht nutzbar.")
            continue
        shutil.copy2(source, OUTPUT_DIR / source.name)
        logger.info(f"Kopiert: {source.name} -> {OUTPUT_DIR}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    main()
