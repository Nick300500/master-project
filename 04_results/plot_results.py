import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

def plot_all_csv_results():
    # Ermittelt den Ordner, in dem dieses Skript liegt
    current_dir = Path(__file__).parent
    csv_files = list(current_dir.glob("*.csv"))

    if not csv_files:
        print(f"Keine CSV-Dateien in {current_dir} gefunden.")
        return

    for csv_file in csv_files:
        try:
            # Daten laden: erste Spalte als Zeitindex, Datumsformate parsen
            df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
            
            if df.empty:
                continue

            # Neues Diagrammfenster erstellen
            fig, ax = plt.subplots(figsize=(12, 6))

            # Spezielle Behandlung für Dispatch-Daten (Flächendiagramm)
            if "dispatch" in csv_file.name.lower():
                df.plot.area(ax=ax, alpha=0.7, title=f"Einsatzplanung: {csv_file.stem}")
                ax.set_ylabel("Leistung [MW]")
            else:
                # Standard-Liniendiagramm für Preise (LMP) etc.
                df.plot(ax=ax, title=f"Zeitreihe: {csv_file.stem}", linewidth=1)
                ax.set_ylabel("Wert")

            ax.set_xlabel("Zeit")
            ax.grid(True, linestyle='--', alpha=0.5)
            plt.tight_layout()
            
            print(f"Diagramm für {csv_file.name} erstellt.")
            plt.show()

        except Exception as e:
            print(f"Fehler beim Plotten von {csv_file.name}: {e}")

if __name__ == "__main__":
    plot_all_csv_results()
