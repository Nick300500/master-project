"""
paper_interconnections.py
==========================
Lädt Interconnection-Kapazitäten aus der paper-eigenen NTC-Tabelle
(statt aus den ERAA-Rohdaten via add_interconnections.py) und fügt sie
als Links ins Netz ein. Für Simulationsläufe, die die exakten NTC-Werte
aus dem Nature-Energy-Paper reproduzieren sollen.
"""

import logging
from pathlib import Path

import pandas as pd
import pypsa

logger = logging.getLogger(__name__)

_ZONE_ALIAS = {"OE": "other eastern european"}


def _resolve_zone(name: str) -> str:
    return _ZONE_ALIAS.get(name.strip(), name.strip())


def _load_paper_ntc(ntc_csv: Path, active_zones: list) -> list:
    if not ntc_csv.exists():
        raise FileNotFoundError(f"NTC-CSV nicht gefunden: {ntc_csv}")

    df = pd.read_csv(ntc_csv, sep=";", decimal=",", thousands=".")
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

        for frm, to in [(zone_a, zone_b), (zone_b, zone_a)]:
            if frm in active_set and to in active_set:
                result.append({"from_zone": frm, "to_zone": to, "ntc_mean_mw": cap})

    logger.info("Paper-NTC: %d Verbindungen geladen", len(result))
    return result


def add_paper_interconnections(n: pypsa.Network, ntc_csv: Path, active_zones: list) -> None:
    """Fügt Interconnection-Links aus der Paper-NTC-Tabelle ins Netz ein."""
    ntc_rows = _load_paper_ntc(ntc_csv, active_zones)
    added, skipped = 0, 0

    for row in ntc_rows:
        frm = row["from_zone"]
        to = row["to_zone"]
        cap = row["ntc_mean_mw"]

        if frm not in n.buses.index or to not in n.buses.index:
            skipped += 1
            continue

        link_name = f"Link_{frm}_to_{to}"

        if link_name in n.links.index:
            old_cap = n.links.loc[link_name, "p_nom"]
            new_cap = old_cap + cap
            n.links.loc[link_name, "p_nom"] = new_cap
            logger.info("  Paper NTC %s -> %s: +%.0f MW -> %.0f MW gesamt", frm, to, cap, new_cap)
            added += 1
            continue

        n.add("Link", link_name,
              bus0=frm, bus1=to,
              p_nom=cap, p_min_pu=0.0,
              efficiency=1.0, carrier="AC")
        logger.info("  Paper NTC %s -> %s: %.0f MW", frm, to, cap)
        added += 1

    logger.info("Paper-Links hinzugefügt: %d, übersprungen: %d", added, skipped)
