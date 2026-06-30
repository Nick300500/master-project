"""
07_gather_global_params.py
"""
from pathlib import Path
import pandas as pd
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

_SCRIPT_DIR   = Path(__file__).parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
ADDITIONAL_DATA = _PROJECT_ROOT / "01_data/04b_accumulated_data_per_node/Additional Data"

CO2_PRICE_PATH     = ADDITIONAL_DATA / "Annex 1 - Input data/CO2 prices/Sheet1.csv"
FUEL_COST_PATH     = ADDITIONAL_DATA / "Annex 1 - Input data/Fuel cost/Sheet1.csv"
EFFICIENCY_PATH    = ADDITIONAL_DATA / "Annex 1 - Input data/Efficiency/Sheet1.csv"
MARGINAL_COST_PATH = ADDITIONAL_DATA / "Annex 1 - Input data/Marginal Cost/Sheet1.csv"
MARKET_CAP_PATH    = ADDITIONAL_DATA / "Annex 1 - Input data/Market price cap/Sheet1.csv"
VOM_PATH           = ADDITIONAL_DATA / "Annex 1 - Input data/VOM/Sheet1.csv"


def _parse_range_mean(value) -> float:
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
    for col in df.columns:
        try:
            if int(float(str(col))) == year:
                return col
        except (ValueError, TypeError):
            continue
    return None


def load_co2_price(path: Path, year: int) -> float:
    try:
        df = pd.read_csv(path, header=0)
        col = _get_year_col(df, year)
        #if col:
            #price = _parse_range_mean(df[col].iloc[0])
            #logger.info(f"CO2-Preis {year}: {price:.1f} €/t")
            #return price #changed due to paper confirmation
            #return 100.0 #changed due to paper confirmation
    except Exception as e:
        logger.warning(f"CO2-Preis konnte nicht geladen werden: {e}")
    logger.warning("Nutze Fallback CO2-Preis: 100 €/t (ERAA 2030)")
    return 100.0


def load_fuel_costs(path: Path, year: int) -> dict:
    fallback = {
        "nuclear"  : 0.47  * 3.6,
        #"lignite"  : 2.25  * 3.6,
        "lignite"  : 3.1  * 3.6, #changed due to paper confirmation
        "hard_coal": 3.05  * 3.6,
        "gas"      : 12.20 * 3.6,
        "light_oil": 19.25 * 3.6,
        "heavy_oil": 15.79 * 3.6,
    }
    try:
        df = pd.read_csv(path, header=0, index_col=0)
        col = _get_year_col(df, year) or _get_year_col(df, 2030)
        mapping = {
            "nuclear"  : ["Nuclear", "nuclear"],
            "hard_coal": ["Hard coal", "Hard Coal", "hard_coal"],
            "gas"      : ["Natural gas", "Gas", "gas"],
            "light_oil": ["Light oil", "Oil", "light_oil"],
            #"lignite"  : ["Lignite", "lignite"], #left out due to paper confirmation
        }
        result = dict(fallback)
        for key, aliases in mapping.items():
            for alias in aliases:
                if alias in df.index and col:
                    val = _parse_range_mean(df.loc[alias, col])
                    if not np.isnan(val):
                        result[key] = val * 3.6
                        break
        logger.info(f"Brennstoffpreise {year} (€/MWh_th): " +
                    ", ".join(f"{k}={v:.2f}" for k, v in result.items()))
        return result
    except Exception as e:
        logger.warning(f"Brennstoffpreise konnten nicht geladen werden: {e}. Nutze Fallback.")
        return fallback


def load_efficiencies(path: Path) -> dict:
    fallback = {
        #"ccgt"     : 0.50,
        "ccgt"     : 0.49, #changed due to paper confirmation
        "ocgt"     : 0.385,
        "lignite"  : 0.405,
        "hard_coal": 0.405,
        "oil"      : 0.345,
        "nuclear"  : 0.33,
    }
    try:
        df = pd.read_csv(path, header=0, index_col=0)
        mapping = {
            #"ccgt"     : ["CCGT"], left out due to paper confirmation
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
                    val = _parse_range_mean(df.loc[alias, df.columns[0]])
                    if not np.isnan(val):
                        result[key] = val / 100.0
                        break
        logger.info("Wirkungsgrade: " + ", ".join(f"{k}={v:.3f}" for k, v in result.items()))
        return result
    except Exception as e:
        logger.warning(f"Wirkungsgrade konnten nicht geladen werden: {e}. Nutze Fallback.")
        return fallback


def load_co2_factors() -> dict:
    factors_kg_per_gj = {
        "gas": 57, "ccgt": 57, "ocgt": 57, "lignite": 101,
        "hard_coal": 94, "oil": 89, "light_oil": 89, "nuclear": 0, "biomass": 0,
    }
    result = {k: v * 3.6 / 1000 for k, v in factors_kg_per_gj.items()}
    logger.info("CO2-Faktoren geladen (t CO2/MWh_th)")
    return result


def load_vom(path: Path, year: int) -> dict:
    fallback = {
        "ccgt": 2.11, "ocgt": 2.80, "lignite": 2.88,
        "hard_coal": 2.96, "oil": 2.80, "nuclear": 7.40,
    }
    try:
        df = pd.read_csv(path, header=0, index_col=0)
        col = _get_year_col(df, year) or _get_year_col(df, 2030)
        mapping = {
            #"ccgt"     : ["CCGT"], left out due to paper confirmation
            "ocgt"     : ["OCGT"],
            "lignite"  : ["Lignite"],
            "hard_coal": ["Hard Coal", "Hard coal"],
            "oil"      : ["Oil"],
            "nuclear"  : ["Nuclear"],
        }
        result = dict(fallback)
        for key, aliases in mapping.items():
            for alias in aliases:
                if alias in df.index and col:
                    val = _parse_range_mean(df.loc[alias, col])
                    if not np.isnan(val):
                        result[key] = val
                        break
        logger.info("VOM (€/MWh_el): " + ", ".join(f"{k}={v:.2f}" for k, v in result.items()))
        return result
    except Exception as e:
        logger.warning(f"VOM konnten nicht geladen werden: {e}. Nutze Fallback.")
        return fallback


def load_market_price_cap(path: Path, year: int) -> float:
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
    return 3000.0 #Laut ERAA 8000€, für Paper-konform 3000€


def compute_marginal_costs(fuel_costs: dict, efficiencies: dict,
                           co2_factors: dict, co2_price: float,
                           vom: dict = None) -> dict:
    if vom is None:
        vom = {}

    def mc(tech_fuel: str, tech_eff: str) -> float:
        fuel = fuel_costs.get(tech_fuel, 0)
        eta  = efficiencies.get(tech_eff, 1)
        co2  = co2_factors.get(tech_fuel, 0)
        v    = vom.get(tech_eff, 0)
        return fuel / eta + co2 * co2_price / eta + v

    costs = {
        "gas_ccgt"  : mc("gas",       "ccgt"),
        "gas_ocgt"  : mc("gas",       "ocgt"),
        "lignite"   : mc("lignite",   "lignite"),
        "hard_coal" : mc("hard_coal", "hard_coal"),
        "oil"       : mc("light_oil", "oil"),
        "nuclear"   : mc("nuclear",   "nuclear"),
        "wind"      : 0.0,
        "solar"     : 0.0,
        "hydro_ror" : 0.0,
        "hydro_res" : 0.0,
        "pump_hydro": 0.0,
        "battery"   : 0.0,
        "biomass"   : 0.0,
    }

    logger.info("Grenzkosten (€/MWh_el):")
    for k, v in costs.items():
        logger.info(f"  {k:12s}: {v:7.2f}")
    return costs


def get_simulation_params(target_year: int = 2030) -> dict:
    logger.info(f"Lade globale Simulationsparameter für Jahr {target_year}...")

    co2_price    = load_co2_price(CO2_PRICE_PATH, target_year)
    fuel_costs   = load_fuel_costs(FUEL_COST_PATH, target_year)
    efficiencies = load_efficiencies(EFFICIENCY_PATH)
    co2_factors  = load_co2_factors()
    vom_costs    = load_vom(VOM_PATH, target_year)
    mc           = compute_marginal_costs(fuel_costs, efficiencies,
                                          co2_factors, co2_price,
                                          vom=vom_costs)
    price_cap    = load_market_price_cap(MARKET_CAP_PATH, target_year)

    params = {
        "target_year"      : target_year,
        "co2_price"        : co2_price,
        "fuel_costs"       : fuel_costs,
        "efficiencies"     : efficiencies,
        "co2_factors"      : co2_factors,
        "vom_costs"        : vom_costs,
        "marginal_costs"   : mc,
        "market_price_cap" : price_cap,
        "voll"             : 3000.0,
    }

    logger.info(f"Parameter erfolgreich geladen für Jahr {target_year}.")
    return params


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
    print("\nVOM (€/MWh_el):")
    for k, v in params["vom_costs"].items():
        print(f"  {k:12s}: {v:.2f}")
    print("\nGrenzkosten (€/MWh_el):")
    for k, v in params["marginal_costs"].items():
        print(f"  {k:12s}: {v:.2f}")