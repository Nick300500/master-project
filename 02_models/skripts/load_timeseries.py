"""
09_load_timeseries.py
=====================
Lädt alle stündlichen Zeitreihen für eine Zone und ein Klimajahr
aus den akkumulierten ERAA-Dateien.

Verwendung in anderen Skripten:
    from 09_load_timeseries import load_zone_timeseries
    ts = load_zone_timeseries("DE", climate_year="2012")

Gibt Dictionary zurück mit pd.Series (8760h, Index = Timestamps 2030):
    ts["load"]          – Last (MW)
    ts["wind_onshore"]  – CF Wind Onshore (0–1)
    ts["wind_offshore"] – CF Wind Offshore (0–1)
    ts["solar_pv"]      – CF Solar PV (0–1)
    ts["hydro_ror"]     – Inflow RoR (MW)
    ts["hydro_pondage"] – Inflow Pondage (MW)
    ts["hydro_reservoir"]– Inflow Reservoir (MW)
    ts["hydro_ps_open"] – Inflow Pump Storage Open Loop (MW)
    ts["hydro_ps_closed"]– Inflow Pump Storage Closed Loop (MW, meist 0)

Optional (nur laden wenn benötigt):
    ts["load_bat"]      – Zusatzlast Batterien (MW)
    ts["load_ev"]       – Zusatzlast E-Fahrzeuge (MW)
    ts["load_hp"]       – Zusatzlast Wärmepumpen (MW)
"""

from pathlib import Path
import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── Basispfad ────────────────────────────────────────────────────────────────
DATA_DIR = Path("01_data/04b_accumulated_data_per_node")

# ── Pfad-Templates (Zone wird als {zone} eingesetzt) ─────────────────────────
PATHS = {
    "load"           : DATA_DIR / "Demand/Demand Time Series/Demand_TimeSeries_2030_NationalTrends_without_bat/{zone}_accumulated.csv",
    "load_bat"       : DATA_DIR / "Demand/Detailed demand (batteries, EVs, HPs)/BAT_2030/{zone}_accumulated.csv",
    "load_ev"        : DATA_DIR / "Demand/Detailed demand (batteries, EVs, HPs)/EV_2030/{zone}_accumulated.csv",
    "load_hp"        : DATA_DIR / "Demand/Detailed demand (batteries, EVs, HPs)/HP_2030/{zone}_accumulated.csv",
    "wind_onshore"   : DATA_DIR / "Climate Data/Wind Onshore/PECD_Wind_Onshore_2030_edition 2022.1/{zone}_accumulated.csv",
    "wind_offshore"  : DATA_DIR / "Climate Data/Wind Offshore/PECD_Wind_Offshore_2030_edition 2022.1/{zone}_accumulated.csv",
    "solar_pv"       : DATA_DIR / "Climate Data/Solar/PECD_LFSolarPV_2030_edition 2022.1/{zone}_accumulated.csv",
    "hydro_ror"      : DATA_DIR / "Climate Data/Hydro Inflows/Run of River/{zone}_accumulated.csv",
    "hydro_pondage"  : DATA_DIR / "Climate Data/Hydro Inflows/Pondage/{zone}_accumulated.csv",
    "hydro_reservoir": DATA_DIR / "Climate Data/Hydro Inflows/Reservoir/{zone}_accumulated.csv",
    "hydro_ps_open"  : DATA_DIR / "Climate Data/Hydro Inflows/Pump storage - Open Loop/{zone}_accumulated.csv",
    "hydro_ps_closed": DATA_DIR / "Climate Data/Hydro Inflows/Pump Storage - Closed Loop/{zone}_accumulated.csv",
}

# Metadaten-Zeilen die übersprungen werden (unterschiedlich je Dateityp)
SKIPROWS = {
    "load"           : 10,   # war 9, korrigiert
    "load_bat"       : 10,
    "load_ev"        : 10,
    "load_hp"        : 10,
    "wind_onshore"   : 10,
    "wind_offshore"  : 10,
    "solar_pv"       : 10,
    "hydro_ror"      : 11,
    "hydro_pondage"  : 11,
    "hydro_reservoir": 11,
    "hydro_ps_open"  : 11,
    "hydro_ps_closed": 11,
}

# Hydro Inflows: täglich (365 Werte) oder wöchentlich (52-53 Werte)
HYDRO_KEYS = {"hydro_ror", "hydro_pondage", "hydro_reservoir",
              "hydro_ps_open", "hydro_ps_closed"}

# CF-Zeitreihen: Werte zwischen 0 und 1
CF_KEYS = {"wind_onshore", "wind_offshore", "solar_pv"}


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _find_climate_col(df: pd.DataFrame, climate_year: str) -> str:
    """Findet die Spalte für das gewählte Klimajahr (auch als '2012.0')."""
    for col in df.columns:
        if str(col).startswith(str(climate_year)):
            return col
    available = [c for c in df.columns[2:7]]
    raise ValueError(f"Klimajahr {climate_year} nicht gefunden. "
                     f"Verfügbare Spalten (erste 5): {available}")


def _read_standard_timeseries(path: Path, climate_year: str,
                               skiprows: int) -> pd.Series:
    """
    Liest eine stündliche ERAA-Zeitreihe ein (Last, Wind, Solar).
    Gibt pd.Series mit 8760 Werten zurück.
    """
    df = pd.read_csv(path, skiprows=skiprows, header=0, on_bad_lines='skip')
    df = df.rename(columns={df.columns[0]: "Date", df.columns[1]: "Hour"})
    df = df[pd.to_numeric(df["Hour"], errors="coerce").notna()]

    col = _find_climate_col(df, climate_year)
    series = pd.to_numeric(df[col].values, errors="coerce")
    series = pd.Series(series,
                       index=pd.date_range("2030-01-01", periods=len(series), freq="h"))
    series = series.interpolate().fillna(0)
    return series.iloc[:8760]


def _read_hydro_inflow(path: Path, climate_year: str,
                        skiprows: int, p_nom: float = None) -> pd.Series:
    # Rohdaten ohne skiprows laden um den richtigen Block zu finden
    raw = pd.read_csv(path, header=None)
    
    # Klimajahr-Spalten finden (suche nach dem Jahr als Zellwert)
    climate_year_int = int(climate_year)
    col_idx = None
    header_row = None
    
    for row_idx in range(min(15, len(raw))):
        for ci, val in enumerate(raw.iloc[row_idx].values):
            try:
                if int(float(str(val))) == climate_year_int:
                    col_idx = ci
                    header_row = row_idx
                    break
            except (ValueError, TypeError):
                continue
        if col_idx is not None:
            break
    
    if col_idx is None:
        raise ValueError(f"Klimajahr {climate_year} nicht in {path.name} gefunden.")
    
    # Datenwerte ab der Zeile nach dem Header
    data_start = header_row + 1
    values = pd.to_numeric(raw.iloc[data_start:, col_idx].values,
                           errors="coerce")
    values = pd.Series(values).fillna(0).values
    
    # Täglich oder wöchentlich?
    n = len(values)
    if n >= 350:
        repeat_h = 24
        values = values[:365]
    else:
        repeat_h = 24 * 7
        values = values[:53]
    
    mw = values * 1000.0 / repeat_h
    hourly_mw = np.repeat(mw, repeat_h)[:8760]
    
    return pd.Series(hourly_mw,
                     index=pd.date_range("2030-01-01", periods=8760, freq="h"))

# ── Haupt-API ────────────────────────────────────────────────────────────────

def load_zone_timeseries(zone: str,
                          climate_year: str = "2012",
                          include_detailed_demand: bool = False,
                          hydro_p_noms: dict = None) -> dict:
    """
    Lädt alle Zeitreihen für eine Zone und ein Klimajahr.

    Args:
        zone                  : Zonenname z.B. "DE", "FR", "adriatic"
        climate_year          : Klimajahr als String z.B. "2012"
        include_detailed_demand: Wenn True, werden BAT/EV/HP-Zeitreihen geladen
                                 und zur Basislast addiert
        hydro_p_noms          : Dict mit p_nom-Werten für Hydro-Normierung
                                 z.B. {"hydro_ror": 4731.8, ...}
                                 Wenn None: absolute MW-Werte zurückgeben

    Returns:
        dict mit pd.Series (8760h)
    """
    result = {}
    timestamps = pd.date_range("2030-01-01", periods=8760, freq="h")

    for key, path_template in PATHS.items():

        # Detaillierte Demand-Zeitreihen nur auf Anfrage
        if key in {"load_bat", "load_ev", "load_hp"} and not include_detailed_demand:
            continue

        path = Path(str(path_template).replace("{zone}", zone))

        if not path.exists():
            logger.debug(f"  {zone} – {key}: Datei nicht gefunden ({path.name}), setze auf 0")
            result[key] = pd.Series(np.zeros(8760), index=timestamps)
            continue

        try:
            skiprows = SKIPROWS[key]

            if key in HYDRO_KEYS:
                series = _read_hydro_inflow(path, climate_year, skiprows)
            else:
                series = _read_standard_timeseries(path, climate_year, skiprows)

            # CF auf [0, 1] clippen
            if key in CF_KEYS:
                series = series.clip(0, 1)

            result[key] = series
            logger.info(f"  {zone} – {key}: Ø={series.mean():.3f}, "
                        f"Max={series.max():.3f}, n={len(series)}")

        except Exception as e:
            logger.warning(f"  {zone} – {key}: Fehler beim Laden: {e}. Setze auf 0.")
            result[key] = pd.Series(np.zeros(8760), index=timestamps)

    # Detaillierte Demand aufaddieren wenn gewünscht
    if include_detailed_demand and "load" in result:
        for detail_key in ["load_bat", "load_ev", "load_hp"]:
            if detail_key in result:
                result["load"] = result["load"] + result[detail_key]
                logger.info(f"  {zone} – {detail_key} zur Last addiert")

    return result


def get_available_zones(key: str = "load") -> list:
    """Gibt alle Zonen zurück für die eine bestimmte Zeitreihe vorhanden ist."""
    path_template = PATHS[key]
    parent = Path(str(path_template).replace("{zone}_accumulated.csv", ""))
    if not parent.exists():
        return []
    return [f.stem.replace("_accumulated", "")
            for f in sorted(parent.glob("*_accumulated.csv"))
            if not f.stem.startswith("01_")]


# ── Direkt ausführbar zum Testen ─────────────────────────────────────────────

if __name__ == "__main__":
    print("Teste Zeitreihen-Loader für Deutschland (Klimajahr 2012)...")
    print("="*60)

    ts = load_zone_timeseries("DE", climate_year="2012")

    print(f"\n{'Zeitreihe':<20} {'Ø':>10} {'Max':>10} {'Min':>10} {'Summe TWh':>12}")
    print("-"*65)
    for key, series in ts.items():
        if key in CF_KEYS:
            print(f"{key:<20} {series.mean():>10.3f} {series.max():>10.3f} "
                  f"{series.min():>10.3f} {'(CF)':>12}")
        else:
            twh = series.sum() / 1e6
            print(f"{key:<20} {series.mean():>10.0f} {series.max():>10.0f} "
                  f"{series.min():>10.0f} {twh:>12.1f}")

    print(f"\nVerfügbare Zonen (Load): {get_available_zones('load')}")