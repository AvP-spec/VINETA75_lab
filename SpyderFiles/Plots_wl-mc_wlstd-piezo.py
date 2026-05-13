"""
Analyse der Master-Strom-Scans.

Liest alle drei Unterordner:
  master_scan_n01_wlm-av-off   (40 Dateien, 1 Scan,  average OFF)
  master_scan_n1_wlm-av-on     (10 Dateien, 1 Scan,  average ON)
  master_scan_n5_wlm-av-on     (10 Dateien, 5 Scans, average ON)

Wellenlänge vs. Master-Strom – Abstimmkurve
  - Mittlere Wellenlänge über alle Piezo-Positionen pro Strom-Schritt
  - Alle drei Datensätze überlagert

Abstimmbreite der Wellenlänge 
  - max-min der Wellenlänge pro Datei in pm
"""

import json
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from pathlib import Path

BASE_PATH = Path(r"/home/erikh/Schreibtisch/Studium/Nextcloud Manz/DATA/")
EXPERIMENT_PATH = "2026-04-21_Andrei_LIF"

EXPERIMENT_DIR = BASE_PATH / EXPERIMENT_PATH
PLOTS_DIR      = EXPERIMENT_DIR / "plots_wl-mc_wlstd-piezo"

SCAN_FOLDERS = [
    {
        "path":    EXPERIMENT_DIR / "master_scan_n01_wlm-av-off",
        "label":   "n=1, avg OFF",
        "n_scans": 1,
        "average": "OFF",
        "color":   "tab:blue",
        "marker":  "o",
        "ls":      "--",
    },
    {
        "path":    EXPERIMENT_DIR / "master_scan_n1_wlm-av-on",
        "label":   "n=1, avg ON",
        "n_scans": 1,
        "average": "ON",
        "color":   "tab:orange",
        "marker":  "s",
        "ls":      "-",
    },
    {
        "path":    EXPERIMENT_DIR / "master_scan_n5_wlm-av-on",
        "label":   "n=5, avg ON",
        "n_scans": 5,
        "average": "ON",
        "color":   "tab:green",
        "marker":  "^",
        "ls":      "-",
    },
]



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
    with open(filepath, "r", encoding="utf-8") as f:
        n_header = int(f.readline().split(":")[-1].strip())
    df = pd.read_csv(filepath, sep="\t", skiprows=n_header, index_col=0)
    return df, meta


def parse_current_mA(filepath: Path) -> float:
    """
    Liest den Master-Strom aus dem Dateinamen.
    Format: HH-MM-SS_mcurrent_NNN_mA.csv → NNN mA
    Fallback: master_set_current aus dem Header.
    """
    match = re.search(r"mcurrent_(\d+)_mA", filepath.stem)
    if match:
        return float(match.group(1))
    return None


def load_folder(folder_cfg: dict) -> pd.DataFrame:
    """
    Lädt alle .csv Dateien aus einem Ordner und gibt einen
    zusammengefassten DataFrame zurück mit Spalten:
      current_mA, wl_mean_nm, wl_std_nm, wl_valid (bool)
    """
    folder_path = folder_cfg["path"]
    csv_files = sorted(folder_path.glob("*.csv"))

    if not csv_files:
        print(f"  WARNUNG: Keine .csv Dateien in {folder_path.name}")
        return pd.DataFrame()

    records = []
    for fp in csv_files:
        try:
            df, meta = load_csv(fp)

            # Master-Strom aus Dateiname
            current_mA = parse_current_mA(fp)
            if current_mA is None:
                # Fallback: aus Header (Betrag wegen negativer Gerätekonvention)
                current_mA = abs(float(meta.get("master_set_current", 0))) * 1000

            # Wellenlänge: nur gültige Werte (> 0)
            wl = df["wlm_wavelength"].values
            valid = wl > 0

            if valid.sum() == 0:
                # Laser unter Schwellstrom – keine Messung
                records.append({
                    "current_mA":  current_mA,
                    "wl_mean_nm":  np.nan,
                    "wl_std_nm":   np.nan,
                    "wl_range_pm": np.nan,
                    "n_valid":     0,
                    "wl_valid":    False,
                    "filename":    fp.name,
                })
                continue

            wl_valid_nm = wl[valid] * 1e9  # m → nm

            # bei n_scans > 1: Mittelwert über alle Scans und Piezo-Positionen
            records.append({
                "current_mA": current_mA,
                "wl_mean_nm": wl_valid_nm.mean(),
                "wl_std_nm":  wl_valid_nm.std(),
                "wl_range_pm":  (wl_valid_nm.max() - wl_valid_nm.min()) * 1e3,  # nm → pm
                "n_valid":    valid.sum(),
                "wl_valid":   True,
                "filename":   fp.name,
            })

        except Exception as e:
            print(f"  FEHLER bei {fp.name}: {e}")

    result = pd.DataFrame(records).sort_values("current_mA").reset_index(drop=True)
    print(f"  {folder_cfg['label']}: {len(result)} Dateien geladen, "
          f"{result['wl_valid'].sum()} mit gültiger Wellenlänge")
    return result




def plot_tuning_curve(
        scan_folders: list = SCAN_FOLDERS,
        plots_dir: Path = PLOTS_DIR,
):
    """
    Erstellt zwei überlagerte Plots:
      A (oben):  Mittlere Wellenlänge [nm] vs. Master-Strom [mA]
      B (unten): Wellenlängen-Streuung [pm] vs. Master-Strom [mA]
    """
    plots_dir.mkdir(parents=True, exist_ok=True)

    datasets = []
    for cfg in scan_folders:
        print(f"Lade {cfg['label']} ...")
        df = load_folder(cfg)
        if not df.empty:
            datasets.append((cfg, df))

    if not datasets:
        print("Keine Daten geladen.")
        return

    fig, axes = plt.subplots(
        2, 1,
        figsize=(11, 8),
        sharex=True,
        gridspec_kw={"hspace": 0.08, "height_ratios": [2, 1]}
    )
    ax_wl  = axes[0]   # Plot A: mittlere Wellenlänge
    ax_std = axes[1]   # Plot B: Streuung

    for cfg, df in datasets:
        valid = df[df["wl_valid"]]
        if valid.empty:
            continue

        valid = valid.iloc[1:]      # <-- der erste wert bei average_off ist ein ausreißer, weil laser noch nicht warm
        if valid.empty: 
            continue

        x   = valid["current_mA"].values
        y   = valid["wl_mean_nm"].values
        err = valid["wl_std_nm"].values * 1e3   # nm → pm für Fehlerbalken
        std = valid["wl_std_nm"].values * 1e3   # nm → pm für Plot B

        ax_wl.errorbar(
            x, y,
            yerr=valid["wl_std_nm"].values,
            color=cfg["color"],
            marker=cfg["marker"],
            markersize=5,
            linewidth=1.4,
            linestyle=cfg["ls"],
            capsize=3,
            capthick=1,
            elinewidth=0.8,
            label=cfg["label"],
            alpha=0.9,
            zorder=3,
        )

        ax_std.plot(
            x, valid["wl_range_pm"].values,
            color=cfg["color"],
            marker=cfg["marker"],
            markersize=4,
            linewidth=1.2,
            linestyle=cfg["ls"],
            label=cfg["label"],
            alpha=0.9,
        )

    ax_wl.set_ylabel("Mittlere Wellenlänge [nm]", fontsize=11)
    ax_wl.legend(fontsize=9, loc="best", framealpha=0.85)
    ax_wl.grid(True, linestyle="--", alpha=0.4)
    ax_wl.tick_params(axis="x", labelbottom=False)

    ax_std.set_xlabel("Master-Strom [mA]", fontsize=11)
    ax_std.set_ylabel("Abstimmbreite λ [pm]\n(max - min über Piezo-Pos.)", fontsize=10)
    ax_std.legend(fontsize=8, loc="lower right", framealpha=0.85)
    ax_std.grid(True, linestyle="--", alpha=0.4)
    # ax_std.set_ylim(bottom=0)

    fig.suptitle(
        "Abstimmkurve Master-Laser\n"
        "A: Wellenlänge vs. Strom   |   B: Piezo-Abstimmbreite vs. Strom",
        fontsize=12, fontweight="bold"
    )
    plt.tight_layout()

    out_path = plots_dir / "master_current_tuning_curve.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\nPlot gespeichert: {out_path}")



if __name__ == "__main__":
    plot_tuning_curve()