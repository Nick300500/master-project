# Robustness of European Electricity Price Stability Estimates

**A PyPSA-based replication and sensitivity analysis** of

> Navia Simon & Diaz Anadon, *Power price stability and the insurance value of renewable technologies*,
> Nature Energy (2025), <https://doi.org/10.1038/s41560-025-01704-0>

Das Paper simuliert den europäischen Strommarkt 2030 mit GenX. Dieses Repo baut denselben
Marktausschnitt mit **PyPSA** auf Basis derselben Eingangsdaten (ENTSO-E **ERAA 2022**) nach und
vergleicht die Ergebnisse mit dem Paper.

## Was das Modell macht (in 5 Zeilen)

```
ERAA-2022-Rohdaten (Excel) → CSV-Aufbereitung (Skripte 01–06) → Zwischenformat pro Zone (01_data/04b_…)
        → PyPSA-Netz (21 Zonen, ein Jahr = 8.760 h) → Optimierung mit Gurobi → Preise, Erzeugung, Flüsse
```

Ein Lauf simuliert **ein historisches Wetterjahr** (1982–2017 verfügbar) für das Stromsystem **2030**
und minimiert die Gesamtkosten des Dispatches. Der Strompreis einer Zone und Stunde ist der
Schattenpreis der Energiebilanz. Details, Annahmen und Grenzen: siehe `docs/` (Abschnitt 6).

## 1. Voraussetzungen

- **Python 3.12** (getestet mit 3.12.10)
- **Gurobi** mit gültiger Lizenz. Eine kostenlose Academic License genügt
  (<https://www.gurobi.com/academia/academic-program-and-licenses/>). Das Modell ruft fest
  `solver_name="gurobi"` auf, ein freier Solver (HiGHS) ist nicht eingebunden.
- Mehrere GB freier Speicher für Daten und Ergebnisse und ausreichend Arbeitsspeicher für einen
  21-Zonen-Lauf (Barrier-Verfahren).

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt   # enthält auch gurobipy
grbgetkey <dein-lizenzschlüssel>  # einmalig, Lizenz aktivieren
python -c "import gurobipy; gurobipy.Model()"   # Test: darf keinen Fehler melden
```

## 2. Daten beschaffen (nicht im Repo)

`01_data/` ist per `.gitignore` ausgeschlossen (mehrere GB). Es gibt zwei Wege:

**a) Fertiges Zwischenformat (`01_data/04b_accumulated_data_per_node/`) vom Projektbesitzer erhalten**
und in das Repo legen. Dann kann direkt mit Abschnitt 4 gestartet werden.

**b) Selbst aus den ERAA-2022-Rohdaten erzeugen.** Quelle: ENTSO-E,
<https://www.entsoe.eu/eraa/2022/modelling-data/>. Benötigt werden die Pakete
*PEMMDB National Estimates*, *Demand Dataset*, *NTC*, *Climate Data* und *Additional Data*.
Die ZIPs entpacken und **mit unveränderter Ordnerstruktur** unter
`01_data/01_raw/ERAA_excel_files/` ablegen. Danach die Kette in Abschnitt 3 ausführen.

> Wichtig: Verwendet wird **ERAA 2022**. Neuere ERAA-Jahrgänge (2023–2026) haben ein anderes
> Dateiformat und laufen **nicht** durch diese Kette, siehe `docs/ERAA_INPUT_DATA_COMPARISON.md`.

## 3. Datenaufbereitung (Excel → Zwischenformat)

Alle Befehle **aus dem Projekt-Root** ausführen (die Pfade sind relativ). Die Reihenfolge ist
verbindlich, einzelne Schritte hängen an den Ausgaben der vorherigen:

| # | Befehl (`python 02_models/skripts/…`) | Was passiert |
|---|---|---|
| 1 | `01_excel_to_csv.py` | Jede Excel-Datei wird in eine CSV pro Reiter zerlegt → `01_data/02_processed/` |
| 2 | `01b_restructure_hydro_inflows.py` | Hydro-Inflow-Dateien nach Technologie sortiert (einmalig, **löscht** danach den Quellordner) |
| 3 | `02b_filter_csvs.py --year 2030` | Nur die Dateien des Zieljahrs → `01_data/03_filtered_data_for_prediction_year/` |
| 4 | `05_transpond TY{year}_csv.py --year 2030` | Kapazitätstabelle `TY 2030.csv` so drehen, dass Zonen in den Zeilen stehen. **Muss vor Schritt 5 und 9 laufen** (liefert die Gewichte für Wind/Solar) |
| 5 | `03_climate_accumulate_data_per_node.py` | Wind/Solar/Hydro je Zone; Länder werden zu `adriatic`, `baltic`, `other eastern european` zusammengefasst (Wind/Solar kapazitätsgewichtet, sonst Summe) |
| 6 | `03_demand_accumulate_data_per_node.py` | Dasselbe für Demand. Kopiert außerdem `Additional Data` und `Transfer capacities` nach 04b. **Muss vor Schritt 8 laufen**, sonst überschreibt die Rohkopie die aggregierten Leitungsdaten |
| 7 | `03_b_add_years_to_hydro.py` | Setzt die Klimajahre 1982–2017 in die Spaltenköpfe der Hydro-Dateien |
| 8 | `04_accumulate_interconnections.py` | Leitungskapazitäten (HVAC/HVDC) je Zonenpaar aggregieren, interne Leitungen entfernen |
| 9 | `06_filter_and_accu_PEMMCD_National_Estimates.py --year 2030` | Installierte Kapazitäten, DSR etc. je Zone → `…/04b_…/ERAA 2022 PEMMDB National Estimates/` |

Ergebnis ist `01_data/04b_accumulated_data_per_node/`. Es ist die **einzige** Eingabe des Modells.

**Verifikationsstand der Kette** (bei der Übergabe geprüft): Die Schritte 1 → 3 → 5 (Hydro) → 7 → 8
wurden aus den vorhandenen Rohdaten (Transfer Capacities 2030, Hydro) neu erzeugt und mit den
vorhandenen 04b-Daten verglichen: identisch. Die übrigen Schritte (2, 4, 6, 9 sowie Wind/Solar in Schritt 5)
konnten ohne die Rohdaten nicht neu nachgefahren werden und sind nur durch den vorhandenen 04b-Bestand belegt.
Bekannter Rohdatenfehler: In `HVDC` (TY2030) ist die Verbindung Finnland–Estland doppelt in gleicher Richtung
beschriftet; Skript 04 korrigiert das automatisch (Warnung im Log).

## 4. Simulation starten

Einziger Einstiegspunkt: `02_models/skripts/run_batch_simulation.py`.

```bash
# 1 Wetterjahr, alle 21 Zonen, ERAA-Leitungskapazitäten
python 02_models/skripts/run_batch_simulation.py --years 2012

# 10 zufällige, noch nicht simulierte Wetterjahre aus 1982–2015 (Standard ohne Argumente)
python 02_models/skripts/run_batch_simulation.py

# Paper-NTC-Werte statt ERAA-Werten, plus Norwegen-Hydro-Korrektur
python 02_models/skripts/run_batch_simulation.py --years 2003 --interconnections paper --no-hydro-fix flow+level
```

| Option | Bedeutung |
|---|---|
| `--years 2011 2012 …` | feste Liste von Wetterjahren (sonst zufällig) |
| `--random N`, `--year-range MIN MAX` | N zufällige Jahre aus dem Bereich (Default 10, 1982–2015) |
| `--skip-existing` / `--no-skip-existing` | bereits berechnete Jahre überspringen (Default: an) |
| `--interconnections {eraa,paper}` | Leitungskapazitäten aus ERAA oder aus der Paper-Tabelle |
| `--no-hydro-fix {off,flow,flow+level}` | zusätzliche Wochen-Nebenbedingungen für norwegische Speicherwasserkraft |
| `--max-limits` / `--no-max-limits` | Länder-Obergrenzen für Import/Export (Default: an) |
| `--suffix TEXT` | Suffix für den Ergebnisordner (sonst automatisch) |
| `--bar-conv-tol`, `--threads` | Gurobi-Einstellungen |

**Ergebnisse** liegen in `04_results/<Zonen>_CY<Jahr><Suffix>/` (nicht im Git): Preiszeitreihen
(`prices_lmp.csv`), Erzeugung je Kraftwerk, Speicherfüllstände, Leitungsflüsse, Kapazitäten und
`summary_annual.csv` (Mittelwert/Median/95 %-Quantil der Preise, Lastabwurf). Das Log steht in
`batch_simulation.log`.

Nachbearbeitung/Analyse: `99_marginal_costs.py`, `plot_merit_order_DE.py`,
`100_germany_network_analysis.py` (Einzelzonen-Check). Sie lesen aus `04_results/`.

## 5. Projektstruktur

```
02_models/skripts/
  01…06_*.py                    Datenaufbereitung (Abschnitt 3)
  gather_global_params.py       Brennstoffpreise, Wirkungsgrade, CO2, Grenzkosten
  load_zone_capacities.py       installierte Kapazitäten je Zone
  load_timeseries.py            Wind/Solar/Hydro/Last-Zeitreihen je Zone und Wetterjahr
  build_network.py              PyPSA-Netz aufbauen (Busse, Kraftwerke, Speicher, DSR, Last)
  add_interconnections.py       Leitungen (ERAA) + Ergebnis-Export
  paper_interconnections.py     Leitungen aus der Paper-Tabelle
  add_max_limits.py             Länder-Import/Export-Obergrenzen (Nebenbedingung)
  no_hydro_fix.py               optionale Norwegen-Hydro-Nebenbedingungen
  run_batch_simulation.py       Einstiegspunkt (CLI)
docs/                           Modelldokumentation, ERAA-Formatvergleich, Arbeitsprotokoll
01_data/                        Daten (nicht im Repo, siehe Abschnitt 2)
04_results/                     Ergebnisse (nicht im Repo)
```

## 6. Dokumentation

- `docs/MODEL_DOCUMENTATION_FOR_PAPER_COMPARISON.md`: vollständige Beschreibung aller Eingaben, Annahmen
  und Vereinfachungen. Startpunkt zum Verständnis des Modells.
- `docs/ERAA_INPUT_DATA_COMPARISON.md`: warum nur ERAA 2022 funktioniert.
- `docs/CLEANUP_PLAN.md`: Protokoll der Aufräumarbeiten.

## 7. Bekannte Einschränkungen

- Es variiert nur das **Wetterjahr**. Brennstoffpreise, CO₂-Preis und Nachfrage sind fest (das Paper zieht
  sie zusätzlich per Monte-Carlo).
- Kein Unit Commitment, keine Rampen, keine Reserven, keine Verluste, kein Netzausbau.
- Die Kapazitäten sind fest auf das Zieljahr **2030** ausgelegt (`load_zone_capacities.py`).
- Einige Parameter sind bewusst auf Paper-Werte festgesetzt (CO₂-Preis 100 €/t, CCGT-Wirkungsgrad 49 %,
  Braunkohlepreis, VOLL 3.000 €/MWh) statt aus den CSV-Dateien gelesen, siehe Modelldokumentation.
