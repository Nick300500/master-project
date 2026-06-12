''' 
In diesem Skript soll das PyPSA-Netz aufgebaut werden, indem die Gebotszonen als Knoten und die Interconnections
Lines definiert werden.
Diese Daten gehen aus den .csvs, abliegend in folder 04_accumulated_data_per_node hervor, 
welche in 04_accumulate_interconnections.py erstellt wurden.

Zuerst sollen alle Knoten definiert werden. Danach werden die Lines zwischen Ihnen definiert, 
wobei die Kapazitäten der Interconnections als Gewichtung der Lines dienen. Daraufhin werden 
'''

import pypsa
import pandas as pd
from pathlib import Path

# Funktion zum Hinzufügen von Bussen aus einer CSV-Datei
def add_buses_from_csv(network: pypsa.Network, nodes_filepath: Path):
    """
    Fügt dem PyPSA-Netzwerk Busse aus einer CSV-Datei hinzu.
    Die CSV-Datei muss eine Spalte 'Bidding Zone' enthalten.
    """
    nodes_df = pd.read_csv(nodes_filepath)
    # Füge alle Busse gleichzeitig hinzu (madd ist effizienter als eine Schleife)
    # Sicherstellen, dass jeder Bus nur einmal hinzugefügt wird
    network.add("Bus", nodes_df["Bidding Zone"].unique(), carrier="AC")
    print(f"Added {len(network.buses)} buses to the network.")

# Funktion zum Hinzufügen von Links aus einer CSV-Datei
def add_links_from_csv(network: pypsa.Network, links_filepath: Path, AC_DC: str):
    """
    Fügt dem PyPSA-Netzwerk Links (Interconnectoren) hinzu.
    Sucht nach Export- und Import-Paaren in den Spalten und setzt p_max_pu / p_min_pu.
    """
    # CSV ohne Header laden, da Metadaten in den ersten Zeilen stehen
    df = pd.read_csv(links_filepath, header=None, low_memory=False)
    
    # Daten-Spalten identifizieren (Spalte 0 & 1 sind Metadaten wie Jahr/Woche)
    data_cols = df.columns[2:]
    from_zones = df.iloc[10, data_cols].values
    to_zones = df.iloc[11, data_cols].values
    
    # Zeitreihen extrahieren (ab Zeile 16) und auf Snapshots mappen
    ts_data = df.iloc[16:, data_cols].astype(float).reset_index(drop=True)
    
    # Daten auf die Länge der Snapshots kürzen (um z.B. eine 8761. Zeile am Ende der CSV zu ignorieren)
    ts_data = ts_data.iloc[:len(network.snapshots)]
    ts_data.index = network.snapshots

    processed_cols = set()
    for i, col_idx in enumerate(data_cols):
        if col_idx in processed_cols:
            continue
        
        b0, b1 = from_zones[i], to_zones[i]
        
        # Suche die Gegenrichtung (Import) in den anderen Spalten
        import_series = pd.Series(0.0, index=network.snapshots)
        for j, other_col_idx in enumerate(data_cols):
            if from_zones[j] == b1 and to_zones[j] == b0:
                import_series = ts_data.iloc[:, j]
                processed_cols.add(other_col_idx)
                break
        
        export_series = ts_data.iloc[:, i]
        # Da ERAA-Daten Kapazitäten als positive Werte angeben, nehmen wir das Maximum beider Richtungen
        p_nom = max(export_series.max(), import_series.max())
        if p_nom == 0: p_nom = 1.0 # Vermeidung von Division durch Null
        
        network.add("Link", 
                    f"{b0}-{b1}_{AC_DC}", 
                    bus0=b0, 
                    bus1=b1, 
                    p_nom=p_nom,
                    p_max_pu=export_series / p_nom,
                    p_min_pu=-import_series / p_nom,
                    carrier=AC_DC)
        
        processed_cols.add(col_idx)
    print(f"Added {len(network.links)} links to the network.")

# Pfade definieren
base_path = Path("01_data/04_accumulated_data_per_node")
nodes_file = base_path / "ERAA 2022 PEMMDB National Estimates/TY 2030.csv"
links_file_AC = base_path / "Transfer capacities/Transfer Capacities_ERAA2022_TY2030/HVAC.csv" # Stelle sicher, dass der Dateiname stimmt
links_file_DC = base_path / "Transfer capacities/Transfer Capacities_ERAA2022_TY2030/HVDC.csv"
# Initialisiere das PyPSA-Netzwerk
EU_GRID = pypsa.Network()

#Snapshots definieren
snapshots = pd.date_range("2030-01-01 00:00", "2030-12-31 23:00", freq="h")
EU_GRID.set_snapshots(snapshots)

# Rufe die Funktion auf, um die Busse hinzuzufügen 
add_buses_from_csv(EU_GRID, nodes_file)

# Rufe die Funktion auf, um die Links (Interconnections) hinzuzufügen
add_links_from_csv(EU_GRID, links_file_AC, "AC")
add_links_from_csv(EU_GRID, links_file_DC, "DC")

#Speichere das Grid als .nc Datei
EU_GRID.export_to_netcdf("03_states_of_the_grid/EU_GRID_links_and_buses_2030.nc")

print("\nAktuelle Busse im Netzwerk:")
print(EU_GRID.buses)

print("\nAktuelle Links im Netzwerk:")
print(EU_GRID.links)
EU_GRID.plot()
# Printe p_nom aus der statischen Tabelle und Durchschnittswerte der Zeitreihen aus links_t
print("\nDetailprüfung der Links (Durchschnittswerte der Zeitreihen):")
for link in EU_GRID.links.index:
    p_nom = EU_GRID.links.loc[link, 'p_nom']
    # Zeitreihen liegen in links_t
    p_max_mean = EU_GRID.links_t.p_max_pu[link].mean()
    p_min_mean = EU_GRID.links_t.p_min_pu[link].mean()
    
    if "AC" in link:
        print(f"AC Link {link}: p_nom = {p_nom:.2f}, p_max_pu (avg) = {p_max_mean:.2f}, p_min_pu (avg) = {p_min_mean:.2f}")
    elif "DC" in link:
        print(f"DC Link {link}: p_nom = {p_nom:.2f}, p_max_pu (avg) = {p_max_mean:.2f}, p_min_pu (avg) = {p_min_mean:.2f}")