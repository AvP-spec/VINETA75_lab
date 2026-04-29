import pandas as pd
from datetime import datetime
from pathlib import Path, PurePath
import os
import sys
import subprocess
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter, ScalarFormatter

##### import project related moduls ####
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import utils.file_utils as fu
from utils.terminal_styler import TerminalColours

class PlotLaserStatus(TerminalColours):
    def __init__(self):
        plt.style.use('seaborn-v0_8-muted')
        
        self._init_figure_wlm()

    def _init_figure_wlm(self):
        # Figure wlm: Wavelength vs Piezo (1x1)
        self.fig_wlm, self.ax_wlm_piezo = plt.subplots(figsize=(10, 6))
        self.ax_wlm_piezo.set_title("Laser wavelength")
        self.ax_wlm_piezo.set_xlabel("Piezo Voltage (V)")
        self.ax_wlm_piezo.set_ylabel("Wavelength (nm)")
        self.ax_wlm_piezo.grid(True, linestyle='--')
        ## set y axis
        y_formatter = ScalarFormatter(useOffset=False)
        y_formatter.set_scientific(False)
        self.ax_wlm_piezo.yaxis.set_major_formatter(FormatStrFormatter('%.4f'))
        self.ax_wlm_piezo.yaxis.set_major_formatter(y_formatter)


    def plot_wlm_piezo(self, df, label, **plt_kwargs):
        """Plots Wavelength vs Piezo Voltage from the provided DataFrame."""

        required_columns = ["master_piezo_off_set_V", "wlm_wavelength"]
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            print(f"{self.RED}{self.__class__.__name__} Error:{self.RESET}")
            print(f"Columns {self.MAGENTA}{missing_cols}{self.RESET} not in df.columns")

            return
        
        plot_params = {
            'marker':'o',
            'markersize': 6,
            # set open marker with bg colour
            'markerfacecolor': self.ax_wlm_piezo.get_facecolor(),
            # set marker colour as line colour
            'markeredgecolor': 'auto',
            'linestyle': '-',
            'linewidth': 1,
            'label': label
        }

        plot_params.update(plt_kwargs)
    
        line, = self.ax_wlm_piezo.plot(df["master_piezo_off_set_V"],
                                       df["wlm_wavelength"]*1e9,
                                       #label=label,
                                       **plot_params
                                       )
        self.ax_wlm_piezo.legend(
            loc='upper left',
            bbox_to_anchor=(1.02, 1),
            borderaxespad=0,
        )
        # Refresh the layout and canvas
        self.fig_wlm.tight_layout()
        self.fig_wlm.canvas.draw()




if __name__ == "__main__":
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)

    plt.ion()
    status_plot = PlotLaserStatus()
    plt.show()

    def test_plot():
        file_path = fu.select_file()
        file_name = Path(file_path).stem
        df, header = fu.read_file(file_path)
        status_plot.plot_wlm_piezo(df, label=file_name)
        plt.pause(0.1)
    


    for i in range(3):
        test_plot()

    print("All files processed. Close the plot window to exit.")
    plt.ioff()
    plt.show()
    print("test ended")

    

