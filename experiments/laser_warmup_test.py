"""
laser_warmup_test.py
====================
Messung der Laser-Parameter ohne Warmup
Speichert DataFrame + Plot mit Metadaten

"""

# ----------------------------------------------------------------
# Imports
# ----------------------------------------------------------------
import sys
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
import getpass

# Projektpfad einbinden
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from managers.lif import LIFManager
import utils.file_utils as fu
from utils.terminal_styler import TerminalColours

tc = TerminalColours()

subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

print(f"{tc.BLUE}============= laser_warmup_test.py ============={tc.RESET}\n \n")

# ----------------------------------------------------------------
# Konfiguration – hier anpassen
# ----------------------------------------------------------------
BASE_PATH = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/")

FILE_BASE_NAME = "laser_warmup"              # Dateiname-Basis
COMMENT = "measuring laser warmup"

N_MEASUREMENTS   = 50
SLEEP            = 2.0

# ----------------------------------------------------------------
# Pfade vorbereiten
# ----------------------------------------------------------------
data_dir = fu.make_data_dir(
    base_path = BASE_PATH,
    base_name = "laser_warmup",         # manuelle Eingabe
)
file_path_csv  = fu.make_data_file_name(
    data_dir  = data_dir,
    base_name = FILE_BASE_NAME,
    extension = "csv",
)
plots_dir = fu.make_data_dir(
    base_path = BASE_PATH, 
    base_name = "laser_warmup/plots",   # manuelle Eingabe
)
file_path_plot = fu.make_data_file_name(
    data_dir  = plots_dir,
    base_name = FILE_BASE_NAME,
    extension = "png",
)

print(f"Daten werden gespeichert in:\n  {data_dir}")
print(f"CSV:  {file_path_csv.name}")
print(f"Plot: {file_path_plot.name}\n")

# ----------------------------------------------------------------
# Messung
# ----------------------------------------------------------------
r_man = LIFManager()
df = None

try: 
    r_man.laser_on()
    # no laser warmup time!

    # Metadaten zusammenstellen
    scan_start_time = datetime.now()
    meta = {
        "operator":         getpass.getuser(),
        "script":           Path(__file__).name, 
        "scan_start_time":  str(scan_start_time), 
        "comment":          COMMENT, 
        "n_measurements":   N_MEASUREMENTS, 
        "sleep":            SLEEP,
    }
    meta.update(r_man.get_device_state_meta())

    df = r_man.measure_laser_warmup(
        n_measurements  = N_MEASUREMENTS, 
        sleep           = SLEEP,
        plot            = True, 
        save_path       = str(file_path_plot),
    )
    meta["duration_total_s"] = (datetime.now() - scan_start_time).total_seconds()
finally: 
    r_man.laser_off()
    r_man.disconnect_all()

# ----------------------------------------------------------------
# Speichern
# ----------------------------------------------------------------
if df is not None and not df.empty:
    fu.save_dataframe(
        df        = df,
        file_path = file_path_csv,
        metadata  = meta,
        sep       = "\t",
        index     = True,
        silent    = False,
    )
else:
    print("WARNUNG: Kein DataFrame zum Speichern – Messung leer oder abgebrochen")