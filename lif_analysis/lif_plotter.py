"""
lif_plotter_flex.py
===================
Flexibles Plot-Skript für LIF-Messdaten.
"""

# Funktion: 
"""
Konfiguration am Anfang des Skripts:
  - X_COL    : Spalte für die X-Achse
  - Y_COL    : Spalte für die Y-Achse
  - GROUP_COL: Spalte für Farb- und Symbol-Kodierung (dritte Größe)
  - Filter   : Wertebereiche für X, Y und GROUP

Verfügbare Spalten (typisch):
  'master_piezo_off_set_V'   Piezo-Spannung [V]
  'current_mA'               Master-Strom [mA]
  'master_temperature_C'     Master-Temperatur [°C]
  'wl_mean_m'                Wellenlänge [m]

Beispiel-Konfigurationen:
  λ vs. Piezo, Farbe = Strom:
      X_COL     = 'master_piezo_off_set_V'
      Y_COL     = 'wl_mean_m'
      GROUP_COL = 'current_mA'

  λ vs. Strom, Farbe = Piezo:
      X_COL     = 'current_mA'
      Y_COL     = 'wl_mean_m'
      GROUP_COL = 'master_piezo_off_set_V'

  λ vs. Temperatur, Farbe = Piezo:
      X_COL     = 'master_temperature_C'
      Y_COL     = 'wl_mean_m'
      GROUP_COL = 'master_piezo_off_set_V'
"""

import os
import sys
import json
import subprocess
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.ticker import ScalarFormatter
from pathlib import Path

# Projektpfad einbinden
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import utils.file_utils as fu

subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

# ================================================================
# KONFIGURATION – hier anpassen
# ================================================================

COMMENT   = "temperature-3"       # im Dateinamen

# --- Achsen ---
X_COL     = 'master_temperature_C'                # X-Achse
Y_COL     = 'wl_mean_m'                 # Y-Achse
GROUP_COL = 'master_piezo_off_set_V'    # Farbe + Symbol (dritte Größe)
""" 
time_s, piezo_V, wl_mean_m, wl_std_m, wl_err_m, master_current_A, master_temperature_C, master_power, master_piezo_off_set_V, 
amplif_current_A, amplif_temperature_C, amplif_power, daq_lif_signal_V, daq_lif_std_V, lia_R, lia_X, lia_Y, lia_theta_deg 
"""

# --- Fehlerbalken ---
# Option A: Spaltenname für absolute Fehler (aus dem CSV)
# Option B: Float für relativen Fehler (z.B. 0.001 = 0.1%)
# Option C: None für keine Fehlerbalken
X_ERR_COL = None
Y_ERR_COL = 'wl_std_m'

# --- Filter: None = kein Filter, sonst [min, max] ---
FILTER = {
    X_COL:     None,          # z.B. [-10, 10]  für Piezo -10 bis +10 V
    Y_COL:     None,          # z.B. [668.5e-9, 668.7e-9]
    GROUP_COL: None,          # z.B. [40, 60]   für Strom 40-60 mA
}

# --- Referenzlinien (Y-Werte in Daten-Einheit, None = keine) ---
REFERENCE_LINES = [
    # {'value': 667.91e-9, 'label': 'Ar I  667.91 nm',  'ls': '--'},
    # {'value': 668.40e-9, 'label': 'Ar II 668.40 nm',  'ls': ':'},
]

# --- Linearer Fit pro Gruppe ---
LINEAR_FIT = True

# --- Colormap ---
COLORMAP = 'tab10'   # 'plasma', 'coolwarm', 'viridis', 'tab10', ...

# --- Plot-Größe ---
FIGSIZE = (11, 7)

# --- Tick-Dichte ---
MAX_X_TICKS = 5
MAX_Y_TICKS = 5

# --- Hysteresis-Mode ---
HYSTERESIS_MODE = False
N_HYSTERESIS_ARROWS = 5

# ================================================================
# Achsenbeschriftungen und Skalierung
# ================================================================

# Einheiten und Skalierung pro Spalte
COL_CONFIG = {
    'time_s': {
        'label':  'Zeit [s]',
        'scale':  1.0,
        'format': '{:.3f}',
        'short':  'time',
    },
    'master_piezo_off_set_V': {
        'label':  'Piezo-Spannung [V]',
        'scale':  1.0,
        'format': '{:.1f}',
        'short':  'piezo',
    },
    'master_current_mA': {
        'label':  'Master-Strom [mA]',
        'scale':  1.0,
        'format': '{:.0f}',
        'short':  'Im',
    },
    'amplif_current_A': {
        'label':  'Amplifier-Strom [A]',
        'scale':  1.0,
        'format': '{:.0f}',
        'short':  'Ia',
    },
    'master_temperature_C': {
        'label':  'Master-Temperatur [°C]',
        'scale':  1.0,
        'format': '{:.3f}',
        'short':  'Tm',
    },
    'amplif_temperature_C':{
        'label':  'Amplifier-Temperatur [°C]',
        'scale':  1.0,
        'format': '{:.3f}',
        'short':  'Ta',
    },
    'wl_mean_m': {
        'label':  'Wellenlänge [nm]',
        'scale':  1e9,
        'format': '{:.4f}',
        'short':  'wl',
    },
    'wl_std_m': {
        'label':  'λ Std [pm]',
        'scale':  1e12,
        'format': '{:.3f}',
        'short':  'wl_std',
    },
}

def get_cfg(col):
    '''Gibt COL_CONFIG für col zurück, mit Fallback für unbekannte Spalten.'''
    return COL_CONFIG.get(col, {
        'label':  col,
        'scale':  1.0,
        'format': '{:.3f}',
        'short':  col,
    })


# ================================================================
# Hilfsfunktionen
# ================================================================

def read_header(filepath: Path) -> dict:
    with open(filepath, 'r', encoding='utf-8') as f:
        first_line = f.readline()
        if not first_line.startswith('# Header-Lines:'):
            return {}
        n_header = int(first_line.split(':')[-1].strip())
        header_lines = [first_line] + [f.readline() for _ in range(n_header - 1)]
    for line in header_lines:
        if line.startswith('# JSON_META:'):
            return json.loads(line.split('# JSON_META:', 1)[1].strip())
    return {}


def load_csv(filepath: Path):
    meta = read_header(filepath)
    with open(filepath, 'r', encoding='utf-8') as f:
        n_header = int(f.readline().split(':')[-1].strip())
    df = pd.read_csv(filepath, sep='\t', skiprows=n_header, index_col=0)
    return df, meta


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    '''Filtert DataFrame nach Wertebereichen.'''
    mask = pd.Series(True, index=df.index)
    for col, bounds in filters.items():
        if bounds is None:
            continue
        if col not in df.columns:
            print(f"  WARNUNG: Spalte '{col}' nicht im DataFrame – Filter ignoriert")
            continue
        lo, hi = bounds
        mask &= (df[col] >= lo) & (df[col] <= hi)
        n_before = len(df)
        n_after  = mask.sum()
        print(f"  Filter '{col}' [{lo}, {hi}]: "
              f"{n_before} → {n_after} Zeilen")
    return df[mask].copy()


def make_plot_filename(csv_path: Path, x_col: str, y_col: str) -> Path:
    '''Erstellt PNG-Dateiname aus CSV-Name + Achseninformation.'''
    stem     = csv_path.stem
    x_short  = get_cfg(x_col)['short']
    y_short  = get_cfg(y_col)['short']
    suffix   = f"_{y_short}-{x_short}"
    comment  = f"_{COMMENT}.png"
    return csv_path.parent / (stem + suffix + comment)

def set_axis_ticks(ax, max_x_ticks: int = 8, max_y_ticks: int = 6):
    '''Reduziert die Tick-Dichte auf beiden Achsen auf übersichtliche Werte.'''
    ax.xaxis.set_major_locator(ticker.MaxNLocator(nbins=max_x_ticks, steps=[1,2,5,10]))
    ax.yaxis.set_major_locator(ticker.MaxNLocator(nbins=max_y_ticks, steps=[1,2,5,10]))

def build_piezo_style(group_values: list, colormap: str = 'tab10') -> dict:
    '''
    Erstellt Farb- und Symbol-Zuordnung für Piezo-Spannung als GROUP_COL.
    - V=0   → schwarz, Kreis 'o', Fit durchgezogen
    - ±|V|  → gleiche Farbe, Symbol-Paar (gefüllt/ungefüllt)
    - alle anderen Fits → gestrichelt

    Returns dict: { piezo_wert: {'color': ..., 'marker': ..., 'linestyle': ...} }
    '''
    # Symbol-Paare für +V / -V (gefüllt / ungefüllt)
    MARKER_PAIRS = [
        ('^', 'v'),   # Dreieck oben / unten
        ('s', 'D'),   # Quadrat / Raute
        ('P', 'X'),   # Plus / Kreuz (gefüllt)
        ('p', 'h'),   # Pentagon / Hexagon
        ('*', 'H'),   # Stern / Hexagon 2
    ]

    cmap   = plt.get_cmap(colormap)
    styles = {}

    # Alle Betragsgruppen (ohne 0)
    abs_vals = sorted(set(abs(v) for v in group_values if v != 0))

    for i, abs_v in enumerate(abs_vals):
        color          = cmap(i % 10)
        marker_pos, marker_neg = MARKER_PAIRS[i % len(MARKER_PAIRS)]

        # Positiver Wert
        pos = +abs_v
        if any(np.isclose(v, pos) for v in group_values):
            styles[pos] = {'color': color, 'marker': marker_pos, 'linestyle': '--'}

        # Negativer Wert
        neg = -abs_v
        if any(np.isclose(v, neg) for v in group_values):
            styles[neg] = {'color': color, 'marker': marker_neg, 'linestyle': '--'}

    # V = 0
    if any(np.isclose(v, 0) for v in group_values):
        zero_key = next(v for v in group_values if np.isclose(v, 0))
        styles[zero_key] = {'color': 'black', 'marker': 'o', 'linestyle': '-'}

    return styles

def add_hysteresis_arrows(ax, x: np.ndarray, y: np.ndarray, color, n_arrows: int = 5):
    '''Zeichnet Richtungspfeile entlang der Hysterese-Kurve.'''
    step = max(1, len(x) // (n_arrows + 1))
    for i in range(step, len(x) - 1, step):
        dx = x[i+1] - x[i]
        dy = y[i+1] - y[i]
        ax.annotate('',
            xy        = (x[i] + dx*0.5, y[i] + dy*0.5),
            xytext    = (x[i],          y[i]),
            arrowprops= dict(
                arrowstyle = '->',
                color      = color,
                lw         = 2.0,
            ),
        )

# ================================================================
# Plot-Funktion
# ================================================================

def plot_flex(df: pd.DataFrame,
              x_col: str,
              y_col: str,
              group_col: str       = None,
              x_err_col: str       = None, 
              y_err_col: str       = None,
              reference_lines: list= None,
              linear_fit: bool     = True,
              colormap: str        = 'plasma',
              figsize: tuple       = (12, 7),
              save_path: str       = None,
              show: bool           = True,
              ) -> plt.Figure:
    '''
    Flexibler Plot: y_col vs. x_col, gruppiert nach group_col.
    Farbe + Symbol kodieren die dritte Größe (group_col).

    Parameters
    ----------
    df             : DataFrame mit Messdaten
    x_col          : Spaltenname X-Achse
    y_col          : Spaltenname Y-Achse
    group_col      : Spaltenname für Farb/Symbol-Kodierung
    y_err_col      : Spaltenname für Fehlerbalken (optional)
    reference_lines: Liste von {'value', 'label', 'ls'} in Y-Daten-Einheit
    linear_fit     : linearen Fit pro Gruppe einzeichnen
    colormap       : matplotlib Colormap Name
    figsize        : Figure-Größe
    save_path      : Speicherpfad für PNG
    show           : Plot anzeigen
    '''
    # Konfiguration für die drei Spalten
    x_cfg   = get_cfg(x_col)
    y_cfg   = get_cfg(y_col)

    # Skalierte Werte
    df = df.copy()
    df[f'_x']   = df[x_col]   * x_cfg['scale']
    df[f'_y']   = df[y_col]   * y_cfg['scale']

    def calc_err(col_name, err_val, scale):
        if err_val is None:
            return np.zeros(len(df))
        if isinstance(err_val, (int, float)):
            # Relativer Fehler: Wert * Prozent
            return (df[col_name] * scale) * err_val
        if isinstance(err_val, str) and err_val in df.columns:
            # Absoluter Fehler aus Spalte
            return df[err_val] * scale
        return np.zeros(len(df))
    
    df['_xerr'] = calc_err(x_col, x_err_col, x_cfg['scale'])
    df['_yerr'] = calc_err(y_col, y_err_col, y_cfg['scale'])

    # Gruppen
    if group_col is not None and group_col in df.columns:
        group_values = sorted(df[group_col].unique())
        grp_cfg = get_cfg(group_col)
        has_groups = True
    else:
        # Erstelle eine Dummy-Gruppe, damit die restliche Schleife funktioniert
        group_values = ['All Data']
        grp_cfg = {'format': '{}', 'label': 'Dataset', 'scale': 1.0}
        has_groups = False
    n = len(group_values)

    # Farben und Symbole
    if has_groups and group_col == 'master_piezo_off_set_V':
        piezo_styles = build_piezo_style(group_values, colormap)
        use_piezo_style = True
    else:
        use_piezo_style = False
        cmap    = plt.get_cmap(colormap if colormap else 'plasma')
        colors  = [cmap(i % 10) if 'tab' in colormap else cmap(i / max(n-1, 1)) for i in range(n)]
        markers = ['o', 's', '^', 'D', 'v', 'p', '*', 'h', 'X', 'P', '<', '>', '8', 'H', 'd']
        markers = (markers * (n // len(markers) + 1))[:n]

    fig, ax = plt.subplots(figsize=figsize)

    # --- VERHINDERN DER SCIENTIFIC NOTATION / OFFSET ---
    formatter = ScalarFormatter()
    formatter.set_scientific(False) # Deaktiviert die E-Notation (z.B. 1e2)
    formatter.set_useOffset(False)  # Deaktiviert den Offset (z.B. +6.684e2)
    ax.yaxis.set_major_formatter(formatter)
    # Falls es auch auf der X-Achse passiert:
    # ax.xaxis.set_major_formatter(formatter)

    fit_rates  = []

    for i, grp_val in enumerate(group_values):
        # Stil bestimmen
        if use_piezo_style:
            key        = next((v for v in piezo_styles if np.isclose(v, grp_val)), None)
            col        = piezo_styles[key]['color']    if key else 'black'
            marker     = piezo_styles[key]['marker']   if key else 'o'
            fit_ls     = piezo_styles[key]['linestyle'] if key else '-'
        else:
            col        = colors[i]
            marker     = markers[i]
            fit_ls     = '--'

        # Daten filtern (oder alle nehmen, falls keine Gruppen)
        if has_groups:
            df_g = df[df[group_col] == grp_val]
            grp_label = grp_cfg['format'].format(grp_val)
        else:
            df_g = df
            grp_label = "Total"
        
        if not HYSTERESIS_MODE: 
            df_g = df_g.sort_values(x_col)

        x = df_g['_x'].values
        y = df_g['_y'].values
        yerr = df_g['_yerr'].values
        xerr = df_g['_xerr'].values

        # Datenpunkte mit X- und Y-Fehlern
        ax.errorbar(
            x, y,
            xerr       = xerr if (x_err_col is not None) else None,
            yerr       = yerr if (y_err_col is not None) else None,
            fmt        = f'{marker}-',
            color      = col,
            markersize = 14,
            linewidth  = 0.0,
            capsize    = 2,
            elinewidth = 0.8,
            label      = grp_label,
            zorder      = 3,
        )

        if HYSTERESIS_MODE: 
            ax.plot(x, y,
                    color       = col, 
                    linewidth   = 2.0, 
                    linestyle   = '-',
                    alpha       = 0.8, 
                    zorder      = 1,
                    )
            add_hysteresis_arrows(ax, x, y, color=col, n_arrows=N_HYSTERESIS_ARROWS)

        # Linearer Fit
        if linear_fit and len(x) >= 2:
            coeffs  = np.polyfit(x, y, 1)
            x_fit   = np.linspace(x.min(), x.max(), 100)
            y_fit   = np.polyval(coeffs, x_fit)
            ax.plot(x_fit, y_fit,
                    color     = col,
                    linewidth = 2.0,
                    linestyle = fit_ls,
                    alpha     = 0.5,
                    zorder    = 2)
            fit_rates.append({
                'group':  grp_val,
                'rate':   coeffs[0],
                'offset': coeffs[1],
            })


    # zusätzliche Legende
    ax.legend(
        title=grp_cfg['label'], 
        fontsize=15, 
        title_fontsize=15, 
        loc='upper left', 
        bbox_to_anchor=(1.01,1),
        frameon=True, 
        edgecolor='gray'
    )

    # Referenzlinien
    if reference_lines:
        for ref in reference_lines:
            y_ref = ref['value'] * y_cfg['scale']
            ax.axhline(y_ref,
                       color     = 'black',
                       linewidth = 1.0,
                       linestyle = ref.get('ls', '--'),
                       alpha     = 0.7,
                       zorder    = 1)
            ax.text(
                0.1, y_ref+0.02,
                ref['label'],
                transform = ax.get_yaxis_transform(),
                fontsize  = 18,
                va        = 'center',
                color     = 'black',
                alpha     = 1.0,
            )

    # Fit-Raten Textbox
    if linear_fit and fit_rates:
        rates     = [r['rate'] for r in fit_rates]
        rate_mean = np.mean(rates) * 1e3   # nm/mA → pm/mA
        rate_std  = np.std(rates)  * 1e3   # nm/mA → pm/mA
        label_text = x_cfg['label']
        if '[' in label_text and ']' in label_text: 
            x_unit = label_text.split('[')[1].split(']')[0]
        else: 
            x_unit = x_cfg.get('short', 'unit')
        ax.text(
            1.03, 0.1,                                             # Position der Textbox
            f"Lin. Fit:\n"
            f"  Mittel: {rate_mean:.3f} pm/{x_unit}\n"
            f"  Std:    {rate_std:.3f} pm/{x_unit}",
            transform = ax.transAxes,
            fontsize  = 13,
            va        = 'top',
            bbox      = dict(boxstyle='round', facecolor='white', alpha=0.85)
        )

    ax.set_xlabel(x_cfg['label'],   fontsize=20)                            # Textgröße Achsenbeschriftung und Ticks
    ax.set_ylabel(y_cfg['label'],   fontsize=20)
    ax.tick_params(axis='both', labelsize=18, direction='in', length=1, width=0.2)
    ax.set_title(
        f"{y_cfg['label'].split('[')[0].strip()} vs. "
        f"{x_cfg['label'].split('[')[0].strip()}\n", 
        # f"({grp_cfg['label'].split('[')[0].strip()} farbkodiert)",
        fontsize=12, fontweight='bold'
    )
    ax.grid(True, linestyle='--', alpha=0.4)

    set_axis_ticks(ax, max_x_ticks=MAX_X_TICKS, max_y_ticks=MAX_Y_TICKS)

    plt.tight_layout()
    fig.subplots_adjust(right=0.75)

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"Plot gespeichert: {save_path}")

    if show:
        plt.show(block=True)
    plt.close(fig)
    return fig


# ================================================================
# Main
# ================================================================

if __name__ == '__main__':

    # --- Datei auswählen ---
    filepath = fu.select_file(filter="CSV Dateien (*.csv);;Alle Dateien (*)")
    if filepath is None:
        print("Keine Datei ausgewählt – Abbruch.")
        sys.exit()

    filepath = Path(filepath)
    print(f"\nDatei: {filepath.name}")

    # --- Laden ---
    df, meta = load_csv(filepath)
    print(f"Geladen: {len(df)} Zeilen, Spalten: {list(df.columns)}")

    if meta:
        print(f"Metadaten: {list(meta.keys())}")

    # --- Filtern ---
    print("\nFilter:")
    df = apply_filters(df, FILTER)
    print(f"Nach Filter: {len(df)} Zeilen\n")

    if df.empty:
        print("WARNUNG: DataFrame nach Filter leer – Abbruch.")
        sys.exit()

    # --- Fehlende Spalten prüfen ---
    for col in [X_COL, Y_COL, GROUP_COL]:
        if col is not None and col not in df.columns:
            print(f"FEHLER: Spalte '{col}' nicht im DataFrame.")
            print(f"Verfügbare Spalten: {list(df.columns)}")
            sys.exit()

    # --- Ausgabepfad ---
    save_path = make_plot_filename(filepath, X_COL, Y_COL)
    print(f"Plot wird gespeichert als: {save_path.name}\n")

    # --- Plot ---
    plot_flex(
        df              = df,
        x_col           = X_COL,
        y_col           = Y_COL,
        group_col       = GROUP_COL,
        x_err_col       = X_ERR_COL,
        y_err_col       = Y_ERR_COL,
        reference_lines = REFERENCE_LINES,
        linear_fit      = LINEAR_FIT,
        colormap        = COLORMAP,
        figsize         = FIGSIZE,
        save_path       = str(save_path),
        show            = True,
    )