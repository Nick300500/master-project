''' 
In diesem Skript werden die Generatoren zum bestehenden PyPSA-Netzwerk hinzugefügt.
Die installierten Kapazitäten (p_nom) werden direkt aus der transponierten 
National Estimates Datei (TY 2030.csv) gelesen.
'''

import pypsa
import pandas as pd
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Pfade definieren
BASE_PATH = Path("01_data/04_accumulated_data_per_node")
CAPACITIES_FILE = BASE_PATH / "ERAA 2022 PEMMDB National Estimates/TY 2030.csv"
NETWORK_INPUT = Path("03_states_of_the_grid/EU_GRID_links_and_buses_2030.nc")
NETWORK_OUTPUT = Path("03_states_of_the_grid/EU_GRID_with_generators_2030.nc")

def add_generators_from_ty_csv(network: pypsa.Network, csv_path: Path):
    """
    Liest p_nom Werte aus der CSV und fügt Generatoren zum Netzwerk hinzu.
    Namenskonvention: {Bus}_{Technologie}
    """
    if not csv_path.exists():
        logger.error(f"Kapazitätsdatei nicht gefunden: {csv_path}")
        return

    # CSV laden
    df = pd.read_csv(csv_path)
    
    # Spaltennamen bereinigen (entfernt führende/nachfolgende Leerzeichen)
    df.columns = df.columns.str.strip()

    if "Bidding Zone" not in df.columns:
        logger.error("Spalte 'Bidding Zone' fehlt in der CSV. Prüfe die Transponierung in Skript 05.")
        return

    # Spalten identifizieren, die keine Generatoren sind
    # 'Demand' und Spalten mit 'Energy Storage' (meist MWh) werden hier ignoriert
    exclude_keywords = ["Bidding Zone", "Demand", "Energy Storage"]
    tech_cols = [c for c in df.columns if not any(k in c for k in exclude_keywords)]

    logger.info(f"Folgende Technologien werden verarbeitet: {tech_cols}")

    for _, row in df.iterrows():
        bus = str(row["Bidding Zone"]).strip()

        # Prüfen, ob der Bus im geladenen Netzwerk existiert
        if bus not in network.buses.index:
            logger.debug(f"Bus {bus} nicht im Netzwerk. Überspringe...")
            continue

        for tech in tech_cols:
            p_nom = pd.to_numeric(row[tech], errors='coerce')

            # Nur Generatoren mit einer Kapazität > 0 hinzufügen
            if p_nom > 0:
                gen_name = f"{bus}_{tech}"
                network.add(
                    "Generator",
                    gen_name,
                    bus=bus,
                    p_nom=p_nom,
                    carrier=tech,
                    marginal_cost=0.0 # Platzhalter für Grenzkosten
                )

    logger.info(f"Hinzufügen abgeschlossen. Anzahl Generatoren im Netz: {len(network.generators)}")

if __name__ == "__main__":
    if not NETWORK_INPUT.exists():
        logger.error(f"Eingangsnetzwerk nicht gefunden: {NETWORK_INPUT}. Bitte 70_grid_build_up.py zuerst ausführen.")
    else:
        n = pypsa.Network(str(NETWORK_INPUT))
        add_generators_from_ty_csv(n, CAPACITIES_FILE)
        
        # Export des erweiterten Netzwerks
        NETWORK_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        n.export_to_netcdf(str(NETWORK_OUTPUT))
        logger.info(f"Erweitertes Netzwerk gespeichert unter: {NETWORK_OUTPUT}")
