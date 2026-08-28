# \utils\plt_styler_avp-py
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, ScalarFormatter
from PyQt6 import QtCore

class PlotStyler:

    def __init__(self, font_size=20):
        self.font_size = font_size


    @staticmethod
    def set_scale_steps(ax):
        '''
        Configure axis ticks to follow steps (1, 2, 3, 5)
        '''

        # Define allowed steps for the locator 
        # (e.g., intervals like 0.1, 0.2, 0.5 or 10, 20, 30, 50)
        allowed_steps = [1, 2, 3, 5, 10]
        # Apply independent locators for each axis to ensure proper scaling
        ax.yaxis.set_major_locator(MaxNLocator(steps=allowed_steps))
        ax.xaxis.set_major_locator(MaxNLocator(steps=allowed_steps))

        # useOffset=False prevents Matplotlib from subtracting 
        # a base value from the axis
        formatter = ScalarFormatter(useOffset=False)
        ax.yaxis.set_major_formatter(formatter)
        ax.xaxis.set_major_formatter(formatter)

        return None


    def _get_font_profile(self, size=None, profile='default'):
        """
        Internal factory to generate font configuration dictionaries.
        """
        base = size if size else self.font_size
        profiles = {
            'default': {
                'font.size': base,
                'axes.labelsize': base,
                'axes.titlesize': base * 1.2,
                'xtick.labelsize': base * 0.8,
                'ytick.labelsize': base * 0.8,
                'legend.fontsize': base * 0.9,
            },

            'compact': {
                'font.size': base,
                'axes.labelsize': base * 0.9,
                'axes.titlesize': base * 1.0,
                'xtick.labelsize': base * 0.7,
                'ytick.labelsize': base * 0.7,
                'legend.fontsize': base * 0.8,
            },

        }

        # Explicit check for the profile key existence
        if profile not in profiles:
            print(f"Notice: Style profile '{profile}' not found. Falling back to 'default'.")
            return profiles['default']
            
        return profiles[profile]
    

    def set_plt_font_style(self, size=None, profile='default'):
        """
        Sets global matplotlib configuration (rcParams). 
        Explicitly named with 'plt' to indicate global scope.
        """
        config = self._get_font_profile(size, profile)
        plt.rcParams.update(config)
        # Synchronize instance state if a specific size is passed
        if size:
            self.font_size = size


    def apply_font_style(self, fig, size=None, profile='default'):
        """
        Directly modifies objects within an existing Figure instance.
        """
        config = self._get_font_profile(size, profile)
        
        for ax in fig.get_axes():
            ax.title.set_size(config['axes.titlesize'])
            ax.xaxis.label.set_size(config['axes.labelsize'])
            ax.yaxis.label.set_size(config['axes.labelsize'])
            for tick in ax.get_xticklabels() + ax.get_yticklabels():
                tick.set_fontsize(config['xtick.labelsize'])
        
        fig.canvas.draw_idle()


    def set_color_palette(self, palette_name='category10'):
        """
        Separate function to manage color cycles (prop_cycle).
        """
        # Example of setting a standard color cycle
        if palette_name == 'tableau':
            from cycler import cycler
            colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728']
            plt.rcParams['axes.prop_cycle'] = cycler(color=colors)


    def set_window_on_top(self, fig, block=False):
        if fig.canvas.manager is None:
            print("if condition finished PlotStyler.set_window_on_top()")
            return 
        
        try:
            window = fig.canvas.manager.window
            top_hint = QtCore.Qt.WindowType.WindowStaysOnTopHint
            current_flags = window.windowFlags()
            window.setWindowFlags(current_flags | top_hint)
            window.show()
            if not block:
                window.setWindowFlags(current_flags & ~top_hint)
                window.show()
        except Exception as e:
            print(f"Warning PlotStyler: Could not set window to top: {e}")