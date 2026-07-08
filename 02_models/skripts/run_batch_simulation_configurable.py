"""
run_batch_simulation_configurable.py
======================================
Simuliert eine feste Liste von Klimajahren mit Paper-NTC-Kapazitäten.
Klimajahre einfach in YEARS anpassen, dann starten.

Verwendung (aus Projekt-Root):
    python 02_models/skripts/run_batch_simulation_configurable.py
"""

import sys
import logging
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))

from build_network import build_network
from add_interconnections import save_results
from add_max_limits import max_limit_extra_functionality

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── Projektpfade ──────────────────────────────────────────────────────────────
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_NTC_CSV      = (_PROJECT_ROOT
                 / "01_data/Exact paper interconnection"
                 / "NTC_Vergleich_ERAA_Paper_Modell.csv")

_ZONE_ALIAS = {"OE": "other eastern european"}

# ── Konfiguration ─────────────────────────────────────────────────────────────
YEARS = [2003, 2012, 2006, 2011, 2014, 1988]

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
    "BarConvTol"    : 1e-4,
    "DualReductions": 0,
    "TimeLimit"     : 14440,
}

RESULT_SUFFIX = "_paperNTC"

# ── Paper-NTC laden und ins Netz einfügen ─────────────────────────────────────

def _resolve_zone(name: str) -> str:
    return _ZONE_ALIAS.get(name.strip(), name.strip())


def _load_paper_ntc(active_zones: list) -> list:
    import pandas as pd

    if not _NTC_CSV.exists():
        raise FileNotFoundError(f"NTC-CSV nicht gefunden: {_NTC_CSV}")

    df = pd.read_csv(_NTC_CSV, sep=";", decimal=",", thousands=".")
    active_set = set(active_zones)
    result = []

    for _, row in df.iterrows():
        linie = str(row["Linie"]).strip()
        if "-" not in linie:
            continue
        raw_val = row["Paper"]
        if pd.isna(raw_val):
            continue
        try:
            cap = float(raw_val)
        except (ValueError, TypeError):
            continue
        if cap <= 0:
            continue

        parts = linie.split("-", 1)
        if len(parts) != 2:
            continue
        zone_a = _resolve_zone(parts[0])
        zone_b = _resolve_zone(parts[1])

        for frm, to in [(zone_a, zone_b), (zone_b, zone_a)]:
            if frm in active_set and to in active_set:
                result.append({"from_zone": frm, "to_zone": to, "ntc_mean_mw": cap})

    logger.info(f"Paper-NTC: {len(result)} Verbindungen geladen")
    return result


def add_interconnections_paper(n, active_zones: list):
    ntc_rows = _load_paper_ntc(active_zones)
    added, skipped = 0, 0

    for row in ntc_rows:
        frm = row["from_zone"]
        to  = row["to_zone"]
        cap = row["ntc_mean_mw"]

        if frm not in n.buses.index:
            skipped += 1
            continue
        if to not in n.buses.index:
            skipped += 1
            continue

        link_name = f"Link_{frm}_to_{to}"

        if link_name in n.links.index:
            old_cap = n.links.loc[link_name, "p_nom"]
            new_cap = old_cap + cap
            n.links.loc[link_name, "p_nom"] = new_cap
            logger.info(f"  Paper NTC {frm} → {to}: +{cap:.0f} MW → {new_cap:.0f} MW gesamt")
            added += 1
            continue

        n.add("Link", link_name,
              bus0=frm, bus1=to,
              p_nom=cap, p_min_pu=0.0,
              efficiency=1.0, carrier="AC")
        logger.info(f"  Paper NTC {frm} → {to}: {cap:.0f} MW")
        added += 1

    logger.info(f"Paper-Links hinzugefügt: {added}, übersprungen: {skipped}")


# ── Haupt-Loop ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    for year in YEARS:
        climate_year = str(year)
        print(f"\n{'='*60}\nKlimajahr {climate_year}\n{'='*60}")

        n = build_network(active_zones=ACTIVE_ZONES, climate_year=climate_year)
        add_interconnections_paper(n, active_zones=ACTIVE_ZONES)

        status, condition = n.optimize(
            solver_name="gurobi",
            solver_options=SOLVER_OPTIONS,
            extra_functionality=(
                max_limit_extra_functionality(ACTIVE_ZONES)
                if ENFORCE_MAX_LIMITS else None
            ),
        )

        if status != "ok":
            print(f"Optimierung fehlgeschlagen für {climate_year}: {status}, {condition}")
            continue

        save_results(n, ACTIVE_ZONES, climate_year, suffix=RESULT_SUFFIX)

    print("\nFertig.")
