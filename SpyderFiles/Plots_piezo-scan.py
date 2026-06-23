"""
Skript zum Einlesen und Plotten von Lasermessdaten.
Alle .csv Dateien aus dem angegebenen Ordner einlesen und plotten. 
Speichert die Dateien in einem Unterordner plots. 
scan_start_time aus dem Header definiert den absoluten Startzeitpunkt. start_time in Sekunden nach Messbeginn. 
"""

import matplotlib.pyplot as plt
import pandas as pd
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import os

RELATIVE_BASE_PATH = Path(r"/home/erikh/Schreibtisch/Studium/Kurse 6/Bachelor-Arbeit/Data/")
ABS_DIR_PATH = Path.home() / RELATIVE_BASE_PATH

EXPERIMENT_DIR = Path(r"2026-04-21_Andrei_LIF")

DATA_DIR = ABS_DIR_PATH / EXPERIMENT_DIR
 
# Zeitzone, in der die Messung aufgezeichnet wurde
LOCAL_TZ = ZoneInfo("Europe/Berlin")

import sys
from pathlib import Path
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from utils.terminal_styler import TerminalColours
style = TerminalColours()


# ----------------------

def read_header(filepath: Path) -> dict:
    """Liest den JSON_META-Block aus dem Datei-Header."""
    with open(filepath, "r", encoding="utf-8") as f:
        first_line = f.readline()
        if not first_line.startswith("# Header-Lines:"):
            raise ValueError(f"Kein gültiger Header in {filepath.name}")
        n_header = int(first_line.split(":")[-1].strip())
        header_lines = [first_line] + [f.readline() for _ in range(n_header - 1)]
 
    for line in header_lines:
        if line.startswith("# JSON_META:"):
            return json.loads(line.split("# JSON_META:", 1)[1].strip())
 
    raise ValueError(f"Kein JSON_META in {filepath.name}")


def load_csv(filepath: Path) -> tuple[pd.DataFrame, dict]:
    """Liest Header-Metadaten und Messdaten aus einer .csv Datei."""
    meta = read_header(filepath)
    n_header = int(meta.get("Header-Lines", 8))
 
    # Header-Lines direkt aus erster Zeile lesen (zuverlässiger)
    with open(filepath, "r", encoding="utf-8") as f:
        first_line = f.readline()
    n_header = int(first_line.split(":")[-1].strip())
 
    df = pd.read_csv(filepath, sep="\t", skiprows=n_header, index_col=0)
    return df, meta


def make_time_axis(df: pd.DataFrame, meta: dict) -> pd.Series:
    """Berechnet absolute Zeitachse aus scan_start_time (Header) + start_time.
    
    scan_start_time Format: '2026-04-21 09:52:07.123456' (datetime.now(), kein tz-Info)
    → wird als Europe/Berlin Lokalzeit interpretiert.
    """
    if "scan_start_time" not in meta:
        raise KeyError("'scan_start_time' nicht im Header — bitte Messscript anpassen.")
 
    scan_start = datetime.fromisoformat(meta["scan_start_time"]).replace(tzinfo=LOCAL_TZ)
    scan_start_unix = scan_start.timestamp()
 
    return pd.to_datetime(
        scan_start_unix + df["start_time"], unit="s", utc=True
    ).dt.tz_convert(LOCAL_TZ)



def plot_file(filepath: Path, plots_dir: Path):
    """Erstellt Plot für eine einzelne .csv Datei und speichert ihn."""
    df, meta = load_csv(filepath)
    time_dt = make_time_axis(df, meta)
 
    fig, axes = plt.subplots(4, 1, figsize=(10, 12), sharex=True)
    fig.suptitle(filepath.stem, fontsize=13, fontweight="bold")
 
    plot_cfg = [
        ("master_current_A",             "Master Current",           "A",    "tab:blue"),
        ("master_photo_diode_current_A", "Master Photodiode Current", "A",   "tab:orange"),
        ("master_temperature_C",         "Master Temperature",        "°C",  "tab:red"),
        ("master_power",                 "Master Power",              "a.u.","tab:green"),
    ]
 
    for ax, (col, label, unit, color) in zip(axes, plot_cfg):
        ax.plot(time_dt, df[col], color=color, linewidth=1.5, marker="o", markersize=4)
        ax.set_ylabel(f"{label}\n[{unit}]", fontsize=10)
        ax.grid(True, linestyle="--", alpha=0.5)
        ax.tick_params(axis="x", rotation=20)
 
    axes[-1].set_xlabel("Absolute Zeit (Europe/Berlin)", fontsize=11)
 
    plt.tight_layout()
    out_path = plots_dir / f"{filepath.stem}.png"
    plt.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  gespeichert: {out_path.name}")

# -----------------------------

def main():
    csv_files = sorted(DATA_DIR.glob("*.csv"))
    if not csv_files:
        print(f"Keine .csv Dateien gefunden in:\n  {DATA_DIR}")
        return
 
    plots_dir = DATA_DIR / "plots"
    plots_dir.mkdir(exist_ok=True)
    print(f"Verarbeite {len(csv_files)} Datei(en) aus:\n  {DATA_DIR}")
    print(f"Plots werden gespeichert in:\n  {plots_dir}\n")
 
    for filepath in csv_files:
        print(f"→ {filepath.name}")
        try:
            plot_file(filepath, plots_dir)
        except Exception as e:
            print(f"  FEHLER: {e}")
 
    print(f"\n {style.GREEN}Fertig. {len(csv_files)} Plot(s) erstellt.{style.RESET}")
 
 
if __name__ == "__main__":
    os.system('cls' if os.name == 'nt' else 'clear')
    print(f"\n {style.MAGENTA}======= Plots_piezo-scan.py ======={style.RESET}")
    main()

