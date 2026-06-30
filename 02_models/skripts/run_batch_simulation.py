"""
run_batch_simulation.py
=======================
Führt die vollständige Simulation (build_network → add_interconnections →
optimize → save_results) für N zufällig gewählte Klimajahre aus.

Bereits simulierte Jahre werden anhand vorhandener Ergebnis-Ordner in
04_results/ erkannt und übersprungen.

Verwendung (aus Projekt-Root):
    python 02_models/skripts/run_batch_simulation.py
"""

import random
import sys
import re
import logging
import traceback
from pathlib import Path

# ── Pfade ────────────────────────────────────────────────────────────────────
_SCRIPT_DIR   = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_RESULTS_DIR  = _PROJECT_ROOT / "04_results"

sys.path.insert(0, str(_SCRIPT_DIR))

from build_network import build_network
from add_interconnections import add_interconnections, save_results

# ── Konfiguration ─────────────────────────────────────────────────────────────
ACTIVE_ZONES = [
    "DE", "FR", "AT", "CH", "NL", "BE", "CZ", "PL", "DK", "SE", "NO", "FI",
    "adriatic", "baltic", "ES", "PT", "IT", "GR", "UK", "IE",
    "other eastern european",
]

YEAR_MIN   = 1982
YEAR_MAX   = 2015
N_STEPS    = 10

SOLVER_OPTIONS = {
    "Method"        : 2,
    "Crossover"     : 0,
    "Threads"       : 8,
    "BarConvTol"    : 1e-5,
    "DualReductions": 0,
}

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_PROJECT_ROOT / "batch_simulation.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _already_simulated_years() -> set[int]:
    """Liest abgeschlossene Klimajahre aus vorhandenen Ergebnis-Ordnern."""
    done = set()
    pattern = re.compile(r"_CY(\d{4})$")
    for d in _RESULTS_DIR.iterdir():
        if not d.is_dir():
            continue
        m = pattern.search(d.name)
        if m:
            done.add(int(m.group(1)))
    return done


def _pick_years(n: int) -> list[int]:
    """Wählt n zufällige Jahre aus dem Pool nicht-simulierter Jahre."""
    done = _already_simulated_years()
    pool = [y for y in range(YEAR_MIN, YEAR_MAX + 1) if y not in done]

    if not pool:
        logger.warning("Alle Jahre im Bereich %d–%d sind bereits simuliert.", YEAR_MIN, YEAR_MAX)
        return []

    if len(pool) < n:
        logger.warning(
            "Nur %d verbleibende Jahre verfügbar (angefordert: %d). Simuliere alle.", len(pool), n
        )
        n = len(pool)

    chosen = random.sample(pool, n)
    return chosen


def run_year(climate_year: str) -> bool:
    """
    Führt die vollständige Simulation für ein Klimajahr durch.
    Gibt True bei Erfolg, False bei Fehler zurück.
    """
    logger.info("=" * 60)
    logger.info("Starte Simulation Klimajahr %s", climate_year)
    logger.info("=" * 60)

    try:
        logger.info("Baue Netz auf...")
        n = build_network(active_zones=ACTIVE_ZONES, climate_year=climate_year)

        logger.info("Füge Interconnections hinzu...")
        add_interconnections(n, active_zones=ACTIVE_ZONES)

        logger.info("Starte Optimierung (Gurobi)...")
        status, condition = n.optimize(
            solver_name="gurobi",
            solver_options=SOLVER_OPTIONS,
        )

        if status != "ok":
            logger.error("Optimierung fehlgeschlagen: status=%s, condition=%s", status, condition)
            return False

        save_results(n, ACTIVE_ZONES, climate_year)
        logger.info("Klimajahr %s erfolgreich abgeschlossen.", climate_year)
        return True

    except Exception:
        logger.error("Unerwarteter Fehler bei Klimajahr %s:\n%s", climate_year, traceback.format_exc())
        return False


def main():
    logger.info("Batch-Simulation gestartet")
    logger.info("Bereich: %d–%d | Schritte: %d", YEAR_MIN, YEAR_MAX, N_STEPS)

    years = _pick_years(N_STEPS)
    if not years:
        logger.info("Keine Jahre zu simulieren. Beende.")
        return

    logger.info("Gewählte Klimajahre (zufällig): %s", years)

    results = {}
    for i, year in enumerate(years, 1):
        logger.info("Fortschritt: %d/%d  →  Klimajahr %s", i, len(years), year)
        success = run_year(str(year))
        results[year] = "OK" if success else "FEHLER"

    logger.info("=" * 60)
    logger.info("Batch abgeschlossen. Zusammenfassung:")
    for year, status in sorted(results.items()):
        logger.info("  CY%s: %s", year, status)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
