"""
run_batch_simulation_configurable.py
======================================
Erweiterung von run_batch_simulation_fixed_years.py mit zwei konfigurierbaren
Optionen, die einmalig beim Start abgefragt werden und dann für alle Klimajahre
des gesamten Runs gelten:

  [1] NTC-Quelle:
        ERAA  – akkumulierte Transfer-Capacity-CSVs (Standardverhalten)
        Paper – Werte aus NTC_Vergleich_ERAA_Paper_Modell.xlsx (Zeile "Paper")

  [2] Gas-Preis:
        Input – aus ERAA-2030-Eingangsdaten (~43.9 €/MWh_th)
        Manuell – frei wählbarer Wert in €/MWh_th

Ergebnisordner erhält automatisch einen Suffix, der die gewählte Konfiguration
kennzeichnet (z.B. "_paperNTC", "_gas30", "_paperNTC_gas30").

Verwendung (aus Projekt-Root):
    python 02_models/skripts/run_batch_simulation_configurable.py
"""

import sys
import logging
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(_SCRIPT_DIR))

from build_network import build_network
from add_interconnections import add_interconnections, save_results
from add_max_limits import max_limit_extra_functionality

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── Projektpfade ──────────────────────────────────────────────────────────────
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
_NTC_CSV      = (_PROJECT_ROOT
                 / "01_data/Exact paper interconnection"
                 / "NTC_Vergleich_ERAA_Paper_Modell.csv")

# "OE" ist das Kürzel im Excel für "other eastern european"
_ZONE_ALIAS = {"OE": "other eastern european"}

# ── Simulationskonstanten (identisch zu run_batch_simulation_fixed_years) ─────
#YEARS = [1988, 1989, 1990, 1993, 2000, 2003, 2004, 2006, 2011, 2012, 2014, 2015]
YEARS = [1990, 2003, 2015]

ACTIVE_ZONES = [
    "DE", "FR", "AT", "CH", "NL", "BE", "CZ", "PL", "DK", "SE", "NO", "FI",
    "adriatic", "baltic", "ES", "PT", "IT", "GR", "UK", "IE",
    "other eastern european",
]

ENFORCE_MAX_LIMITS = True

SOLVER_OPTIONS = {
    "Method"        : 2,
    "Crossover"     : 0,
    "Threads"       : 8,
    "BarConvTol"    : 1e-5,
    "DualReductions": 0,
}


# ── Konfigurationsabfrage ─────────────────────────────────────────────────────

def _ask(prompt: str, valid: tuple) -> str:
    """Fragt solange nach, bis eine gültige Eingabe erfolgt."""
    while True:
        answer = input(prompt).strip()
        if answer in valid:
            return answer
        print(f"  Ungültige Eingabe. Bitte {'/'.join(valid)} eingeben.")


def prompt_config() -> dict:
    """
    Einmalige interaktive Konfigurationsabfrage beim Skriptstart.

    Returns:
        dict mit Schlüsseln:
          use_paper_ntc      (bool)
          gas_price_override (float | None)   in €/MWh_th; None = Input-Daten
          result_suffix      (str)            z.B. "_paperNTC_gas30"
    """
    print("\n" + "=" * 62)
    print("  SIMULATIONSKONFIGURATION")
    print("=" * 62)

    # ── [1] Interconnection-Quelle ────────────────────────────────────────────
    print("\n[1] Interconnection-Kapazitäten (NTC):")
    print("    1  ERAA-Daten  – akkumulierte Transfer-Capacity-CSVs  [Standard]")
    print("    2  Paper-Werte – NTC_Vergleich_ERAA_Paper_Modell.csv")
    ntc_choice    = _ask("    Auswahl [1/2]: ", ("1", "2"))
    use_paper_ntc = ntc_choice == "2"

    # ── [2] Gas-Preis ─────────────────────────────────────────────────────────
    print("\n[2] Gas-Preis (Brennstoffkosten für Gas/CCGT):")
    print("    1  Aus Input-Daten (ERAA 2030, ~43.9 €/MWh_th)  [Standard]")
    print("    2  Manuell eingeben (in €/MWh_th)")
    gas_choice = _ask("    Auswahl [1/2]: ", ("1", "2"))

    gas_price_override = None
    if gas_choice == "2":
        while True:
            raw = input("    Gas-Preis in €/MWh_th (z.B. 43.9): ").strip()
            try:
                val = float(raw.replace(",", "."))
                if val >= 0:
                    gas_price_override = val
                    print(f"    → Gas-Preis gesetzt: {val:.2f} €/MWh_th")
                    break
            except ValueError:
                pass
            print("    Ungültige Eingabe. Bitte eine positive Zahl eingeben.")

    # ── Ergebnis-Suffix zusammensetzen ────────────────────────────────────────
    suffix_parts = []
    if use_paper_ntc:
        suffix_parts.append("paperNTC")
    if gas_price_override is not None:
        suffix_parts.append(f"gas{gas_price_override:.0f}")
    result_suffix = ("_" + "_".join(suffix_parts)) if suffix_parts else ""

    # ── Zusammenfassung ───────────────────────────────────────────────────────
    print("\n── Gewählte Konfiguration " + "─" * 36)
    print(f"  NTC-Quelle    : {'Paper (Excel)' if use_paper_ntc else 'ERAA-Daten (CSV)'}")
    if gas_price_override is not None:
        print(f"  Gas-Preis     : {gas_price_override:.2f} €/MWh_th (manuell)")
    else:
        print(f"  Gas-Preis     : Input-Daten (ERAA 2030)")
    print(f"  Ergebnis-Suffix: '{result_suffix}' (leer = kein Suffix)")
    print("=" * 62 + "\n")

    return {
        "use_paper_ntc"    : use_paper_ntc,
        "gas_price_override": gas_price_override,
        "result_suffix"    : result_suffix,
    }


# ── Paper-NTC laden und ins Netz einfügen ─────────────────────────────────────

def _resolve_zone(name: str) -> str:
    """Löst Excel-Kürzel (z.B. 'OE') in den Modell-Zonennamen auf."""
    return _ZONE_ALIAS.get(name.strip(), name.strip())


def _load_paper_ntc_df(active_zones: list) -> list:
    """
    Liest Paper-NTC-Werte (Spalte 'Paper') aus der CSV-Datei.

    Die CSV enthält eine Kapazität pro Verbindungspaar (symmetrisch).
    Beide Richtungen (A→B und B→A) werden mit identischer Kapazität
    zurückgegeben, analog zur Behandlung in add_interconnections().

    Returns:
        Liste von dicts: {from_zone, to_zone, ntc_mean_mw}
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError("pandas wird benötigt: pip install pandas") from exc

    if not _NTC_CSV.exists():
        raise FileNotFoundError(f"NTC-CSV nicht gefunden: {_NTC_CSV}")

    df = pd.read_csv(_NTC_CSV, sep=";", decimal=",", thousands=".")

    active_set = set(active_zones)
    result = []

    for _, row in df.iterrows():
        linie = str(row["Linie"]).strip()
        if "-" not in linie:
            continue

        raw_val = row["Paper"]
        if pd.isna(raw_val):
            continue
        try:
            cap = float(raw_val)
        except (ValueError, TypeError):
            continue
        if cap <= 0:
            continue

        parts = linie.split("-", 1)
        if len(parts) != 2:
            continue
        zone_a = _resolve_zone(parts[0])
        zone_b = _resolve_zone(parts[1])

        # Beide Richtungen (Paper-NTC ist symmetrisch)
        for frm, to in [(zone_a, zone_b), (zone_b, zone_a)]:
            if frm in active_set and to in active_set:
                result.append({"from_zone": frm, "to_zone": to, "ntc_mean_mw": cap})

    logger.info(f"Paper-NTC: {len(result)} Verbindungen geladen "
                f"(aus {_NTC_CSV.name})")
    return result


def _print_used_capacities(n) -> None:
    """Gibt die verwendeten Link-Kapazitäten vor dem Optimieren aus."""
    print("\nVerwendete Kapazitäten vor Optimierung:")
    if n.links.empty:
        print("  (keine Links vorhanden)")
        return

    for link_name, link in n.links.iterrows():
        p_nom = link.get("p_nom", 0)
        if p_nom is None:
            continue
        print(f"  - {link_name}: {p_nom:.0f} MW")


def add_interconnections_paper(n, active_zones: list):
    """
    Fügt Paper-NTC-Verbindungen als unidirektionale Links ins PyPSA-Netz ein.

    Verhält sich identisch zu add_interconnections(), liest die Kapazitäten
    aber aus der Paper-CSV-Datei statt aus den akkumulierten CSVs.

    Args:
        n            : PyPSA-Netz (Busse müssen bereits vorhanden sein)
        active_zones : Liste aktiver Zonen
    """
    ntc_rows  = _load_paper_ntc_df(active_zones)
    added     = 0
    skipped   = 0

    for row in ntc_rows:
        frm = row["from_zone"]
        to  = row["to_zone"]
        cap = row["ntc_mean_mw"]

        if frm not in n.buses.index:
            logger.debug(f"  Bus {frm} nicht im Netz, überspringe {frm}→{to}")
            skipped += 1
            continue
        if to not in n.buses.index:
            logger.debug(f"  Bus {to} nicht im Netz, überspringe {frm}→{to}")
            skipped += 1
            continue

        link_name = f"Link_{frm}_to_{to}"

        # Falls Link bereits existiert: Kapazität addieren
        if link_name in n.links.index:
            old_cap = n.links.loc[link_name, "p_nom"]
            new_cap = old_cap + cap
            n.links.loc[link_name, "p_nom"] = new_cap
            logger.info(f"  Paper NTC {frm} → {to}: "
                        f"+{cap:.0f} MW addiert → {new_cap:.0f} MW gesamt")
            added += 1
            continue

        n.add("Link", link_name,
              bus0=frm,
              bus1=to,
              p_nom=cap,
              p_min_pu=0.0,
              efficiency=1.0,
              carrier="AC")

        logger.info(f"  Paper NTC {frm} → {to}: {cap:.0f} MW")
        added += 1

    logger.info(f"Paper-Links hinzugefügt: {added}, übersprungen: {skipped}")


# ── Haupt-Loop ────────────────────────────────────────────────────────────────

if __name__ == "__main__":

    config = prompt_config()

    use_paper_ntc     = config["use_paper_ntc"]
    gas_price_override = config["gas_price_override"]
    result_suffix     = config["result_suffix"]

    for year in YEARS:
        climate_year = str(year)
        print(f"\n{'='*60}\nKlimajahr {climate_year}\n{'='*60}")

        n = build_network(
            active_zones=ACTIVE_ZONES,
            climate_year=climate_year,
            gas_price_eur_mwh_th=gas_price_override,   # None = ERAA-Daten
        )

        if use_paper_ntc:
            add_interconnections_paper(n, active_zones=ACTIVE_ZONES)
        else:
            add_interconnections(n, active_zones=ACTIVE_ZONES)

        _print_used_capacities(n)

        status, condition = n.optimize(
            solver_name="gurobi",
            solver_options=SOLVER_OPTIONS,
            extra_functionality=(
                max_limit_extra_functionality(ACTIVE_ZONES)
                if ENFORCE_MAX_LIMITS else None
            ),
        )

        if status != "ok":
            print(f"Optimierung fehlgeschlagen für {climate_year}: "
                  f"{status}, {condition}")
            continue

        save_results(n, ACTIVE_ZONES, climate_year, suffix=result_suffix)

    print("\nFertig.")
