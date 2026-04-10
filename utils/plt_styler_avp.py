import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, ScalarFormatter

class PlotStyler:

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



