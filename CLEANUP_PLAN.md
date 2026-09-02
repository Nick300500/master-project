# Clean-Code-Refactor — Plan & Auftrag

Branch: `clean-code`
Angelegt: 2026-08-26

## Ausgangslage

Das Repo baut eine europäische Strompreisprognose mit PyPSA (Replikation von
Navia Simon & Diaz Anadon, Nature Energy 2025, siehe [README.md](README.md)).
Grundlage sind ERAA-Rohdaten (Excel), die über eine Kette von nummerierten
Skripten in `02_models/skripts/` schrittweise verarbeitet werden, bis daraus
ein PyPSA-Netzwerk gebaut und optimiert wird.

Der Code wurde von einem Nicht-Informatiker organisch über die Zeit gebaut:
er funktioniert (End-Ergebnis ist lauffähig), ist aber historisch gewachsen,
enthält alte/parallele Versionen einzelner Schritte und es ist von außen
nicht klar ersichtlich, welche Datei/welcher Pfad gerade tatsächlich zur
produktiven Pipeline gehört und welcher nur Altlast ist.

Beispiele für erkennbare Altlasten (noch nicht verifiziert, nur Auflistung
aus der Ordnerstruktur — vor dem Löschen muss geprüft werden, ob wirklich
nichts mehr davon referenziert wird):
- `02_models/skripts/999_OLD_climate_accumulate_data_per_node.py`
- `02_models/skripts/999_06_filter_and_accu_PEMMCD_National_Estimates/`
- `02_models/skripts/100_germany_network_analysis_OLD/`
- `02_models/skripts/test/`, `test_NO.py`, `NO extreme check 1995`
- mehrere parallele `run_batch_simulation*.py`-Varianten
  (`run_batch_simulation.py`, `_configurable.py`, `_fixed_years.py`,
  `_NO_hydro_fix.py`)
- `01_data/04_accumulated_data_per_node_OLD/` neben
  `01_data/04b_accumulated_data_per_node/`
- `Earlier results/`, `Results for ERAA-values with NO problem/`

## Ziel

1. **Aufräumen**: alles entfernen, was nicht mehr zur produktiven Pipeline
   gehört (alte Versionen, Duplikate, Fragmente, die "eigentlich" nur
   Zwischenstände waren).
2. **Klären, Schritt für Schritt**: den verbleibenden Code durchgehen und
   nach und nach klarer/logischer/nachvollziehbarer machen — nicht alles auf
   einmal, sondern in überschaubaren, review-baren Schritten.
3. **Endzustand**: ein Repo, das lauffähig ist, klar strukturiert ist und
   nicht mehr wie "hingehunzt" aussieht.
4. **Wichtigster fachlicher Punkt**: die Pipeline von den ERAA-Rohdaten bis
   zum fertigen PyPSA-Netzwerk soll am Ende als **eigenständiges, klares
   Tool** funktionieren — nicht hart auf ERAA 2022 verdrahtet, sondern so,
   dass sie auch mit **ERAA 2025**-Daten läuft.

## Phase 1 — Bestandsaufnahme: Lösch-Liste (Stand 2026-08-26, zur Freigabe)

Nachverfolgt: was importiert/nutzt was tatsächlich (Pipeline-Kern sind die
Module `build_network.py`, `add_interconnections.py`, `add_max_limits.py`,
`gather_global_params.py`, `load_zone_capacities.py`, `load_timeseries.py`,
die von allen `run_batch_simulation*.py`-Varianten importiert werden; die
nummerierten Skripte 01–06 sind eine manuell nacheinander laufende
ETL-Kette ohne Imports untereinander — das ist für diese Art Pipeline normal).

### (a) Definitiv tot — nie referenziert, gefahrlos löschbar
- `02_models/skripts/98_analysis.py` — leere Datei (0 Zeilen)
- `02_models/skripts/test` — Scratch-Skript (Hydro-Inflow-Debugging), kein echter Test
- `02_models/skripts/test_NO.py` — Scratch-Skript (CSV-Shapes ausgeben)
- `02_models/skripts/NO extreme check 1995` — Scratch-Skript (manuelle Ausreißer-Prüfung)
- `02_models/skripts/__pycache__` — Bytecode-Cache
- `02_models/Start` — praktisch leere Datei (2 Leerzeilen, kein Code)

### (b) Alte/überholte Versionen — per Diff bestätigt superseded
- `02_models/skripts/999_OLD_climate_accumulate_data_per_node.py`
  → ersetzt durch `03_climate_accumulate_data_per_node.py` (Diff: fast identisch, 999 ist Vorentwurf)
- `02_models/skripts/999_06_filter_and_accu_PEMMCD_National_Estimates`
  → ersetzt durch `06_filter_and_accu_PEMMCD_National_Estimates.py` (Diff: 06.py hat zusätzliches Grouping nach `Technology`)
- `02_models/skripts/100_germany_network_analysis_OLD`
  → ersetzt durch `100_germany_network_analysis.py` (Diff: aktuelle Version hat zusätzlich Run-of-River/Pondage-Hydro-Inflow, Carrier-Definitionen)
- `02_models/skripts/70_grid_build_up.py` und `80_grid_implement_generators.py`
  → alter, eigenständiger `.nc`-Export-Ansatz (Buses/Links bzw. Generatoren) gegen die **alte** Datenordner-Struktur (`01_data/04_accumulated_data_per_node`, nicht `04b_...`); von nichts importiert; die erzeugte Datei `03_states_of_the_grid/EU_GRID_links_and_buses_2030.nc` wird von keinem anderen Skript gelesen (geprüft per Grep) — vollständig isoliert. Funktional ersetzt durch `build_network.py` + `load_zone_capacities.py`.
- `02_models/skripts/run_batch_simulation_fixed_years.py`
  → schmale Kopie der Kernschleife aus `run_batch_simulation.py`, laut eigenem Docstring ein einmaliger Re-Run nach einem konkreten Bugfix (FI-Baltic-DC-Fehler). Funktional eine Teilmenge von `run_batch_simulation_configurable.py`.

### (c) Aktiv — bleibt (Kern der Pipeline)
- ETL-Kette 01→06 (`01_excel_to_csv.py`, `01b_restructure_hydro_inflows.py`,
  `02b_filter_csvs.py`, `03_b_add_years_to_hydro.py`,
  `03_climate_accumulate_data_per_node.py`, `03_demand_accumulate_data_per_node.py`,
  `04_accumulate_interconnections.py`, `05_transpond TY{year}_csv.py`,
  `06_filter_and_accu_PEMMCD_National_Estimates.py`)
- Kern-Module: `gather_global_params.py`, `load_zone_capacities.py`,
  `load_timeseries.py`, `build_network.py`, `add_interconnections.py`,
  `add_max_limits.py`
- Entry-Points: `run_batch_simulation.py` (generischer Batch-Lauf),
  `run_batch_simulation_configurable.py` (Paper-NTC + NO-Hydro-Fix-Szenario,
  aktuellste/vollständigste Variante), `run_batch_simulation_NO_hydro_fix.py`
  (wird von `_configurable.py` importiert — trotz Docstring "separates
  Test-Skript" **nicht tot**)
- Analyse-Tools (eigenständig, manuell ausgeführt, nicht Teil der
  Kern-Pipeline, aber real genutzt): `99_marginal_costs.py`,
  `100_germany_network_analysis.py`, `plot_merit_order_DE.py`

### (d) Ungeklärt — braucht deine Entscheidung
1. **Welches `run_batch_simulation*.py` ist "der" Einstiegspunkt?**
   Empfehlung: `run_batch_simulation.py` bleibt genereller Default-Treiber,
   `_configurable.py` und `_NO_hydro_fix.py` bleiben als Szenario-Varianten,
   `_fixed_years.py` wird gelöscht (b). Alternative (passend zum
   Phase-3/4-Ziel): alle drei zu einem parametrisierten Skript
   zusammenführen — das wäre aber ein Phase-3-Schritt, kein reines Löschen.
2. **`98_analysis.py`** — leer, Nummerierung direkt vor `99_marginal_costs.py`.
   War hier mal ein allgemeiner Analyse-Schritt geplant, der nie geschrieben
   wurde? Löschbar in jedem Fall, nur zur Info.
3. `02_models/Start` — keine erkennbare Funktion, vermutlich Versehen.

## Phase 1b — Analyse der vier `run_batch_simulation*.py` (Stand 2026-08-26)

Noch nicht gelöscht (auf Wunsch zurückgestellt) — hier die genaue funktionale
Abgrenzung, damit die Konsolidierungs-Entscheidung fundiert getroffen werden
kann.

Die vier Skripte unterscheiden sich in **drei unabhängigen Dimensionen**,
nicht in einer linearen "alt→neu"-Kette:

| Skript | Jahresauswahl | Interconnections | NO-Hydro-Fix | Sonstiges |
|---|---|---|---|---|
| `run_batch_simulation.py` | zufällig aus 1982–2015, überspringt bereits simulierte Jahre (scannt `04_results/`), N=10 pro Lauf | ERAA-Standard (`add_interconnections.py`) | nein | BarConvTol 1e-5, Threads 8, generischer Default-Treiber |
| `run_batch_simulation_fixed_years.py` | feste Liste `[2003, 2012, 2006, 2011, 2014, 1988]`, kein Skip | ERAA-Standard | nein | BarConvTol 1e-4; laut eigenem Docstring ein einmaliger Re-Run von Jahren aus "Earlier results/Results with FI-baltic DC error" nach Bugfix — funktional sonst fast identisch zu `run_batch_simulation.py`, nur ohne Zufallsauswahl/Skip-Logik |
| `run_batch_simulation_NO_hydro_fix.py` | feste Liste via `--years` CLI (Default `[2003]`) | ERAA-Standard | **ja**, vollständig: liest norwegische PEMMDB-Bietzonen-Excel-Dateien (NOM1/NON1/NOS0), passt Speicherkapazität von `PSOpen_NO` an, setzt wöchentliche Erzeugungs- UND Reservoir-Level-Constraints | eigenständiges CLI (`--years`, `--suffix`, `--no-flow`, `--no-level`); **wird von `_configurable.py` importiert** — trotz Docstring "Separates Test-Skript" also eine aktive Bibliothek |
| `run_batch_simulation_configurable.py` | feste Liste (Default wie `fixed_years.py`) via `--years` CLI | **Paper-NTC** (aus `01_data/Exact paper interconnection/NTC_Vergleich_ERAA_Paper_Modell.csv`, ersetzt ERAA-Werte vollständig — passend zum Commit "changed to only be able to simulate Paper NTC values") | ja, aber nur **Flow-Constraints** (keine Reservoir-Level-Constraints, im Gegensatz zu `_NO_hydro_fix.py`) | nutzt 7 Funktionen aus `_NO_hydro_fix.py` per Import; aktuell das Skript für die eigentlichen Paper-Vergleichsläufe |

**Kernaussage:** Keines der vier ist eine reine Weiterentwicklung eines
anderen — sie kombinieren drei unabhängige Achsen (Jahresauswahl /
Interconnection-Quelle / NO-Hydro-Fix-Tiefe) auf unterschiedliche Weise.
`run_batch_simulation_fixed_years.py` ist der Datei nach am ehesten
verzichtbar (Teilmenge von `run_batch_simulation.py`, nur mit fester statt
zufälliger Jahresliste), aber aktuell die *einzige* Möglichkeit, "ERAA-NTC +
bestimmte Jahre + kein NO-Fix" zu fahren, ohne `run_batch_simulation.py`
selbst zu ändern.

**Umgesetzt (2026-08-27):** Konsolidierung wie oben vorgeschlagen durchgeführt.
`run_batch_simulation.py` ist jetzt der einzige Einstiegspunkt mit den Flags
`--years` / `--random N --year-range MIN MAX --skip-existing`,
`--interconnections {eraa,paper}`, `--no-hydro-fix {off,flow,flow+level}`,
`--max-limits/--no-max-limits`, `--suffix`, `--bar-conv-tol`, `--threads`.
Die NO-Hydro-Fix-Logik wurde nach `no_hydro_fix.py` ausgelagert, die
Paper-NTC-Logik nach `paper_interconnections.py` (beides eigenständige
Module statt Funktionen, die aus einem "run_*"-Skript importiert wurden).
`run_batch_simulation_fixed_years.py`, `run_batch_simulation_NO_hydro_fix.py`
und `run_batch_simulation_configurable.py` wurden entfernt — ihre komplette
Funktionalität ist über Flags des neuen `run_batch_simulation.py` erreichbar.
**Getestet (2026-09-02):** Zwei End-to-End-Testläufe erfolgreich:
1. `--interconnections eraa --no-hydro-fix off`, Zone DE, Klimajahr 2012 →
   Optimierung optimal gelöst, Ergebnisse korrekt in `04_results/` gespeichert.
2. `--interconnections paper --no-hydro-fix flow+level`, Zonen DE+NO,
   Klimajahr 2012 → Paper-NTC-Links korrekt geladen, alle 52
   Wochen-Flow- und Reservoir-Level-Constraints gesetzt, Check-CSVs
   (`NO_hydro_fix_weekly_check_NO.csv`, `NO_hydro_fix_reservoir_level_check_NO.csv`)
   korrekt geschrieben. Optimierung optimal gelöst.
3. CLI (`--help`) parst korrekt, alle Flags wie dokumentiert.

Test-Ergebnisordner wieder gelöscht (nur zum Testen erzeugt).

**Nebenbefund:** `gurobipy` fehlte im System-Python UND fehlt in
`requirements.txt` (im Gegensatz zu `openpyxl`, das zwar installiert werden
musste, aber immerhin gelistet ist) — vermutlich weil Gurobi bisher über
eine separate lokale Installation (`C:\gurobi1302`) eingebunden wurde statt
über pip. Für Phase 3 vormerken: `requirements.txt` (auch UTF-16-Encoding-Fix,
siehe oben) um `gurobipy` ergänzen, damit ein frischer Checkout ohne
manuelles Nachinstallieren lauffähig ist.

**Nicht angefasst** (außerhalb Scope laut Absprache): Datenordner
(`01_data/04_accumulated_data_per_node_OLD` etc.), Ergebnis-Ordner
(`04_results`, `Earlier results`, `Results for ERAA-values with NO problem`
— dort auch ein identisches Duplikat `plot_results.py` gefunden, aber
bewusst nicht angefasst).

## Vorgehen

- Phase 0 (dieser Schritt): Auftrag dokumentieren, Branch `clean-code`
  anlegen, offene Fragen klären (siehe unten).
- Phase 1: Bestandsaufnahme — welche Dateien/Pfade werden vom tatsächlichen
  Pipeline-Einstiegspunkt (vermutlich `run_batch_simulation*.py` bzw. die
  nummerierten Skripte 01–100) tatsächlich importiert/aufgerufen? Alles
  andere ist Kandidat zum Entfernen.
- Phase 2: Entfernen der als tot identifizierten Dateien/Ordner (in eigenen,
  nachvollziehbaren Commits, nicht in einem Rutsch).
- Phase 3: Schrittweise Klärung/Vereinheitlichung des verbleibenden Codes,
  Stück für Stück, mit Zwischenständen zum Gegenlesen.
- Phase 4: ERAA-Input→PyPSA-Netzwerk-Pipeline als eigenständiges,
  parametrisierbares Tool herausschälen (Konfigurationsjahr statt
  hart codiertem 2022), inkl. Test mit ERAA-2025-Daten.

## Entscheidungen (Rückfrage vom 2026-08-26)

- **ERAA 2025**: Rohdaten liegen noch nicht vor, nur ERAA 2022. Die Pipeline
  soll aber schon jetzt so gebaut werden (Jahr als Parameter statt hart
  codiert), dass sie 2025-Daten aufnehmen kann, sobald sie verfügbar sind.
- **Löschstrategie**: Vor dem tatsächlichen Löschen wird zuerst nachverfolgt,
  was vom Pipeline-Einstiegspunkt tatsächlich benutzt wird, und dem Nutzer
  eine konkrete Lösch-Liste zur Freigabe gezeigt. Erst nach OK wird gelöscht.
- **Ergebnis-Ordner** (`04_results`, `Earlier results`,
  `Results for ERAA-values with NO problem`): bleiben unangetastet, Fokus
  liegt auf Code/Skripten, nicht auf Datenständen.
- **Arbeitstempo**: so weit wie sinnvoll in einem Zug durcharbeiten (Branch
  ist neu, `main` bleibt als Fallback erhalten), Rückfragen nur bei wirklich
  unklaren/riskanten Stellen — die Lösch-Liste selbst wird trotzdem vor dem
  Löschen vorgelegt (siehe Löschstrategie).
