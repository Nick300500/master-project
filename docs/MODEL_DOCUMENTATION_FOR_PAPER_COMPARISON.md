# Vollständige Modell-Dokumentation für Paper-Abgleich

Stand: 2026-09-02. Zweck dieses Dokuments: **vollständige, code-unabhängige
Beschreibung** dessen, was die Simulationspipeline in diesem Repository
tatsächlich tut — jeder Input, jede Annahme, jede Vereinfachung, jede
Implementierungsentscheidung — damit ein Vergleich mit dem Referenzpaper
(ohne Zugriff auf den Code) vorgenommen werden kann. Enthält explizit auch
Limitationen, bewusste Vereinfachungen, unbewusste Lücken und intern
unbeantwortete Fragen.

**Referenzpaper:** Navia Simon & Diaz Anadon, "Power price stability and
the insurance value of renewable technologies", Nature Energy, 2025
(https://doi.org/10.1038/s41560-025-01704-0). Das Paper simuliert den
europäischen Strommarkt mit dem Modell GenX; dieses Repository baut eine
Replikation mit PyPSA (Python for Power System Analysis) auf denselben
bzw. möglichst ähnlichen Input-Daten.

---

## 1. Grobarchitektur der Pipeline

```
ERAA-2022-Rohdaten (Excel, ENTSO-E)
  → 01_excel_to_csv.py            (jedes Excel-Sheet → eigene CSV)
  → 01b_restructure_hydro_inflows.py  (Hydro-Inflow-Dateien nach Technologie sortiert)
  → 02b_filter_csvs.py            (nur Daten fürs Zieljahr behalten, Nutzer gibt Jahr interaktiv ein)
  → 03_climate_accumulate_data_per_node.py   (Wind/Solar/Hydro/CSP je Gebotszonen-Gruppe akkumulieren)
  → 03_demand_accumulate_data_per_node.py    (Demand je Gebotszonen-Gruppe akkumulieren)
  → 03_b_add_years_to_hydro.py    (Platzhalter-Spaltenköpfe der Hydro-Dateien durch echte Klimajahre 1982–2017 ersetzen)
  → 04_accumulate_interconnections.py  (NTC-Verbindungen je Zonen-Gruppenpaar akkumulieren, interne Verbindungen rausfiltern)
  → 05_transpond TY{year}_csv.py  (PEMMDB-"National Estimates"-Tabelle transponieren)
  → 06_filter_and_accu_PEMMCD_National_Estimates.py  (PEMMDB-Kapazitätstabellen nach Zieljahr filtern, nach Gebotszonen-Gruppe summieren)
  → 01_data/04b_accumulated_data_per_node/   (EINHEITLICHES Zwischenformat: eine CSV pro Zone/Gruppe und Kategorie)
  → gather_global_params.py / load_zone_capacities.py / load_timeseries.py   (Zwischenformat → Python-Dicts/Series)
  → build_network.py              (PyPSA-Netz aufbauen: Busse, Generatoren, Speicher, DSR, Last)
  → add_interconnections.py ODER paper_interconnections.py   (NTC-Links einfügen: ERAA-Werte oder Paper-eigene Werte)
  → add_max_limits.py + no_hydro_fix.py (optional)  (zusätzliche Nebenbedingungen)
  → n.optimize() (Gurobi, lineares Programm)
  → Ergebnis-CSVs in 04_results/
```

Wichtig für die Bewertung: Alle Schritte ab `gather_global_params.py`
arbeiten NICHT mehr mit ENTSO-E-Rohformaten, sondern mit einem selbst
definierten Zwischenformat (eine CSV pro Zone/Kategorie mit fester
Zeilen-/Spaltenstruktur). Die Schritte 01–06 sind reine Formatübersetzung,
kein Teil des eigentlichen ökonomischen Modells.

---

## 2. Datenquelle

- **ERAA 2022** (European Resource Adequacy Assessment), veröffentlicht von
  ENTSO-E. Enthält PECD (Pan-European Climate Database, Wind/Solar-CF und
  Hydro-Zuflüsse für Wetterjahre 1982–2017) und PEMMDB (Pan-European Market
  Modelling Database, installierte Kapazitäten/technische Parameter je
  Gebotszone und Zieljahr).
- **Zieljahr (Kapazitäten):** fest auf **2030** verdrahtet
  (`06_filter_and_accu_PEMMCD_National_Estimates.py`, Zeile
  `filter_by_year(df, 2030)` — nicht parametrisierbar ohne Codeänderung).
  Die einzige verwendete PEMMDB-Kapazitätsdatei heißt entsprechend
  konsequent `TY 2030.csv`.
- **Demand-Szenario:** "National Trends", explizit ohne Batterie-Zusatzlast
  im Standardpfad (`Demand_TimeSeries_2030_NationalTrends_without_bat`).
  Es gibt zusätzliche Zeitreihen für Batterien/E-Autos/Wärmepumpen
  (`load_bat`, `load_ev`, `load_hp`), die geladen, aber standardmäßig NICHT
  zur Last addiert werden (`include_detailed_demand=False` als Default in
  `load_zone_timeseries()`). Ein früherer Commit hatte das aktiviert,
  wurde aber wieder zurückgenommen ("wahrscheinlich falsch") — bis heute
  nicht abschließend geklärt, ob die aggregierte Last mit oder ohne diese
  Zusatzlasten dem Paper entsprechen sollte.
- **Kostenparameter** (Brennstoffpreise, Wirkungsgrade, CO2-Preis, VOM):
  aus `Additional Data/Annex 1 - Input data/*` — pan-europäische
  Einzelwerte je Technologie, NICHT nach Zone differenziert.

---

## 3. Räumliche Auflösung

23 Modellzonen: `DE, FR, AT, BE, NL, CH, CZ, PL, DK, ES, PT, IT, GR, SE, NO,
FI, UK, IE, LU, MT, CY, TR, UA` plus drei **aggregierte "hypothetische"
Zonen**:

| Modellzone | Zusammengefasste ERAA-Gebotszonen |
|---|---|
| `adriatic` | AL, BA, HR, ME, MK, RS, SI |
| `baltic` | EE, LV, LT |
| `other eastern european` | BG, HU, RO, SK |

Diese Gruppierungsregel (`GROUP_RULES`) ist **identisch und konsistent**
über alle Pipeline-Skripte hinweg definiert (Klimadaten, Demand,
Interconnections, PEMMDB-Kapazitäten, Max-Limits) — intern also
widerspruchsfrei. Ob sie mit der Länderzuordnung des Papers übereinstimmt
(Paper nennt nur "Baltic"/"Adriatic"/"Other Europe" ohne explizite
Länderliste in den ausgewerteten Textstellen), ist die zentrale offene
Frage für den Abgleich (siehe `OPEN_QUESTIONS_AUTHORS.md`, Punkt A.2).

**Aggregationsmethode innerhalb einer Gruppen-Zone** (wichtig, oft
übersehene Design-Entscheidung):
- **Wind/Solar-Kapazitätsfaktoren:** kapazitätsgewichteter Durchschnitt
  über die Einzelländer der Gruppe, gewichtet mit der installierten
  Kapazität (`p_nom`) je Land aus der TY2030-Tabelle. Länder mit `p_nom=0`
  fließen nicht ein. Kein einfacher arithmetischer Mittelwert.
- **Alles andere** (Demand, Hydro-Inflows, installierte Kapazitäten,
  NTC-Werte): einfache Summation über die Länder der Gruppe.
- **Interne Verbindungen** innerhalb einer Gruppen-Zone (z. B. HR↔SI)
  werden beim Interconnections-Schritt explizit herausgefiltert (nur
  Verbindungen zwischen unterschiedlichen Gruppen werden übernommen).
- Landescode-Duplikate auf Rohdaten-Ebene (identisches Zonenpaar taucht
  zweimal in den Rohdaten auf) werden erkannt und die zweite Instanz
  verworfen (behebt den in `OPEN_QUESTIONS_AUTHORS.md` erwähnten
  FI–Baltic-Doppelverbindungs-Bug).

---

## 4. Zeitliche Auflösung

- **Snapshots:** 8.760 Stunden (ein volles Kalenderjahr), Index künstlich
  auf `2030-01-01` gesetzt (reines Datenraster, keine reale
  Zieljahres-Kalenderinformation nötig für Dispatch-Optimierung).
- **Klimajahr ("weather year"):** frei wählbar als String-Parameter
  (`climate_year`, z. B. `"2012"`). Steuert, welche PECD-Spalte für
  Wind/Solar/Hydro sowie ggf. für Demand herangezogen wird.
- **Verfügbarer Wertebereich:** PECD/ERAA liefert 1982–2017 (36 Jahre;
  `03_b_add_years_to_hydro.py` erzeugt exakt diese Spannbreite). Der
  ursprüngliche Batch-Treiber (`run_batch_simulation.py`, vor der
  Konsolidierung) zog zufällige Jahre aus **1982–2015** (`YEAR_MIN=1982,
  YEAR_MAX=2015`) — deckt **2016 und 2017 nicht ab**, obwohl die Daten
  verfügbar wären. Nicht abschließend geklärt, ob das Absicht war.
  Zum Vergleich: Das Paper spricht in der Einleitung von "1982–2016", in
  der Methods-Sektion aber explizit von "1987–2016" als Ziehungsbereich —
  **beide Angaben weichen vom im Code verwendeten Bereich ab** (siehe
  `OPEN_QUESTIONS_AUTHORS.md`, Punkt A.1, bislang ungeklärt).
- **Kein Monte-Carlo über ökonomische Parameter:** Das Paper zieht laut
  Methods für jede Wiederholung sowohl ein zufälliges Wetterjahr als auch
  (basierend auf einer historischen Kovarianzmatrix 1990–2021) zufällige
  Demand- und Brennstoffpreis-Realisationen. **Dieses Repository variiert
  ausschließlich das Klimajahr** — Brennstoffpreise, Demand-Niveau,
  CO2-Preis etc. sind für alle Läufe identisch (fixe Werte aus
  `Additional Data`, s. u.). Ein Parameter für Gaspreis-Override existiert
  im Code (`gas_price_eur_mwh_th` in `build_network()`), wird aber vom
  aktuellen CLI (`run_batch_simulation.py`) nicht genutzt. **Das ist die
  vermutlich größte methodische Lücke gegenüber dem Paper** — die
  Simulation bildet nur die Wetter-bedingte Varianz ab, nicht die vom
  Paper explizit adressierte Kombination aus Wetter- UND
  Wirtschaftsvarianz.
- **Perfect Foresight:** Die Optimierung läuft über das gesamte Jahr
  gleichzeitig (kein Rolling Horizon, keine Unsicherheit innerhalb des
  Laufs) — Standardannahme für PyPSA-Dispatch-Modelle, entspricht
  vermutlich auch GenX' Herangehensweise im Paper (nicht verifiziert).

---

## 5. Erzeugungstechnologien

Kapazitäten (`p_nom`, MW) kommen ausschließlich aus `TY 2030.csv`
(PEMMDB National Estimates), pro Zone in folgende Kategorien aufgeteilt:

| Modell-Generator | ERAA-Spalte(n) | Grenzkosten-Quelle | Marginal Cost (€/MWh) fix? |
|---|---|---|---|
| `Gas_{zone}` | "Gas " + "Others non-renewable" (aggregiert) | `gas`-Brennstoffpreis ÷ CCGT-Wirkungsgrad + CO2 + VOM | Brennstoffpreis: aus CSV falls vorhanden. **Wirkungsgrad CCGT: IMMER 0.49 (fix, CSV-Mapping bewusst deaktiviert)**. VOM CCGT: **immer 2.11 (fix, CSV-Mapping deaktiviert)** |
| `Lignite_{zone}` | "Lignite" | analog | **Brennstoffpreis Lignite: IMMER 3.1×3.6=11.16 €/MWh_th (fix, CSV-Mapping deaktiviert)** |
| `Coal_{zone}` | "Hard Coal" | analog | aus CSV falls vorhanden (Mapping aktiv) |
| `Nuclear_{zone}` | "Nuclear" | analog | aus CSV falls vorhanden (Mapping aktiv) |
| `Oil_{zone}` | "Oil" | über `light_oil`/`oil` | aus CSV falls vorhanden (Mapping aktiv) |
| `Biomass_{zone}` | "Biofuel" + "Others renewable" (aggregiert) | — | **fest 30 €/MWh, keine CSV-Anbindung, reine Annahme** (siehe `OPEN_QUESTIONS_AUTHORS.md`, Punkt A.7) |
| `WindOn_{zone}`, `WindOff_{zone}`, `Solar_{zone}` | "Wind Onshore"/"Wind Offshore"/"Solar (Photovoltaic)" | — | 0 (kein Brennstoff) |
| `RoR_{zone}`, `Pondage_{zone}` | "Hydro - Run of River/Pondage (Turbine)" | — | 0 |
| `LoadShedding_{zone}` | künstlich, `p_nom=1e6` MW | — | = VOLL, fest 3000 €/MWh |
| `DSR_{zone}_band{1..8}` | "Explicit DSR.csv" | — | je Preisband aus CSV |

**Wichtiger, sonst nicht offensichtlicher Punkt:** "Gas" und "Others
non-renewable" werden zu EINEM Generator addiert, ebenso "Biofuel" und
"Others renewable" zu einem Biomasse-Generator — laut Code-Kommentar
"paper-konform, Supplement S.3". Diese Aggregation ist eine bewusste
Anpassung an die (vermutete) Kategorisierung des Papers, keine
ERAA-Standardkategorie.

**CO2-Preis:** Die Lade-Funktion `load_co2_price()` liest technisch aus
`CO2 prices/Sheet1.csv`, ABER der komplette CSV-Auswertungscode ist
auskommentiert — es wird **immer** der Fallback-Wert **100 €/t** verwendet,
unabhängig vom tatsächlichen CSV-Inhalt. Das ist keine Fallback-Logik für
fehlende Daten, sondern ein bewusst (mit Kommentar "changed due to paper
confirmation") fest verdrahteter Wert.

**Market Price Cap:** Wird geladen (`load_market_price_cap()` gibt fix
3000 €/MWh zurück, mit explizitem Hinweis im Log, dass der ERAA-Wert
8000 €/MWh ignoriert wird) und im Parameter-Dict gespeichert — **wird aber
nirgends im Modell tatsächlich als Constraint verwendet**. Der einzige
faktische Preisdeckel im Modell ergibt sich indirekt aus dem
Load-Shedding-Generator mit `marginal_cost = VOLL = 3000`. Der separate
"Market Price Cap"-Parameter ist aktuell totes Datum ohne Wirkung.

**VOLL (Value of Lost Load):** fest 3000 €/MWh, mit explizitem Verweis
"paper-konform" (ERAA würde 8000 €/MWh vorsehen).

---

## 6. Erneuerbare Energien (Wind, Solar)

- Kapazitätsfaktor-Zeitreihen (0–1) direkt aus PECD, je Klimajahr eine
  Spalte in der akkumulierten CSV.
- Bei Gruppen-Zonen: kapazitätsgewichteter Mittelwert (s. Abschnitt 3).
- Werte werden vor Verwendung auf `[0, 1]` geclippt (Interpolation +
  Clipping in `load_timeseries.py` bzw. `build_network.py`).
- Keine Abregelung/Curtailment-Kosten, kein Netzengpass unterhalb der
  Zonenebene (kupferplatten-Annahme pro Zone).
- Solar Thermal (`solar_thermal`) wird zwar aus der TY2030-Tabelle
  gelesen, aber **nirgends als eigener Generator ins Netz eingefügt** —
  faktisch ignoriert (keine Zeile in `add_zone()` dafür vorhanden).

---

## 7. Hydro-Modellierung

Fünf ERAA-Hydro-Kategorien, alle mit `efficiency_dispatch = 0.87`
(Turbinen-Wirkungsgrad, einheitlich):

| Kategorie | PyPSA-Komponente | Speicher? | Inflow-Herkunft |
|---|---|---|---|
| Run of River | `Generator` | nein (reiner CF-Generator) | Inflow ÷ p_nom als Kapazitätsfaktor |
| Pondage | `Generator` | nein (Tagesspeicher wird ignoriert) | analog |
| Reservoir | `StorageUnit`, `efficiency_store=1.0` (kein Pumpverlust) | ja | wöchentlicher/täglicher ERAA-Inflow |
| Pump Storage Open Loop | `StorageUnit`, `efficiency_store=0.87` | ja, mit Pumpen | wöchentlicher/täglicher ERAA-Inflow |
| Pump Storage Closed Loop | `StorageUnit`, `efficiency_store=0.87` | ja, mit Pumpen | **kein** natürlicher Inflow |

**Wichtige Vereinfachung bei den Inflow-Zeitreihen:** ERAA liefert
Hydro-Zuflüsse nur als wöchentliche (52–53 Werte) oder tägliche (365 Werte)
Summen. Der Code (`_read_hydro_inflow()` in `load_timeseries.py`) verteilt
diese Summe **gleichmäßig** auf alle Stunden des jeweiligen Zeitfensters
(konstanter MW-Wert für 168h bzw. 24h). Es gibt **keine
Innerhalb-Woche/Innerhalb-Tag-Dynamik** — ein Sonntagnachmittag bekommt
denselben Zufluss wie ein Dienstagvormittag. Das ist eine reale,
möglicherweise vom Paper/GenX abweichende Vereinfachung.

**Speicherkapazität (`max_hours`):** berechnet als
`MWh-Energiespeicherkapazität (aus TY2030) ÷ MW-Turbinenkapazität`.
Fallback `8.0h`, falls einer der beiden Werte fehlt oder 0 ist. Diese
Fallback-Annahme ist willkürlich und nicht paper-referenziert — betrifft
laut `OPEN_QUESTIONS_AUTHORS.md` Punkt A.8 direkt eine der offenen
Autoren-Fragen.

**Norwegen-Sonderfall:** ERAA klassifiziert die gesamte norwegische
Speicherwasserkraft unter "Pump Storage Open Loop" (kein separater
Reservoir-Eintrag). Der Code behandelt das im Kern (`build_network.py`)
konsistent (kein Umleitungshack nötig). Zusätzlich existiert ein
optionales Zusatzmodul (`no_hydro_fix.py`, aktivierbar über
`--no-hydro-fix flow` oder `flow+level`), das aus den norwegischen
PEMMDB-Bietzonen-Exceldateien (NOM1/NON1/NOS0) **zusätzliche wöchentliche
Erzeugungs- und Reservoir-Level-Constraints** ableitet und der StorageUnit
`PSOpen_NO` auferlegt — ein Versuch, die vom reinen PyPSA-Speichermodell
nicht erfasste ERAA-Bewirtschaftungslogik (Min/Max-Wochenerzeugung,
Füllstandsgrenzen) nachzubilden. **Dieses Zusatzmodul ist standardmäßig
AUS** (`--no-hydro-fix off`) und wird nur bei expliziter Aktivierung
verwendet.

**Pumpleistung (`p_min_pu` für Pumpspeicher):** aus dem Verhältnis
Pump-MW ÷ Turbinen-MW berechnet (PyPSA-Konvention: `p_min_pu ≤ 0` bedeutet
Laden/Pumpen). Fällt der Pumping-Wert in den Kapazitätsdaten, wird
`-1.0` angenommen (volle Turbinenkapazität als Pumpleistung) — eine
konservative Fallback-Annahme, keine ERAA-Ableitung.

---

## 8. Batteriespeicher

`Battery_{zone}`, `efficiency_store = efficiency_dispatch = 0.92`,
`p_min_pu = -1.0` (volle Ladeleistung = `p_nom`), `cyclic_state_of_charge
= True`. Kapazität und `max_hours` aus TY2030 (Injektions-MW und
Speicher-MWh).

---

## 9. Demand-Side-Response (DSR)

- Quelle: `Explicit DSR.csv`, je Zone bis zu 8 "Price Bands" mit Kapazität
  (MW) und Aktivierungspreis (€/MWh).
- **Implementierung:** je Preisband ein eigener `Generator`
  (`DSR_{zone}_band{n}`), `p_nom_extendable=False`, `p_min_pu=0`,
  `p_max_pu=1`, `marginal_cost = Aktivierungspreis`. DSR wird also
  modelliert wie eine zusätzliche, günstige Erzeugungsquelle, die sich
  aktiviert, sobald der Marktpreis ihren Aktivierungspreis erreicht/
  übersteigt (ökonomischer Dispatch, kein separates Gebotsverfahren) —
  entspricht dem im `OPEN_QUESTIONS_AUTHORS.md` erwähnten Fix "Load →
  Generator with economic dispatch".
- **Explizit weggelassene Einschränkung** (im Code kommentiert): kein
  Tagesstunden-Limit für DSR-Aktivierung. In der Realität (und vermutlich
  auch im Paper/GenX) kann DSR meist nur eine begrenzte Anzahl Stunden pro
  Tag/Woche aktiviert werden ("kann verschieben, aber nicht permanent
  reduzieren"). Dieses Modell erlaubt DSR-Aktivierung in **beliebig vielen
  Stunden im Jahr**, solange der Preis hoch genug ist — eine
  Überschätzung der DSR-Flexibilität gegenüber einer realistischeren
  Modellierung.
- Keine Rückverschiebung (Lastanstieg zu einem späteren Zeitpunkt) wird
  modelliert — DSR wirkt hier als reine Lastreduktion, nicht als
  Lastverschiebung.

---

## 10. Interconnections / Net Transfer Capacity (NTC)

Zwei alternative Implementierungen, per CLI wählbar:

1. **ERAA-Standard** (`add_interconnections.py`, `--interconnections
   eraa`): Liest akkumulierte HVAC- und HVDC-Transferkapazitäten
   (`Transfer Capacities_ERAA2022_TY2030/{HVAC,HVDC}.csv`), bildet den
   **Jahresdurchschnitt** je Verbindungspaar (statische Kapazität für die
   gesamte Simulation, keine Stundenvarianz trotz stündlicher
   ERAA-Rohdaten!), addiert HVAC+HVDC bei identischem Zonenpaar. Für jede
   Verbindung werden **zwei unidirektionale Links** (A→B und B→A)
   eingefügt, damit asymmetrische Kapazitäten möglich sind.
2. **Paper-NTC** (`paper_interconnections.py`, `--interconnections
   paper`): Liest eine separat gepflegte CSV
   (`NTC_Vergleich_ERAA_Paper_Modell.csv`) mit vom Paper übernommenen
   NTC-Werten, additiv zu bereits vorhandenen Links.

**Übertragungseffizienz:** `efficiency=1.0` (verlustfrei) bei beiden
Varianten — explizit als "paper-konform" kommentiert.

**Country-Level-Max-Limits** (`add_max_limits.py`, optional
zuschaltbar, Standard AN): zusätzliche Brutto-Import-/Export-Obergrenze
pro Zone, aber **nur für die Zonen, für die ERAA diese Daten liefert**
(`BG00, CH00, CY00, CZ00, HR00, MT00, NL00, RS00, SK00, UK00` laut
Code-Kommentar — für DE, FR, AT, ES, IT etc. existiert kein solches
Limit). NL wird bewusst NICHT constraint, weil die verfügbare Kennzahl
eine Netto- statt Brutto-Größe ist.

**Wichtig für den Vergleich:** Die Wahl zwischen ERAA- und
Paper-NTC-Werten war laut Commit-Historie ("Added optional choice...",
später "changed to only be able to simulate Paper NTC values bc of
mix-up beforehand") bereits Gegenstand von Unsicherheit im Projekt selbst
— ob die SI-Tabellenwerte des Papers 1:1 den ERAA-Rohdaten entsprechen
oder zusätzlich bearbeitet wurden, ist eine offene Autoren-Frage
(`OPEN_QUESTIONS_AUTHORS.md`, Punkt A.3).

---

## 11. Optimierungsmodell

- **Solver:** Gurobi (`Method=2` Barrier, `Crossover=0`, `DualReductions=0`,
  `BarConvTol` typischerweise `1e-4`–`1e-5`).
- **Formulierung:** lineares Programm (kein Mixed-Integer) — **keine
  Unit-Commitment-Logik**: keine Mindeststillstands-/Mindestlaufzeiten,
  keine Anfahrkosten, keine binären Ein/Aus-Zustände für konventionelle
  Kraftwerke. Jeder Generator ist stufenlos zwischen 0 und `p_nom`
  regelbar.
- **Keine Rampenraten-Constraints** (`ramp_limit_up`/`down` nicht gesetzt).
- **Keine Reserve-/Ancillary-Services-Modellierung** (Regelleistung,
  Schwungmasse etc. bleiben außen vor).
- **Keine Netzengpässe innerhalb einer Zone** (Kupferplatten-Annahme pro
  Zone/Land bzw. Zonen-Gruppe).
- **Keine Übertragungsverluste** (`efficiency=1.0` bei allen Links).
- **Keine Kapazitätserweiterung** (`p_nom_extendable` nirgends gesetzt,
  alle Kapazitäten sind fix — reine Dispatch-Optimierung für den
  ERAA-Zieljahresbestand 2030, keine Investitionsentscheidung).
- **Zielfunktion:** minimale Gesamtsystemkosten über alle Snapshots
  (Standard-PyPSA-Zielfunktion: Summe `marginal_cost × Erzeugung` über
  alle Komponenten und Stunden).
- **Marktpreis:** die Dualvariable (`marginal_price`) der
  Leistungsbilanz-Nebenbedingung je Bus/Zone und Snapshot — Standard-LMP-
  Interpretation, entspricht vermutlich dem, was das Paper als
  "Strompreis" ausweist (nicht verifiziert, ob GenX dieselbe Definition
  verwendet).
- **`n.consistency_check()`** wird seit 2026-09-02 nach dem Netzaufbau
  aufgerufen (fand zuvor einen Bug: Carrier "DSR" war nicht registriert —
  inzwischen behoben, siehe `CLEANUP_PLAN.md`).

---

## 12. Was bewusst NICHT modelliert wird (Zusammenfassung der Limitationen)

- Keine Monte-Carlo-Variation von Demand/Brennstoffpreisen (nur
  Klimajahr variiert) — größte methodische Abweichung, falls das Paper
  genau das als Kern seiner Sensitivitätsanalyse verwendet.
- Keine Innerhalb-Woche/Tag-Dynamik bei Hydro-Zuflüssen (Gleichverteilung
  über den ERAA-Berichtszeitraum).
- Keine Unit-Commitment-Logik, keine Rampenraten, keine Reserven.
- Keine Netzengpässe/Verluste innerhalb oder zwischen den 23 Modellzonen
  außer den (statischen, jahresdurchschnittlichen) NTC-Grenzen.
- Solar Thermal wird geladen, aber nie ins Modell eingefügt.
- DSR ohne Aktivierungsstunden-Limit (Überschätzung der Flexibilität).
- `market_price_cap` wird berechnet, aber nirgends angewendet (totes
  Datum).
- Zieljahr für Kapazitäten ist hart auf 2030 verdrahtet
  (`06_filter_and_accu_PEMMCD_National_Estimates.py`); der
  `target_year`-Parameter in `build_network()` wirkt NUR auf die
  Kostenberechnung (`gather_global_params.py`), nicht auf die
  Kapazitätsdaten selbst — ein latenter Widerspruch, falls jemand
  `target_year != 2030` übergibt, ohne das zu wissen.
- CO2-Preis, CCGT-Wirkungsgrad, CCGT-VOM und Lignite-Brennstoffpreis sind
  trotz vorhandener CSV-Lade-Infrastruktur **fest auf Paper-konforme
  Werte verdrahtet** (CSV-Inhalt wird an diesen Stellen ignoriert, nicht
  nur als Fallback für fehlende Daten benutzt).
- Biomasse-Grenzkosten (30 €/MWh) sind reine Annahme ohne
  Quellenverweis.

---

## 13. Bekannte offene Fragen (siehe `OPEN_QUESTIONS_AUTHORS.md` für Details)

1. Exakter Klimajahr-Ziehungsbereich (Paper: 1982–2016 vs. 1987–2016;
   Code: 1982–2015 im alten Default).
2. Exakte Länderzuordnung der hypothetischen Zonen Baltic/Adriatic/Other
   Europe im Paper (Code-Zuordnung siehe Abschnitt 3 oben, aber nicht
   gegen SI-Text verifiziert).
3. Ob Paper-NTC-Werte 1:1 aus ERAA übernommen oder angepasst wurden.
4. Exakte DSR-Kostenkurve/Gebotslogik im Paper/GenX (Code-Implementierung
   siehe Abschnitt 9).
5. Herkunft der historischen Zeitreihen für die Kovarianzmatrix
   (1990–2021) im Paper — im Code nicht reproduziert (siehe Abschnitt 4,
   "kein Monte-Carlo über ökonomische Parameter").
6. Tatsächlicher Wert für Biomasse-/Other-Res-Brennstoffkosten im Paper.
7. Herkunft der angenommenen Speicherkapazität (MWh) für Hydro-Reservoirs
   im Paper.
8. Bestätigung VOLL = 3.000 €/MWh (im Code bereits so umgesetzt).

---

## 14. Für den Chat-Abgleich: worauf besonders zu achten ist

Beim Abgleich mit dem Paper-Volltext/Supplementary Info sind aus
Code-Sicht folgende Stellen am ehesten geeignet, echte methodische
Abweichungen aufzudecken (nicht nur Implementierungsdetails):

- Abschnitt 4 (fehlende ökonomische Monte-Carlo-Variation) — vermutlich
  die größte Lücke.
- Abschnitt 7 (Gleichverteilung der Hydro-Zuflüsse über Wochen/Tage) —
  falls GenX/das Paper eine feinere zeitliche Auflösung für
  Hydro-Zuflüsse verwendet.
- Abschnitt 9 (DSR ohne Stunden-Limit) — falls das Paper eine explizite
  Aktivierungsdauer-Beschränkung nennt.
- Abschnitt 5 (Gas+Others-non-renewable- bzw. Biomasse+Others-renewable-
  Aggregation) — Annahme "paper-konform", aber nicht anhand des
  Supplements verifiziert.
- Abschnitt 10 (statische Jahresdurchschnitts-NTC statt stündlicher NTC-
  Werte, obwohl ERAA stündliche Daten liefert) — falls das Paper
  zeitlich variable Interconnection-Kapazitäten verwendet.
