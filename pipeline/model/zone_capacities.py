"""
zone_capacities.py
==================
Lädt installierte Kapazitäten (p_nom) und Speicherkapazitäten (max_hours)
für alle Zonen aus der akkumulierten Kapazitätstabelle "TY <Zieljahr>.csv".

Verwendung:
    from pipeline.model.zone_capacities import load_all_zones, get_zone_capacities

    all_zones = load_all_zones()          # DataFrame mit allen Zonen
    de_caps   = get_zone_capacities("DE") # Dict für eine Zone

Schnelltest (aus dem Projekt-Root):
    python -m pipeline.model.zone_capacities
"""

import logging
from pathlib import Path

import pandas as pd

import config

logger = logging.getLogger(__name__)

# ── Pfad ─────────────────────────────────────────────────────────────────────
CAPACITY_TABLE_PATH = (config.ACCUMULATED_DIR / config.NATIONAL_ESTIMATES_DIRNAME
                       / f"TY {config.TARGET_YEAR}.csv")

# ── Spaltenmapping: Spalte der Kapazitätstabelle → interner Schlüssel ────────
# Nur Spalten die für den Dispatch relevant sind
COLUMN_MAP = {
    # Generatoren (MW)
    "Nuclear"                                    : "nuclear",
    "Lignite"                                    : "lignite",
    "Hard Coal"                                  : "hard_coal",
    "Gas "                                       : "gas",        # Leerzeichen beachten
    "Oil"                                        : "oil",
    "Wind Onshore"                               : "wind_onshore",
    "Wind Offshore"                              : "wind_offshore",
    "Solar (Photovoltaic)"                       : "solar_pv",
    "Solar (Thermal)"                            : "solar_thermal",
    "Hydro - Run of River (Turbine)"             : "hydro_ror",
    "Hydro - Pondage (Turbine)"                  : "hydro_pondage",
    "Biofuel"                                    : "biomass",
    "Others renewable"                           : "other_res",
    "Others non-renewable"                       : "other_nonres",
    "Demand Side Response capacity"              : "dsr_total",

    # Speicher – Turbinen-/Injektionskapazität (MW)
    "Hydro - Reservoir (Turbine)"                : "hydro_reservoir",
    "Hydro - Pump Storage Open Loop (Turbine)"   : "ps_open_turbine",
    "Hydro - Pump Storage Closed Loop (Turbine)" : "ps_closed_turbine",
    "Hydro - Pump Storage Open Loop (Pumping)"   : "ps_open_pumping",
    "Hydro - Pump Storage Closed Loop (Pumping)" : "ps_closed_pumping",
    "Batteries (Injection)"                      : "battery_injection",
    "Batteries (Offtake)"                        : "battery_offtake",

    # Speicherkapazitäten (MWh) – für max_hours Berechnung
    "Hydro - Pondage - Energy Storage (MWh)"              : "mwh_pondage",
    "Hydro - Reservoir - Energy Storage (MWh)"            : "mwh_reservoir",
    "Hydro - Pump Storage Open Loop - Energy Storage (MWh)": "mwh_ps_open",
    "Hydro - Pump Storage Closed Loop - Energy Storage (MWh)": "mwh_ps_closed",
    "Batteries - Energy Storage (MWh)"                    : "mwh_battery",
}


def load_all_zones(path: Path = CAPACITY_TABLE_PATH) -> pd.DataFrame:
    """
    Lädt die gesamte Kapazitätstabelle und gibt einen bereinigten DataFrame zurück.
    Index = Zonenname, Spalten = interne Schlüssel aus COLUMN_MAP.
    """
    df = pd.read_csv(path, index_col=0)

    # Nur bekannte Spalten behalten und umbenennen
    rename = {}
    for orig_col, internal in COLUMN_MAP.items():
        # Suche nach exaktem Match oder stripped Match
        for col in df.columns:
            if col.strip() == orig_col.strip():
                rename[col] = internal
                break

    df = df[list(rename.keys())].rename(columns=rename)

    # Absolutwerte für Pumping-Kapazitäten (stehen als negative Werte in ERAA)
    for col in ["ps_open_pumping", "ps_closed_pumping",
                "battery_offtake", "battery_injection"]:
        if col in df.columns:
            df[col] = df[col].abs()

    # NaN → 0
    df = df.fillna(0.0)

    logger.info(f"{path.name} geladen: {len(df)} Zonen, {len(df.columns)} Parameter")
    return df


def get_zone_capacities(zone: str, df: pd.DataFrame = None) -> dict:
    """
    Gibt alle Kapazitäten einer Zone als Dictionary zurück,
    inklusive berechneter max_hours für Speicher.

    Args:
        zone: Zonenname z.B. "DE", "FR", "adriatic"
        df:   Optional vorgeladener DataFrame (für Batch-Verarbeitung)

    Returns:
        dict mit p_nom-Werten (MW) und max_hours-Werten
    """
    if df is None:
        df = load_all_zones()

    if zone not in df.index:
        logger.warning(f"Zone '{zone}' nicht in der Kapazitätstabelle gefunden.")
        return {}

    row = df.loc[zone]

    # ── Hilfsfunktion: max_hours berechnen ──────────────────────────────────
    def max_hours(mwh_col: str, mw_col: str) -> float:
        mwh = row.get(mwh_col, 0)
        mw  = row.get(mw_col,  0)
        if mw > 0 and mwh > 0:
            return mwh / mw
        return config.STORAGE_MAX_HOURS_FALLBACK

    caps = {
        # ── Generatoren (MW) ────────────────────────────────────────────────
        "p_nom_nuclear"       : row.get("nuclear",        0),
        "p_nom_lignite"       : row.get("lignite",        0),
        "p_nom_hard_coal"     : row.get("hard_coal",      0),
        "p_nom_gas"           : row.get("gas",            0),
        "p_nom_oil"           : row.get("oil",            0),
        "p_nom_wind_onshore"  : row.get("wind_onshore",   0),
        "p_nom_wind_offshore" : row.get("wind_offshore",  0),
        "p_nom_solar_pv"      : row.get("solar_pv",       0),
        "p_nom_solar_thermal" : row.get("solar_thermal",  0),
        "p_nom_hydro_ror"     : row.get("hydro_ror",      0),
        "p_nom_hydro_pondage" : row.get("hydro_pondage",  0),
        "p_nom_biomass"       : row.get("biomass",        0)
                              + row.get("other_res",      0),  # Biomasse + andere EE
        "p_nom_other_nonres"  : row.get("other_nonres",   0),

        # ── Speicher: Turbinen-/Injektionskapazität (MW) ─────────────────────
        "p_nom_hydro_reservoir": row.get("hydro_reservoir",   0),
        "p_nom_ps_open"        : row.get("ps_open_turbine",   0),
        "p_nom_ps_closed"      : row.get("ps_closed_turbine", 0),
        "p_nom_battery"        : row.get("battery_injection", 0),

        # Pumping-Kapazitäten (für efficiency_store in PyPSA)
        "p_nom_ps_open_pumping"  : row.get("ps_open_pumping",   0),
        "p_nom_ps_closed_pumping": row.get("ps_closed_pumping", 0),
        "p_nom_battery_offtake"  : row.get("battery_offtake",   0),

        # ── max_hours (MWh / MW) ─────────────────────────────────────────────
        "max_hours_hydro_pondage" : max_hours("mwh_pondage",   "hydro_pondage"),
        "max_hours_hydro_reservoir": max_hours("mwh_reservoir", "hydro_reservoir"),
        "max_hours_ps_open"       : max_hours("mwh_ps_open",   "ps_open_turbine"),
        "max_hours_ps_closed"     : max_hours("mwh_ps_closed", "ps_closed_turbine"),
        "max_hours_battery"       : max_hours("mwh_battery",   "battery_injection"),

        # ── DSR gesamt (wird separat aus Explicit DSR geladen) ────────────────
        "p_nom_dsr_total"     : row.get("dsr_total", 0),
    }

    return caps


def get_all_zone_names(df: pd.DataFrame = None) -> list:
    """Gibt alle verfügbaren Zonennamen zurück."""
    if df is None:
        df = load_all_zones()
    return list(df.index)


# ── Direkt ausführbar zum Testen ─────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    df = load_all_zones()

    print(f"\nVerfügbare Zonen ({len(df)}):")
    print(", ".join(df.index.tolist()))

    print("\n" + "="*55)
    print("Kapazitäten Deutschland (DE)")
    print("="*55)
    de = get_zone_capacities("DE", df)
    for k, v in de.items():
        if v > 0:
            print(f"  {k:35s}: {v:12.1f}")

    print("\n" + "="*55)
    print("Kapazitäten Frankreich (FR)")
    print("="*55)
    fr = get_zone_capacities("FR", df)
    for k, v in fr.items():
        if v > 0:
            print(f"  {k:35s}: {v:12.1f}")
