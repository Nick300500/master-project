"""
plot_merit_order_DE.py
======================
Merit-Order-Kurve für eine einzelne Stunde, wahlweise:
  a) Stilisierter Einzelstundenfall (Default, Grenzpreis ≈ 12,5 €/MWh)
  b) Echter Dispatch aus dispatch_generators.csv + capacities_generators.csv

Verwendung:
    # Stilisierter Fall (12,5 €/MWh):
    python 02_models/skripts/plot_merit_order_DE.py

    # Echter Dispatch, Stunde 0:
    python 02_models/skripts/plot_merit_order_DE.py \
        --dispatch  "04_results/.../dispatch_generators.csv" \
        --caps      "04_results/.../capacities_generators.csv" \
        --hour 0 --zone DE

    python 02_models/skripts/plot_merit_order_DE.py --output merit_order_DE.png
"""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker
import pandas as pd

# ── Real-data generators DE (CY2011) ──────────────────────────────────────────
# Renewables: annual average dispatch (MW) from dispatch_generators.csv CY2011
# Dispatchable: installed capacity from capacities_generators.csv
STYLIZED_GENERATORS = [
    # name              MW (avg dispatch / installed)  MC (€/MWh)  Carrier
    ("Wind Onshore",        35_963,          0.0,    "wind"),    # avg dispatch CY2011
    ("Wind Offshore",       14_302,          0.0,    "wind"),    # avg dispatch CY2011
    ("Solar PV",            19_433,          0.0,    "solar"),   # avg dispatch CY2011
    ("Run-of-River",         1_727,          0.0,    "hydro"),   # avg dispatch CY2011
    ("Biomass",             12_034,         30.0,    "biomass"), # installed capacity
    ("DSR Band 1",             112,        100.0,    "DSR"),     # installed capacity
    ("DSR Band 2",             349,        125.0,    "DSR"),
    ("Gas (CCGT)",          35_449,        133.6,    "gas"),     # installed capacity
    ("DSR Band 3",           1_051,        150.0,    "DSR"),
    ("DSR Band 4",           1_300,        200.0,    "DSR"),
    ("DSR Band 5",           2_687,        300.0,    "DSR"),
    ("Oil",                    850,        296.5,    "oil"),     # installed capacity
    ("Load Shedding",       50_000,       3000.0,    "mismatch"),
]

CARRIER_COLORS = {
    "wind"         : "#29B6F6",
    "solar"        : "#FDD835",
    "hydro"        : "#4DD0E1",
    "hydro_storage": "#00897B",
    "biomass"      : "#66BB6A",
    "gas"          : "#EF5350",
    "oil"          : "#AB47BC",
    "nuclear"      : "#FFF176",
    "lignite"      : "#8D6E63",
    "coal"         : "#78909C",
    "DSR"          : "#FFA726",
    "mismatch"     : "#BDBDBD",
}

DEMAND_MW        = 74_466   # annual average DE 2030
DEMAND_PEAK_MW   = 74_466   # annual average sits just above zero-cost block (~71.4 GW)
                             # → biomass sets clearing price at 30 €/MWh vs 0 €/MWh

# Grenzkosten je Carrier (für echte Dispatch-Daten)
MC_MAP = {
    "gas"     : 133.62,
    "oil"     : 296.54,
    "biomass" :  30.0,
    "wind"    :   0.0,
    "solar"   :   0.0,
    "hydro"   :   0.0,
    "nuclear" :  12.53,
    "lignite" : 120.21,
    "coal"    : 113.62,
    "DSR"     : 100.0,   # Band 1 default
    "mismatch": 3000.0,
}

# Feinere MC-Zuweisung über Generatornamen (Priorität über Carrier-Map)
def _mc_from_name(name: str, carrier: str) -> float:
    n = name.lower()
    if "band1" in n or "band_1" in n: return 100.0
    if "band2" in n or "band_2" in n: return 125.0
    if "band3" in n or "band_3" in n: return 150.0
    if "band4" in n or "band_4" in n: return 200.0
    if "band5" in n or "band_5" in n: return 300.0
    if "band6" in n or "band_6" in n: return 400.0
    return MC_MAP.get(carrier, 0.0)


def load_real_dispatch(dispatch_csv: Path, caps_csv: Path, zone: str, hour: int) -> list:
    """Lädt tatsächlichen Dispatch + Kapazitätsdaten für eine Zone und Stunde."""
    disp = pd.read_csv(dispatch_csv, index_col=0)
    caps = pd.read_csv(caps_csv)

    zone_cols = [c for c in disp.columns if c.endswith(f"_{zone}") or c.endswith(f"_{zone} ")]
    row = disp.iloc[hour][zone_cols]

    caps_zone = caps[caps["bus"] == zone].set_index("name")

    generators = []
    for col in zone_cols:
        mw = float(row[col])
        if mw < 0.01:
            continue
        gen_name = col
        if gen_name in caps_zone.index:
            carrier = str(caps_zone.at[gen_name, "carrier"])
        else:
            carrier = _guess_carrier(gen_name)
        mc = _mc_from_name(gen_name, carrier)
        label = _short_label(gen_name, zone)
        generators.append((label, mw, mc, carrier))

    return generators


def _guess_carrier(name: str) -> str:
    n = name.lower()
    for kw, c in [("wind", "wind"), ("solar", "solar"), ("ror", "hydro"), ("run", "hydro"),
                  ("gas", "gas"), ("oil", "oil"), ("biomass", "biomass"), ("nuclear", "nuclear"),
                  ("lignite", "lignite"), ("coal", "coal"), ("dsr", "DSR"),
                  ("loadshedding", "mismatch"), ("mismatch", "mismatch")]:
        if kw in n:
            return c
    return "other"


def _short_label(name: str, zone: str) -> str:
    return name.replace(f"_{zone}", "").replace("_", " ")


def build_merit_order(generators: list) -> list:
    rows = sorted(generators, key=lambda r: (r[2], -r[1]))
    result, cum = [], 0.0
    for name, p_nom, mc, carrier in rows:
        result.append({
            "name": name, "p_nom": p_nom, "mc": mc,
            "carrier": carrier, "x_start": cum, "x_end": cum + p_nom,
        })
        cum += p_nom
    return result


def plot_merit_order(
    generators: list,
    demand_mw: float = DEMAND_MW,
    title: str = "Merit-Order Deutschland (DE) – Einzelstundenfall",
    subtitle: str = "",
    output_path: Path = None,
):
    mo = build_merit_order(generators)
    mo_visible = [r for r in mo if r["carrier"] != "mismatch"]

    if not mo_visible:
        print("Keine Daten zum Plotten.")
        return

    x_total = mo_visible[-1]["x_end"]
    y_max   = max(r["mc"] for r in mo_visible) * 1.25
    y_max   = max(y_max, 20)

    # Grenzpreis
    clearing_price, clearing_name = None, None
    for r in mo:
        if r["x_end"] >= demand_mw:
            clearing_price = r["mc"]
            clearing_name  = r["name"]
            break

    fig, ax = plt.subplots(figsize=(13, 6))
    full_title = title + (f"\n{subtitle}" if subtitle else "")
    ax.set_title(full_title, fontsize=12, fontweight="bold", pad=10)

    seen = set()
    for r in mo_visible:
        c = r["carrier"]
        color = CARRIER_COLORS.get(c, "#BDBDBD")
        lbl = c.replace("_", " ").title() if c not in seen else "_nolegend_"
        seen.add(c)

        mid = (r["x_start"] + r["x_end"]) / 2
        gap = min(200, r["p_nom"] * 0.03)

        ax.bar(
            x=mid,
            height=max(r["mc"], 0.8),
            width=r["p_nom"] - gap,
            bottom=0,
            color=color,
            label=lbl,
            edgecolor="white",
            linewidth=0.6,
            zorder=2,
        )

        # MC-Label in Balken (wenn breit und hoch genug)
        if r["p_nom"] > 1_500 and r["mc"] > 2:
            ax.text(
                mid, r["mc"] * 0.45,
                f"{r['mc']:.0f}",
                ha="center", va="center",
                fontsize=7, color="white", fontweight="bold", zorder=3,
            )

    # ── Nachfragelinie ────────────────────────────────────────────────────────
    if demand_mw <= x_total * 1.1:
        ax.axvline(demand_mw, color="#C62828", lw=2.5, ls="-", zorder=5,
                   label=f"Nachfrage ({demand_mw/1000:.1f} GW)")

    # ── Grenzpreis-Annotation ─────────────────────────────────────────────────
    if clearing_price is not None and demand_mw <= x_total * 1.1:
        ax.axhline(clearing_price, color="#1A237E", lw=1.4, ls="--", alpha=0.75, zorder=4)
        offset_x = min(demand_mw + x_total * 0.03, x_total * 0.98)
        offset_y = min(clearing_price + y_max * 0.08, y_max * 0.92)
        ax.annotate(
            f"Grenzpreis: {clearing_price:.1f} €/MWh\n({clearing_name})",
            xy=(demand_mw, clearing_price),
            xytext=(offset_x, offset_y),
            fontsize=9, color="#1A237E", fontweight="bold",
            arrowprops=dict(arrowstyle="->", color="#1A237E", lw=1.2),
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#1A237E", alpha=0.9),
            zorder=6,
        )

    # ── Achsen ────────────────────────────────────────────────────────────────
    ax.set_xlim(0, x_total * 1.02)
    ax.set_ylim(0, y_max)
    ax.set_xlabel("Kumulierte verfügbare Kapazität (GW)", fontsize=11)
    ax.set_ylabel("Grenzkosten (€/MWh)", fontsize=11)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}"))
    ax.xaxis.set_major_locator(mticker.MultipleLocator(10_000))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(25))
    ax.grid(axis="y", alpha=0.2, linestyle=":", zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=10)

    # Gesamt-Erneuerbare Annotation
    res_total = sum(r["p_nom"] for r in mo_visible if r["carrier"] in ("wind", "solar", "hydro"))
    if res_total > 0:
        ax.text(
            res_total / 2, y_max * 0.04,
            f"EE: {res_total/1000:.0f} GW",
            ha="center", va="bottom", fontsize=8, color="#37474F",
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#CCCCCC", alpha=0.7),
        )

    ax.legend(loc="upper left", fontsize=9, frameon=True, framealpha=0.9,
              edgecolor="#CCCCCC", ncol=2)

    plt.tight_layout()

    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Gespeichert: {output_path}")
    else:
        plt.show()


def _make_biomass_variant(generators: list, biomass_mc: float) -> list:
    """Gibt Kopie der Generatorliste zurück mit angepasstem Biomasse-Grenzkosten."""
    return [
        (name, mw, biomass_mc if carrier == "biomass" else mc, carrier)
        for name, mw, mc, carrier in generators
    ]


CARRIER_LABELS_EN = {
    "wind"         : "Wind",
    "solar"        : "Solar PV",
    "hydro"        : "Run-of-River",
    "hydro_storage": "Hydro Storage",
    "biomass"      : "Biomass",
    "gas"          : "Gas (CCGT)",
    "oil"          : "Oil",
    "nuclear"      : "Nuclear",
    "lignite"      : "Lignite",
    "coal"         : "Coal",
    "DSR"          : "DSR",
    "mismatch"     : "VoLL",
}


def _draw_panel(ax, generators: list, demand_mw: float, title: str, y_cap: float = 350.0,
                min_load_mw: float = None, max_load_mw: float = None):
    """Draws one merit-order panel on ax. VoLL is shown as a capped stub at y_cap."""
    mo = build_merit_order(generators)
    mo_dispatch = [r for r in mo if r["carrier"] != "mismatch"]
    mo_voll     = [r for r in mo if r["carrier"] == "mismatch"]

    x_total = mo_dispatch[-1]["x_end"] if mo_dispatch else 1
    zero_end = max((r["x_end"] for r in mo_dispatch if r["mc"] == 0.0), default=0)

    # ── Zero-cost shading ────────────────────────────────────────────────────
    if zero_end > 0:
        ax.axvspan(0, zero_end, color="#E3F2FD", alpha=0.45, zorder=0)

    # ── Dispatchable bars ────────────────────────────────────────────────────
    seen = set()
    for r in mo_dispatch:
        c = r["carrier"]
        color = CARRIER_COLORS.get(c, "#BDBDBD")
        lbl = CARRIER_LABELS_EN.get(c, c) if c not in seen else "_nolegend_"
        seen.add(c)
        mid = (r["x_start"] + r["x_end"]) / 2
        gap = min(200, r["p_nom"] * 0.03)
        ax.bar(x=mid, height=max(r["mc"], 0.8), width=r["p_nom"] - gap,
               bottom=0, color=color, label=lbl,
               edgecolor="white", linewidth=0.6, zorder=2)
        if r["p_nom"] > 1_500 and r["mc"] > 2:
            ax.text(mid, r["mc"] * 0.45, f"{r['mc']:.0f}",
                    ha="center", va="center",
                    fontsize=7, color="white", fontweight="bold", zorder=3)

    # ── VoLL stub at top ────────────────────────────────────────────────────
    for r in mo_voll:
        mid = (r["x_start"] + r["x_end"]) / 2
        stub_h = y_cap * 0.12
        color = CARRIER_COLORS.get(r["carrier"], "#BDBDBD")
        lbl = "VoLL (3,000 €/MWh)" if "VoLL" not in seen else "_nolegend_"
        seen.add("VoLL")
        ax.bar(x=mid, height=stub_h, width=r["p_nom"] * 0.98,
               bottom=y_cap * 0.88, color=color, label=lbl,
               edgecolor="white", linewidth=0.5, zorder=2, alpha=0.85)
        ax.text(mid, y_cap * 0.935, "VoLL = 3,000 €/MWh ↑",
                ha="center", va="center", fontsize=8,
                color="#616161", fontweight="bold", zorder=4)
        # wavy break indicator
        ax.plot([r["x_start"], r["x_end"]], [y_cap * 0.87, y_cap * 0.87],
                color="#9E9E9E", lw=0.8, ls=":", zorder=3)

    # ── Zero-cost annotation ────────────────────────────────────────────────
    if zero_end > 0:
        ax.annotate(
            "MC = 0 €/MWh\n(wind, solar, RoR)",
            xy=(zero_end / 2, 1.5),
            xytext=(zero_end / 2, y_cap * 0.22),
            ha="center", fontsize=8.5, color="#1565C0", fontweight="bold",
            arrowprops=dict(arrowstyle="-", color="#1565C0", lw=1.0, linestyle="dashed"),
            bbox=dict(boxstyle="round,pad=0.3", fc="#E3F2FD", ec="#1565C0", alpha=0.9),
            zorder=5,
        )

    # ── Demand line ─────────────────────────────────────────────────────────
    ax.axvline(demand_mw, color="#C62828", lw=2.5, zorder=5,
               label=f"Demand ({demand_mw/1000:.1f} GW)")

    # ── Clearing price ───────────────────────────────────────────────────────
    for r in mo:
        if r["x_end"] >= demand_mw:
            cp, cn = r["mc"], r["name"]
            if cp <= y_cap:
                ax.axhline(cp, color="#1A237E", lw=1.4, ls="--", alpha=0.75, zorder=4)
                ax.annotate(
                    f"Clearing price: {cp:.1f} €/MWh\n({cn})",
                    xy=(demand_mw, cp),
                    xytext=(demand_mw + x_total * 0.04, cp + y_cap * 0.07),
                    fontsize=9, color="#1A237E", fontweight="bold",
                    arrowprops=dict(arrowstyle="->", color="#1A237E", lw=1.2),
                    bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#1A237E", alpha=0.9),
                    zorder=6,
                )
            print(f"  [{title}]  Clearing price: {cp:.1f} €/MWh  |  {cn}")
            break

    # ── Min / Max load band ──────────────────────────────────────────────────
    if min_load_mw is not None:
        ax.axvline(min_load_mw, color="#E65100", lw=1.6, ls="--", zorder=4,
                   label=f"Min load ({min_load_mw/1000:.0f} GW)")
        ax.text(min_load_mw - x_total * 0.008, y_cap * 0.97,
                f"min\n{min_load_mw/1000:.0f} GW",
                ha="right", va="top", fontsize=7.5, color="#E65100", fontweight="bold")

    if max_load_mw is not None:
        capped = max_load_mw <= x_total * 1.02
        ax.axvline(min(max_load_mw, x_total * 1.015), color="#B71C1C", lw=1.6, ls="--",
                   zorder=4, label=f"Max load ({max_load_mw/1000:.0f} GW)")
        x_label = min(max_load_mw, x_total * 0.99)
        ax.text(x_label + x_total * 0.008, y_cap * 0.97,
                f"max\n{max_load_mw/1000:.0f} GW",
                ha="left", va="top", fontsize=7.5, color="#B71C1C", fontweight="bold")

    if min_load_mw is not None and max_load_mw is not None:
        ax.axvspan(min_load_mw, min(max_load_mw, x_total * 1.015),
                   alpha=0.07, color="#FF6F00", zorder=1,
                   label="_nolegend_")

    # ── Axes ─────────────────────────────────────────────────────────────────
    ax.set_xlim(0, x_total * 1.02)
    ax.set_ylim(0, y_cap)
    ax.set_title(title, fontsize=11, fontweight="bold")
    ax.set_xlabel("Cumulative available capacity (GW)", fontsize=10)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1000:.0f}"))
    ax.xaxis.set_major_locator(mticker.MultipleLocator(10_000))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(50))
    ax.grid(axis="y", alpha=0.2, linestyle=":", zorder=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=10)
    ax.legend(loc="upper left", fontsize=8.5, frameon=True,
              framealpha=0.9, edgecolor="#CCCCCC", ncol=2)


def plot_comparison(
    generators_base: list,
    biomass_mc_a: float = 0.0,
    biomass_mc_b: float = 30.0,
    demand_mw: float = DEMAND_MW,
    min_load_mw: float = None,
    max_load_mw: float = None,
    output_path: Path = None,
):
    """Comparison plot: biomass=0 (left) vs biomass=30 (right)."""
    gen_a = _make_biomass_variant(generators_base, biomass_mc_a)
    gen_b = _make_biomass_variant(generators_base, biomass_mc_b)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(17, 6), sharey=True)
    fig.suptitle(
        f"Merit-Order Comparison – Impact of Biomass Marginal Cost (DE)\n"
        f"High-demand winter hour  |  Demand = {demand_mw/1000:.0f} GW",
        fontsize=12, fontweight="bold",
    )

    _draw_panel(ax1, gen_a, demand_mw, title=f"Biomass MC = {biomass_mc_a:.0f} €/MWh  (reference)",
                min_load_mw=min_load_mw, max_load_mw=max_load_mw)
    _draw_panel(ax2, gen_b, demand_mw, title=f"Biomass MC = {biomass_mc_b:.0f} €/MWh  (model)",
                min_load_mw=min_load_mw, max_load_mw=max_load_mw)

    ax1.set_ylabel("Marginal Cost (€/MWh)", fontsize=11)
    ax2.set_ylabel("")

    plt.tight_layout()
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"Saved: {output_path}")
    else:
        plt.show()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dispatch", type=Path, default=None,
                        help="dispatch_generators.csv")
    parser.add_argument("--caps",     type=Path, default=None,
                        help="capacities_generators.csv")
    parser.add_argument("--zone",     type=str,  default="DE")
    parser.add_argument("--hour",     type=int,  default=0)
    parser.add_argument("--demand",   type=float, default=DEMAND_MW)
    parser.add_argument("--output",   type=Path,  default=None)
    parser.add_argument("--compare",   action="store_true",
                        help="Comparison plot: biomass 0 vs. 30 €/MWh")
    parser.add_argument("--min-load", type=float, default=None,
                        help="Min load line in MW (e.g. 44000)")
    parser.add_argument("--max-load", type=float, default=None,
                        help="Max load line in MW (e.g. 115000)")
    args = parser.parse_args()

    if args.dispatch and args.dispatch.exists() and args.caps and args.caps.exists():
        generators = load_real_dispatch(args.dispatch, args.caps, args.zone, args.hour)
        total_mw = sum(g[1] for g in generators)
        print(f"Real dispatch hour {args.hour}: {len(generators)} generators, "
              f"total {total_mw/1000:.1f} GW")
        subtitle = f"Real dispatch – hour {args.hour}  |  Zone: {args.zone}"
        title = f"Merit Order {args.zone} – Single Hour (real)"
    else:
        if args.dispatch:
            print("WARNING: dispatch CSV not found, using stylized scenario.")
        generators = STYLIZED_GENERATORS
        subtitle = "Stylized single-hour scenario – hydro storage (12.5 €/MWh) sets clearing price"
        title = "Merit Order Germany (DE) – Single Hour"

    if args.compare:
        demand_cmp = args.demand if args.demand != DEMAND_MW else DEMAND_PEAK_MW
        plot_comparison(generators, biomass_mc_a=0.0, biomass_mc_b=30.0,
                        demand_mw=demand_cmp,
                        min_load_mw=args.min_load,
                        max_load_mw=args.max_load,
                        output_path=args.output)
    else:
        mo = build_merit_order(generators)
        for r in mo:
            if r["x_end"] >= args.demand:
                print(f"Clearing price: {r['mc']:.1f} €/MWh  |  {r['name']}")
                break
        plot_merit_order(generators, demand_mw=args.demand, title=title,
                         subtitle=subtitle, output_path=args.output)
