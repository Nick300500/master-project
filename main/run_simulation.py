"""
run_simulation.py
=================
Simuliert den europäischen Strommarkt für ein oder mehrere Wetterjahre:
Netz bauen -> Leitungen hinzufügen -> optimieren (Gurobi) -> Ergebnisse
speichern. Ein Wetterjahr = ein Lauf = ein Ergebnisordner in 04_results/.

Voraussetzung: 01_data/04b_accumulated_data_per_node/ existiert
(fertig erhalten oder mit main/prepare_data.py erzeugt).

Defaults stehen in config.py; die Flags unten überschreiben sie pro Lauf.

Beispiele (aus dem Projekt-Root):
    # ein Wetterjahr, Standard-Szenario aus config.py
    python main/run_simulation.py --years 2012

    # 10 zufällige, noch nicht simulierte Wetterjahre aus 1982-2015
    python main/run_simulation.py

    # Paper-NTC + vollständiger NO-Hydro-Fix (Flow + Reservoir-Level)
    python main/run_simulation.py --years 2003 --interconnections paper --no-hydro-fix flow+level
"""

import argparse
import logging
import random
import re
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from pipeline.model import no_hydro_fix, paper_interconnections
from pipeline.model.build_network import build_network
from pipeline.model.eraa_interconnections import add_eraa_interconnections
from pipeline.model.max_limits import max_limit_extra_functionality
from pipeline.model.results import save_results

logger = logging.getLogger(__name__)


def _already_simulated_years(suffix: str) -> set[int]:
    """Liest abgeschlossene Klimajahre (für den gegebenen Ergebnis-Suffix) aus dem Ergebnisordner."""
    done = set()
    pattern = re.compile(r"_CY(\d{4})" + re.escape(suffix) + r"$")
    if not config.RESULTS_DIR.exists():
        return done
    for d in config.RESULTS_DIR.iterdir():
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
    zones = config.ACTIVE_ZONES
    logger.info("=" * 60)
    logger.info("Starte Simulation Klimajahr %s (interconnections=%s, no_hydro_fix=%s)",
                climate_year, interconnections, no_hydro_fix_level)
    logger.info("=" * 60)

    try:
        logger.info("Baue Netz auf...")
        n = build_network(active_zones=zones, climate_year=climate_year)

        logger.info("Füge Interconnections hinzu (%s)...", interconnections)
        if interconnections == "paper":
            paper_interconnections.add_paper_interconnections(n, active_zones=zones)
        else:
            add_eraa_interconnections(n, active_zones=zones)

        check_data = None
        no_fix_extra = None
        if no_hydro_fix_level != "off":
            logger.info("Bereite NO-Hydro-Fix vor (Level=%s)...", no_hydro_fix_level)
            no_fix_extra, check_data = no_hydro_fix.build_no_hydro_extra_functionality(
                n, level=no_hydro_fix_level,
            )

        max_limits_extra = max_limit_extra_functionality(zones) if enforce_max_limits else None

        def extra_functionality(n_network, snapshots):
            if max_limits_extra is not None:
                max_limits_extra(n_network, snapshots)
            if no_fix_extra is not None:
                no_fix_extra(n_network, snapshots)

        logger.info("Starte Optimierung (%s)...", config.SOLVER_NAME)
        status, condition = n.optimize(
            solver_name=config.SOLVER_NAME,
            solver_options=solver_options,
            extra_functionality=extra_functionality if (max_limits_extra or no_fix_extra) else None,
        )

        if status != "ok":
            logger.error("Optimierung fehlgeschlagen: status=%s, condition=%s", status, condition)
            return False

        out_dir = save_results(n, zones, climate_year, suffix=suffix)

        if check_data is not None:
            no_hydro_fix.write_check_files(n, check_data, out_dir)

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
                            help=f"N zufällige Klimajahre ziehen (Default: {config.RANDOM_YEARS_COUNT}, "
                                 f"falls --years nicht gesetzt)")
    parser.add_argument("--year-range", type=int, nargs=2, default=list(config.RANDOM_YEARS_RANGE),
                        metavar=("MIN", "MAX"),
                        help="Jahresbereich für --random (Default: %d %d)" % config.RANDOM_YEARS_RANGE)
    parser.add_argument("--skip-existing", dest="skip_existing", action="store_true", default=True,
                        help="Bei --random bereits simulierte Jahre überspringen (Default: an)")
    parser.add_argument("--no-skip-existing", dest="skip_existing", action="store_false")
    parser.add_argument("--interconnections", choices=["eraa", "paper"], default=config.INTERCONNECTIONS,
                        help=f"Quelle der Leitungskapazitäten (Default: {config.INTERCONNECTIONS})")
    parser.add_argument("--no-hydro-fix", choices=["off", "flow", "flow+level"], default=config.NO_HYDRO_FIX,
                        help=f"Tiefe der Norwegen-Hydro-Korrektur (Default: {config.NO_HYDRO_FIX})")
    parser.add_argument("--max-limits", dest="max_limits", action="store_true", default=config.ENFORCE_MAX_LIMITS,
                        help="Länder-Import/Export-Obergrenzen erzwingen (Default: %s)"
                             % ("an" if config.ENFORCE_MAX_LIMITS else "aus"))
    parser.add_argument("--no-max-limits", dest="max_limits", action="store_false")
    parser.add_argument("--suffix", type=str, default=None,
                        help="Ergebnis-Ordner-Suffix (Default: automatisch aus den Szenario-Flags abgeleitet)")
    parser.add_argument("--bar-conv-tol", type=float, default=config.SOLVER_OPTIONS["BarConvTol"],
                        help=f"Gurobi BarConvTol (Default: {config.SOLVER_OPTIONS['BarConvTol']})")
    parser.add_argument("--threads", type=int, default=config.SOLVER_OPTIONS["Threads"],
                        help=f"Gurobi Threads (Default: {config.SOLVER_OPTIONS['Threads']})")
    args = parser.parse_args()

    # Windows-Konsolen (cp1252) können z.B. '→' nicht darstellen: ersetzen statt abbrechen
    sys.stdout.reconfigure(errors="replace")
    sys.stderr.reconfigure(errors="replace")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        ],
    )

    suffix = args.suffix if args.suffix is not None else _auto_suffix(args.interconnections, args.no_hydro_fix)
    solver_options = {**config.SOLVER_OPTIONS, "BarConvTol": args.bar_conv_tol, "Threads": args.threads}

    if args.years is not None:
        years = args.years
        logger.info("Feste Klimajahre: %s", years)
    else:
        n_random = args.random if args.random is not None else config.RANDOM_YEARS_COUNT
        years = _pick_random_years(n_random, args.year_range[0], args.year_range[1], suffix, args.skip_existing)
        if not years:
            logger.info("Keine Jahre zu simulieren. Beende.")
            return
        logger.info("Gewählte Klimajahre (zufällig): %s", years)

    first, last = config.CLIMATE_YEARS_AVAILABLE
    invalid = [y for y in years if not first <= y <= last]
    if invalid:
        parser.error(f"Klimajahre außerhalb {first}-{last}: {invalid}")

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
