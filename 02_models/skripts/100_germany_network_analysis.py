"""
PyPSA Deutschland-Simulation mit Gurobi
Echte ERAA-Zeitreihen für Last, Wind, Solar
"""

import pypsa
import pandas as pd
import numpy as np
import sys
from pathlib import Path

# ─────────────────────────────────────────────
# KONFIGURATION
# ─────────────────────────────────────────────
CLIMATE_YEAR = "2012"       # Wetterjahr (Spalte in den CSV-Dateien)
SOLVER       = "gurobi"
TARGET_ZONE  = "DE"         # Aggregierte Zone nach deiner Akkumulation

DATA_DIR = Path("01_data/04b_accumulated_data_per_node")

# Pfade zu deinen akkumulierten Dateien
PATH_LOAD        = DATA_DIR / "Demand" / "Demand Time Series" / "Demand_TimeSeries_2030_NationalTrends_without_bat" / "DE_accumulated.csv"
PATH_WIND_ON     = DATA_DIR / "Climate Data/Wind Onshore" / "PECD_Wind_Onshore_2030_edition 2022.1" / "DE_accumulated.csv"
PATH_WIND_OFF    = DATA_DIR / "Climate Data/Wind Offshore" / "PECD_Wind_Offshore_2030_edition 2022.1" / "DE_accumulated.csv"
PATH_SOLAR_PV    = DATA_DIR / "Climate Data/Solar"   / "PECD_LFSolarPV_2030_edition 2022.1"   / "DE_accumulated.csv"
PATH_ROR         = DATA_DIR / "Climate Data/Hydro Inflows"     / "Run of River"       / "DE_accumulated.csv"
PATH_PONDAGE     = DATA_DIR / "Climate Data/Hydro Inflows"     / "Pondage"            / "DE_accumulated.csv"
PATH_RESERVOIR   = DATA_DIR / "Climate Data/Hydro Inflows"     / "Reservoir"          / "DE_accumulated.csv"
PATH_PS_OPEN     = DATA_DIR / "Climate Data/Hydro Inflows"     / "Pump storage - Open Loop"   / "DE_accumulated.csv"
PATH_PS_CLOSED   = DATA_DIR / "Climate Data/Hydro Inflows"     / "Pump storage - Closed Loop" / "DE_accumulated.csv"

# Welche DE-Zonen gehen in die Offshore-Akkumulation ein und mit welchem Gewicht?
summary = pd.read_csv(
    DATA_DIR / "Climate Data/Wind Offshore/PECD_Wind_Offshore_2030_edition 2022.1/01_group_summary.csv"
)
print(summary[summary["group"] == "DE"])

# ─────────────────────────────────────────────
# HILFSFUNKTION: ERAA-Zeitreihe einlesen
# ─────────────────────────────────────────────
def read_eraa_timeseries(path: Path, climate_year: str, 
                          skiprows: int = 9) -> pd.Series:
    """
    Liest eine ERAA-Zeitreihen-CSV ein und gibt eine stündliche
    pd.Series für das gewählte Klimajahr zurück (8760 Werte).
    
    - skiprows: Anzahl Metadaten-Zeilen (Load=9, vRES=10 – anpassen!)
    - Klimajahr: als String, z.B. "2012" oder "2012.0"
    """
    df = pd.read_csv(path, skiprows=skiprows, header=0)
    
    # Erste zwei Spalten: Date + Hour
    df = df.rename(columns={df.columns[0]: "Date", 
                             df.columns[1]: "Hour"})
    
    # Klimajahr-Spalte finden (manchmal "2012", manchmal "2012.0")
    matching_cols = [c for c in df.columns 
                     if str(c).startswith(str(climate_year))]
    if not matching_cols:
        raise ValueError(f"Klimajahr {climate_year} nicht gefunden in {path.name}. "
                         f"Verfügbare Spalten: {list(df.columns[2:7])}...")
    col = matching_cols[0]
    
    # Nur numerische Zeilen behalten (Datum nicht leer, Stunde numerisch)
    df = df.dropna(subset=["Hour"])
    df = df[pd.to_numeric(df["Hour"], errors="coerce").notna()]
    
    # Zeitindex aufbauen: 8760 stündliche Timestamps für 2030
    # (Klimajahr bestimmt das Wetterprofil, Simulationsjahr bleibt 2030)
    timestamps = pd.date_range("2030-01-01", periods=len(df), freq="h")
    
    series = pd.Series(
        pd.to_numeric(df[col].values, errors="coerce"),
        index=timestamps,
        name=path.stem
    )
    
    # Fehlende Werte interpolieren (Lücken durch Metadaten-Reste)
    series = series.interpolate()
    
    # Auf 8760 Stunden beschränken (Schaltjahre haben 8784h)
    return series.iloc[:8760]

def read_hydro_inflow(path: Path, climate_year: str, p_nom_col: int = 2,
                      header_row: int = 12, data_start_row: int = 13,
                      climate_col_start: int = 17) -> tuple[float, pd.Series]:

    raw = pd.read_csv(path, header=None)
    p_nom = abs(float(raw.iloc[5, p_nom_col]))
    
    header = raw.iloc[header_row, climate_col_start:].values
    data   = raw.iloc[data_start_row:, climate_col_start:].copy()
    data.columns = header
    data = data[pd.to_numeric(data.iloc[:, 0], errors="coerce").notna()]
    
    matching_cols = [c for c in data.columns if str(c).startswith(str(climate_year))]
    if not matching_cols:
        raise ValueError(f"Klimajahr {climate_year} nicht in {path.name} gefunden.")
    col = matching_cols[0]
    
    target_data = data[col].iloc[:, 0] if isinstance(data[col], pd.DataFrame) else data[col]
    values = pd.to_numeric(target_data, errors="coerce").fillna(0).values

    # ── NEU: automatisch erkennen ob täglich oder wöchentlich ──
    n_values = len(values)
    if n_values >= 360:        # ~365 Tage
        repeat_hours = 24
        values = values[:365]
    else:                      # ~52-53 Wochen
        repeat_hours = 24 * 7
        values = values[:53]

    # GWh/Periode → MW (stündlich)
    hourly_mw = np.repeat(values * 1000 / repeat_hours, repeat_hours)[:8760]

    cf = pd.Series(
        hourly_mw / p_nom if p_nom > 0 else hourly_mw,
        index=pd.date_range("2030-01-01", periods=8760, freq="h")
    ).clip(0, 1)
    
    return p_nom, cf


# ── Aufruf pro Technologie ───────────────────
ror_pnom,      ror_cf      = read_hydro_inflow(PATH_ROR,           CLIMATE_YEAR)
pondage_pnom,  pondage_cf  = read_hydro_inflow(PATH_PONDAGE,       CLIMATE_YEAR)



# ─────────────────────────────────────────────
# ZEITREIHEN LADEN
# ─────────────────────────────────────────────
print("Lade Zeitreihen...")

# Load: Werte in MW, direkt verwendbar
# vRES: Werte sind CF (0–1), direkt als p_max_pu verwendbar
# skiprows=10 für vRES (11 Zeilen Metadaten, dann Header)
load_ts = read_eraa_timeseries(PATH_LOAD, CLIMATE_YEAR, skiprows=10)
wind_on_cf  = read_eraa_timeseries(PATH_WIND_ON,  CLIMATE_YEAR, skiprows=10)
wind_off_cf = read_eraa_timeseries(PATH_WIND_OFF, CLIMATE_YEAR, skiprows=10)
solar_cf    = read_eraa_timeseries(PATH_SOLAR_PV, CLIMATE_YEAR, skiprows=10)

# CF auf [0,1] clippen (nach gewichtetem Durchschnitt sollte das passen)
wind_on_cf  = wind_on_cf.clip(0, 1)
wind_off_cf = wind_off_cf.clip(0, 1)
solar_cf    = solar_cf.clip(0, 1)

print(f"Last:      {load_ts.mean():.0f} MW Durchschnitt, "
      f"{len(load_ts)} Stunden")
print(f"Wind On:   {wind_on_cf.mean():.3f} CF Durchschnitt")
print(f"Wind Off:  {wind_off_cf.mean():.3f} CF Durchschnitt")
print(f"Solar PV:  {solar_cf.mean():.3f} CF Durchschnitt")

# ─────────────────────────────────────────────
# NETZ AUFBAUEN
# ─────────────────────────────────────────────
print("\nBaue PyPSA-Netz auf...")
n = pypsa.Network()
n.set_snapshots(load_ts.index)

# Carrier definieren (bereinigt Warnungen)
for c in ["AC", "gas", "coal", "nuclear", "biomass", "oil", "wind", "solar", "hydro", "battery", "mismatch", "dsr"]:
    n.add("Carrier", c)

# Bus
n.add("Bus", "DE", v_nom=380, carrier="AC")

# ── Generatoren: konventionell ───────────────
# Marginal Costs: gas_price/eta + co2*intensity/eta
# Werte aus ERAA 2030 Baseline (Supplement S.2)
gas_price  = 44.0   # €/MWh_th
eta_ccgt   = 0.49
co2        = 100.0  # €/t
co2_gas    = 0.202  # t/MWh_th
mc_gas     = gas_price / eta_ccgt + co2 * co2_gas / eta_ccgt

coal_price = 28.0   # €/MWh_th  
eta_coal   = 0.38
co2_coal   = 0.341
mc_coal    = coal_price / eta_coal + co2 * co2_coal / eta_coal

# p_nom-Werte aus deiner akkumulierten PEMMDB-Tabelle (TY 2030, DE)
#Other non-renewables wird zu Gas gerechnet
p_nom_gas_total = 35449 + 5874.9  # Gas + Others non-renewable (aus TY2030)

n.add("Generator", "Gas_DE",
      bus="DE", p_nom=p_nom_gas_total, marginal_cost=mc_gas, carrier="gas")

n.add("Generator", "Coal_DE",
      bus="DE", p_nom=0,     marginal_cost=mc_coal, carrier="coal")

n.add("Generator", "Nuclear_DE",
      bus="DE", p_nom=0,     marginal_cost=15.0,   carrier="nuclear")

n.add("Generator", "Biomass_DE",
      bus="DE", p_nom=12034, marginal_cost=60.0,   carrier="biomass")

n.add("Generator", "Oil_DE",
      bus="DE", p_nom=850,   marginal_cost=150.0,  carrier="oil")

# ── Generatoren: vRES ────────────────────────
# p_max_pu wird stündlich über Zeitreihe gesetzt
n.add("Generator", "WindOn_DE",
      bus="DE", p_nom=110000, marginal_cost=0.0, carrier="wind")

n.add("Generator", "WindOff_DE",
      bus="DE", p_nom=30048,      marginal_cost=0.0, carrier="wind")

n.add("Generator", "Solar_DE",
      bus="DE", p_nom=200000, marginal_cost=0.0, carrier="solar")

n.add("Generator", "RoR_DE",
      bus="DE", p_nom=ror_pnom, marginal_cost=0.0, carrier="hydro")

n.add("Generator", "Pondage_DE",
      bus="DE", p_nom=pondage_pnom, marginal_cost=0.0, carrier="hydro")

# ── Demand Side Response inkludieren ──
# DSR-Daten laden
dsr = pd.read_csv("01_data/04b_accumulated_data_per_node/ERAA 2022 PEMMDB National Estimates/Explicit DSR.csv")
dsr_de = dsr[dsr["Bidding Zone"] == "DE"].iloc[0]

# Alle 8 Preisbänder durchgehen
for band in range(1, 9):
    cap   = dsr_de[f"Price Band {band} capacity (MW)"]
    price = dsr_de[f"Activation Price for demand reduction for Price Band {band} (EUR/MWh)"]
    hours = dsr_de[f"Max hours to be used per day for Price Band {band}"]

    # Nur Bänder mit echter Kapazität einbauen
    if cap <= 0 or price <= 0:
        continue

    # Max. Stunden/Tag → p_max_pu (tägliche Obergrenze)
    # hours/24 = maximaler Anteil des Tages wo DSR aktiv sein darf
    p_max_pu = hours / 24.0 if hours > 0 else 1.0

    n.add("Generator", f"DSR_DE_band{band}",
              bus="DE",
              p_nom=cap,
              marginal_cost=-price,   # negativ: DSR reduziert Last → senkt Systemkosten
              carrier="dsr",
              p_max_pu=p_max_pu)
    
    
# ── Mismatch Generator (verhindert Infeasibility) ──
# Dieser Generator springt ein, wenn die Last sonst nicht gedeckt werden kann.
# Die Grenzkosten von 10.000 €/MWh markieren den Preis für "Value of Lost Load".
n.add("Generator", "Load_Shedding_DE",
      bus="DE", p_nom=1e6, marginal_cost=3000.0, carrier="mismatch")

# Zeitreihen für vRES einbinden
n.generators_t.p_max_pu["WindOn_DE"]  = wind_on_cf
n.generators_t.p_max_pu["WindOff_DE"] = wind_off_cf
n.generators_t.p_max_pu["Solar_DE"]   = solar_cf
n.generators_t.p_max_pu["RoR_DE"] = ror_cf
n.generators_t.p_max_pu["Pondage_DE"] = pondage_cf

# ── Speicher ─────────────────────────────────

#Adde die Hydro-Speicher als StorageUnits mit Inflow-Zeitreihen (p_nom aus ERAA, Inflow aus Akkumulation)
res_pnom,      res_cf      = read_hydro_inflow(PATH_RESERVOIR,     CLIMATE_YEAR)
res_inflow_mw = res_cf * res_pnom #CF* p_nom -> zurück zu MW
psopen_pnom,   psopen_cf   = read_hydro_inflow(PATH_PS_OPEN,       CLIMATE_YEAR)
psopen_inflow_mw = psopen_cf * psopen_pnom
psclosed_pnom, psclosed_cf = read_hydro_inflow(PATH_PS_CLOSED,     CLIMATE_YEAR) #Kein Zufluss, daher keine Inflow-Zeitreihe nötig, aber p_nom für Kapazität wichtig


n.add("StorageUnit", "PumpHydro_DE",
      bus="DE",
      p_nom=9026,
      marginal_cost=0.0,
      carrier="hydro",
      efficiency_store=0.87,
      efficiency_dispatch=0.87,
      cyclic_state_of_charge=True,
      max_hours=8)

n.add("StorageUnit", "Battery_DE",
      bus="DE",
      p_nom=3200,
      marginal_cost=0.0,
      carrier="battery",
      efficiency_store=0.92,
      efficiency_dispatch=0.92,
      cyclic_state_of_charge=True,
      max_hours=4)

n.add("StorageUnit", "PSOpen_DE",
      bus="DE",
      p_nom=psopen_pnom,
      marginal_cost=0.0,
      carrier="hydro",
      efficiency_store=0.87,
      efficiency_dispatch=0.87,
      cyclic_state_of_charge=True,
      max_hours=8)

n.storage_units_t.inflow["PSOpen_DE"] = psopen_inflow_mw

n.add("StorageUnit", "PSClosed_DE",
      bus="DE",
      p_nom=psclosed_pnom,
      marginal_cost=0.0,
      carrier="hydro",
      efficiency_store=0.87,
      efficiency_dispatch=0.87,
      cyclic_state_of_charge=True,
      max_hours=8)
# kein inflow nötig

n.add("StorageUnit", "Reservoir_DE",
      bus="DE",
      p_nom=res_pnom,
      marginal_cost=0.0,
      carrier="hydro",
      cyclic_state_of_charge=True,
      max_hours=168)  # ~1 Woche, für Reservoir eher größer ansetzen

n.storage_units_t.inflow["Reservoir_DE"] = res_inflow_mw

# ── Last ──────────────────────────────────────
n.add("Load", "Load_DE",
      bus="DE",
      p_set=load_ts)

print("\n── Debug: Kapazitäten ──")
print(n.generators[["p_nom", "marginal_cost"]])
print(n.storage_units[["p_nom", "max_hours", "cyclic_state_of_charge"]])
print(f"\nInflow Reservoir Max: {n.storage_units_t.inflow['Reservoir_DE'].max():.1f} MW")
print(f"Inflow PSOpen Max:    {n.storage_units_t.inflow['PSOpen_DE'].max():.1f} MW")
print(f"Last Max:            {load_ts.max():.1f} MW")
print(f"Gen Kapazität Total: {n.generators.p_nom.sum():.1f} MW")

# ─────────────────────────────────────────────
# OPTIMIERUNG
# ─────────────────────────────────────────────
print("\nStarte Optimierung mit Gurobi (8760h, perfect foresight)...")
print(f"Snapshots: {len(n.snapshots)}")
print(f"Generatoren: {len(n.generators)}")

status, condition = n.optimize(
    solver_name="gurobi",
    include_objective_constant=False,
    solver_options={
        "Method"     : 2,   # Barrier (schnellste für große LP)
        "Crossover"  : 0,   # Kein Crossover nötig für LMP
        "Threads"    : 4,   # Nutze mehrere Threads für schnellere Lösung
        "BarConvTol" : 1e-6,# Strengerer Konvergenztoleranz für genauere LMPs
        "DualReductions": 0,  # ← NEU: trennt infeasible von unbounded
    }
)

if status != "ok":
    print(f"Optimierung fehlgeschlagen! Status: {status}, Bedingung: {condition}")
    sys.exit(1)

print(f"Optimierung erfolgreich beendet (Status: {status})")

# ─────────────────────────────────────────────
# ERGEBNISSE
# ─────────────────────────────────────────────
lmp = n.buses_t.marginal_price["DE"]

print(f"\n── Preiszeitreihe Deutschland (Klimajahr {CLIMATE_YEAR}) ──")
print(f"Jahres-Ø:  {lmp.mean():.2f} €/MWh")
print(f"Median:    {lmp.median():.2f} €/MWh")
print(f"Std:       {lmp.std():.2f} €/MWh")
print(f"p85:       {lmp.quantile(0.85):.2f} €/MWh")
print(f"p95:       {lmp.quantile(0.95):.2f} €/MWh")

print("\n── Erzeugung je Technologie (GWh/Jahr) ──")
for gen in n.generators.index:
    gwh = n.generators_t.p[gen].sum() / 1000
    print(f"  {gen:20s}: {gwh:8.1f} GWh")

# Speichern
lmp.to_csv("04_results/lmp_DE_2030.csv", header=["price_EUR_MWh"])
n.generators_t.p.to_csv("04_results/dispatch_DE_2030.csv")
print("\nErgebnisse gespeichert in 04_results/")

n.consistency_check()