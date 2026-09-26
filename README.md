# Robustness of European Electricity Price Stability Estimates

**A PyPSA-based replication and sensitivity analysis** of

> Navia Simon & Diaz Anadon, *Power price stability and the insurance value of renewable technologies*,
> Nature Energy (2025), <https://doi.org/10.1038/s41560-025-01704-0>

Das Paper simuliert den europäischen Strommarkt 2030 mit GenX. Dieses Repo baut denselben
Marktausschnitt mit **PyPSA** auf Basis derselben Eingangsdaten (ENTSO-E **ERAA 2022**) nach.

Ein Lauf simuliert **ein historisches Wetterjahr** (1982–2017) für das Stromsystem **2030**:
21 Marktzonen, 8.760 Stunden, kostenminimaler Kraftwerkseinsatz mit Gurobi. Der Strompreis einer
Zone und Stunde ist der Schattenpreis der Energiebilanz.

```
ERAA-2022-Excel  ──main/prepare_data.py──▶  01_data/04b_…  ──main/run_simulation.py──▶  04_results/
 (Rohdaten)            (10 Schritte)         (Zwischenformat)     (PyPSA + Gurobi)        (Preise, Erzeugung, …)
```

---

## Inhalt

1. [Ablauf im Überblick](#1-ablauf-im-überblick)
2. [Installation](#2-installation)
3. [ERAA-Rohdaten herunterladen und ablegen](#3-eraa-rohdaten-herunterladen-und-ablegen)
4. [Datenaufbereitung](#4-datenaufbereitung)
5. [Simulation starten](#5-simulation-starten)
6. [Stellschrauben](#6-stellschrauben)
7. [Ergebnisse und Auswertung](#7-ergebnisse-und-auswertung)
8. [Projektstruktur](#8-projektstruktur)
9. [Bekannte Einschränkungen und weitere Doku](#9-bekannte-einschränkungen-und-weitere-doku)

---

## 1. Ablauf im Überblick

Vom Download bis zum Ergebnis sind es vier Schritte. Alle Befehle werden **aus dem Projekt-Root**
ausgeführt.

| # | Was | Wie | Dauer |
|---|---|---|---|
| 1 | Installation (Python-Pakete, Gurobi-Lizenz) | [Abschnitt 2](#2-installation) | einmalig |
| 2 | ERAA-2022-Rohdaten herunterladen, entpacken, Pfad in `config.py` eintragen | [Abschnitt 3](#3-eraa-rohdaten-herunterladen-und-ablegen) | einmalig |
| 3 | Rohdaten in das Zwischenformat je Modellzone überführen | `python main/prepare_data.py` | einmalig, lange (Excel-Konvertierung) |
| 4 | Netz bauen und optimieren, ein Lauf je Wetterjahr | `python main/run_simulation.py --years 2012` | 2–3 h je Wetterjahr |

Schritt 3 muss nur erneut laufen, wenn sich die Rohdaten, `TARGET_YEAR` oder `ZONE_GROUPS` ändern.
Danach kann beliebig oft simuliert werden.

> **Abkürzung:** Wer den fertigen Ordner `04b_accumulated_data_per_node/` (Ergebnis von Schritt 3)
> von jemandem bekommt, kann Schritte 2 und 3 überspringen: Ordner nach `01_data/` legen (bzw. nach
> `DATA_DIR` aus `config.py`) und direkt mit Abschnitt 5 starten.

**Erster Test:** Vor dem ersten vollen Lauf in `config.py` `ACTIVE_ZONES = ["DE", "NO"]` setzen und
`python main/run_simulation.py --years 2012` starten. Das dauert etwa eine Minute und zeigt, ob Daten,
Pfade und Gurobi funktionieren. Danach `ACTIVE_ZONES` wieder zurückstellen.

---

## 2. Installation

**Voraussetzungen**

- **Python 3.12** (getestet mit 3.12.10)
- **Gurobi** mit gültiger Lizenz. Eine kostenlose Academic License genügt
  (<https://www.gurobi.com/academia/academic-program-and-licenses/>). Nur Gurobi ist getestet.
- Genug Arbeitsspeicher: Ein Lauf mit allen 21 Zonen braucht rund 5 GB RAM.

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt   # enthält auch gurobipy und pypsa
grbgetkey <dein-lizenzschlüssel>  # einmalig, Lizenz aktivieren
python -c "import gurobipy; gurobipy.Model()"   # Test: darf keinen Fehler melden
```

---

## 3. ERAA-Rohdaten herunterladen und ablegen

**Herunterladen.** ENTSO-E, <https://www.entsoe.eu/eraa/2022/modelling-data/>. Benötigt werden fünf
Pakete (zusammen rund 5 GB):

| Paket | Format |
|---|---|
| PEMMDB National Estimates | xlsx |
| Climate Data | zip, ~2 GB |
| Demand Dataset | zip, ~2 GB |
| NTC | zip |
| Additional Data | zip |

> Verwendet wird **ERAA 2022**. Neuere Jahrgänge (2023–2026) haben ein anderes Dateiformat und laufen
> nicht durch diese Kette, siehe `docs/ERAA_INPUT_DATA_COMPARISON.md`.

**Ablegen.** Alles **mit unveränderter Ordnerstruktur** in den Rohdatenordner `RAW_DIR` entpacken
(Standard: `01_data/01_raw/`). In *Climate Data* steckt `Hydro Inflows.zip` als
weiteres Zip, das ebenfalls entpackt werden muss. Danach sollte es so aussehen:

```
<RAW_DIR>/
  ERAA 2022 PEMMDB National Estimates.xlsx
  Additional Data/Annex 1 - Input data/        Fuel cost.xlsx, Efficiency.xlsx, VOM.xlsx, …
  Climate Data/Hydro Inflows/                  PEMMDB_<Zone>_Hydro Inflow_<Jahr>.xlsx
  Climate Data/Solar/, Wind onshore/, Wind offshore/, PECD_CSP/
  Demand/Demand Time Series/                   Demand_TimeSeries_<Jahr>_NationalTrends_without_bat.xlsx
  Transfer capacities/                         Transfer Capacities_ERAA2022_TY<Jahr>.xlsx
```

**Speicherort.** Die Aufbereitung schreibt noch mehrere GB Zwischendaten neben die Rohdaten
(`02_processed/`, `03_filtered…/`, `04b…/`). Das Projekt sollte deshalb nicht in einem
Cloud-synchronisierten Ordner (OneDrive o.ä.) liegen. Die Daten dürfen auch außerhalb des Projekts
liegen, dann in `config.py` z.B. `DATA_DIR = Path(r"D:\ERAA 2022")` setzen; die Rohdaten gehören
dort nach `01_raw/`.

**Tipp: nur das Zieljahr behalten.** Die Pakete enthalten jede Datei für die Zieljahre 2024, 2025,
2027 und 2030 (zusammen ~7 GB). Die Excel-Konvertierung ist der mit Abstand langsamste Schritt und
würde alles umwandeln, obwohl nur `TARGET_YEAR` gebraucht wird. Die übrigen Jahre vorher auslagern
spart etwa drei Viertel der Zeit (PowerShell, im Datenordner):

```powershell
New-Item -ItemType Directory -Force "andere_Zieljahre"
Get-ChildItem -Recurse "01_raw" -Include *2024*,*2025*,*2027* -File | Move-Item -Destination "andere_Zieljahre"
```

**Paper-Leitungskapazitäten.** Im Repo enthalten ist `inputs/NTC_Vergleich_ERAA_Paper_Modell.csv`,
eine selbst erstellte Tabelle der Leitungskapazitäten je Grenze: ERAA-Wert (aggregiert, HVAC + HVDC),
Wert laut Paper-Supplement und Begründung der Abweichung. Sie wird für `--interconnections paper`
verwendet (Spalte „Paper“) und muss nicht heruntergeladen werden.

---

## 4. Datenaufbereitung

```bash
python main/prepare_data.py                                # alle 10 Schritte
python main/prepare_data.py --list                         # Schritte anzeigen
python main/prepare_data.py --only excel_to_csv            # nur einen Schritt
python main/prepare_data.py --from aggregate_climate_data  # ab einem Schritt weitermachen
python main/prepare_data.py --force                        # Excel neu konvertieren statt vorhandene CSVs zu nutzen
```

Die Schritte liegen in `pipeline/data_preparation/` und laufen in dieser Reihenfolge (jeder liest die
Ausgabe der vorherigen). Alle Ausgabeordner liegen in `DATA_DIR`:

| # | Schritt | Was passiert | Ausgabe |
|---|---|---|---|
| 1 | `excel_to_csv` | jede Excel-Datei → eine CSV pro Reiter | `02_processed/` |
| 2 | `sort_hydro_inflows` | Hydro-Inflows nach Technologie statt nach Zone ordnen | `02_processed/` |
| 3 | `filter_target_year` | nur Dateien des Zieljahrs übernehmen | `03_filtered_data_for_prediction_year/` |
| 4 | `transpose_capacity_table` | Kapazitätstabelle `TY 2030.csv` drehen (Zonen als Zeilen). Liefert die Gewichte für Schritt 5 | `03_filtered_…/` |
| 5 | `aggregate_climate_data` | Wind/Solar (leistungsgewichtet gemittelt) und Hydro (summiert) je Modellzone | `04b_…/Climate Data/` |
| 6 | `aggregate_demand_data` | Last je Modellzone summieren; kopiert außerdem `Additional Data` und `Transfer capacities` | `04b_…/Demand/` u.a. |
| 7 | `label_hydro_climate_years` | Klimajahre 1982–2017 in die Spaltenköpfe der Hydro-Dateien schreiben | `04b_…/` |
| 8 | `aggregate_interconnections` | Leitungen (HVAC/HVDC) je Zonenpaar summieren, zoneninterne entfernen. Muss nach 6 laufen | `04b_…/Transfer capacities/` |
| 9 | `aggregate_national_estimates` | installierte Kapazitäten, DSR etc. je Modellzone | `04b_…/ERAA 2022 PEMMDB National Estimates/` |
| 10 | `copy_no_hydro_files` | die drei norwegischen PEMMDB-Hydro-Dateien (NOM1/NON1/NOS0) für den NO-Hydro-Fix kopieren | `04b_…/Climate Data/Hydro Inflows/NO constraint approach/` |

Ergebnis ist `04b_accumulated_data_per_node/`, die einzige Eingabe der Simulation. Bricht ein Schritt
ab, lässt er sich nach der Korrektur mit `--from <schritt>` fortsetzen; die Excel-Konvertierung
überspringt bereits vorhandene CSVs.

**Platz sparen.** Nach einem vollständigen Durchlauf wird nur noch `04b_accumulated_data_per_node/`
gebraucht (plus `01_raw/`, falls man später neu aufbereiten will). `02_processed/` und
`03_filtered_data_for_prediction_year/` sind reine Zwischenstände und können gelöscht werden; sie
entstehen bei einem erneuten `prepare_data.py`-Lauf wieder (Schritt 1 dauert dann erneut ca. 25 min).

**Verifikationsstand.** Die Kette wurde aus Rohdaten neu gefahren und mit dem bisher verwendeten
04b-Bestand verglichen: Transfer Capacities identisch (HVDC bis auf eine Rundung von 0,000005 MW),
Norwegen-Hydro-Dateien byte-identisch. Bekannter Rohdatenfehler: In HVDC (TY2030) ist
Finnland–Estland doppelt in gleicher Richtung beschriftet; Schritt 8 korrigiert das automatisch
(Warnung im Log).

---

## 5. Simulation starten

Einziger Einstiegspunkt: **`main/run_simulation.py`**. Er baut aus `04b_accumulated_data_per_node/`
das PyPSA-Netz, optimiert es mit Gurobi und speichert die Ergebnisse. Jedes Wetterjahr ist ein
eigener Lauf mit eigenem Ergebnisordner.

```bash
# ein oder mehrere feste Wetterjahre
python main/run_simulation.py --years 2012
python main/run_simulation.py --years 2003 2006 2011

# ohne --years: 10 zufällige, noch nicht simulierte Jahre aus 1982–2015
python main/run_simulation.py
python main/run_simulation.py --random 5 --year-range 1990 2010

# Szenario wie im Paper: Paper-Leitungskapazitäten + Norwegen-Hydro-Korrektur
python main/run_simulation.py --years 2003 --interconnections paper --no-hydro-fix flow+level

# alle Optionen
python main/run_simulation.py --help
```

| Flag | Bedeutung | Default (aus `config.py`) |
|---|---|---|
| `--years Y1 Y2 …` | feste Liste von Wetterjahren (1982–2017) | – |
| `--random N` | N zufällige Wetterjahre ziehen | `RANDOM_YEARS_COUNT` = 10 |
| `--year-range MIN MAX` | Bereich für `--random` | `RANDOM_YEARS_RANGE` = 1982 2015 |
| `--skip-existing` / `--no-skip-existing` | bei `--random` schon berechnete Jahre überspringen | an |
| `--interconnections {eraa,paper}` | Leitungskapazitäten aus ERAA oder aus der Paper-Tabelle | `INTERCONNECTIONS` = eraa |
| `--no-hydro-fix {off,flow,flow+level}` | Wochen-Nebenbedingungen für Norwegens Speicherwasserkraft (siehe unten) | `NO_HYDRO_FIX` = off |
| `--max-limits` / `--no-max-limits` | Länder-Obergrenzen für Gesamtimport/-export | `ENFORCE_MAX_LIMITS` = an |
| `--suffix TEXT` | Zusatz am Ergebnisordner-Namen | automatisch aus den Szenario-Flags, z.B. `_paperNTC_NO_hydro_fix_full` |
| `--bar-conv-tol`, `--threads` | Gurobi-Einstellungen | `SOLVER_OPTIONS` |

**Was die Szenario-Optionen bedeuten**

- **`--interconnections paper`**: Statt der ERAA-Leitungskapazitäten (Jahresmittel aus HVAC + HVDC)
  werden die im Paper genannten Werte verwendet. Für den direkten Vergleich mit dem Paper.
- **`--no-hydro-fix`**: ERAA führt die gesamte norwegische Speicherwasserkraft als einen großen
  Pumpspeicher (`PSOpen_NO`). Ohne Zusatzbedingung kann das Modell diesen Speicher unrealistisch
  frei bewirtschaften. `flow` begrenzt die wöchentliche Erzeugung auf die ERAA-Minima/-Maxima,
  `flow+level` begrenzt zusätzlich den Füllstand am Ende jeder Woche. Dazu werden zwei Check-Dateien
  in den Ergebnisordner geschrieben (`NO_hydro_fix_*_check_NO.csv`).
- **`--max-limits`**: ERAA liefert für einige Engpassländer (u.a. CH, CZ, UK, Adriatic) eine
  Obergrenze für die Summe aller Importe bzw. Exporte. Sie gilt zusätzlich zu den einzelnen Leitungen.

Ein Lauf mit allen Zonen dauert erfahrungsgemäß 2–3 Stunden pro Wetterjahr. Das Log läuft in der
Konsole mit und wird in `batch_simulation.log` gespeichert. Scheitert ein Jahr, läuft der Batch mit
dem nächsten weiter; die Zusammenfassung am Ende zeigt `OK`/`FEHLER` je Jahr.

---

## 6. Stellschrauben

**Alle Modellparameter stehen in [`config.py`](config.py)** im Projekt-Root, gruppiert und
kommentiert. Die Skripte lesen nur von dort. Die Szenario-Defaults lassen sich zusätzlich pro Lauf
über die Flags aus Abschnitt 5 überschreiben. Alles andere wird nur in `config.py` geändert.

### 6.1 Übersicht `config.py`

| Parameter | Wert | Wirkung | Neue Datenaufbereitung nötig? |
|---|---|---|---|
| **Zieljahr und Zonen** | | | |
| `TARGET_YEAR` | 2030 | ERAA-Zieljahr für Kapazitäten, Nachfrage, Leitungen. Nur 2030 getestet. | **ja** |
| `ZONE_GROUPS` | adriatic, baltic, other eastern european | welche Länder zu einer Modellzone zusammengefasst werden | **ja** |
| `ACTIVE_ZONES` | 21 Zonen | welche Zonen simuliert werden. Zum Testen z.B. `["DE", "NO"]` | nein |
| **Simulationslauf** | | | |
| `RANDOM_YEARS_COUNT`, `RANDOM_YEARS_RANGE` | 10, (1982, 2015) | Zufallsauswahl der Wetterjahre ohne `--years` | nein |
| `INTERCONNECTIONS` | `"eraa"` | Default für `--interconnections` | nein |
| `NO_HYDRO_FIX` | `"off"` | Default für `--no-hydro-fix` | nein |
| `ENFORCE_MAX_LIMITS` | `True` | Default für `--max-limits` | nein |
| `SOLVER_NAME`, `SOLVER_OPTIONS` | gurobi, Barrier ohne Crossover, 8 Threads, BarConvTol 1e-5 | Solver-Einstellungen | nein |
| **Wirtschaftliche Parameter** | | | |
| `CO2_PRICE_EUR_PER_T` | 100 | CO₂-Preis in €/t (ERAA-Datei wird ignoriert) | nein |
| `VOLL_EUR_PER_MWH` | 3000 | Kosten des Lastabwurfs = faktische Preisobergrenze | nein |
| `FUEL_PRICE_OVERRIDES_EUR_PER_GJ` | `{"lignite": 3.1}` | feste Brennstoffpreise statt ERAA. Für eine Gaspreis-Sensitivität z.B. `"gas": 10.0` ergänzen | nein |
| `EFFICIENCY_OVERRIDES` | `{"ccgt": 0.49}` | feste Wirkungsgrade statt ERAA | nein |
| `VOM_OVERRIDES_EUR_PER_MWH` | `{"ccgt": 2.11}` | feste variable Betriebskosten statt ERAA | nein |
| `BIOMASS_MARGINAL_COST_EUR_PER_MWH` | 30 | Grenzkosten Biomasse (inkl. „Others renewable“) | nein |
| **Technische Parameter** | | | |
| `HYDRO_EFFICIENCY_DISPATCH` / `_STORE` | 0.87 / 0.87 | Turbinen- bzw. Pumpwirkungsgrad Wasserkraft | nein |
| `RESERVOIR_EFFICIENCY_STORE` | 1.0 | Speicherseen stauen Zufluss verlustfrei | nein |
| `BATTERY_EFFICIENCY_STORE` / `_DISPATCH` | 0.92 / 0.92 | Batteriewirkungsgrade | nein |
| `STORAGE_MAX_HOURS_FALLBACK` | 8 | Speicherdauer (h), falls ERAA keine Energiekapazität liefert | nein |
| `LINK_EFFICIENCY` | 1.0 | Übertragungsverluste der Leitungen (1.0 = keine) | nein |
| `NO_HYDRO_RESERVOIR_BOUNDS` | `"historical"` | Füllstandsgrenzen für `--no-hydro-fix flow+level`: historische oder technische | nein |
| **Pfade** | | | |
| `DATA_DIR`, `RAW_DIR`, `RESULTS_DIR`, `PAPER_NTC_CSV`, … | `01_data/…`, `04_results/`, `inputs/…` | wo Rohdaten liegen, Zwischendaten und Ergebnisse geschrieben werden | – |

Die übrigen Brennstoffpreise, Wirkungsgrade und VOM-Kosten kommen aus
`04b_accumulated_data_per_node/Additional Data/Annex 1 - Input data/` (ERAA). Welche Werte
tatsächlich verwendet werden, zeigt:

```bash
python -m pipeline.model.global_params    # druckt Brennstoffpreise, VOM und Grenzkosten je Technologie
```

### 6.2 Tiefer im Code (keine Einstellung, sondern Modelllogik)

| Was | Wo |
|---|---|
| welche ERAA-Kapazitätsspalte zu welcher Technologie wird (z.B. „Gas“ + „Others non-renewable“ → ein Gas-Generator) | `COLUMN_MAP` in [pipeline/model/zone_capacities.py](pipeline/model/zone_capacities.py) |
| welche Kraftwerke, Speicher, DSR-Stufen je Zone angelegt werden und mit welchen Grenzkosten | `add_zone()` in [pipeline/model/build_network.py](pipeline/model/build_network.py) |
| Grenzkostenformel (Brennstoff/η + CO₂ · Faktor/η + VOM), CO₂-Faktoren | [pipeline/model/global_params.py](pipeline/model/global_params.py) |
| welche Zeitreihendatei für Last, Wind, Solar, Hydro gelesen wird | `PATHS` in [pipeline/model/timeseries.py](pipeline/model/timeseries.py) |
| welche Ergebnisdateien geschrieben werden | [pipeline/model/results.py](pipeline/model/results.py) |
| zusätzliche Nebenbedingungen | [pipeline/model/max_limits.py](pipeline/model/max_limits.py), [pipeline/model/no_hydro_fix.py](pipeline/model/no_hydro_fix.py) |

---

## 7. Ergebnisse und Auswertung

Jeder Lauf schreibt nach `04_results/<Zonen>_CY<Wetterjahr><Suffix>/`:

| Datei | Inhalt |
|---|---|
| `summary_annual.csv` | je Zone: mittlerer, Median- und 95%-Preis (€/MWh), Lastabwurf (GWh) |
| `prices_lmp.csv` | Strompreis je Zone und Stunde (€/MWh) |
| `dispatch_generators.csv` | Erzeugung je Kraftwerk und Stunde (MW) |
| `storage_dispatch.csv`, `storage_store.csv`, `storage_state_of_charge.csv` | Speicher: Entladen, Laden (MW), Füllstand (MWh) |
| `interconnection_flows.csv` | Leitungsflüsse (MW) |
| `capacities_generators.csv`, `capacities_storage.csv`, `capacities_links.csv` | installierte Leistung und Grenzkosten |
| `loads.csv`, `total_loads.csv` | Last stündlich und als Jahressumme |

Auswertungsskripte in `analysis/` (lesen aus `04_results/`):

```bash
# Grenzkosten, Erzeugung und Preis bei Einspeisung je Technologie × Zone × Jahr
python analysis/marginal_costs.py          # -> 04_results/grenzkosten_summary.csv

# Merit-Order-Kurve einer Stunde: stilisiert oder aus echtem Dispatch
python analysis/plot_merit_order.py --output merit_order.png
python analysis/plot_merit_order.py --dispatch "04_results/<Lauf>/dispatch_generators.csv" --caps "04_results/<Lauf>/capacities_generators.csv" --hour 0 --zone DE

# früher Einzelzonen-Prototyp für Deutschland (eigene, fest eingetragene Parameter, nicht config.py!)
python analysis/germany_single_zone.py
```

---

## 8. Projektstruktur

```
config.py                     alle Stellschrauben (Abschnitt 6)
main/
  run_simulation.py           Simulation starten (Abschnitt 5)
  prepare_data.py             Datenaufbereitung starten (Abschnitt 4)
pipeline/
  data_preparation/           die 10 Aufbereitungsschritte (von prepare_data.py aufgerufen)
  model/
    global_params.py          Brennstoffpreise, Wirkungsgrade, CO2, Grenzkosten
    zone_capacities.py        installierte Kapazitäten je Zone
    timeseries.py             Last-, Wind-, Solar-, Hydro-Zeitreihen je Zone und Wetterjahr
    build_network.py          PyPSA-Netz aufbauen (Busse, Kraftwerke, Speicher, DSR, Last)
    eraa_interconnections.py  Leitungen aus ERAA
    paper_interconnections.py Leitungen aus der Paper-Tabelle
    max_limits.py             Länder-Import/Export-Obergrenzen
    no_hydro_fix.py           Norwegen-Hydro-Nebenbedingungen
    results.py                Ergebnis-CSVs schreiben
analysis/                     Auswertung der Ergebnisse (Abschnitt 7)
inputs/                       selbst erstellte Eingaben (Paper-NTC-Tabelle)
docs/                         Modelldokumentation, ERAA-Formatvergleich
01_data/                      Daten (nicht im Git, Abschnitt 3; Ort über DATA_DIR wählbar)
04_results/                   Ergebnisse (nicht im Git)
```

Die Module in `pipeline/` sind keine eigenständigen Skripte. Einige haben einen Schnelltest, der mit
`python -m pipeline.model.<modul>` aus dem Projekt-Root läuft (z.B. `global_params`,
`zone_capacities`, `timeseries`).

---

## 9. Bekannte Einschränkungen und weitere Doku

- Es variiert nur das **Wetterjahr**. Brennstoffpreise, CO₂-Preis und Nachfrage sind fest (das Paper
  zieht sie zusätzlich per Monte-Carlo).
- Kein Unit Commitment, keine Rampen, keine Reserven, keine Netzverluste, kein Netzausbau.
- Leitungskapazitäten sind statisch (Jahresmittel), DSR hat kein Stundenlimit.
- Einige Parameter sind bewusst auf Paper-Werte festgesetzt statt aus ERAA gelesen (siehe
  Abschnitt 6.1, „Wirtschaftliche Parameter“).

Weitere Dokumentation:

- [docs/MODEL_DOCUMENTATION_FOR_PAPER_COMPARISON.md](docs/MODEL_DOCUMENTATION_FOR_PAPER_COMPARISON.md):
  alle Eingaben, Annahmen und Vereinfachungen im Detail. Startpunkt zum Verständnis des Modells.
- [docs/ERAA_INPUT_DATA_COMPARISON.md](docs/ERAA_INPUT_DATA_COMPARISON.md): warum nur ERAA 2022 funktioniert.
