"""
max_limits.py
=============
Lädt länderweite Gross-Import/Export-NTC-Obergrenzen (ENTSO-E
"Country Level Maximum NTC", Datei "Max limit.csv") und erzwingt sie als
zusätzliche Nebenbedingung im PyPSA-Optimierungsmodell:

    Summe aller Export-Flüsse einer Zone (Links mit bus0 == Zone)
        <= Gross_Export_limit
    Summe aller Import-Flüsse einer Zone (Links mit bus1 == Zone)
        <= Gross_Import_limit

Diese Grenzen ergänzen die bilateralen NTC-Kapazitäten um eine
Top-Level-Begrenzung pro Gebotszone (an/aus: config.ENFORCE_MAX_LIMITS bzw.
--max-limits / --no-max-limits).

WICHTIG - Datenlage:
ERAA liefert dieses Limit NICHT für alle Gebotszonen, sondern nur für
ausgewählte Bottleneck-Märkte. Im TY2030-Datensatz sind das (Stand
dieses Skripts): BG00, CH00, CY00, CZ00, HR00, MT00, NL00, RS00, SK00,
UK00. Für alle anderen Zonen (u.a. DE, FR, AT, ES, IT...) existiert
keine Country-Level-Grenze - dort bleibt der Austausch ausschließlich
durch die bilateralen Link-Kapazitäten begrenzt. Das ist kein
Datenfehler, sondern ERAA-Methodik (nur bekannte Engpassregionen werden
zusätzlich gedeckelt).

NL00 liefert nur "Country_position-net_exp/imp_limit" (Netto-Position),
keine Gross-Werte. Da das eine andere physikalische Größe ist als die
gerichteten Brutto-Flüsse, die hier modelliert werden, wird NL bewusst
NICHT constraint - eine Gleichsetzung wäre fachlich falsch.

Verwendung:
    from pipeline.model.max_limits import max_limit_extra_functionality
    n.optimize(
        solver_name="gurobi",
        extra_functionality=max_limit_extra_functionality(active_zones),
    )
"""

import logging
from pathlib import Path

import pandas as pd
import pypsa

import config

logger = logging.getLogger(__name__)

# "Max limit.csv" wird von der Datenaufbereitung unverändert (nicht
# aggregiert) kopiert; die Zonen-Gruppierung passiert deshalb hier.
MAX_LIMIT_PATH = (
    config.ACCUMULATED_DIR / "Transfer capacities"
    / f"Transfer Capacities_ERAA2022_TY{config.TARGET_YEAR}" / "Max limit.csv"
)


def _normalize_zone(candidate: str) -> str:
    candidate = candidate.upper()
    if len(candidate) == 4 and candidate[:2].isalpha() and candidate[2:].isdigit():
        return candidate[:2]
    if len(candidate) == 2 and candidate.isalpha():
        return candidate
    return candidate


def _resolve_group(zone: str) -> str:
    normalized = _normalize_zone(str(zone).strip().upper())
    for group_name, zones in config.ZONE_GROUPS.items():
        if normalized in zones:
            return group_name
    return normalized


def load_max_limits(active_zones: list, path: Path = MAX_LIMIT_PATH) -> dict:
    """
    Liest Max limit.csv und aggregiert Gross_Import_limit/Gross_Export_limit
    je PyPSA-Zone (Jahresmittel, paper-konform statisch wie die übrigen NTCs).

    Gibt zurück: {zone: {"import": mw, "export": mw}} - nur für Zonen mit
    tatsächlich vorhandenen Daten in active_zones.
    """
    if not path.exists():
        logger.warning(f"Max limit-Datei nicht gefunden: {path}")
        return {}

    raw = pd.read_csv(path, header=None, low_memory=False)

    # Layout dieser Rohdatei (ENTSO-E Country_Level_Maximum_NTC Export):
    #   Zeile 9  (index 8): Zonencode, 4x je Zone wiederholt
    #   Zeile 10 (index 9): Metrikname "{zone}-Gross_Import_limit" etc.
    #   Ab Zeile 16 (index 15): stündliche Werte
    zone_row   = raw.iloc[8, 2:]
    metric_row = raw.iloc[9, 2:]
    data       = raw.iloc[15:, 2:].apply(pd.to_numeric, errors="coerce")
    means      = data.mean(axis=0)

    active_set = set(active_zones)
    aggregated = {}  # zone -> {"import": float, "export": float}

    for col, zone_code, metric, mean_val in zip(
        zone_row.index, zone_row.values, metric_row.values, means.values
    ):
        if pd.isna(mean_val) or mean_val <= 0:
            continue
        metric = str(metric)
        if metric.endswith("Gross_Import_limit"):
            kind = "import"
        elif metric.endswith("Gross_Export_limit"):
            kind = "export"
        else:
            # Country_position-net_exp/imp_limit: andere physikalische
            # Größe (Netto statt Brutto-Richtungsfluss), bewusst ignoriert.
            continue

        group = _resolve_group(zone_code)
        if group not in active_set:
            continue

        aggregated.setdefault(group, {})
        aggregated[group][kind] = aggregated[group].get(kind, 0.0) + float(mean_val)

    for zone, lim in aggregated.items():
        logger.info(
            f"  Max-Limit {zone}: "
            f"Import<={lim.get('import', float('inf')):.0f} MW, "
            f"Export<={lim.get('export', float('inf')):.0f} MW"
        )

    return aggregated


def max_limit_extra_functionality(active_zones: list, limits: dict = None):
    """
    Erstellt eine extra_functionality-Funktion für n.optimize(), die die
    Country-Level-Max-Limits als lineare Nebenbedingung je Snapshot
    durchsetzt. Zonen ohne Daten bleiben unverändert unconstrained.
    """
    if limits is None:
        limits = load_max_limits(active_zones)

    def extra_functionality(n: pypsa.Network, snapshots):
        if not limits:
            logger.info("Keine Max-Limit-Daten für aktive Zonen - keine zusätzlichen Constraints.")
            return
        if "Link-p" not in n.model.variables:
            logger.warning("Keine Link-p Variable im Modell gefunden - Max-Limits übersprungen.")
            return

        p = n.model.variables["Link-p"]
        applied = []

        for zone, lim in limits.items():
            export_links = list(n.links.index[n.links.bus0 == zone])
            import_links = list(n.links.index[n.links.bus1 == zone])

            export_cap = lim.get("export")
            if export_cap and export_links:
                lhs = p.sel(name=export_links).sum("name")
                n.model.add_constraints(lhs <= export_cap, name=f"MaxLimit-export-{zone}")
                applied.append(f"{zone} Export<={export_cap:.0f}MW ({len(export_links)} Links)")

            import_cap = lim.get("import")
            if import_cap and import_links:
                lhs = p.sel(name=import_links).sum("name")
                n.model.add_constraints(lhs <= import_cap, name=f"MaxLimit-import-{zone}")
                applied.append(f"{zone} Import<={import_cap:.0f}MW ({len(import_links)} Links)")

        logger.info("Max-Limit-Constraints aktiv: %s", "; ".join(applied) if applied else "keine (keine passenden Links)")

    return extra_functionality
