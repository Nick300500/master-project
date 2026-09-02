"""
build_network.py
=================
Baut ein PyPSA-Netz für beliebige Zonen auf.
Nutzt gather_global_params.py, load_zone_capacities.py und
load_timeseries.py als Datenquellen.

Verwendung:
    from build_network import build_network
    n = build_network(active_zones=["DE"], climate_year="2012")

Zonen schrittweise erweitern:
    ACTIVE_ZONES = ["DE"]                          # Start
    ACTIVE_ZONES = ["DE", "FR", "AT", "NL"]       # Schritt 2
    ACTIVE_ZONES = ALL_ZONES                       # Vollständig

Hinweise zur Hydro-Modellierung:
    - Reservoir:   efficiency_store=1.0 (kein Pumpverlust), efficiency_dispatch=0.87
    - PSOpen:      efficiency_store=0.87 (Pumpverlust), p_min_pu aus Pumping-Kapazität
    - PSClosed:    efficiency_store=0.87, kein natürlicher Inflow
    - ERAA-Sonderfall NO: Gesamte Speicherwasserkraft unter "PS Open Loop" klassifiziert.
      caps["p_nom_ps_open"] und ts["hydro_ps_open"] enthalten das vollständige
      norwegische Reservoir-System. Keine Umleitungslogik nötig — ERAA ist konsistent.
"""

import pypsa
import pandas as pd
import numpy as np
import logging
from pathlib import Path

# ── Imports der eigenen Module ───────────────────────────────────────────────
import sys
sys.path.insert(0, str(Path(__file__).parent))

from gather_global_params import get_simulation_params, compute_marginal_costs
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
_PROJECT_ROOT = Path(__file__).parent.parent.parent
DSR_PATH = (_PROJECT_ROOT / "01_data/04b_accumulated_data_per_node"
            / "ERAA 2022 PEMMDB National Estimates/Explicit DSR.csv")

# ── ERAA 2022 Hydro-Effizienz-Konstanten ────────────────────────────────────
# Turbinen-Wirkungsgrad (Dispatch): einheitlich für alle Hydro-Typen
HYDRO_EFF_DISPATCH = 0.87
# Pump-Wirkungsgrad (Store): nur für echte Pumpspeicher (PS Open/Closed)
HYDRO_EFF_STORE    = 0.87
# Reservoir speichert Wasser ohne Energieverlust (kein Pumpen)
RESERVOIR_EFF_STORE = 1.0


# ── Hilfsfunktion: DSR für eine Zone laden ───────────────────────────────────
def _load_dsr(zone: str) -> pd.Series:
    """Gibt DSR-Zeile für eine Zone zurück (leer wenn nicht vorhanden)."""
    try:
        dsr = pd.read_csv(DSR_PATH)
        row = dsr[dsr["Bidding Zone"] == zone]
        if row.empty:
            return pd.Series()
        return row.iloc[0]
    except Exception as e:
        logger.warning(f"DSR für {zone} nicht geladen: {e}")
        return pd.Series()


# ── Hilfsfunktion: p_min_pu für Pumpspeicher ─────────────────────────────────
def _pumping_p_min_pu(caps: dict,
                      turbine_key: str,
                      pumping_key: str,
                      zone: str) -> float:
    """
    Berechnet p_min_pu für eine Pumpspeicher-StorageUnit.

    PyPSA-Konvention: p_min_pu ≤ 0 bedeutet Pumpen (Laden).
    Wert = -abs(pumping_capacity) / turbine_capacity.

    Der Pumping-Wert aus TY2030 kann positiv oder negativ in der Quelle sein —
    abs() stellt sicher dass das Vorzeichen korrekt gesetzt wird.

    Falls pumping_key nicht im caps-Dict vorhanden ist, wird -1 zurückgegeben
    (PyPSA-Default: volle p_nom als Pumpleistung) und eine Warnung geloggt.

    Args:
        caps        : Kapazitäts-Dict der Zone
        turbine_key : Key der Turbinenkapazität z.B. "p_nom_ps_open"
        pumping_key : Key der Pumpleistung z.B. "p_nom_ps_open_pumping"
                      Wert kann positiv oder negativ sein (abs() wird angewendet)
        zone        : Zonenname für Logging

    Returns:
        p_min_pu als float ≤ 0
    """
    p_nom_turbine = caps.get(turbine_key, 0.0)
    if p_nom_turbine <= 0:
        return -1.0

    p_nom_pump = caps.get(pumping_key, None)

    if p_nom_pump is None:
        logger.warning(
            f"  {zone}: '{pumping_key}' nicht in caps — "
            f"p_min_pu=-1 (volle Pumpleistung). Pumping-Key in "
            f"load_zone_capacities.py prüfen."
        )
        return -1.0

    if p_nom_pump == 0:
        # Keine Pumpleistung vorgesehen → reine Turbine (z.B. Reservoir)
        return 0.0

    # abs() weil TY2030-Pumping-Werte manchmal negativ geliefert werden
    p_min_pu = -abs(p_nom_pump) / p_nom_turbine
    logger.debug(
        f"  {zone}: {pumping_key}={p_nom_pump:.1f} MW / "
        f"{turbine_key}={p_nom_turbine:.1f} MW → p_min_pu={p_min_pu:.4f}"
    )
    return p_min_pu


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
    # Modelliert als Generator mit CF-Zeitreihe (kein Speicher, kein Dispatch)
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
    # Tagesregulierung: Generator mit täglichem Inflow-CF (kein Wochenspeicher)
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
    # Natürlicher Zufluss, kein Pumpen → efficiency_store=1.0
    # ERAA-Sonderfall NO: Reservoir-Kapazität ist 0, alles unter PSOpen (s.u.)
    if caps["p_nom_hydro_reservoir"] > 0:
        n.add("StorageUnit", f"Reservoir_{zone}",
              bus=zone,
              p_nom=caps["p_nom_hydro_reservoir"],
              p_min_pu=0.0,                        # kein Pumpen, nur Turbinieren
              marginal_cost=0.0,
              carrier="hydro",
              efficiency_store=RESERVOIR_EFF_STORE, # 1.0: Wasser stauen ohne Verlust
              efficiency_dispatch=HYDRO_EFF_DISPATCH,
              cyclic_state_of_charge=True,
              max_hours=caps["max_hours_hydro_reservoir"])
        n.storage_units_t.inflow[f"Reservoir_{zone}"] = ts["hydro_reservoir"]

    # ── Speicher: Pump Storage Open Loop ─────────────────────────────────────
    # Natürlicher Zufluss + Pumpen möglich.
    #
    # ERAA-Sonderfall NO:
    #   ENTSO-E klassifiziert die gesamte norwegische Speicherwasserkraft
    #   als "Pump Storage Open Loop" (kein separater Reservoir-Eintrag).
    #   caps["p_nom_ps_open"] = 37.830 MW (Turbine)
    #   caps["p_nom_ps_open_pump"] = 1.093 MW (minimale Pumpleistung)
    #   ts["hydro_ps_open"] enthält den vollen Reservoir-Inflow (~20.500 MW Ø)
    #   max_hours ≈ 2.368 h → saisonaler Speicher, physikalisch korrekt.
    #   Keine Umleitungslogik nötig — ERAA ist intern konsistent.
    if caps["p_nom_ps_open"] > 0:
        p_min_pu_ps_open = _pumping_p_min_pu(
            caps,
            turbine_key="p_nom_ps_open",
            pumping_key="p_nom_ps_open_pumping",
            zone=zone,
        )
        n.add("StorageUnit", f"PSOpen_{zone}",
              bus=zone,
              p_nom=caps["p_nom_ps_open"],
              p_min_pu=p_min_pu_ps_open,
              marginal_cost=0.0,
              carrier="hydro",
              efficiency_store=HYDRO_EFF_STORE,
              efficiency_dispatch=HYDRO_EFF_DISPATCH,
              cyclic_state_of_charge=True,
              max_hours=caps["max_hours_ps_open"])
        n.storage_units_t.inflow[f"PSOpen_{zone}"] = ts["hydro_ps_open"]

    # ── Speicher: Pump Storage Closed Loop ────────────────────────────────────
    # Kein natürlicher Zufluss (geschlossenes System).
    if caps["p_nom_ps_closed"] > 0:
        p_min_pu_ps_closed = _pumping_p_min_pu(
            caps,
            turbine_key="p_nom_ps_closed",
            pumping_key="p_nom_ps_closed_pumping",
            zone=zone,
        )
        n.add("StorageUnit", f"PSClosed_{zone}",
              bus=zone,
              p_nom=caps["p_nom_ps_closed"],
              p_min_pu=p_min_pu_ps_closed,
              marginal_cost=0.0,
              carrier="hydro",
              efficiency_store=HYDRO_EFF_STORE,
              efficiency_dispatch=HYDRO_EFF_DISPATCH,
              cyclic_state_of_charge=True,
              max_hours=caps["max_hours_ps_closed"])
        # Kein Inflow für geschlossene Systeme

    # ── Speicher: Batterie ────────────────────────────────────────────────────
    if caps["p_nom_battery"] > 0:
        n.add("StorageUnit", f"Battery_{zone}",
              bus=zone,
              p_nom=caps["p_nom_battery"],
              p_min_pu=-1.0,                       # volle Ladeleistung = p_nom
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
            if cap <= 0 or price <= 0:
                continue

            # DSR als Generator (sign=+1, default): Dispatch reduziert Nettolast auf dem Bus.
            # Aktiviert sich, wenn Marktpreis >= marginal_cost (= Aktivierungspreis).
            # Tagesstunden-Limit bewusst weggelassen (Vereinfachung).
            n.add("Generator", f"DSR_{zone}_band{band}",
                  bus=zone,
                  p_nom=cap,
                  p_nom_extendable=False,
                  p_min_pu=0.0,
                  p_max_pu=1.0,
                  marginal_cost=price,
                  carrier="DSR")

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
                  target_year: int = 2030,
                  gas_price_eur_mwh_th: float = None) -> pypsa.Network:
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

    if gas_price_eur_mwh_th is not None:
        params["fuel_costs"]["gas"] = gas_price_eur_mwh_th
        params["marginal_costs"] = compute_marginal_costs(
            params["fuel_costs"], params["efficiencies"],
            params["co2_factors"], params["co2_price"],
            vom=params["vom_costs"],
        )
        logger.info(f"Gas-Preis überschrieben: {gas_price_eur_mwh_th:.2f} €/MWh_th "
                    f"→ Gas-CCGT MC = {params['marginal_costs']['gas_ccgt']:.2f} €/MWh_el")

    # ── Kapazitätstabelle laden ───────────────────────────────────────────────
    caps_df = load_all_zones()

    # ── Netz initialisieren ───────────────────────────────────────────────────
    n = pypsa.Network()

    # Carrier definieren
    for carrier in ["AC", "gas", "coal", "lignite", "nuclear",
                    "biomass", "oil", "wind", "solar",
                    "hydro", "battery", "mismatch"]:
        n.add("Carrier", carrier)

    # ── Zonen-Schleife ────────────────────────────────────────────────────────
    timestamps = None

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

    ACTIVE_ZONES = ["NO"]
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
    print(n.storage_units[["p_nom", "max_hours", "p_min_pu"]].to_string())

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

    print("\n── Speicher p_min_pu (Pumpleistungs-Check) ──")
    print(n.storage_units[["p_nom", "p_min_pu", "max_hours"]].to_string())