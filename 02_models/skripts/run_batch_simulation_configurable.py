"""
run_batch_simulation_configurable.py
======================================
Simuliert eine feste Liste von Klimajahren mit Paper-NTC-Kapazitäten.
Klimajahre einfach in YEARS anpassen, dann starten.

Verwendung (aus Projekt-Root):
    python 02_models/skripts/run_batch_simulation_configurable.py
"""

import argparse
import sys
import logging
from pathlib import Path

import pandas as pd
import pypsa

_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))

from build_network import build_network
from add_interconnections import save_results
from add_max_limits import max_limit_extra_functionality
from run_batch_simulation_NO_hydro_fix import (
    HYDRO_ZONE_CONFIGS,
    load_no_hydro_weekly_constraints,
    load_no_hydro_reservoir_capacity,
    map_weeks_to_snapshots_no_hydro_fix,
    _adjust_storage_capacity,
    add_no_hydro_weekly_constraints,
    _write_weekly_check,
)

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--years", type=int, nargs="+", default=YEARS)
    parser.add_argument("--suffix", type=str, default=RESULT_SUFFIX)
    args = parser.parse_args()
    YEARS = args.years
    RESULT_SUFFIX = args.suffix

    for year in YEARS:
        climate_year = str(year)
        print(f"\n{'='*60}\nKlimajahr {climate_year}\n{'='*60}")

        n = build_network(active_zones=ACTIVE_ZONES, climate_year=climate_year)
        add_interconnections_paper(n, active_zones=ACTIVE_ZONES)

        zone_weekly_data = {}
        zone_week_snapshot_map = {}
        for zone_config in HYDRO_ZONE_CONFIGS:
            weekly_df, _ = load_no_hydro_weekly_constraints(
                _PROJECT_ROOT,
                codes=zone_config["codes"],
            )
            reservoir_capacity_gwh, _ = load_no_hydro_reservoir_capacity(
                _PROJECT_ROOT,
                codes=zone_config["codes"],
            )

            if reservoir_capacity_gwh > 0:
                _adjust_storage_capacity(n, reservoir_capacity_gwh, storage_name=zone_config["storage_name"])
            else:
                logger.info(
                    "Keine aggregierte Reservoir-Kapazität verfügbar für %s; %s bleibt unverändert.",
                    zone_config["zone"],
                    zone_config["storage_name"],
                )

            if not weekly_df.empty:
                zone_week_snapshot_map[zone_config["zone"]] = map_weeks_to_snapshots_no_hydro_fix(n)
                zone_weekly_data[zone_config["zone"]] = weekly_df

        extra_functionality = None
        if ENFORCE_MAX_LIMITS:
            extra_functionality = max_limit_extra_functionality(ACTIVE_ZONES)

        def combined_extra_functionality(n_network: pypsa.Network, snapshots):
            if extra_functionality is not None:
                extra_functionality(n_network, snapshots)

            for zone_config in HYDRO_ZONE_CONFIGS:
                zone_name = zone_config["zone"]
                weekly_df = zone_weekly_data.get(zone_name)
                if weekly_df is None or weekly_df.empty:
                    continue

                add_no_hydro_weekly_constraints(
                    n_network,
                    weekly_df,
                    zone_week_snapshot_map.get(zone_name, {}),
                    enforce_min_generation=True,
                    storage_name=zone_config["storage_name"],
                )

        status, condition = n.optimize(
            solver_name="gurobi",
            solver_options=SOLVER_OPTIONS,
            extra_functionality=combined_extra_functionality,
        )

        if status != "ok":
            print(f"Optimierung fehlgeschlagen für {climate_year}: {status}, {condition}")
            continue

        save_results(n, ACTIVE_ZONES, climate_year, suffix=RESULT_SUFFIX)
        result_dir = Path(save_results.__globals__["_RESULTS_DIR"]) / f"{'_'.join(ACTIVE_ZONES)}_CY{climate_year}{RESULT_SUFFIX}"
        result_dir.mkdir(parents=True, exist_ok=True)
        for zone_config in HYDRO_ZONE_CONFIGS:
            zone_name = zone_config["zone"]
            weekly_df = zone_weekly_data.get(zone_name)
            if weekly_df is None or weekly_df.empty:
                continue
            _write_weekly_check(
                n,
                weekly_df,
                zone_week_snapshot_map.get(zone_name, {}),
                result_dir,
                storage_name=zone_config["storage_name"],
                file_name=f"NO_hydro_fix_weekly_check_{zone_name}.csv",
            )

    print("\nFertig.")
