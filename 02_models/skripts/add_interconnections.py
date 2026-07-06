"""
11_add_interconnections.py
==========================
Liest akkumulierte Transfer Capacities aus 04b_accumulated_data_per_node
und fügt zwei unidirektionale Links pro Verbindungspaar ins PyPSA-Netz ein.

Direkt aus akkumulierten Dateien – keine erneute Aggregation nötig.
Zonenbezeichnungen sind bereits korrekt (DE, FR, adriatic etc.).

Verwendung:
    from add_interconnections import add_interconnections
    add_interconnections(n, active_zones=["DE", "FR"])
"""

import pypsa
import pandas as pd
import numpy as np
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# ── Pfade zu den akkumulierten Transfer Capacity Dateien ─────────────────────
_PROJECT_ROOT = Path(__file__).parent.parent.parent
TC_DIR    = _PROJECT_ROOT / "01_data/04b_accumulated_data_per_node/Transfer capacities"
HVAC_PATH = TC_DIR / "Transfer Capacities_ERAA2022_TY2030/HVAC.csv"
HVDC_PATH = TC_DIR / "Transfer Capacities_ERAA2022_TY2030/HVDC.csv"
_RESULTS_DIR = _PROJECT_ROOT / "04_results"


def _load_accumulated_ntc(path: Path) -> pd.DataFrame:
    """
    Liest eine akkumulierte Transfer Capacities CSV ein.
    Struktur:
      Zeile 1 (index 1): From-Zonen (bereits aggregiert: DE, FR, adriatic...)
      Zeile 2 (index 2): To-Zonen
      Ab Zeile 7 (index 6): stündliche NTC-Werte (Datum, Stunde, Werte...)

    Gibt DataFrame zurück mit Spalten:
      from_zone, to_zone, ntc_mean_mw
    """
    raw = pd.read_csv(path, header=None, low_memory=False)

    # From/To direkt aus akkumulierter Datei lesen
    from_zones = raw.iloc[10, 2:].values
    to_zones   = raw.iloc[11, 2:].values

    # Datenwerte ab Zeile 6 (0-indiziert), Spalte 2
    data = raw.iloc[16:, 2:].copy()
    data = data.apply(pd.to_numeric, errors="coerce")

    # Jahresdurchschnitt pro Verbindung (paper-konform: statische Kapazität)
    means = data.mean(axis=0).values

    result = []
    for frm, to, mean_ntc in zip(from_zones, to_zones, means):
        frm_str = str(frm).strip()
        to_str  = str(to).strip()
        if frm_str in ("nan", "") or to_str in ("nan", ""):
            continue
        if pd.isna(mean_ntc) or mean_ntc <= 0:
            continue
        result.append({
            "from_zone"   : frm_str,
            "to_zone"     : to_str,
            "ntc_mean_mw" : float(mean_ntc),
        })

    df = pd.DataFrame(result)
    logger.info(f"  {path.name}: {len(df)} Verbindungen geladen")
    return df


def add_interconnections(n: pypsa.Network,
                          active_zones: list = None,
                          efficiency: float = 1.0) -> pd.DataFrame:
    """
    Liest akkumulierte NTC-Kapazitäten und fügt zwei unidirektionale
    Links pro Verbindungspaar ins PyPSA-Netz ein.

    Zwei separate Links (A→B und B→A) erlauben asymmetrische Kapazitäten
    und werden vom Optimierer unabhängig genutzt.

    Args:
        n            : PyPSA-Netz (Busse müssen bereits vorhanden sein)
        active_zones : Liste aktiver Zonen; None = alle Busse im Netz
        efficiency   : Übertragungseffizienz (1.0 = verlustfrei, paper-konform)

    Returns:
        DataFrame mit allen hinzugefügten Links
    """
    if active_zones is None:
        active_zones = list(n.buses.index)

    active_set = set(active_zones)
    logger.info(f"Lade akkumulierte Transfer Capacities für "
                f"{len(active_zones)} Zonen...")

    # ── HVAC und HVDC laden ───────────────────────────────────────────────────
    hvac = _load_accumulated_ntc(HVAC_PATH)
    hvdc = _load_accumulated_ntc(HVDC_PATH)
    all_ntc = pd.concat([hvac, hvdc], ignore_index=True)

    # ── Filtern: nur aktive Zonen, keine Selbstverbindungen ───────────────────
    all_ntc = all_ntc[
        all_ntc["from_zone"].isin(active_set) &
        all_ntc["to_zone"].isin(active_set)   &
        (all_ntc["from_zone"] != all_ntc["to_zone"])
    ].copy()

    logger.info(f"Verbindungen nach Filterung: {len(all_ntc)}")

    # ── Links ins Netz einfügen ───────────────────────────────────────────────
    added   = 0
    skipped = 0
    added_links = []

    for _, row in all_ntc.iterrows():
        frm = row["from_zone"]
        to  = row["to_zone"]
        cap = row["ntc_mean_mw"]

        # Busse prüfen
        if frm not in n.buses.index:
            logger.debug(f"  Bus {frm} nicht im Netz, überspringe {frm}→{to}")
            skipped += 1
            continue
        if to not in n.buses.index:
            logger.debug(f"  Bus {to} nicht im Netz, überspringe {frm}→{to}")
            skipped += 1
            continue

        # Eindeutiger Name für unidirektionalen Link
        link_name = f"Link_{frm}_to_{to}"

        # Falls Link bereits existiert: Kapazität addieren (HVAC + HVDC additiv)
        if link_name in n.links.index:
            old_cap = n.links.loc[link_name, "p_nom"]
            new_cap = old_cap + cap
            n.links.loc[link_name, "p_nom"] = new_cap
            logger.info(f"  {frm} → {to}: +{cap:.0f} MW addiert "
                        f"(HVAC {old_cap:.0f} + HVDC {cap:.0f} = {new_cap:.0f} MW)")
            added_links.append({"name": link_name, "from": frm,
                                "to": to, "p_nom_mw": new_cap})
            added += 1
            continue


        n.add("Link", link_name,
              bus0=frm,
              bus1=to,
              p_nom=cap,
              p_min_pu=0.0,    # unidirektional (0 bis p_nom)
              efficiency=efficiency,
              carrier="AC")

        logger.info(f"  {frm} → {to}: {cap:.0f} MW")
        added_links.append({"name": link_name, "from": frm,
                             "to": to, "p_nom_mw": cap})
        added += 1

    logger.info(f"Links hinzugefügt: {added}, übersprungen: {skipped}")
    return pd.DataFrame(added_links)

def save_results(n: pypsa.Network, active_zones: list, climate_year: str,
                 suffix: str = ""):
    """Speichert alle Ergebnisse in 04_results/{zonen_string}_CY{year}{suffix}/"""

    # Ordnername aus Zonen zusammensetzen
    zones_str = "_".join(active_zones)
    out_dir = _RESULTS_DIR / f"{zones_str}_CY{climate_year}{suffix}"
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
    print(f"\nErgebnisse gespeichert in: {out_dir}")
    
# ── Direkt ausführbar zum Testen ─────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).parent))

    from build_network import build_network
    from add_max_limits import max_limit_extra_functionality

    ENFORCE_MAX_LIMITS = True  # Country-Level-Max-NTC-Limits (siehe add_max_limits.py)

    #ACTIVE_ZONES = ["DE"]
    #ACTIVE_ZONES = ["DE","FR","CH"]
    #ACTIVE_ZONES = ["DE", "FR", "AT", "CH", "NL", "BE"]
    #ACTIVE_ZONES = ["DE", "FR", "AT", "CH", "NL", "BE", "CZ", "PL", "DK", "SE", "NO", "FI"]
    #ACTIVE_ZONES = ["DE", "FR", "AT", "CH", "NL", "BE", "CZ", "PL", "DK", "SE", "NO", "FI", "adriatic", "baltic"]
    ACTIVE_ZONES = ["DE", "FR", "AT", "CH", "NL", "BE","CZ", "PL", "DK", "SE", "NO", "FI","adriatic", "baltic", "ES", "PT", "IT", "GR", "UK", "IE", "other eastern european"]
    
    CLIMATE_YEAR = "1990"

    print("Baue Netz auf...")
    n = build_network(active_zones=ACTIVE_ZONES, climate_year=CLIMATE_YEAR)

    # ── Temporärer Debug FI ──────────────────────────────────────────────────
    #print(f"\nNO PSOpen p_nom:    {n.storage_units.loc['PSOpen_NO', 'p_nom']:.1f} MW")
    #print(f"NO PSOpen max_hours:{n.storage_units.loc['PSOpen_NO', 'max_hours']:.1f} h")
    #print(f"NO PSOpen inflow Ø: {n.storage_units_t.inflow['PSOpen_NO'].mean():.1f} MW")
    # ── Ende Debug ───────────────────────────────────────────────────────────

    print("\nFüge Interconnections hinzu...")
    links = add_interconnections(n, active_zones=ACTIVE_ZONES)

    print(f"\n── Links im Netz ({len(n.links)}) ──")
    print(n.links[["bus0", "bus1", "p_nom"]].to_string())


    print("\nStarte Optimierung...")
    status, condition = n.optimize(
        solver_name="gurobi",
        solver_options={
        "Method"        : 2,
        "Crossover"     : 0,
        "Threads"       : 8,
        "BarConvTol"    : 1e-5, #Changed for computing reasons
        "DualReductions": 0,
        },
        extra_functionality=(
            max_limit_extra_functionality(ACTIVE_ZONES) if ENFORCE_MAX_LIMITS else None
        ),
    )

    if status != "ok":
        print(f"Optimierung fehlgeschlagen: {status}, {condition}")
        sys.exit(1)

    save_results(n, ACTIVE_ZONES, CLIMATE_YEAR)  # ← fix: ACTIVE_ZONES statt args.zones

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
            print(f"  {gen:35s}: {gwh:8.1f} GWh")

    print("\n── Übertragung (GWh/Jahr) ──")
    for link in n.links.index:
        gwh = n.links_t.p0[link].sum() / 1000
        if abs(gwh) > 0.1:
            print(f"  {link:40s}: {gwh:8.1f} GWh")

    # ── Speicher SOC Diagnose ─────────────────────────────────────────────────────
    print("\n── Speicher State of Charge (Diagnose) ──")
    for su in n.storage_units.index:
        if su in n.storage_units_t.state_of_charge.columns:
            soc = n.storage_units_t.state_of_charge[su]
            print(f"  {su:35s}: Ø={soc.mean():.1f}, Min={soc.min():.1f}, "
                  f"Max={soc.max():.1f}, Start={soc.iloc[0]:.1f}, End={soc.iloc[-1]:.1f}")