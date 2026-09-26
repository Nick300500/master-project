"""
results.py
==========
Schreibt die Ergebnisse eines gelösten PyPSA-Netzes als CSV-Dateien.

Ordner: config.RESULTS_DIR/<Zonen>_CY<Klimajahr><Suffix>/
  prices_lmp.csv              Strompreis je Zone und Stunde (€/MWh)
  dispatch_generators.csv     Erzeugung je Kraftwerk und Stunde (MW)
  storage_dispatch.csv        Speicher-Entladung (MW)
  storage_store.csv           Speicher-Ladung (MW)
  storage_state_of_charge.csv Speicherfüllstand (MWh)
  interconnection_flows.csv   Leitungsflüsse (MW)
  capacities_*.csv            installierte Kapazitäten (Kraftwerke, Speicher, Leitungen)
  loads.csv, total_loads.csv  Last stündlich bzw. Jahressumme je Zone
  summary_annual.csv          Mittelwert/Median/95%-Quantil der Preise, Lastabwurf
"""

import logging
from pathlib import Path

import pandas as pd
import pypsa

import config

logger = logging.getLogger(__name__)


def result_dir(active_zones: list, climate_year: str, suffix: str = "") -> Path:
    """Ergebnisordner eines Laufs, z.B. 04_results/DE_FR_CY2012_paperNTC."""
    return config.RESULTS_DIR / f"{'_'.join(active_zones)}_CY{climate_year}{suffix}"


def save_results(n: pypsa.Network, active_zones: list, climate_year: str,
                 suffix: str = ""):
    """
    Speichert alle Ergebnisse eines gelösten Netzes in
    config.RESULTS_DIR/<Zonen>_CY<Jahr><Suffix>/ und gibt den Ordner zurück.
    """
    out_dir = result_dir(active_zones, climate_year, suffix)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Preiszeitreihen (LMP) pro Zone
    lmp = n.buses_t.marginal_price
    lmp.to_csv(out_dir / "prices_lmp.csv")

    # Dispatch je Generator
    n.generators_t.p.to_csv(out_dir / "dispatch_generators.csv")

    # Speicher: Dispatch, Laden, State of Charge
    n.storage_units_t.p_dispatch.to_csv(out_dir / "storage_dispatch.csv")
    n.storage_units_t.p_store.to_csv(out_dir / "storage_store.csv")
    n.storage_units_t.state_of_charge.to_csv(out_dir / "storage_state_of_charge.csv")

    # Interconnection-Flüsse
    if len(n.links) > 0:
        n.links_t.p0.to_csv(out_dir / "interconnection_flows.csv")

    # Kapazitäten (statisch)
    n.generators[["bus", "p_nom", "marginal_cost", "carrier"]].to_csv(
        out_dir / "capacities_generators.csv")
    n.storage_units[["bus", "p_nom", "max_hours", "carrier"]].to_csv(
        out_dir / "capacities_storage.csv")
    if len(n.links) > 0:
        n.links[["bus0", "bus1", "p_nom", "carrier"]].to_csv(
            out_dir / "capacities_links.csv")

    # Lasten (stündlich, alle Load-Komponenten)
    load_ts = n.loads_t.p if not n.loads_t.p.empty else n.loads_t.p_set
    load_ts.to_csv(out_dir / "loads.csv")

    # Gesamtlast je Zone (über alle Load-Komponenten pro Zone)
    total_load_rows = []
    if not n.loads.empty and "bus" in n.loads.columns:
        bus_map = n.loads["bus"]  # Series: load-name → bus-name
        for zone in active_zones:
            zone_cols = bus_map.index[bus_map == zone].intersection(load_ts.columns)
            total_load_gwh = load_ts[zone_cols].sum(axis=1).sum() / 1000.0 if len(zone_cols) > 0 else 0.0
            total_load_rows.append({"zone": zone, "total_load_gwh": total_load_gwh})
    else:
        total_load_rows = [{"zone": zone, "total_load_gwh": 0.0} for zone in active_zones]

    total_load = pd.DataFrame(total_load_rows)
    total_load.to_csv(out_dir / "total_loads.csv", index=False)

    # Zusammenfassung (Jahreswerte)
    summary = pd.DataFrame({
        "zone": active_zones,
        "climate_year": climate_year,
        "price_mean_eur_mwh": [lmp[z].mean() if z in lmp.columns else None
                                for z in active_zones],
        "price_median_eur_mwh": [lmp[z].median() if z in lmp.columns else None
                                  for z in active_zones],
        "price_p95_eur_mwh": [lmp[z].quantile(0.95) if z in lmp.columns else None
                               for z in active_zones],
        "load_shedding_gwh": [
            n.generators_t.p.get(f"LoadShedding_{z}", pd.Series(0)).sum() / 1000
            for z in active_zones
        ],
    })
    summary.to_csv(out_dir / "summary_annual.csv", index=False)

    logger.info(f"Ergebnisse gespeichert in {out_dir}")
    return out_dir
