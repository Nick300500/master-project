"""
run_batch_simulation.py
=======================
Einziger Einstiegspunkt für Batch-Simulationsläufe (build_network ->
Interconnections -> optimize -> save_results), konfigurierbar über
CLI-Flags statt über separate Skript-Kopien.

Deckt die drei bisher getrennten Szenarien ab:
  - Standard-ERAA-Lauf mit zufälligen Klimajahren
    (vorher: run_batch_simulation.py)
  - Fester Jahres-Lauf mit ERAA-NTC ohne Zusatz-Constraints
    (vorher: run_batch_simulation_fixed_years.py)
  - Paper-NTC + NO-Hydro-Fix-Szenarien
    (vorher: run_batch_simulation_configurable.py /
    run_batch_simulation_NO_hydro_fix.py)

Beispiele (aus Projekt-Root):
    # 10 zufällige, noch nicht simulierte Klimajahre, Standard-ERAA-NTC
    python 02_models/skripts/run_batch_simulation.py

    # bestimmte Klimajahre, Standard-ERAA-NTC
    python 02_models/skripts/run_batch_simulation.py --years 2011 2012 2014

    # Paper-NTC + vollständiger NO-Hydro-Fix (Flow + Reservoir-Level)
    python 02_models/skripts/run_batch_simulation.py --years 2003 \
        --interconnections paper --no-hydro-fix flow+level
"""

import argparse
import logging
import random
import re
import sys
import traceback
from pathlib import Path

import no_hydro_fix
import paper_interconnections
from add_interconnections import add_interconnections, save_results
from add_max_limits import max_limit_extra_functionality
from build_network import build_network

_SCRIPT_DIR = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_RESULTS_DIR = _PROJECT_ROOT / "04_results"
_PAPER_NTC_CSV = (
    _PROJECT_ROOT / "01_data/Exact paper interconnection" / "NTC_Vergleich_ERAA_Paper_Modell.csv"
)

sys.path.insert(0, str(_SCRIPT_DIR))

ACTIVE_ZONES = [
    "DE", "FR", "AT", "CH", "NL", "BE", "CZ", "PL", "DK", "SE", "NO", "FI",
    "adriatic", "baltic", "ES", "PT", "IT", "GR", "UK", "IE",
    "other eastern european",
]

DEFAULT_SOLVER_OPTIONS = {
    "Method": 2,
    "Crossover": 0,
    "Threads": 8,
    "BarConvTol": 1e-5,
    "DualReductions": 0,
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_PROJECT_ROOT / "batch_simulation.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _already_simulated_years(suffix: str) -> set[int]:
    """Liest abgeschlossene Klimajahre (für den gegebenen Ergebnis-Suffix) aus 04_results/."""
    done = set()
    pattern = re.compile(r"_CY(\d{4})" + re.escape(suffix) + r"$")
    if not _RESULTS_DIR.exists():
        return done
    for d in _RESULTS_DIR.iterdir():
        if not d.is_dir():
            continue
        m = pattern.search(d.name)
        if m:
            done.add(int(m.group(1)))
    return done


def _pick_random_years(n: int, year_min: int, year_max: int, suffix: str, skip_existing: bool) -> list[int]:
    """Wählt n zufällige Klimajahre; überspringt bereits simulierte, falls gewünscht."""
    done = _already_simulated_years(suffix) if skip_existing else set()
    pool = [y for y in range(year_min, year_max + 1) if y not in done]

    if not pool:
        logger.warning("Alle Jahre im Bereich %d-%d sind bereits simuliert.", year_min, year_max)
        return []

    if len(pool) < n:
        logger.warning("Nur %d verbleibende Jahre verfügbar (angefordert: %d). Simuliere alle.", len(pool), n)
        n = len(pool)

    return random.sample(pool, n)


def _auto_suffix(interconnections: str, no_hydro_fix_level: str) -> str:
    """Baut einen Ergebnis-Ordner-Suffix aus den gewählten Szenario-Optionen."""
    parts = []
    if interconnections == "paper":
        parts.append("paperNTC")
    if no_hydro_fix_level == "flow":
        parts.append("NO_hydro_fix")
    elif no_hydro_fix_level == "flow+level":
        parts.append("NO_hydro_fix_full")
    return ("_" + "_".join(parts)) if parts else ""


def run_year(
    climate_year: str,
    interconnections: str,
    no_hydro_fix_level: str,
    enforce_max_limits: bool,
    suffix: str,
    solver_options: dict,
) -> bool:
    """Führt die vollständige Simulation für ein Klimajahr durch. True bei Erfolg."""
    logger.info("=" * 60)
    logger.info("Starte Simulation Klimajahr %s (interconnections=%s, no_hydro_fix=%s)",
                climate_year, interconnections, no_hydro_fix_level)
    logger.info("=" * 60)

    try:
        logger.info("Baue Netz auf...")
        n = build_network(active_zones=ACTIVE_ZONES, climate_year=climate_year)

        logger.info("Füge Interconnections hinzu (%s)...", interconnections)
        if interconnections == "paper":
            paper_interconnections.add_paper_interconnections(n, _PAPER_NTC_CSV, active_zones=ACTIVE_ZONES)
        else:
            add_interconnections(n, active_zones=ACTIVE_ZONES)

        check_data = None
        no_fix_extra = None
        if no_hydro_fix_level != "off":
            logger.info("Bereite NO-Hydro-Fix vor (Level=%s)...", no_hydro_fix_level)
            no_fix_extra, check_data = no_hydro_fix.build_no_hydro_extra_functionality(
                n, _PROJECT_ROOT, level=no_hydro_fix_level,
            )

        max_limits_extra = max_limit_extra_functionality(ACTIVE_ZONES) if enforce_max_limits else None

        def extra_functionality(n_network, snapshots):
            if max_limits_extra is not None:
                max_limits_extra(n_network, snapshots)
            if no_fix_extra is not None:
                no_fix_extra(n_network, snapshots)

        logger.info("Starte Optimierung (Gurobi)...")
        status, condition = n.optimize(
            solver_name="gurobi",
            solver_options=solver_options,
            extra_functionality=extra_functionality if (max_limits_extra or no_fix_extra) else None,
        )

        if status != "ok":
            logger.error("Optimierung fehlgeschlagen: status=%s, condition=%s", status, condition)
            return False

        save_results(n, ACTIVE_ZONES, climate_year, suffix=suffix)

        if check_data is not None:
            result_dir = _RESULTS_DIR / f"{'_'.join(ACTIVE_ZONES)}_CY{climate_year}{suffix}"
            result_dir.mkdir(parents=True, exist_ok=True)
            no_hydro_fix.write_check_files(n, check_data, result_dir)

        logger.info("Klimajahr %s erfolgreich abgeschlossen.", climate_year)
        return True

    except Exception:
        logger.error("Unerwarteter Fehler bei Klimajahr %s:\n%s", climate_year, traceback.format_exc())
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    year_group = parser.add_mutually_exclusive_group()
    year_group.add_argument("--years", type=int, nargs="+", help="Feste Liste von Klimajahren")
    year_group.add_argument("--random", type=int, metavar="N",
                             help="N zufällige, noch nicht simulierte Klimajahre ziehen (Default: 10, falls --years nicht gesetzt)")
    parser.add_argument("--year-range", type=int, nargs=2, default=[1982, 2015], metavar=("MIN", "MAX"),
                         help="Jahresbereich für --random (Default: 1982 2015)")
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True,
                         help="Bei --random bereits simulierte Jahre überspringen (Default: an)")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    parser.add_argument("--interconnections", choices=["eraa", "paper"], default="eraa",
                         help="Quelle der Interconnection-Kapazitäten (Default: eraa)")
    parser.add_argument("--no-hydro-fix", choices=["off", "flow", "flow+level"], default="off",
                         help="Tiefe der NO-PSOpen-Hydro-Korrektur (Default: off)")
    parser.add_argument("--max-limits", dest="max_limits", action="store_true", default=True,
                         help="Country-Level-Max-NTC-Limits erzwingen (Default: an)")
    parser.add_argument("--no-max-limits", dest="max_limits", action="store_false")
    parser.add_argument("--suffix", type=str, default=None,
                         help="Ergebnis-Ordner-Suffix (Default: automatisch aus den Szenario-Flags abgeleitet)")
    parser.add_argument("--bar-conv-tol", type=float, default=DEFAULT_SOLVER_OPTIONS["BarConvTol"],
                         help=f"Gurobi BarConvTol (Default: {DEFAULT_SOLVER_OPTIONS['BarConvTol']})")
    parser.add_argument("--threads", type=int, default=DEFAULT_SOLVER_OPTIONS["Threads"],
                         help=f"Gurobi Threads (Default: {DEFAULT_SOLVER_OPTIONS['Threads']})")
    args = parser.parse_args()

    suffix = args.suffix if args.suffix is not None else _auto_suffix(args.interconnections, args.no_hydro_fix)
    solver_options = {**DEFAULT_SOLVER_OPTIONS, "BarConvTol": args.bar_conv_tol, "Threads": args.threads}

    if args.years is not None:
        years = args.years
        logger.info("Feste Klimajahre: %s", years)
    else:
        n_random = args.random if args.random is not None else 10
        years = _pick_random_years(n_random, args.year_range[0], args.year_range[1], suffix, args.skip_existing)
        if not years:
            logger.info("Keine Jahre zu simulieren. Beende.")
            return
        logger.info("Gewählte Klimajahre (zufällig): %s", years)

    results = {}
    for i, year in enumerate(years, 1):
        logger.info("Fortschritt: %d/%d  ->  Klimajahr %s", i, len(years), year)
        success = run_year(
            str(year),
            interconnections=args.interconnections,
            no_hydro_fix_level=args.no_hydro_fix,
            enforce_max_limits=args.max_limits,
            suffix=suffix,
            solver_options=solver_options,
        )
        results[year] = "OK" if success else "FEHLER"

    logger.info("=" * 60)
    logger.info("Batch abgeschlossen. Zusammenfassung:")
    for year, status in sorted(results.items()):
        logger.info("  CY%s: %s", year, status)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
