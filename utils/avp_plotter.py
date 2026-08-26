# \utils\avp_plotter.py
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

from plt_styler_avp import PlotStyler 


class avpPlotter():
    def __init__(self, fig_width=10, fig_height=7, 
                 font_size=20, profile='default'):

        self.font_size = font_size
        self.ax_styler = PlotStyler(font_size=font_size) 
        # Apply font settings before creating the figure
        self.ax_styler.set_plt_font_style(size=font_size, profile=profile)

        self.fig = plt.figure(figsize=(fig_width, fig_height),
                              layout='constrained' # to automatically adjust axes when legend moves outside
                              )
        self.axes = {}
        self.lines = {}
        self.texts = {}
        # Internal counters for automatic naming
        self._ax_counter = 0
        self._line_counter = 0
        self._text_counter = 0


    def _generate_ax_name(self):
        """Internal method to create unique axis names like ax_0, ax_1..."""
        name = f"ax_{self._ax_counter}"
        self._ax_counter += 1
        return name

    def _generate_line_name(self):
        """Internal method to create unique line names like line_0, line_1..."""
        name = f"line_{self._line_counter}"
        self._line_counter += 1
        return name


    def add_to_plot(self, df, x_col:str, y_col:str, 
                    line_name=None, ax_name=None, **kwargs):
        """
        Plot data from a DataFrame onto a specific axis and store the line object.
        """
        ## 1. Determine which axis to use
        if ax_name is not None:
            # If a specific name is provided but doesn't exist, create it
            if ax_name not in self.axes:
                self.axes[ax_name] = self.fig.add_subplot(111)

        else:
            ## If no axis specified, use the first one or create a new one
            if not self.axes:
                ax_name = self._generate_ax_name()
                self.axes[ax_name] = self.fig.add_subplot(111)
            else:
                ax_name = list(self.axes.keys())[-1]

        ax = self.axes[ax_name]
        ax.set_title(ax_name) # Set the axis title as the axis name

        ## 2. Automatic Label Management
        current_xlabel = ax.get_xlabel()
        current_ylabel = ax.get_ylabel()
        ## If labels are empty (first line), set them from column names
        if not current_xlabel and not current_ylabel:
            ax.set_xlabel(x_col)
            ax.set_ylabel(y_col)
        else:
            ## If adding more lines, check for name consistency
            if current_xlabel != x_col or current_ylabel != y_col:
                print(f"Warning: Column names '{x_col}, {y_col}' do not match "
                      f"existing axis labels '{current_xlabel}, {current_ylabel}'.")

        ## 3. Determine the line name
        if line_name is None:
            line_name = self._generate_line_name()
        elif line_name in self.lines:
            print(f"Label '{line_name}' already exists. Generating a unique name.")
            line_name = f"{line_name}_{self._generate_line_name()}"

        ## 4. Plot the data
        ## Note: plot returns a list of lines, we take the first one
        line, = ax.plot(df[x_col], df[y_col], label=line_name, **kwargs)


        ## 5. Storage for future manipulation (e.g., removal)
        self.lines[line_name] = line
        ## 6. Refresh legend and apply source-based styling
        ax.legend()
        self.ax_styler.set_scale_steps(ax) # Integration with PlotStyler from sources [1]

        self.fig.canvas.draw_idle()

        return line_name


    def remove_from_plot(self, line_name):
        """
        Remove a specific line from the plot using its unique name.
        Automatically updates the legend and refreshes the display.
        """
        # 1. Validation: check if the line exists in the internal dictionary
        if line_name not in self.lines:
            print(f"Error: line_name '{line_name}' not found in current plot storage.")
            return

        # 2. Retrieve the line object; it stores a reference to its parent axis
        line = self.lines[line_name]
        ax = line.axes 
        
        # 3. Physically remove the line object from the axes
        line.remove()
        
        # 4. Remove from internal dictionary to allow name reuse
        del self.lines[line_name]
        
        # 5. UI Updates: manage the legend box
        # Redraw legend if other lines still exist on this axis
        if ax.get_lines():
            ax.legend()
        else:
            # If the last line is removed, clear the remaining legend frame
            legend = ax.get_legend()
            if legend:
                legend.remove()
        
        # 6. Refresh the canvas to apply changes in interactive backends (like Qt)
        self.fig.canvas.draw_idle()
        print(f"Line '{line_name}' successfully removed from plot.")


    def set_legend(self, ax_name=None, loc='upper left', bbox=(1.05, 1.0), **kwargs):
        """
        Adjust legend position and styling for a specific axis.
        Use bbox_to_anchor to move it outside the axes area.
        """
        # 1. Select the axis
        if ax_name is None:
            ax_name = list(self.axes.keys())[-1] if self.axes else None
        
        if ax_name not in self.axes:
            print(f"Error: Axis '{ax_name}' not found.")
            return
            
        ax = self.axes[ax_name]
        
        # 2. Re-create or update legend with positioning parameters
        # loc: position of the anchor point on the legend itself
        # bbox_to_anchor: coordinates where the anchor point is placed
        ax.legend(loc=loc, bbox_to_anchor=bbox, **kwargs)
        
        # 3. Refresh the canvas to apply layout changes
        self.fig.canvas.draw_idle()


    def add_text(self, text='defoult text', x=None, y=None, 
                 ax_name=None, text_name=None, 
                 use_axes_coords=True, # False will use data coordinates
                 **kwargs):
        """
        Unified method to add styled text. Handles axis selection, 
        automatic naming, and default positioning.
        """
        # Check if any axes exist to avoid IndexError
        if not self.axes:
            print("Error: No axes available to add text.")
            return None
            
        # Fallback to the last axis if name is missing or incorrect
        if ax_name not in self.axes:
            ax_name = list(self.axes.keys())[-1]
            print(f"Notice: Target axis not found. Adding text to the last axis: '{ax_name}'")

        ax = self.axes[ax_name]

        # 2. Automatic naming logic: text_01, text_02...
        if text_name is None:
            self._text_counter += 1
            text_name = f"text_{self._text_counter:02d}"

        # 3. Handle missing coordinates: default to top-left of the axes
        if x is None or y is None:
            x, y = 0.05, 0.95
            use_axes_coords = True
            print(f"Notice: Coordinates for '{text_name}' missing. "
                  f"Placing at default ({x}, {y}) in axes coords.")

        # 4. Coordinate system selection
        transform = ax.transAxes if use_axes_coords else ax.transData
        
        # 5. Apply consistent styling from our font settings
        if 'fontsize' not in kwargs:
            kwargs['fontsize'] = self.font_size
            
        # 6. Create the text artist and store it
        text_obj = ax.text(x, y, text, transform=transform, **kwargs)
        self.texts[text_name] = text_obj
        
        # 7. Update display
        self.fig.canvas.draw_idle()
        
        return text_name


    def remove_text(self, text_name):
            """
            Remove a specific text annotation from the plot by its name.
            """
            # 1. Validation: Check if the text name exists in storage
            if text_name not in self.texts:
                print(f"Error: Text element '{text_name}' not found.")
                return

            # 2. Get the text object (Artist) and remove it from the plot
            text_obj = self.texts[text_name]
            text_obj.remove()

            # 3. Clean up the internal dictionary
            del self.texts[text_name]

            # 4. Refresh the interactive canvas to reflect changes
            self.fig.canvas.draw_idle()
            print(f"Text '{text_name}' successfully removed.")


if __name__ == "__main__":

    # 1. Create dummy data
    x = np.linspace(0, 10, 100)
    df1 = pd.DataFrame({'piezo_v': x, 'nm': np.sin(x)})
    df2 = pd.DataFrame({'piezo_v': x, 'nm': np.cos(x)})


    # 2. Initialize our plotter
    plotter = avpPlotter(fig_width=10, fig_height=7)
    plotter.add_to_plot(df1, x_col='piezo_v', y_col='nm', 
                        line_name='test_sine', 
                        ax_name="piezo_scan",
                        color='red', linestyle='--'
                        )

    plotter.add_to_plot(df2, x_col='piezo_v', y_col='nm', 
                            line_name='test_cosine', 
                            ax_name="piezo_scan",
                            color='blue', linestyle='-'
                            )
    plt.show()