"""
global_params.py
================
Lädt globale Simulationsparameter (Brennstoffpreise, Wirkungsgrade,
CO2-Preis/-Faktoren, VOM-Kosten) und berechnet daraus marginale Kosten
pro Erzeugungstechnologie.

Werte aus den ERAA-Dateien werden durch die festen Paper-Werte in config.py
(Abschnitt 4) überschrieben.

Schnelltest (aus dem Projekt-Root):
    python -m pipeline.model.global_params
"""
import logging

import numpy as np
import pandas as pd

import config

logger = logging.getLogger(__name__)

ADDITIONAL_DATA = config.ACCUMULATED_DIR / "Additional Data" / "Annex 1 - Input data"

FUEL_COST_PATH  = ADDITIONAL_DATA / "Fuel cost/Sheet1.csv"
EFFICIENCY_PATH = ADDITIONAL_DATA / "Efficiency/Sheet1.csv"
VOM_PATH        = ADDITIONAL_DATA / "VOM/Sheet1.csv"


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


def load_fuel_costs(year: int) -> dict:
    """Brennstoffpreise in €/MWh_th. ERAA-Werte, danach config-Overrides."""
    # Fallback in €/GJ, falls die ERAA-Datei fehlt
    fallback_gj = {
        "nuclear"  : 0.47,
        "lignite"  : 2.25,
        "hard_coal": 3.05,
        "gas"      : 12.20,
        "light_oil": 19.25,
        "heavy_oil": 15.79,
    }
    result = {k: v * 3.6 for k, v in fallback_gj.items()}
    mapping = {
        "nuclear"  : ["Nuclear", "nuclear"],
        "lignite"  : ["Lignite", "lignite"],
        "hard_coal": ["Hard coal", "Hard Coal", "hard_coal"],
        "gas"      : ["Natural gas", "Gas", "gas"],
        "light_oil": ["Light oil", "Oil", "light_oil"],
    }
    try:
        df = pd.read_csv(FUEL_COST_PATH, header=0, index_col=0)
        col = _get_year_col(df, year) or _get_year_col(df, 2030)
        for key, aliases in mapping.items():
            if key in config.FUEL_PRICE_OVERRIDES_EUR_PER_GJ:
                continue
            for alias in aliases:
                if alias in df.index and col:
                    val = _parse_range_mean(df.loc[alias, col])
                    if not np.isnan(val):
                        result[key] = val * 3.6
                        break
    except Exception as e:
        logger.warning(f"Brennstoffpreise konnten nicht geladen werden: {e}. Nutze Fallback.")

    for key, val_gj in config.FUEL_PRICE_OVERRIDES_EUR_PER_GJ.items():
        result[key] = val_gj * 3.6
    logger.info(f"Brennstoffpreise {year} (€/MWh_th): " +
                ", ".join(f"{k}={v:.2f}" for k, v in result.items()))
    return result


def load_efficiencies() -> dict:
    """Wirkungsgrade (0-1). ERAA-Werte, danach config-Overrides."""
    result = {
        "ccgt"     : 0.50,
        "ocgt"     : 0.385,
        "lignite"  : 0.405,
        "hard_coal": 0.405,
        "oil"      : 0.345,
        "nuclear"  : 0.33,
    }
    mapping = {
        "ccgt"     : ["CCGT"],
        "ocgt"     : ["OCGT"],
        "lignite"  : ["Lignite"],
        "hard_coal": ["Hard Coal", "Hard coal"],
        "oil"      : ["Oil"],
        "nuclear"  : ["Nuclear"],
    }
    try:
        df = pd.read_csv(EFFICIENCY_PATH, header=0, index_col=0)
        for key, aliases in mapping.items():
            if key in config.EFFICIENCY_OVERRIDES:
                continue
            for alias in aliases:
                if alias in df.index:
                    val = _parse_range_mean(df.loc[alias, df.columns[0]])
                    if not np.isnan(val):
                        result[key] = val / 100.0
                        break
    except Exception as e:
        logger.warning(f"Wirkungsgrade konnten nicht geladen werden: {e}. Nutze Fallback.")

    result.update(config.EFFICIENCY_OVERRIDES)
    logger.info("Wirkungsgrade: " + ", ".join(f"{k}={v:.3f}" for k, v in result.items()))
    return result


def load_co2_factors() -> dict:
    """CO2-Emissionsfaktoren in t CO2/MWh_th."""
    factors_kg_per_gj = {
        "gas": 57, "ccgt": 57, "ocgt": 57, "lignite": 101,
        "hard_coal": 94, "oil": 89, "light_oil": 89, "nuclear": 0, "biomass": 0,
    }
    return {k: v * 3.6 / 1000 for k, v in factors_kg_per_gj.items()}


def load_vom(year: int) -> dict:
    """Variable Betriebskosten in €/MWh_el. ERAA-Werte, danach config-Overrides."""
    result = {
        "ccgt": 2.11, "ocgt": 2.80, "lignite": 2.88,
        "hard_coal": 2.96, "oil": 2.80, "nuclear": 7.40,
    }
    mapping = {
        "ccgt"     : ["CCGT"],
        "ocgt"     : ["OCGT"],
        "lignite"  : ["Lignite"],
        "hard_coal": ["Hard Coal", "Hard coal"],
        "oil"      : ["Oil"],
        "nuclear"  : ["Nuclear"],
    }
    try:
        df = pd.read_csv(VOM_PATH, header=0, index_col=0)
        col = _get_year_col(df, year) or _get_year_col(df, 2030)
        for key, aliases in mapping.items():
            if key in config.VOM_OVERRIDES_EUR_PER_MWH:
                continue
            for alias in aliases:
                if alias in df.index and col:
                    val = _parse_range_mean(df.loc[alias, col])
                    if not np.isnan(val):
                        result[key] = val
                        break
    except Exception as e:
        logger.warning(f"VOM konnten nicht geladen werden: {e}. Nutze Fallback.")

    result.update(config.VOM_OVERRIDES_EUR_PER_MWH)
    logger.info("VOM (€/MWh_el): " + ", ".join(f"{k}={v:.2f}" for k, v in result.items()))
    return result


def compute_marginal_costs(fuel_costs: dict, efficiencies: dict,
                           co2_factors: dict, co2_price: float,
                           vom: dict = None) -> dict:
    """Grenzkosten in €/MWh_el = Brennstoff/η + CO2-Faktor·CO2-Preis/η + VOM."""
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
        "biomass"   : config.BIOMASS_MARGINAL_COST_EUR_PER_MWH,
    }

    logger.info("Grenzkosten (€/MWh_el):")
    for k, v in costs.items():
        logger.info(f"  {k:12s}: {v:7.2f}")
    return costs


def get_simulation_params(target_year: int = config.TARGET_YEAR) -> dict:
    logger.info(f"Lade globale Simulationsparameter für Jahr {target_year}...")

    co2_price    = config.CO2_PRICE_EUR_PER_T
    fuel_costs   = load_fuel_costs(target_year)
    efficiencies = load_efficiencies()
    co2_factors  = load_co2_factors()
    vom_costs    = load_vom(target_year)
    mc           = compute_marginal_costs(fuel_costs, efficiencies,
                                          co2_factors, co2_price,
                                          vom=vom_costs)

    return {
        "target_year"   : target_year,
        "co2_price"     : co2_price,
        "fuel_costs"    : fuel_costs,
        "efficiencies"  : efficiencies,
        "co2_factors"   : co2_factors,
        "vom_costs"     : vom_costs,
        "marginal_costs": mc,
        "voll"          : config.VOLL_EUR_PER_MWH,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    params = get_simulation_params()

    print("\n" + "="*50)
    print(f"Simulationsparameter für {params['target_year']}")
    print("="*50)
    print(f"CO2-Preis:        {params['co2_price']:.1f} €/t")
    print(f"VOLL:             {params['voll']:.0f} €/MWh")
    print("\nBrennstoffpreise (€/MWh_th):")
    for k, v in params["fuel_costs"].items():
        print(f"  {k:12s}: {v:.2f}")
    print("\nVOM (€/MWh_el):")
    for k, v in params["vom_costs"].items():
        print(f"  {k:12s}: {v:.2f}")
    print("\nGrenzkosten (€/MWh_el):")
    for k, v in params["marginal_costs"].items():
        print(f"  {k:12s}: {v:.2f}")
