import pandas as pd
import os
import sys
import subprocess
from pathlib import Path, PurePath
import matplotlib.pyplot as plt

##### import project related moduls ####
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import utils.file_utils as fu
from utils.terminal_styler import TerminalColours
from lif_analysis.ploter_laser_state import PlotLaserStatus

DATA_PATH = Path("C:/Users/Andrei/Nextcloud/5360.AG_Manz/DATA/2026-04-21_Andrei_LIF/piezo_scan")
tc = TerminalColours()


if __name__ == "__main__":
    subprocess.run('cls' if os.name == 'nt' else 'clear', shell=True)
    print(project_root)
    # print(fu.select_folder()) # for selection of the DATA_PATH

    status_plot = PlotLaserStatus()

    plot_params_ON = {
        'color': 'blue',
        'marker': 'o',
        'markerfacecolor': status_plot.ax_wlm_piezo.get_facecolor(), # open marker
        'markeredgecolor': 'blue',
        'linestyle': '-',
        'linewidth': 1.5
    }   

    plot_params_OFF = {
        'color': 'gray',
        'marker': 'o',
        'markerfacecolor': 'gray',  
        'linestyle': '--',
        'alpha': 0.6                # Сделаем чуть бледнее, так как это "OFF"
    }

    files = DATA_PATH.iterdir()
    for file in files:
        df, header = fu.read_file(file)
        f_name = file.stem
        mc = df['master_current_A'].mean()*1000
        label = file.stem.replace("average_", "")
        label += f" {mc:.1f} mA"
        # print(label)
        plt_kwargs = {}
        if 'ON' in f_name:
            plt_kwargs.update(plot_params_ON)
        elif 'OFF' in f_name:
            plt_kwargs.update(plot_params_OFF)
        else:
            print(f"{tc.RED}{f_name}{tc.RESET} ploting with defoult settings")

        if mc < -60:
            print(label)
            plt_kwargs.update({
                'color': 'tab:pink',
                })


        status_plot.plot_wlm_piezo(df, label=label, **plt_kwargs)


    plt.show()


        
        