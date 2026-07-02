"""
run_batch_simulation_fixed_years.py
====================================
Simple Re-Simulation einer festen Liste von Klimajahren (z.B. zum erneuten
Durchlauf von Jahren aus "Earlier results/Results with FI-baltic DC error",
nachdem der Fehler behoben wurde). Keine Zufallsauswahl, kein Skip von
bereits vorhandenen Jahren - läuft einfach die Liste der Reihe nach durch.

Verwendung (aus Projekt-Root):
    python 02_models/skripts/run_batch_simulation_fixed_years.py
"""

import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))

from build_network import build_network
from add_interconnections import add_interconnections, save_results
from add_max_limits import max_limit_extra_functionality

# ── Jahre, die erneut simuliert werden sollen ──────────────────────────────
YEARS = [1988, 1989, 1990, 1993, 2000, 2003, 2004, 2006, 2011, 2012, 2014, 2015]

ACTIVE_ZONES = [
    "DE", "FR", "AT", "CH", "NL", "BE", "CZ", "PL", "DK", "SE", "NO", "FI",
    "adriatic", "baltic", "ES", "PT", "IT", "GR", "UK", "IE",
    "other eastern european",
]

ENFORCE_MAX_LIMITS = True

SOLVER_OPTIONS = {
    "Method"        : 2,
    "Crossover"     : 0,
    "Threads"       : 8,
    "BarConvTol"    : 1e-5,
    "DualReductions": 0,
}

for year in YEARS:
    climate_year = str(year)
    print(f"\n{'='*60}\nKlimajahr {climate_year}\n{'='*60}")

    n = build_network(active_zones=ACTIVE_ZONES, climate_year=climate_year)
    add_interconnections(n, active_zones=ACTIVE_ZONES)

    status, condition = n.optimize(
        solver_name="gurobi",
        solver_options=SOLVER_OPTIONS,
        extra_functionality=(
            max_limit_extra_functionality(ACTIVE_ZONES) if ENFORCE_MAX_LIMITS else None
        ),
    )

    if status != "ok":
        print(f"Optimierung fehlgeschlagen für {climate_year}: {status}, {condition}")
        continue

    save_results(n, ACTIVE_ZONES, climate_year)

print("\nFertig.")
