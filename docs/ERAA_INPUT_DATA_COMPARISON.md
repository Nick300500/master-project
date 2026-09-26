# ERAA-Input-Daten 2022–2026: Struktur-Vergleich

Stand: 2026-09-02. Quelle: die offiziellen ENTSO-E-"Modelling data"-Seiten
pro Jahrgang (`https://www.entsoe.eu/eraa/{jahr}/modelling-data/`), jeweils
Kategorien/Formate der zum Download angebotenen Dateien. **Hinweis zur
Verlässlichkeit:** Ausgewertet wurden die aktuell live angezeigten
Download-Listen der Seiten — keine tiefere Schema-Prüfung einzelner
Excel-Sheets/CSV-Spalten innerhalb der ZIPs (das wäre nur nach echtem
Download+Diff jeder Datei möglich). Für 2022–2024 zeigt ENTSO-E außerdem oft
nur den *aktuellen* Stand der Seite, nicht zwingend das Original-Release —
Nachträge (z. B. "Hydro Dataset" bei 2023, hinzugefügt 14.03.2024) sind
möglich und teils vermerkt.

## Kategorien-Übersicht je Jahrgang

| Kategorie | 2022 | 2023 | 2024 | 2025 | 2026 (Preliminary) |
|---|---|---|---|---|---|
| Generation/Kapazitäten (PEMMDB) | **PEMMDB National Estimates** (xlsx, 124 KB) | **PEMMDB Generation** (xls, 153 KB) — umbenannt | *nicht mehr als eigene Kategorie sichtbar* | *nicht mehr als eigene Kategorie sichtbar* | *nicht mehr als eigene Kategorie sichtbar* |
| Wirtschafts-/Technik-Parameter | *(vermutlich Teil von PEMMDB oder "Additional Data")* | *(vermutlich Teil von PEMMDB oder "Additional Data")* | **Economic and Technical Investment Parameters** (zip, 177 KB) — NEU als eigene Kategorie | **Economic and Technical Investment Parameters** (zip, 209 KB) | **Economic & Technical Parameters** (xlsx, 401 KB) |
| Klimadaten (Wind/Solar/Hydro) | **Climate Data** (zip, 2 GB) — Wind, Solar, Hydro, Temperatur zusammen | **PECD** (zip, 1.3 MB, klein!) + **Hydro Dataset** (zip, 106 MB, separat, nachträglich hinzugefügt 03/2024) | **PECD - RES** (zip, 734 MB) + **PECD - Weather** (zip, 2 GB) — in zwei Kategorien gesplittet | **PECD** (zip, 1 GB) + **PECD Weather** (zip, 2 GB) | **PECD - RES** (zip, 1 GB) + **PECD - Weather** (zip, 1 GB) |
| Demand | **Demand Dataset** (zip, 2 GB, stündlich) | **Demand Dataset** (zip, 887 MB) — "yearly + peak demand" | **Demand Data** (zip, 701 MB) | **Demand Data** (zip, 432 MB) — Beschreibung betont "Annual electricity demand (TWh) aggregated by geographical area" | **Demand Data** (zip, 2 GB) |
| NTC/Interconnections | **NTC** (zip, 25.7 MB) | **NTC** (zip, 16.7 MB) | **NTCs** (zip, 15 MB) | **NTCs** (zip, 18 MB) | **NTCs** (xlsx, 1 MB — deutlich kleiner/anderes Format als Vorjahre) |
| Flow-Based-Domains | **Flow-Based Domains and CNECs** (zip, 1.1 MB) | **FB Domain CORE Merged** (xls, 1.8 MB) — umbenannt+Formatwechsel | **Flow-Based Domains** (zip, 30 MB) | **FB Domains** (zip, 11 MB) | **FB Domains** (zip, 17 MB) |
| DSR | *(kein eigener Eintrag)* | *(kein eigener Eintrag)* | **iDSR Ratios** (zip, 2 KB) — NEU | *(kein eigener Eintrag laut Fetch)* | *(kein eigener Eintrag laut Fetch)* |
| Dashboard-Rohdaten | *(kein eigener Eintrag)* | *(kein eigener Eintrag)* | **Dashboard Raw Data** (zip, 1.1 MB) — NEU | **Dashboard - Raw Data** (zip, 18 MB) | **Dashboard Data Raw** (zip, 2 MB) |
| Sonstiges/Common | **Additional Data** (zip, 5.7 MB) | **Additional Data** (zip, 1.2 MB) | **Common Data** (zip, 81 KB) + **Other Data** (zip, 11 KB) — in zwei Kategorien gesplittet | **General Information - Common Data** (zip, 82 KB) + **Other Data** (zip, 98 KB) | **Common Data** (xlsx, 20 KB) + **Other Data** (zip, 70 KB) |
| Versionierung/Changelog | *(keine)* | *(keine)* | *(keine)* | **Data Change Log** (txt) — NEU | Explizit als "v1/v2"-Iterationen im Pre-CfE-Bereich markiert |
| Doku (Explanatory Note etc.) | *(nicht separat gelistet)* | **Data Collection Guidelines** (pdf) | **Data Collection Guidelines** (pdf) + **Post Consultation Explanatory Note** (pdf) | **Data Collection Guidelines** (pdf) + **Explanatory Note on Data Release** (pdf) | **Data Collection Guidelines**, **Explanatory Note**, **Post CfE Release Note**, **Call-for-Evidence Responses** |

## Was das konkret bedeutet (Kernbefunde)

1. **PEMMDB als eigene, benannte Kategorie verschwindet nach 2023.** 2022/2023
   gab es eine klar identifizierbare "PEMMDB National Estimates"/"PEMMDB
   Generation"-Datei — genau die Quelle, die
   `aggregate_national_estimates.py` in der Pipeline
   verarbeitet. Ab 2024 taucht "PEMMDB" auf der Download-Seite nicht mehr als
   eigener Eintrag auf; die Generatoren-/Kapazitätsdaten stecken vermutlich
   jetzt in "Economic and Technical Investment Parameters" und/oder "Other
   Data" — das müsste vor einer 2025er-Anpassung durch echtes Herunterladen
   und Reinschauen bestätigt werden, ist aber allein von der Kategorien-Seite
   her ein Bruch, kein bloßes Update.
2. **Klimadaten wurden mehrfach umstrukturiert:** 2022 ein Bündel ("Climate
   Data" inkl. Hydro), 2023 aufgeteilt in "PECD" (klein) + separates "Hydro
   Dataset" (groß, nachträglich ergänzt), ab 2024 wieder anders aufgeteilt in
   "PECD - RES" vs. "PECD - Weather". Das exakte Aufteilungsschema, das
   `aggregate_climate_data.py` heute für 2022 annimmt (ein
   Ordner mit Wind/Solar/Hydro-Unterordnern), ist also nicht die Norm über
   die Jahrgänge hinweg — es war sogar innerhalb von 2023 selbst nicht
   stabil (Hydro kam nachträglich als separates Datenpaket dazu).
3. **Neue Kategorien tauchen jahrgangsweise auf** (iDSR Ratios 2024,
   Dashboard Raw Data ab 2024, Data Change Log ab 2025) — das ERAA-Datenpaket
   wird nicht nur inhaltlich aktualisiert, sondern strukturell erweitert.
4. **NTC-Format wechselt sogar den Dateityp:** 2022–2025 durchgehend ZIP,
   2026 (Preliminary) nur eine einzelne XLSX-Datei (1 MB) — ein deutlich
   anderes Format als in den Vorjahren.
5. **2024–2026 sind sich untereinander deutlich ähnlicher** als 2022/2023 es
   zu 2024 sind — d. h. es gab vermutlich einen bewussten
   Strukturumbau bei ENTSO-E zwischen ERAA 2023 und ERAA 2024 (neue,
   seitdem relativ stabile Kategorien: Common Data, Dashboard Raw Data,
   Demand Data, Economic & Technical Parameters, FB Domains, NTCs, Other
   Data, PECD-RES, PECD-Weather).

## Reale Schema-Prüfung: heruntergeladene ERAA-2025-Dateien (2026-09-02)

Der Nutzer hat die ERAA-2025-Pakete heruntergeladen
(`C:\Users\Nick Herrmann\OneDrive\Desktop\Master Projekt\ERAA Data 2025`).
Im Gegensatz zum Abschnitt oben (nur Download-Seiten-Kategorien) wurden
hier die tatsächlichen Dateien geöffnet und mit dem 2022er-Format
verglichen, das die aktuelle Pipeline erwartet. Ergebnis: **die
Strukturänderungen sind noch tiefgreifender als die Kategorien-Ebene
vermuten ließ.**

### PEMMDB-Nachfolger gefunden: `GenerationCapacities.csv` (Dashboard Raw Data)

Das ist die Antwort auf die offene Frage aus dem oberen Abschnitt — die
PEMMDB-Kapazitätsdaten stecken jetzt in der Dashboard-Rohdaten-Kategorie,
nicht in "Economic and Technical Investment Parameters" (das enthält nur
Kosten-/Technik-Parameter je Technologie, keine Zonen-Kapazitäten). Aber
das Format ist grundlegend anders:

- **Long-Format statt Wide-Format**: Spalten sind `data_version, Target
  year, Market_Node, Technology, Technology_Simplified,
  Operational_Status, Value` — eine Zeile pro (Zone, Technologie, Status),
  nicht eine Zeile pro Zone mit einer Spalte pro Technologie wie in
  `TY 2030.csv`. `zone_capacities.py` (Spalten-Mapping,
  `pd.read_csv(path, index_col=0)`) kann das nicht ohne Pivot verarbeiten.
- **Drei Datenversionen in einer Datei gemischt**: `data_version` enthält
  `"ERAA 2024"`, `"ERAA 2025 pre-CfE"` UND `"ERAA 2025 final"` — ohne
  Filterung auf die richtige Version würde man Kapazitäten mehrfach zählen
  oder veraltete Werte verwenden.
- **`Operational_Status`-Aufsplittung**: Derselbe Zonen/Technologie-Eintrag
  kann mehrfach vorkommen, aufgeteilt nach Status wie `"Available on
  market"`, `"Out of market/cannot be used for adequacy"`,
  `"Non-market"`, `"Mothballed"` etc. (12 verschiedene Werte gefunden).
  Beispiel DE00/2028/Gas: 24.900 MW "Available on market" **plus separat**
  900 MW "Out of market/cannot be used for adequacy" — eine naive Summe
  über alle Zeilen würde nicht-dispatchbare Kapazität mit einrechnen. Das
  Modell muss jetzt explizit entscheiden, welche Status-Werte als
  Dispatch-Kapazität zählen.
- **Deutlich feinere Technologie-Kategorien**: 44 `Technology`-Werte statt
  der ~15 TY2030-Spalten von 2022. Solar ist z. B. in 6 Unterkategorien
  aufgeteilt (`Solar (PV)`, `Solar roof-top PV`, `Solar PV rooftop
  industrial/residential`, `Solar PV utility non-tracking/tracking`, dazu
  `Solar (thermal)`, `Solar thermal with/without storage`), Wind Offshore
  in `fixed`/`floating`, Biomasse/Sonstige-EE in `Biofuel`, `Small
  biomass`, `Waste`, `Geothermal`, `Marine`, `Not defined or splitting not
  known RES`. Das heutige `COLUMN_MAP` in `zone_capacities.py`
  (1:1-Zuordnung Spaltenname→interner Key) reicht als Konzept nicht mehr —
  es braucht eine Viele-zu-eins-Aggregationsregel pro Modell-Kategorie.
- **Vier Zieljahre in einer Datei**: `Target year` ∈ {2028, 2030, 2033,
  2035} über die `Target year`-Spalte filterbar (statt vier getrennter
  `TY {jahr}.csv`-Dateien) — an sich eine Verbesserung, aber ein weiterer
  Parsing-Unterschied.
- **Neue Zonencodes**: u. a. `ITN1` (Italien Nord), `LUG1` (Luxemburg) —
  Codes, die nicht dem einfachen `XX00`-Muster entsprechen, auf dem die
  aktuellen `normalize_zone()`/`extract_zone_from_path()`-Regexes in allen
  06/04/03-Skripten beruhen. Durchgerechnet: `ITN1` und `LUG1` fallen bei
  den aktuellen Regex-Mustern (`[A-Z]{2}\d{2}` mit Wortgrenzen, danach
  `[A-Z]{2}`-Fallback) durch **beide** Erkennungsstufen durch und würden
  auf den ungefilterten Rohstring zurückfallen — ein konkretes,
  nachvollziehbares Bug-Risiko bei einer 1:1-Wiederverwendung der
  bestehenden Skripte, kein bloß theoretisches.

### Demand-Zeitreihen: Klimajahre jetzt anonymisiert

`Demand data/Demand timeseries/{zone}_Demand_total_{jahr}_National
Trends.csv` hat Spalten `Date, Month, Day, Hour, WS01, WS02, ..., WS36` —
36 "Weather Scenario"-Spalten statt der 2022-Konvention mit dem echten
Kalenderjahr als Spaltenname (z. B. `"2012"`). Um weiterhin ein
bestimmtes historisches Wetterjahr auszuwählen, braucht es zusätzlich die
neu mitgelieferte `PECD - weather/WeatherScenarios_Mapping.xlsx` als
Übersetzungstabelle WS-Code → Kalenderjahr — eine Indirektionsebene, die
es 2022 nicht gab. `_find_climate_col()` in `timeseries.py` (sucht
Spalte per `str(col).startswith(climate_year)`) funktioniert mit diesem
Schema nicht mehr.

### NTC: von flacher CSV zu interaktivem Excel-Dashboard

`NTCs/NTCs Consolidated TY2030.xlsx` hat vier Sheets (`Drop-down values`,
`Limits`, `HVAC`, `HVDC`). Die eigentlichen Daten liegen in
`HVAC`/`HVDC`, im Kern strukturell ähnlich zu 2022 (From-Zeile, To-Zeile,
dann stündliche Werte je gerichteter Verbindung), aber:
- als Excel-Workbook mit Array-Formeln und Dropdown-Filterlogik
  ausgeliefert (`Drop-down values`-Sheet enthält z. B.
  `=MID(CELL("filename"),...)`-Formeln), nicht als reine Werte-CSV,
- Verbindungen sind als benannte Paare in einer Header-Zeile organisiert
  (`"CH00-FR00"`, `"CH00-ITN1"`, ...) statt in zwei getrennten
  Metadaten-Zeilen (From-Zone-Zeile / To-Zone-Zeile) wie in der 2022er
  `HVAC.csv`.
- Der aktuelle Parser `_load_accumulated_ntc()` (liest mit `header=None`
  feste Zeilenindizes 10/11 für From/To) müsste komplett neu geschrieben
  werden, nicht nur angepasst.

### Common Data.xlsx: viel granularere Technologie-Charakteristika

Nachfolger von `Additional Data/Annex 1 - Input data` (Fuel Cost,
Efficiency, VOM, CO2). Statt einem Wert pro grober Kategorie (z. B. ein
Wirkungsgrad für "Hard Coal") liefert ERAA 2025 jetzt **pro
Technologie-Untervariante** (z. B. 5 Hard-Coal-Vintages: "old 1/old
2/New/CCS", 8 Gas-Vintages von "conventional old" bis "CCGT CCS")
jeweils eigene Effizienz-, CO2-Faktor-, VOM- UND zusätzlich **Min-Time-
On/Off**-Werte (Hinweis: ERAA selbst rechnet demnach intern mit
Unit-Commitment-artigen Mindestlaufzeiten — die eigene Pipeline ignoriert
das bewusst, siehe `MODEL_DOCUMENTATION_FOR_PAPER_COMPARISON.md`
Abschnitt 11). Zusätzlich neue Sheets `Hydro Normal/Dry/Wet` und `Hydro
Yearly Classification` — ein Trocken-/Normal-/Nassjahr-Szenariokonzept für
Hydrologie, das es 2022 in dieser Form nicht gab. `global_params.py`
müsste nicht nur neue Pfade, sondern eine neue Aggregationsentscheidung
treffen (welche Vintage-Variante als "der" Wert je Grobkategorie gilt).

### Fazit der Schema-Prüfung

Die Vermutung aus dem theoretischen Kategorien-Vergleich oben bestätigt
sich in der Praxis vollständig, und zwar deutlicher: **kein einziges** der
für die Pipeline zentralen Dateiformate (PEMMDB-Kapazitäten, NTC,
Klimajahr-Kennzeichnung in Demand) ist strukturell mit 2022 kompatibel.
Das ist keine Frage von Spaltenumbenennungen, sondern von
Long-vs-Wide-Format, CSV-vs-Excel-Dashboard, und einer neuen
Versions-/Status-Filterebene, die es 2022 nicht gab. Die in Abschnitt
"Einordnung für die eigene Pipeline" unten vorgeschlagene Adapter-Schicht
ist also nicht optional, sondern zwingend — ein Versuch, die 2022er
Lese-Skripte per Parameter auf 2025 umzubiegen, würde an praktisch jeder
Stelle scheitern.

## Einordnung für die eigene Pipeline

Die Befürchtung war berechtigt: **die Formate/Kategorien ändern sich nicht
nur graduell, sondern strukturell, und zwar fast jedes Jahr.** Ein reines
"Jahres-Parameter statt hart codiert 2022" (wie ursprünglich für Phase 4
geplant) würde **nicht ausreichen**, um dieselbe Pipeline unverändert auf
ERAA 2025 oder 2026 laufen zu lassen — insbesondere weil:

- die PEMMDB-Datenquelle (Kernstück von Schritt 06 der Pipeline) ab 2024 in
  ihrer bisherigen Form nicht mehr existiert,
- die Klimadaten-Ordnerstruktur, auf der `excel_to_csv.py` und
  `aggregate_climate_data.py` aufbauen, sich mindestens zweimal
  geändert hat (2022→2023, 2023→2024),
- selbst *innerhalb* eines ERAA-Jahrgangs Nachträge/Versionsstände (v1/v2,
  Change Logs) vorkommen.

**Empfehlung:** Phase 4 nicht als "ERAA-Jahr als Parameter" verstehen,
sondern als **Adapter-Schicht pro ERAA-Jahrgang**: ein stabiler Kern
(`build_network.py`, `global_params.py`, `zone_capacities.py`,
`timeseries.py` — die alle mit dem bereits vereinheitlichten Format in
`01_data/04b_accumulated_data_per_node/` arbeiten) bleibt unverändert; davor
kommt pro ERAA-Jahrgang ein eigenes, austauschbares Set von
Einlese-/Umformungs-Skripten (heute: 01–06), das auf das jeweilige
Quellformat zugeschnitten ist und in dasselbe Zielschema überführt. Um das
für 2025 konkret zu bauen, muss zuerst wirklich heruntergeladen und
reingeschaut werden, was in "Economic and Technical Investment Parameters"
und "Other Data" für 2025 tatsächlich drinsteckt (v. a. wo die
PEMMDB-Nachfolgedaten stecken) — das ist der nötige nächste Rechercheschritt,
sobald die eigentliche Phase-4-Arbeit beginnt.
