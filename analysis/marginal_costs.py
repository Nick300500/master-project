"""
marginal_costs.py
=================
Berechnet Grenzkosten aller Energiequellen über alle simulierten Klimajahre.

Für jeden Carrier × Zone × Jahr:
  - marginal_cost_eur_mwh     : statische Grenzkosten aus dem Modell (kapazitätsgewichtet)
  - dispatch_gwh               : gesamte Erzeugung
  - mc_dispatch_weighted       : dispatch-gewichtete Grenzkosten
  - lmp_at_dispatch_eur_mwh   : Ø Strompreis (LMP) in Stunden, in denen die Quelle aktiv war

Liest alle Ergebnisordner in 04_results/ (von main/run_simulation.py).

Aufruf (aus dem Projekt-Root):
    python analysis/marginal_costs.py
Output: 04_results/grenzkosten_summary.csv
"""

import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config

# ── Pfade ────────────────────────────────────────────────────────────────────
RESULTS_DIR  = config.RESULTS_DIR
OUT_FILE     = RESULTS_DIR / "grenzkosten_summary.csv"

_CY_RE = re.compile(r"CY(\d{4})")


def _load_folder(folder: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gibt (gen_df, storage_df) zurück; beide mit Spalten [year, zone, carrier,
    dispatch_gwh, marginal_cost, lmp_at_dispatch]."""
    m = _CY_RE.search(folder.name)
    year = int(m.group(1)) if m else -1

    cap_gen = pd.read_csv(folder / "capacities_generators.csv", index_col=0)
    dis_gen = pd.read_csv(folder / "dispatch_generators.csv",   index_col=0)
    lmp     = pd.read_csv(folder / "prices_lmp.csv",           index_col=0)

    # Dispatch-Summe (GWh) und LMP-beim-Dispatch pro Generator
    dis_gwh = dis_gen.sum() / 1000
    active_mask = dis_gen > 0.1          # Stunden mit Einspeisung
    # Ø LMP in aktiven Stunden: für jeden Generator den Bus-Preis nehmen
    lmp_means = {}
    for gen in dis_gen.columns:
        bus = cap_gen.at[gen, "bus"] if gen in cap_gen.index else None
        if bus and bus in lmp.columns:
            prices_when_active = lmp.loc[active_mask[gen], bus]
            lmp_means[gen] = prices_when_active.mean() if len(prices_when_active) > 0 else float("nan")
        else:
            lmp_means[gen] = float("nan")

    gen_df = cap_gen[["bus", "carrier", "marginal_cost"]].copy()
    gen_df["dispatch_gwh"]       = dis_gwh
    gen_df["lmp_at_dispatch"]    = pd.Series(lmp_means)
    gen_df["year"]               = year
    gen_df["source_type"]        = "generator"

    # ── Storage ──────────────────────────────────────────────────────────────
    cap_sto = pd.read_csv(folder / "capacities_storage.csv",  index_col=0)
    dis_sto = pd.read_csv(folder / "storage_dispatch.csv",    index_col=0)

    dis_sto_gwh = dis_sto.sum() / 1000
    active_sto  = dis_sto > 0.1
    lmp_sto = {}
    for su in dis_sto.columns:
        bus = cap_sto.at[su, "bus"] if su in cap_sto.index else None
        if bus and bus in lmp.columns:
            prices_when_active = lmp.loc[active_sto[su], bus]
            lmp_sto[su] = prices_when_active.mean() if len(prices_when_active) > 0 else float("nan")
        else:
            lmp_sto[su] = float("nan")

    sto_df = cap_sto[["bus", "carrier"]].copy()
    sto_df["marginal_cost"]   = 0.0
    sto_df["dispatch_gwh"]    = dis_sto_gwh
    sto_df["lmp_at_dispatch"] = pd.Series(lmp_sto)
    sto_df["year"]            = year
    sto_df["source_type"]     = "storage"

    return gen_df, sto_df


def run():
    folders = sorted(p for p in RESULTS_DIR.iterdir() if p.is_dir())
    if not folders:
        print(f"Keine Ergebnisordner in {RESULTS_DIR}")
        return

    all_frames: list[pd.DataFrame] = []
    for folder in folders:
        try:
            gen_df, sto_df = _load_folder(folder)
            all_frames.extend([gen_df, sto_df])
            print(f"  OK {folder.name}")
        except Exception as e:
            print(f"  FEHLER {folder.name}: {e}")

    if not all_frames:
        print("Keine Daten geladen.")
        return

    df = pd.concat(all_frames)
    df.index.name = "name"
    df = df.rename(columns={"bus": "zone"}).reset_index()

    # ── Aggregation: Carrier × Zone × Jahr ───────────────────────────────────
    def agg_group(g: pd.DataFrame) -> pd.Series:
        total_gwh = g["dispatch_gwh"].sum()
        mc_static = (
            (g["marginal_cost"] * g["dispatch_gwh"]).sum() / total_gwh
            if total_gwh > 0
            else g["marginal_cost"].mean()
        )
        lmp_disp = (
            (g["lmp_at_dispatch"] * g["dispatch_gwh"]).sum() / total_gwh
            if total_gwh > 0
            else float("nan")
        )
        return pd.Series({
            "dispatch_gwh"            : round(total_gwh, 3),
            "marginal_cost_eur_mwh"   : round(g["marginal_cost"].mean(), 4),
            "mc_dispatch_weighted"    : round(mc_static, 4),
            "lmp_at_dispatch_eur_mwh" : round(lmp_disp, 4),
            "source_type"             : g["source_type"].iloc[0],
        })

    summary = (
        df.groupby(["year", "zone", "carrier"])
          .apply(agg_group)
          .reset_index()
          .sort_values(["year", "zone", "carrier"])
    )

    summary.to_csv(OUT_FILE, index=False, float_format="%.4f")
    print(f"\nGespeichert: {OUT_FILE}")
    print(f"Zeilen: {len(summary):,}  |  Jahre: {summary['year'].nunique()}  "
          f"|  Carrier: {sorted(summary['carrier'].unique())}")
    print()
    print(summary.to_string(index=False))


if __name__ == "__main__":
    run()
