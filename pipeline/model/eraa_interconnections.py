"""
eraa_interconnections.py
========================
Liest die akkumulierten ERAA-Transfer-Capacities (HVAC + HVDC) und fügt zwei
unidirektionale Links pro Verbindungspaar ins PyPSA-Netz ein
(Standard, --interconnections eraa).

Zonenbezeichnungen sind bereits aggregiert (DE, FR, adriatic etc.).

Verwendung:
    from pipeline.model.eraa_interconnections import add_eraa_interconnections
    add_eraa_interconnections(n, active_zones=["DE", "FR"])
"""

import logging
from pathlib import Path

import pandas as pd
import pypsa

import config

logger = logging.getLogger(__name__)

# ── Pfade zu den akkumulierten Transfer Capacity Dateien ─────────────────────
TC_DIR    = (config.ACCUMULATED_DIR / "Transfer capacities"
             / f"Transfer Capacities_ERAA2022_TY{config.TARGET_YEAR}")
HVAC_PATH = TC_DIR / "HVAC.csv"
HVDC_PATH = TC_DIR / "HVDC.csv"


def _load_accumulated_ntc(path: Path) -> pd.DataFrame:
    """
    Liest eine akkumulierte Transfer Capacities CSV ein.
    Struktur:
      Zeile 11 (index 10): From-Zonen (bereits aggregiert: DE, FR, adriatic...)
      Zeile 12 (index 11): To-Zonen
      Ab Zeile 17 (index 16): stündliche NTC-Werte (Datum, Stunde, Werte...)

    Gibt DataFrame zurück mit Spalten:
      from_zone, to_zone, ntc_mean_mw
    """
    raw = pd.read_csv(path, header=None, low_memory=False)

    # From/To direkt aus akkumulierter Datei lesen
    from_zones = raw.iloc[10, 2:].values
    to_zones   = raw.iloc[11, 2:].values

    # Stündliche Werte ab Zeile 17, ab Spalte 3
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


def add_eraa_interconnections(n: pypsa.Network,
                              active_zones: list = None,
                              efficiency: float = config.LINK_EFFICIENCY) -> pd.DataFrame:
    """
    Liest akkumulierte NTC-Kapazitäten und fügt zwei unidirektionale
    Links pro Verbindungspaar ins PyPSA-Netz ein.

    Zwei separate Links (A→B und B→A) erlauben asymmetrische Kapazitäten
    und werden vom Optimierer unabhängig genutzt.

    Args:
        n            : PyPSA-Netz (Busse müssen bereits vorhanden sein)
        active_zones : Liste aktiver Zonen; None = alle Busse im Netz
        efficiency   : Übertragungseffizienz (Default config.LINK_EFFICIENCY)

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
