import pandas as pd
from datetime import datetime
from pathlib import Path, PurePath
import os
import sys
import subprocess
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter, ScalarFormatter
from matplotlib.lines import Line2D

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
        self._last_label = None
        self._last_color = None
        self.clr_cycle = [
            '#e41a1c', '#377eb8', '#4daf4a', '#ff7f00', 
            '#984ea3', '#000000', '#a65628', '#008080'
            ]
        self.clr_counter = 0
        self.alpha = 0.7
        self.file_entries = [] # for plot_monitoring()
        self._init_figure_wlm()
        self._init_figure_monitoring()

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

    def _init_figure_monitoring(self):
        self.fig_mon, self.axs = plt.subplots(2, 2, num="Monitoring Status", figsize=(12, 10))
        self.fig_mon.suptitle("Lasers Parameters over Time", fontsize=14)
        alpha = self.alpha
        self.ax_map = {
            'current': {
                'ax': self.axs[0, 0], 
                'title': 'Laser Current', 
                'ylabel': 'Current (mA)',
                'lines': [
                    {'col': 'master_current_A', 'suffix': 'M Real',
                     'plt_kwargs': {
                                    'ls': '-',  'marker': 'o', 'ms': 5, 
                                    'mfc': self.axs[0,0].get_facecolor(), 'mew': 1.2
                                    }
                    },

                    {'col': 'master_set_current_A', 'suffix': 'M Set',
                     'plt_kwargs': {
                                    'ls': '-', 'marker': '', 'lw': 1
                                    }
                    },

                    {'col': 'amplif_current_A', 'suffix': 'A Real',    
                     'plt_kwargs': { 
                                     'ls': '--',  'marker': '^', 'ms': 5, 
                                     'alpha': alpha
                                     }
                    },

                    {'col': 'amplif_set_current_A',
                     'plt_kwargs': {   
                                    'ls': '--', 'marker': '', 'lw': 1, 
                                    'alpha': alpha
                                    }
                    },
                ]
            },

            'temp': {
                'ax': self.axs[0, 1], 
                'title': 'Temperature', 
                'ylabel': 'Temp (K)',
                'lines': [
                    {'col': 'master_temperature_C', 'suffix': 'M Real',
                     'plt_kwargs': {
                                    'ls': '',  'marker': 'o', 'ms': 4
                                    }
                     },

                    {'col': 'master_set_temperature_C', 
                     'plt_kwargs': {  
                                     'ls': '-', 'marker': '', 'ms': 5, 
                                     'mfc': self.axs[0,1].get_facecolor(), 
                                     'mew': 1.2
                                    }
                     },

                    {'col': 'amplif_temperature_C', 'suffix': 'A Real',    
                     'plt_kwargs': {   
                                     'ls': '--', 'marker': '^', 'ms': 5, 
                                     'alpha': alpha
                                    }
                     },

                    {'col': 'amplif_set_temperature_C', 'suffix': 'A Set',
                     'plt_kwargs': {     
                                    'ls': '--', 'marker': '', 
                                    'alpha': alpha
                                    }
                     },
                ]
            },

            'pd': {
                'ax': self.axs[1, 0], 
                'title': 'Photodiode', 
                'ylabel': 'PD Current (A)',
                'lines': [
                    {'col': 'master_photo_diode_current_A', 'suffix': 'M PD',
                     'plt_kwargs': {
                                    'ls': '-', 'marker': 'o', 'ms': 4, 
                                    'mfc': self.axs[1,0].get_facecolor() 
                                    }
                     },

                    {'col': 'amplif_photo_diode_current_A', 'suffix': 'A PD',
                     'plt_kwargs': {
                                    'ls': '--', 'marker': '^', 'ms': 4, 
                                    'alpha': alpha
                                    }
                     },
                ]
            },

            'power': {
                'ax': self.axs[1, 1], 
                'title': 'Output Power', 
                'ylabel': 'Power (W)',
                'lines': [
                    {'col': 'master_power', 'suffix': 'M Pwr',
                     'plt_kwargs': {
                     'ls': '-', 'marker': 'o', 'ms': 4, 
                     'mfc': self.axs[1,1].get_facecolor()
                     }
                     },

                    {'col': 'amplif_power', 'suffix': 'A Pwr',
                     'plt_kwargs': {   
                                    'ls': '--', 'marker': '^', 'ms': 4, 
                                    'alpha': alpha
                                    }
                     },
                ]
            }
        }

        for key in self.ax_map:
            ax = self.ax_map[key]['ax']
            ax.set_title(self.ax_map[key]['title'])
            ax.set_ylabel(self.ax_map[key]['ylabel'])
            ax.set_xlabel("Time (s)")
            ax.grid(True, linestyle='--')

        self.fig_mon.tight_layout(rect=[0, 0.03, 1, 0.95])


    def _get_color(self, label, color_arg=None):
        if color_arg is not None:
            return color_arg
        
        if label == self._last_label:
            return self._last_color
        
        color = self.clr_cycle[self.clr_counter % len(self.clr_cycle)]
        self.clr_counter += 1
        self._last_label = label
        self._last_color = color
        return color
    

    def plot_wlm_piezo(self, df, label, color=None, **plt_kwargs):
        """Plots Wavelength vs Piezo Voltage from the provided DataFrame."""

        required_columns = ["master_piezo_off_set_V", "wlm_wavelength"]
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            print(f"{self.RED}{self.__class__.__name__} Error:{self.RESET}")
            print(f"Columns {self.MAGENTA}{missing_cols}{self.RESET} not in df.columns")
            return
        
        color_ = color or plt_kwargs.get('color') or self._get_color(label)
        plot_params = {
            'marker':'o',
            'markersize': 6,
            # set open marker with bg colour
            'markerfacecolor': self.ax_wlm_piezo.get_facecolor(),
            # set marker colour as line colour
            'markeredgecolor': color_,
            'linestyle': '-',
            'linewidth': 1,
            'label': label,
            'color': color_,
        }

        plot_params.update(plt_kwargs)

        
        #plot_params.update({'color': color_})  
    
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


    def plot_monitoring(self, df, label, color=None):

        color_ = color or self._get_color(label)

        for key in self.ax_map:
            ax_info = self.ax_map[key]
            ax = ax_info['ax']

            for line in ax_info['lines']:
                col = line['col']
                if col in df.columns:
                    plot_param = line['plt_kwargs'].copy()
                    plot_param['color'] = color_
                    ax.plot(
                        df['start_time'],
                        df[col],
                        **plot_param,
                    )
        if (label, color_) not in self.file_entries:
            self.file_entries.append((label, color_))

        self._monitoring_legends()

        self.fig_mon.canvas.draw()

    def _monitoring_legends(self):
        """
        Gemei function
        Dynamically adjusts the subplot area to fit legends on the right.
        Colorizes file names and stacks legends vertically.
        """
        from matplotlib.lines import Line2D

        # --- 1. DATA STYLE LEGEND (Top Right) ---
        style_proxies = [
            Line2D([0], [0], color='gray', ls='-', marker='o', mfc='none', 
                   label='Master Real', markeredgewidth=1.2),
            Line2D([0], [0], color='gray', ls='-', label='Master Set'),
            Line2D([0], [0], color='gray', ls='--', marker='^', 
                   label='Amp Real', alpha=0.5),
            Line2D([0], [0], color='gray', ls='--', label='Amp Set', alpha=0.5)
        ]

        # Use fig_mon.legend to make it global
        self.style_leg = self.fig_mon.legend(
            handles=style_proxies, 
            loc='upper left', 
            bbox_to_anchor=(0.82, 0.95), 
            fontsize='small', 
            title="Data Styles",
            frameon=True
        )

        # --- 2. FILE LEGEND (Colored Text) ---
        file_proxies = [
            Line2D([0], [0], color=c, lw=0, label=lbl) 
            for lbl, c in self.file_entries
        ]

        self.file_leg = self.fig_mon.legend(
            handles=file_proxies,
            loc='upper left',
            bbox_to_anchor=(0.82, 0.75),
            title="Files",
            handlelength=0,
            handletextpad=0,
            frameon=True
        )

        # Colorize the text labels
        for text, entry in zip(self.file_leg.get_texts(), self.file_entries):
            text.set_color(entry[1])
            text.set_weight('bold')

        # --- DYNAMIC ADJUSTMENT ---
        # 1. Force a draw to calculate legend sizes accurately
        self.fig_mon.canvas.draw()
        
        # 2. Get the bounding box of the legend in pixels, then convert to figure coordinates
        # We use the wider of the two legends
        leg1_box = self.style_leg.get_window_extent()
        leg2_box = self.file_leg.get_window_extent()
        max_width_px = max(leg1_box.width, leg2_box.width)
        
        # Convert pixel width to a fraction of the figure width
        fig_width_px = self.fig_mon.get_window_extent().width
        # Add a small margin (e.g., 10% of the legend width)
        margin = (max_width_px / fig_width_px) + 0.05
        
        # 3. Adjust subplots: 'right' defines the edge of the grid (0 to 1)
        right_limit = 1.0 - margin
        
        # Apply the layout. tight_layout must be called first, then subplots_adjust
        self.fig_mon.tight_layout(rect=[0, 0.03, right_limit, 0.95])






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
        status_plot.plot_monitoring(df,label=file_name)
        plt.pause(0.1)
    

    for i in range(2):
        test_plot()

    # print("All files processed. Close the plot window to exit.")
    plt.ioff()
    plt.show()
    # print("test ended")

    

