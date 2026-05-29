import pandas as pd
import json
import matplotlib.pyplot as plt
from pathlib import Path
import sys

# Projektpfad einbinden
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Importiere deine Plot-Funktion aus deinem Modul
import utils.lif_plots as lp

# ----------------------------------------------------------------
# Konfiguration
# ----------------------------------------------------------------
CSV_FILE_PATH = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/2026-05-29_erikh_LIF/laser_characterization/12-43-25_laser_characterization.csv")

# Neuer Dateiname für den Plot: 
# .stem holt "11-33-44_laser_characterization"
# Dann hängen wir "_extraplot" an und fügen die Endung .png hinzu
SAVE_PLOT_PATH = CSV_FILE_PATH.parent / f"{CSV_FILE_PATH.stem}_filtered-only-40-50-60-70.png"

# ----------------------------------------------------------------
# JSON-Metadaten einlesen
# ----------------------------------------------------------------
meta_data = {}
try:
    with open(CSV_FILE_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('# JSON_META:'):
                # Extrahiere den Teil nach dem Doppelpunkt
                json_string = line.split('# JSON_META:', 1)[1].strip()
                # Wandle den String in ein Python-Dictionary um
                meta_data = json.loads(json_string)
                break # Wir haben das JSON gefunden, Rest der Datei ignorieren
    
    print("Metadaten erfolgreich geladen:")
    print(f"  Operator: {meta_data.get('operator')}")
    print(f"  Step: {meta_data.get('current_step_mA')} mA")
except Exception as e:
    print(f"Fehler beim Lesen der Metadaten: {e}")
    # Fallback-Werte setzen, falls das JSON nicht gelesen werden konnte
    meta_data = {'current_step_mA': 5.0}

# ----------------------------------------------------------------
# 1. CSV Laden
# ----------------------------------------------------------------
# Da deine Datei Metadaten mit '#' am Anfang hat, nutzt pandas 
# standardmäßig comment='#', um diese Zeilen zu ignorieren.
# Achte darauf, ob das Trennzeichen Tabulator ('\t') oder Komma (',') ist.
try:
    df = pd.read_csv(
        CSV_FILE_PATH, 
        sep='\t',          # Falls du in fu.save_dataframe sep='\t' genutzt hast
        comment='#',       # Ignoriert alle Zeilen, die mit # beginnen
        index_col=0        # Falls der Index als erste Spalte gespeichert wurde
    )
    print(f"Datei erfolgreich geladen: {CSV_FILE_PATH.name}")
    print(f"Anzahl Messpunkte: {len(df)}")
except Exception as e:
    print(f"Fehler beim Laden der Datei: {e}")
    exit()

# ----------------------------------------------------------------
# 2. Datenfilterung (Optional)
# ----------------------------------------------------------------
# Hier kannst du fehlerhafte Daten entfernen, bevor du plottest.
# Beispiel: Nur Daten plotten, bei denen die Wellenlänge nicht NaN ist
# df = df.dropna(subset=['wl_mean_m']) 

current_filter = [20.0, 25.0, 30.0, 35.0, 45.0, 55.0, 65.0]
df = df[~df['current_mA'].isin(current_filter)]

print(f"Filterung abgeschlossen. Verbleibende Ströme: {df['current_mA'].unique()}")


# ----------------------------------------------------------------
# 3. Plotten
# ----------------------------------------------------------------
# Jetzt einfach den DataFrame an deine bestehende Funktion übergeben
lp.plot_characterization(
    df=df, 
    CURRENT_STEP_MA=meta_data.get('current_step_ma', 5.0), 
    save_path=str(SAVE_PLOT_PATH), 
    show=True
)