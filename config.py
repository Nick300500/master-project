"""
config.py
=========
Zentrale Stellschrauben des Modells. Alle Skripte in main/, pipeline/ und
analysis/ lesen ihre Einstellungen von hier.

Aufbau:
  1. Pfade
  2. Zieljahr und Zonen
  3. Simulationslauf (Wetterjahre, Szenario-Defaults, Solver)
  4. Wirtschaftliche Parameter (CO2, Brennstoffe, VOLL, ...)
  5. Technische Parameter (Wirkungsgrade, Speicher, Leitungen)
  6. Datenformat (nur anfassen, wenn sich die ERAA-Ordnerstruktur ändert)

Die Werte unter "Szenario-Defaults" lassen sich pro Lauf auch über
Kommandozeilen-Flags von main/run_simulation.py überschreiben (siehe
`python main/run_simulation.py --help`); alles andere wird nur hier geändert.
"""

from pathlib import Path

# ════════════════════════════════════════════════════════════════════════════
# 1. Pfade
# ════════════════════════════════════════════════════════════════════════════
PROJECT_ROOT = Path(__file__).resolve().parent

# Datenordner. Darf auch außerhalb des Projekts liegen, z.B.
# DATA_DIR = Path(r"D:\ERAA 2022")
DATA_DIR = PROJECT_ROOT / "01_data"
# ERAA-Excel-Dateien, unverändert entpackt (Eingang der Datenaufbereitung)
RAW_DIR = DATA_DIR / "01_raw"
# Eine CSV pro Excel-Reiter
PROCESSED_DIR = DATA_DIR / "02_processed"
# Nur die Dateien des Zieljahrs
FILTERED_DIR = DATA_DIR / "03_filtered_data_for_prediction_year"
# Aggregiert je Modellzone: die EINZIGE Eingabe des Modells
ACCUMULATED_DIR = DATA_DIR / "04b_accumulated_data_per_node"
# Selbst erstellte NTC-Tabelle mit den Paper-Werten (für --interconnections paper), liegt im Repo
PAPER_NTC_CSV = PROJECT_ROOT / "inputs" / "NTC_Vergleich_ERAA_Paper_Modell.csv"

RESULTS_DIR = PROJECT_ROOT / "04_results"
LOG_FILE = PROJECT_ROOT / "batch_simulation.log"


# ════════════════════════════════════════════════════════════════════════════
# 2. Zieljahr und Zonen
# ════════════════════════════════════════════════════════════════════════════
# Zieljahr (ERAA "Target Year"): bestimmt, welche Kapazitäten, Nachfrage- und
# Leitungsdaten verwendet werden. Getestet ist nur 2030; die fest gesetzten
# Paper-Werte in Abschnitt 4 gelten ebenfalls für 2030. Nach einer Änderung
# muss die Datenaufbereitung (main/prepare_data.py) neu laufen.
TARGET_YEAR = 2030

# Länder, die zu einer Modellzone zusammengefasst werden. Gilt für die gesamte
# Datenaufbereitung (Zeitreihen, Kapazitäten, Leitungen) und für die
# Länder-Import/Export-Grenzen im Modell. Nicht aufgeführte Länder bleiben
# eigene Zonen (Ländercode, z.B. "DE").
# Nach einer Änderung muss die Datenaufbereitung neu laufen.
ZONE_GROUPS = {
    "adriatic": ["AL", "BA", "HR", "ME", "MK", "RS", "SI"],
    "baltic": ["EE", "LV", "LT"],
    "other eastern european": ["BG", "HU", "RO", "SK"],
}

# Zonen, die im Modell simuliert werden (Busse im PyPSA-Netz). Leitungen
# werden nur zwischen aktiven Zonen angelegt. Zum schnellen Testen z.B.
# ["DE"] oder ["DE", "FR", "NO"].
ACTIVE_ZONES = [
    "DE", "FR", "AT", "CH", "NL", "BE", "CZ", "PL", "DK", "SE", "NO", "FI",
    "adriatic", "baltic", "ES", "PT", "IT", "GR", "UK", "IE",
    "other eastern european",
]


# ════════════════════════════════════════════════════════════════════════════
# 3. Simulationslauf
# ════════════════════════════════════════════════════════════════════════════
# Wetterjahre, die in den ERAA-2022-Zeitreihen vorhanden sind.
CLIMATE_YEARS_AVAILABLE = (1982, 2017)

# Ohne --years zieht run_simulation.py zufällige Wetterjahre:
RANDOM_YEARS_COUNT = 10            # --random N
RANDOM_YEARS_RANGE = (1982, 2015)  # --year-range MIN MAX

# ── Szenario-Defaults (per CLI-Flag überschreibbar) ─────────────────────────
# Quelle der Leitungskapazitäten: "eraa" (ERAA-Daten) oder "paper" (PAPER_NTC_CSV)
INTERCONNECTIONS = "eraa"
# Zusätzliche Wochen-Nebenbedingungen für die norwegische Speicherwasserkraft:
# "off", "flow" (Wochen-Erzeugung min/max) oder "flow+level" (zusätzlich
# Wochen-Füllstände min/max)
NO_HYDRO_FIX = "off"
# Länder-Import/Export-Obergrenzen aus ERAA ("Max limit.csv") erzwingen
ENFORCE_MAX_LIMITS = True

# ── Solver ──────────────────────────────────────────────────────────────────
SOLVER_NAME = "gurobi"
SOLVER_OPTIONS = {
    "Method": 2,          # Barrier
    "Crossover": 0,       # kein Crossover (schneller, Preise bleiben genau genug)
    "Threads": 8,         # --threads
    "BarConvTol": 1e-5,   # --bar-conv-tol
    "DualReductions": 0,
}


# ════════════════════════════════════════════════════════════════════════════
# 4. Wirtschaftliche Parameter
# ════════════════════════════════════════════════════════════════════════════
# Die meisten Brennstoffpreise, Wirkungsgrade und VOM-Kosten werden aus den
# ERAA-Dateien unter ACCUMULATED_DIR/"Additional Data" gelesen. Die Werte hier
# ÜBERSCHREIBEN die ERAA-Werte. Sie sind auf die im Paper bestätigten Werte
# gesetzt (siehe docs/MODEL_DOCUMENTATION_FOR_PAPER_COMPARISON.md).

# CO2-Preis in €/t (ERAA-Datei wird ignoriert)
CO2_PRICE_EUR_PER_T = 100.0

# Value of Lost Load: Grenzkosten des Lastabwurfs in €/MWh
VOLL_EUR_PER_MWH = 3000.0

# Feste Brennstoffpreise in €/GJ (überschreiben ERAA).
# Schlüssel: "nuclear", "lignite", "hard_coal", "gas", "light_oil", "heavy_oil".
# Beispiel für eine Gaspreis-Sensitivität: {"lignite": 3.1, "gas": 10.0}
FUEL_PRICE_OVERRIDES_EUR_PER_GJ = {
    "lignite": 3.1,
}

# Feste Wirkungsgrade (0-1, überschreiben ERAA).
# Schlüssel: "ccgt", "ocgt", "lignite", "hard_coal", "oil", "nuclear".
EFFICIENCY_OVERRIDES = {
    "ccgt": 0.49,
}

# Feste variable Betriebskosten in €/MWh_el (überschreiben ERAA).
# Schlüssel wie bei EFFICIENCY_OVERRIDES.
VOM_OVERRIDES_EUR_PER_MWH = {
    "ccgt": 2.11,
}

# Grenzkosten Biomasse (inkl. "Others renewable") in €/MWh_el
BIOMASS_MARGINAL_COST_EUR_PER_MWH = 30.0


# ════════════════════════════════════════════════════════════════════════════
# 5. Technische Parameter
# ════════════════════════════════════════════════════════════════════════════
# Wasserkraft (ERAA 2022)
HYDRO_EFFICIENCY_DISPATCH = 0.87   # Turbine, alle Hydro-Speicher
HYDRO_EFFICIENCY_STORE = 0.87      # Pumpen, nur Pumpspeicher (Open/Closed Loop)
RESERVOIR_EFFICIENCY_STORE = 1.0   # Speicherseen stauen Zufluss verlustfrei

# Batterien
BATTERY_EFFICIENCY_STORE = 0.92
BATTERY_EFFICIENCY_DISPATCH = 0.92

# Speicherdauer in Stunden, falls ERAA für einen Speicher keine
# Energiekapazität (MWh) liefert
STORAGE_MAX_HOURS_FALLBACK = 8.0

# Übertragungswirkungsgrad der ERAA-Leitungen (1.0 = verlustfrei, wie im Paper)
LINK_EFFICIENCY = 1.0

# NO-Hydro-Fix: welche Füllstandsgrenzen aus den PEMMDB-Dateien gelten
# ("historical" oder "technical"). Nur relevant bei NO_HYDRO_FIX = "flow+level".
NO_HYDRO_RESERVOIR_BOUNDS = "historical"


# ════════════════════════════════════════════════════════════════════════════
# 6. Datenformat
# ════════════════════════════════════════════════════════════════════════════
# Ordnername der ERAA-Kapazitätsdaten (so wie er aus dem ERAA-ZIP kommt)
NATIONAL_ESTIMATES_DIRNAME = "ERAA 2022 PEMMDB National Estimates"
