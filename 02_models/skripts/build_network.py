"""
10_build_network.py
===================
Baut ein PyPSA-Netz für beliebige Zonen auf.
Nutzt 07, 08 und 09 als Datenquellen.

Verwendung:
    from 10_build_network import build_network
    n = build_network(active_zones=["DE"], climate_year="2012")

Zonen schrittweise erweitern:
    ACTIVE_ZONES = ["DE"]                          # Start
    ACTIVE_ZONES = ["DE", "FR", "AT", "NL"]       # Schritt 2
    ACTIVE_ZONES = ALL_ZONES                       # Vollständig
"""

import pypsa
import pandas as pd
import numpy as np
import logging
from pathlib import Path

# ── Imports der eigenen Module ───────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent))

from gather_global_params import get_simulation_params
from load_zone_capacities import load_all_zones, get_zone_capacities
from load_timeseries import load_zone_timeseries

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── Alle verfügbaren Zonen ───────────────────────────────────────────────────
ALL_ZONES = [
    "DE", "FR", "AT", "BE", "NL", "CH", "CZ", "PL", "DK",
    "ES", "PT", "IT", "GR", "SE", "NO", "FI", "UK", "IE",
    "LU", "MT", "CY", "TR", "UA",
    "adriatic", "baltic", "other eastern european",
]

# ── DSR-Pfad ─────────────────────────────────────────────────────────────────
DSR_PATH = Path("01_data/04b_accumulated_data_per_node/"
                "ERAA 2022 PEMMDB National Estimates/Explicit DSR.csv")


# ── Hilfsfunktion: DSR für eine Zone laden ───────────────────────────────────
def _load_dsr(zone: str) -> pd.DataFrame:
    """Gibt DSR-Bänder für eine Zone zurück (nur aktive Bänder)."""
    try:
        dsr = pd.read_csv(DSR_PATH)
        row = dsr[dsr["Bidding Zone"] == zone]
        if row.empty:
            return pd.DataFrame()
        return row.iloc[0]
    except Exception as e:
        logger.warning(f"DSR für {zone} nicht geladen: {e}")
        return pd.Series()


# ── Kernfunktion: Zone ins Netz einfügen ─────────────────────────────────────
def add_zone(n: pypsa.Network,
             zone: str,
             caps: dict,
             ts: dict,
             params: dict) -> None:
    """
    Fügt alle Komponenten einer Zone zum PyPSA-Netz hinzu:
    Bus, Generatoren (konventionell + vRES), Speicher, DSR, Last.

    Args:
        n     : PyPSA-Netz
        zone  : Zonenname z.B. "DE"
        caps  : Kapazitäten aus 08_load_zone_capacities
        ts    : Zeitreihen aus 09_load_timeseries
        params: Globale Parameter aus 07_gather_global_params
    """
    mc = params["marginal_costs"]

    # ── Bus ──────────────────────────────────────────────────────────────────
    n.add("Bus", zone, v_nom=380, carrier="AC")
    logger.info(f"  {zone}: Bus hinzugefügt")

    # ── Konventionelle Generatoren ────────────────────────────────────────────
    # Gas + Others non-renewable aggregiert (paper-konform, Supplement S.3)
    p_nom_gas = caps["p_nom_gas"] + caps["p_nom_other_nonres"]
    if p_nom_gas > 0:
        n.add("Generator", f"Gas_{zone}",
              bus=zone,
              p_nom=p_nom_gas,
              marginal_cost=mc["gas_ccgt"],
              carrier="gas")

    if caps["p_nom_lignite"] > 0:
        n.add("Generator", f"Lignite_{zone}",
              bus=zone,
              p_nom=caps["p_nom_lignite"],
              marginal_cost=mc["lignite"],
              carrier="lignite")

    if caps["p_nom_hard_coal"] > 0:
        n.add("Generator", f"Coal_{zone}",
              bus=zone,
              p_nom=caps["p_nom_hard_coal"],
              marginal_cost=mc["hard_coal"],
              carrier="coal")

    if caps["p_nom_nuclear"] > 0:
        n.add("Generator", f"Nuclear_{zone}",
              bus=zone,
              p_nom=caps["p_nom_nuclear"],
              marginal_cost=mc["nuclear"],
              carrier="nuclear")

    if caps["p_nom_oil"] > 0:
        n.add("Generator", f"Oil_{zone}",
              bus=zone,
              p_nom=caps["p_nom_oil"],
              marginal_cost=mc["oil"],
              carrier="oil")

    # Biomasse + Others renewable aggregiert (paper-konform, Supplement S.3)
    if caps["p_nom_biomass"] > 0:
        n.add("Generator", f"Biomass_{zone}",
              bus=zone,
              p_nom=caps["p_nom_biomass"],
              marginal_cost=mc["biomass"],
              carrier="biomass")

    # ── vRES: Wind Onshore ────────────────────────────────────────────────────
    if caps["p_nom_wind_onshore"] > 0:
        n.add("Generator", f"WindOn_{zone}",
              bus=zone,
              p_nom=caps["p_nom_wind_onshore"],
              marginal_cost=0.0,
              carrier="wind")
        n.generators_t.p_max_pu[f"WindOn_{zone}"] = (
            ts["wind_onshore"].clip(0, 1))

    # ── vRES: Wind Offshore ───────────────────────────────────────────────────
    if caps["p_nom_wind_offshore"] > 0:
        n.add("Generator", f"WindOff_{zone}",
              bus=zone,
              p_nom=caps["p_nom_wind_offshore"],
              marginal_cost=0.0,
              carrier="wind")
        n.generators_t.p_max_pu[f"WindOff_{zone}"] = (
            ts["wind_offshore"].clip(0, 1))

    # ── vRES: Solar PV ────────────────────────────────────────────────────────
    if caps["p_nom_solar_pv"] > 0:
        n.add("Generator", f"Solar_{zone}",
              bus=zone,
              p_nom=caps["p_nom_solar_pv"],
              marginal_cost=0.0,
              carrier="solar")
        n.generators_t.p_max_pu[f"Solar_{zone}"] = (
            ts["solar_pv"].clip(0, 1))

    # ── Hydro: Run of River ───────────────────────────────────────────────────
    if caps["p_nom_hydro_ror"] > 0:
        ror_inflow = ts["hydro_ror"]
        ror_cf     = (ror_inflow / caps["p_nom_hydro_ror"]).clip(0, 1)
        n.add("Generator", f"RoR_{zone}",
              bus=zone,
              p_nom=caps["p_nom_hydro_ror"],
              marginal_cost=0.0,
              carrier="hydro")
        n.generators_t.p_max_pu[f"RoR_{zone}"] = ror_cf

    # ── Hydro: Pondage ────────────────────────────────────────────────────────
    if caps["p_nom_hydro_pondage"] > 0:
        pondage_inflow = ts["hydro_pondage"]
        pondage_cf     = (pondage_inflow / caps["p_nom_hydro_pondage"]).clip(0, 1)
        n.add("Generator", f"Pondage_{zone}",
              bus=zone,
              p_nom=caps["p_nom_hydro_pondage"],
              marginal_cost=0.0,
              carrier="hydro")
        n.generators_t.p_max_pu[f"Pondage_{zone}"] = pondage_cf

    # ── Speicher: Reservoir ───────────────────────────────────────────────────
    if caps["p_nom_hydro_reservoir"] > 0:
        n.add("StorageUnit", f"Reservoir_{zone}",
              bus=zone,
              p_nom=caps["p_nom_hydro_reservoir"],
              marginal_cost=0.0,
              carrier="hydro",
              efficiency_store=0.87,
              efficiency_dispatch=0.87,
              cyclic_state_of_charge=True,
              max_hours=caps["max_hours_hydro_reservoir"])
        n.storage_units_t.inflow[f"Reservoir_{zone}"] = ts["hydro_reservoir"]

    # ── Speicher: Pump Storage Open Loop ─────────────────────────────────────
    if caps["p_nom_ps_open"] > 0:
        n.add("StorageUnit", f"PSOpen_{zone}",
              bus=zone,
              p_nom=caps["p_nom_ps_open"],
              marginal_cost=0.0,
              carrier="hydro",
              efficiency_store=0.87,
              efficiency_dispatch=0.87,
              cyclic_state_of_charge=True,
              max_hours=caps["max_hours_ps_open"])
        n.storage_units_t.inflow[f"PSOpen_{zone}"] = ts["hydro_ps_open"]

    # ── Speicher: Pump Storage Closed Loop ────────────────────────────────────
    if caps["p_nom_ps_closed"] > 0:
        # Kein Inflow: geschlossenes System, kein natürlicher Zufluss
        n.add("StorageUnit", f"PSClosed_{zone}",
              bus=zone,
              p_nom=caps["p_nom_ps_closed"],
              marginal_cost=0.0,
              carrier="hydro",
              efficiency_store=0.87,
              efficiency_dispatch=0.87,
              cyclic_state_of_charge=True,
              max_hours=caps["max_hours_ps_closed"])

    # ── Speicher: Batterie ────────────────────────────────────────────────────
    if caps["p_nom_battery"] > 0:
        n.add("StorageUnit", f"Battery_{zone}",
              bus=zone,
              p_nom=caps["p_nom_battery"],
              marginal_cost=0.0,
              carrier="battery",
              efficiency_store=0.92,
              efficiency_dispatch=0.92,
              cyclic_state_of_charge=True,
              max_hours=caps["max_hours_battery"])

    # ── DSR ───────────────────────────────────────────────────────────────────
    dsr_row = _load_dsr(zone)
    if not dsr_row.empty:
        for band in range(1, 9):
            cap   = dsr_row.get(f"Price Band {band} capacity (MW)", 0)
            price = dsr_row.get(
                f"Activation Price for demand reduction for Price Band {band} (EUR/MWh)", 0)
            hours = dsr_row.get(
                f"Max hours to be used per day for Price Band {band}", 0)
            if cap <= 0 or price <= 0:
                continue

            # Max. Stunden/Tag → p_min_pu Untergrenze
            # Wenn hours=24: Last kann komplett auf 0 reduziert werden
            # Wenn hours=8: Last kann maximal 8/24 = 33% reduziert werden
            p_min_pu = 1.0 - (hours / 24.0)  # Untergrenze: 1 - max_reduction

            n.add("Load", f"DSR_{zone}_band{band}",
                bus=zone,
                p_set=cap,           # feste DSR-Kapazität als Last
                p_min_pu=p_min_pu)   # kann bis auf p_min_pu reduziert werden

    # ── Load Shedding (VOLL) ──────────────────────────────────────────────────
    n.add("Generator", f"LoadShedding_{zone}",
          bus=zone,
          p_nom=1e6,
          marginal_cost=params["voll"],
          carrier="mismatch")

    # ── Last ──────────────────────────────────────────────────────────────────
    n.add("Load", f"Load_{zone}",
          bus=zone,
          p_set=ts["load"])

    logger.info(f"  {zone}: alle Komponenten hinzugefügt")


# ── Haupt-API ────────────────────────────────────────────────────────────────
def build_network(active_zones: list = None,
                  climate_year: str = "2012",
                  target_year: int = 2030) -> pypsa.Network:
    """
    Baut ein vollständiges PyPSA-Netz für die gewählten Zonen.

    Args:
        active_zones : Liste der Zonen z.B. ["DE"] oder ["DE", "FR", "AT"]
                       None → alle verfügbaren Zonen
        climate_year : Klimajahr für Zeitreihen z.B. "2012"
        target_year  : Zieljahr für Kapazitäten und Parameter (2030)

    Returns:
        pypsa.Network mit allen Komponenten, bereit zur Optimierung
    """
    if active_zones is None:
        active_zones = ALL_ZONES

    logger.info(f"Baue Netz für {len(active_zones)} Zonen: {active_zones}")
    logger.info(f"Klimajahr: {climate_year}, Zieljahr: {target_year}")

    # ── Globale Parameter laden ───────────────────────────────────────────────
    params = get_simulation_params(target_year)

    # ── Kapazitätstabelle laden ───────────────────────────────────────────────
    caps_df = load_all_zones()

    # ── Netz initialisieren ───────────────────────────────────────────────────
    n = pypsa.Network()

    # Timestamps: erst nach Last-Zeitreihe der ersten Zone setzen
    timestamps = None

    # Carrier definieren
    for carrier in ["AC", "gas", "coal", "lignite", "nuclear",
                    "biomass", "oil", "wind", "solar",
                    "hydro", "battery", "mismatch"]:
        n.add("Carrier", carrier)

    # ── Zonen-Schleife ────────────────────────────────────────────────────────
    for zone in active_zones:
        logger.info(f"Verarbeite Zone: {zone}")

        # Kapazitäten
        caps = get_zone_capacities(zone, caps_df)
        if not caps:
            logger.warning(f"  {zone}: keine Kapazitäten gefunden, überspringe")
            continue

        # Zeitreihen
        ts = load_zone_timeseries(zone, climate_year=climate_year)

        # Snapshots beim ersten Durchlauf setzen
        if timestamps is None:
            timestamps = ts["load"].index
            n.set_snapshots(timestamps)

        # Zone ins Netz einfügen
        add_zone(n, zone, caps, ts, params)

    logger.info(f"Netz aufgebaut: {len(n.buses)} Busse, "
                f"{len(n.generators)} Generatoren, "
                f"{len(n.storage_units)} Speicher, "
                f"{len(n.loads)} Lasten")
    return n


# ── Direkt ausführbar zum Testen ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys

    # Start: nur Deutschland
    ACTIVE_ZONES = ["DE"]
    CLIMATE_YEAR = "2012"

    n = build_network(active_zones=ACTIVE_ZONES, climate_year=CLIMATE_YEAR)

    print("\n── Debug: Netz-Übersicht ──")
    print(f"Busse:       {list(n.buses.index)}")
    print(f"Generatoren: {len(n.generators)}")
    print(f"Speicher:    {len(n.storage_units)}")
    print(f"Lasten:      {len(n.loads)}")
    print(f"Snapshots:   {len(n.snapshots)}")

    print("\n── Kapazitäten ──")
    print(n.generators[["p_nom", "marginal_cost"]].to_string())
    print(n.storage_units[["p_nom", "max_hours"]].to_string())

    print("\n── Optimierung ──")
    status, condition = n.optimize(
        solver_name="gurobi",
        solver_options={
            "Method"        : 2,
            "Crossover"     : 0,
            "Threads"       : 4,
            "BarConvTol"    : 1e-6,
            "DualReductions": 0,
        }
    )

    if status != "ok":
        print(f"Optimierung fehlgeschlagen: {status}, {condition}")
        sys.exit(1)

    lmp = n.buses_t.marginal_price
    for zone in ACTIVE_ZONES:
        if zone in lmp.columns:
            print(f"\n── Preiszeitreihe {zone} ──")
            print(f"  Jahres-Ø:  {lmp[zone].mean():.2f} €/MWh")
            print(f"  Median:    {lmp[zone].median():.2f} €/MWh")
            print(f"  p95:       {lmp[zone].quantile(0.95):.2f} €/MWh")

    print("\n── Erzeugung (GWh/Jahr) ──")
    for gen in n.generators.index:
        gwh = n.generators_t.p[gen].sum() / 1000
        if gwh > 0.1:
            print(f"  {gen:30s}: {gwh:8.1f} GWh")