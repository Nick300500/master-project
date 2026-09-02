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
   `06_filter_and_accu_PEMMCD_National_Estimates.py` in der Pipeline
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
   `03_climate_accumulate_data_per_node.py` heute für 2022 annimmt (ein
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

## Einordnung für die eigene Pipeline

Die Befürchtung war berechtigt: **die Formate/Kategorien ändern sich nicht
nur graduell, sondern strukturell, und zwar fast jedes Jahr.** Ein reines
"Jahres-Parameter statt hart codiert 2022" (wie ursprünglich für Phase 4
geplant) würde **nicht ausreichen**, um dieselbe Pipeline unverändert auf
ERAA 2025 oder 2026 laufen zu lassen — insbesondere weil:

- die PEMMDB-Datenquelle (Kernstück von Schritt 06 der Pipeline) ab 2024 in
  ihrer bisherigen Form nicht mehr existiert,
- die Klimadaten-Ordnerstruktur, auf der `01_excel_to_csv.py` und
  `03_climate_accumulate_data_per_node.py` aufbauen, sich mindestens zweimal
  geändert hat (2022→2023, 2023→2024),
- selbst *innerhalb* eines ERAA-Jahrgangs Nachträge/Versionsstände (v1/v2,
  Change Logs) vorkommen.

**Empfehlung:** Phase 4 nicht als "ERAA-Jahr als Parameter" verstehen,
sondern als **Adapter-Schicht pro ERAA-Jahrgang**: ein stabiler Kern
(`build_network.py`, `gather_global_params.py`, `load_zone_capacities.py`,
`load_timeseries.py` — die alle mit dem bereits vereinheitlichten Format in
`01_data/04b_accumulated_data_per_node/` arbeiten) bleibt unverändert; davor
kommt pro ERAA-Jahrgang ein eigenes, austauschbares Set von
Einlese-/Umformungs-Skripten (heute: 01–06), das auf das jeweilige
Quellformat zugeschnitten ist und in dasselbe Zielschema überführt. Um das
für 2025 konkret zu bauen, muss zuerst wirklich heruntergeladen und
reingeschaut werden, was in "Economic and Technical Investment Parameters"
und "Other Data" für 2025 tatsächlich drinsteckt (v. a. wo die
PEMMDB-Nachfolgedaten stecken) — das ist der nötige nächste Rechercheschritt,
sobald die eigentliche Phase-4-Arbeit beginnt.
