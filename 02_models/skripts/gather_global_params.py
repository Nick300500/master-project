"""
07_gather_global_params.py
==========================
Lädt alle technologieübergreifenden Parameter für die PyPSA-Simulation
aus den ERAA Additional Data Dateien und stellt sie als Dictionary bereit.

Verwendung in anderen Skripten:
    from 07_gather_global_params import get_simulation_params
    params = get_simulation_params(target_year=2030)

Enthaltene Parameter:
    - CO2-Preis (€/t)
    - Brennstoffpreise (€/MWh_th)
    - Thermische Wirkungsgrade (%)
    - Grenzkosten (marginal cost) pro Technologie (€/MWh_el)
    - CO2-Emissionsfaktoren (t CO2/MWh_th)
    - VOLL (Value of Lost Load) - paper-konform 3000 €/MWh
    - Market Price Cap

Nicht enthalten (für Dispatch-Simulation nicht benötigt):
    - CAPEX, WACC, Economic Life (Investitionsentscheidungen)
    - Forced Outage Rates (Unit Commitment ausgeschaltet)
    - Hydrogen Prices (kein Elektrolyseur-Dispatch)
    - Resource Capacities Forced Outages
"""

from pathlib import Path
import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── Pfade ────────────────────────────────────────────────────────────────────
ADDITIONAL_DATA = Path("01_data/03_filtered_data_for_prediction_year/Additional Data")

CO2_PRICE_PATH    = ADDITIONAL_DATA / "Annex 1 - Input data/CO2 prices/Sheet1.csv"
FUEL_COST_PATH    = ADDITIONAL_DATA / "Annex 1 - Input data/Fuel cost/Sheet1.csv"
EFFICIENCY_PATH   = ADDITIONAL_DATA / "Annex 1 - Input data/Efficiency/Sheet1.csv"
MARGINAL_COST_PATH= ADDITIONAL_DATA / "Annex 1 - Input data/Marginal Cost/Sheet1.csv"
MARKET_CAP_PATH   = ADDITIONAL_DATA / "Annex 1 - Input data/Market price cap/Sheet1.csv"


# ── Hilfsfunktionen ──────────────────────────────────────────────────────────

def _parse_range_mean(value) -> float:
    """Parst Bereiche wie '40 - 60' oder '1.96 – 2.31' und gibt den Mittelwert zurück."""
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("–", "-").replace("−", "-")
    if "-" in text:
        parts = text.split("-")
        try:
            lo = float(parts[0].strip())
            hi = float(parts[1].strip())
            return (lo + hi) / 2.0
        except ValueError:
            pass
    try:
        return float(text)
    except ValueError:
        return np.nan


def _get_year_col(df: pd.DataFrame, year: int) -> str:
    """Findet die Spalte für ein bestimmtes Jahr (auch als int oder string)."""
    for col in df.columns:
        try:
            if int(float(str(col))) == year:
                return col
        except (ValueError, TypeError):
            continue
    return None


# ── Loader-Funktionen ────────────────────────────────────────────────────────

def load_co2_price(path: Path, year: int) -> float:
    """Lädt den CO2-Preis für das Zieljahr in €/t CO2."""
    try:
        df = pd.read_csv(path, header=0)
        col = _get_year_col(df, year)
        if col:
            val = df[col].iloc[0]
            price = _parse_range_mean(val)
            logger.info(f"CO2-Preis {year}: {price:.1f} €/t")
            return price
    except Exception as e:
        logger.warning(f"CO2-Preis konnte nicht geladen werden: {e}")
    # Fallback: ERAA 2030 Annahme aus Paper
    logger.warning("Nutze Fallback CO2-Preis: 100 €/t (ERAA 2030)")
    return 100.0


def load_fuel_costs(path: Path, year: int) -> dict:
    """
    Lädt Brennstoffpreise für das Zieljahr in €/GJ_net.
    Gibt Dictionary zurück mit Technologie → €/MWh_th (konvertiert: ×3.6).
    """
    # Referenzwerte aus ERAA 2022 Supplement (Fallback)
    fallback = {
        "nuclear"  : 0.47  * 3.6,   # €/GJ → €/MWh_th
        "lignite"  : 2.25  * 3.6,
        "hard_coal": 3.05  * 3.6,
        "gas"      : 12.20 * 3.6,   # ERAA 2030 Baseline (~44 €/MWh_th)
        "light_oil": 19.25 * 3.6,
        "heavy_oil": 15.79 * 3.6,
    }
    try:
        df = pd.read_csv(path, header=0, index_col=0)
        col = _get_year_col(df, year)
        if col is None:
            col = _get_year_col(df, 2030)  # nächstbester Fallback

        mapping = {
            "nuclear"  : ["Nuclear", "nuclear"],
            "hard_coal": ["Hard coal", "Hard Coal", "hard_coal"],
            "gas"      : ["Natural gas", "Gas", "gas"],
            "light_oil": ["Light oil", "Oil", "light_oil"],
            "lignite"  : ["Lignite", "lignite"],
        }

        result = dict(fallback)
        for key, aliases in mapping.items():
            for alias in aliases:
                if alias in df.index and col:
                    val = _parse_range_mean(df.loc[alias, col])
                    if not np.isnan(val):
                        result[key] = val * 3.6  # €/GJ → €/MWh_th
                        break

        logger.info(f"Brennstoffpreise {year} (€/MWh_th): " +
                    ", ".join(f"{k}={v:.2f}" for k, v in result.items()))
        return result

    except Exception as e:
        logger.warning(f"Brennstoffpreise konnten nicht geladen werden: {e}. Nutze Fallback.")
        return fallback


def load_efficiencies(path: Path) -> dict:
    """
    Lädt thermische Wirkungsgrade in Dezimalform (0–1).
    Nutzt Mittelwert bei Bereichsangaben.
    """
    # Fallback-Werte (aus Paper Supplement + ERAA)
    fallback = {
        "ccgt"     : 0.49,   # Paper-Annahme (Supplement S.1)
        "ocgt"     : 0.385,
        "lignite"  : 0.405,
        "hard_coal": 0.405,
        "oil"      : 0.345,
        "nuclear"  : 0.33,
    }
    try:
        df = pd.read_csv(path, header=0, index_col=0)
        mapping = {
            "ccgt"     : ["CCGT"],
            "ocgt"     : ["OCGT"],
            "lignite"  : ["Lignite"],
            "hard_coal": ["Hard Coal", "Hard coal"],
            "oil"      : ["Oil"],
            "nuclear"  : ["Nuclear"],
        }
        result = dict(fallback)
        for key, aliases in mapping.items():
            for alias in aliases:
                if alias in df.index:
                    col = df.columns[0]
                    val = _parse_range_mean(df.loc[alias, col])
                    if not np.isnan(val):
                        result[key] = val / 100.0  # % → Dezimal
                        break

        logger.info("Wirkungsgrade: " +
                    ", ".join(f"{k}={v:.3f}" for k, v in result.items()))
        return result

    except Exception as e:
        logger.warning(f"Wirkungsgrade konnten nicht geladen werden: {e}. Nutze Fallback.")
        return fallback


def load_co2_factors() -> dict:
    """
    CO2-Emissionsfaktoren in t CO2/MWh_th.
    Direkt aus ERAA Additional Data (Table 11).
    Werte sind stabil, daher hardcodiert aus der Tabelle.
    """
    # Aus Additional Data Table 11: CO2 emission factor [CO2 kg/GJ]
    # Konversion: kg/GJ × 3.6 / 1000 = t/MWh_th
    factors_kg_per_gj = {
        "gas"      : 57,
        "ccgt"     : 57,
        "ocgt"     : 57,
        "lignite"  : 101,
        "hard_coal": 94,
        "oil"      : 89,    # Mittelwert 78-100
        "light_oil": 89,
        "nuclear"  : 0,
        "biomass"  : 0,     # Biogen, gilt als CO2-neutral in ERAA
    }
    result = {k: v * 3.6 / 1000 for k, v in factors_kg_per_gj.items()}
    logger.info("CO2-Faktoren geladen (t CO2/MWh_th)")
    return result


def load_market_price_cap(path: Path, year: int) -> float:
    """Lädt die Strompreisobergrenze in €/MWh."""
    try:
        df = pd.read_csv(path, header=0)
        col = _get_year_col(df, year)
        if col:
            val = _parse_range_mean(df[col].iloc[0])
            logger.info(f"Market Price Cap {year}: {val:.0f} €/MWh")
            return val
    except Exception as e:
        logger.warning(f"Market Price Cap konnte nicht geladen werden: {e}")
    logger.warning("Nutze Fallback Market Price Cap: 3000 €/MWh (VOLL paper-konform)")
    print("To be paper conform, later we can use the real value from the Additional Data if needed.")
    return 3000.0 #To be paper conform


# ── Marginal Cost Berechnung ─────────────────────────────────────────────────

def compute_marginal_costs(fuel_costs: dict, efficiencies: dict,
                           co2_factors: dict, co2_price: float) -> dict:
    """
    Berechnet Grenzkosten (€/MWh_el) für alle thermischen Technologien:
        mc = fuel_cost / eta + co2_factor * co2_price / eta

    Quelle der Formel: ERAA Methodology + Paper Supplement S.1
    """
    def mc(tech_fuel: str, tech_eff: str) -> float:
        fuel = fuel_costs.get(tech_fuel, 0)
        eta  = efficiencies.get(tech_eff, 1)
        co2  = co2_factors.get(tech_fuel, 0)
        return fuel / eta + co2 * co2_price / eta

    costs = {
        "gas_ccgt"  : mc("gas",       "ccgt"),
        "gas_ocgt"  : mc("gas",       "ocgt"),
        "lignite"   : mc("lignite",   "lignite"),
        "hard_coal" : mc("hard_coal", "hard_coal"),
        "oil"       : mc("light_oil", "oil"),
        "nuclear"   : mc("nuclear",   "nuclear"),
        # Erneuerbare und Speicher: null variable Kosten
        "wind"      : 0.0,
        "solar"     : 0.0,
        "hydro_ror" : 0.0,
        "hydro_res" : 0.0,
        "pump_hydro": 0.0,
        "battery"   : 0.0,
        # Biomasse: nur Brennstoffkosten, kein CO2 (biogen)
        "biomass"   : 60.0,  # €/MWh (typischer ERAA-Wert, keine Formel da variabel)
    }

    logger.info("Grenzkosten (€/MWh_el):")
    for k, v in costs.items():
        logger.info(f"  {k:12s}: {v:7.2f}")

    return costs


# ── Haupt-API ────────────────────────────────────────────────────────────────

def get_simulation_params(target_year: int = 2030) -> dict:
    """
    Lädt und berechnet alle Parameter für die PyPSA-Simulation.

    Returns:
        dict mit Schlüsseln:
            co2_price        : float  [€/t CO2]
            fuel_costs       : dict   [€/MWh_th]
            efficiencies     : dict   [0–1]
            co2_factors      : dict   [t CO2/MWh_th]
            marginal_costs   : dict   [€/MWh_el]
            market_price_cap : float  [€/MWh]
            voll             : float  [€/MWh] – paper-konform 3000
    """
    logger.info(f"Lade globale Simulationsparameter für Jahr {target_year}...")

    co2_price    = load_co2_price(CO2_PRICE_PATH, target_year)
    fuel_costs   = load_fuel_costs(FUEL_COST_PATH, target_year)
    efficiencies = load_efficiencies(EFFICIENCY_PATH)
    co2_factors  = load_co2_factors()
    mc           = compute_marginal_costs(fuel_costs, efficiencies,
                                          co2_factors, co2_price)
    price_cap    = load_market_price_cap(MARKET_CAP_PATH, target_year)

    params = {
        "target_year"      : target_year,
        "co2_price"        : co2_price,
        "fuel_costs"       : fuel_costs,
        "efficiencies"     : efficiencies,
        "co2_factors"      : co2_factors,
        "marginal_costs"   : mc,
        "market_price_cap" : price_cap,
        "voll"             : 3000.0,   # Paper-konform (Methods Sektion)
    }

    logger.info(f"Parameter erfolgreich geladen für Jahr {target_year}.")
    return params


# ── Direkt ausführbar zum Testen ─────────────────────────────────────────────

if __name__ == "__main__":
    params = get_simulation_params(target_year=2030)

    print("\n" + "="*50)
    print(f"Simulationsparameter für {params['target_year']}")
    print("="*50)
    print(f"CO2-Preis:        {params['co2_price']:.1f} €/t")
    print(f"VOLL:             {params['voll']:.0f} €/MWh")
    print(f"Market Price Cap: {params['market_price_cap']:.0f} €/MWh")
    print("\nBrennstoffpreise (€/MWh_th):")
    for k, v in params["fuel_costs"].items():
        print(f"  {k:12s}: {v:.2f}")
    print("\nGrenzkosten (€/MWh_el):")
    for k, v in params["marginal_costs"].items():
        print(f"  {k:12s}: {v:.2f}")