"""
Juan García Sánchez, 2023
"""

###############################################################################
#                                                                             #
# Magnitudes' unit converter: U Converter                                     #
# UI                                                                          #
#                                                                             #
###############################################################################

from tkinter import *
from tkinter import ttk, font, messagebox, filedialog, PhotoImage
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import os
import gc



# ================= Program parameters ==========

__author__ = 'Juan García Sánchez'
__title__= 'M Visualizer'
__rootf__ = os.getcwd()
__version__ = '1.0'
__datver__ = '05-2023'
__pyver__ = '3.10.9'
__license__ = 'GPLv3'



# ================= UI class ====================

class MVis_UI(Tk):

    def __init__(self):

# Main properties of the UI
        Tk.__init__(self)
        self.title(__title__)
        self.size_frame = 600
        self.size_width = 280
        self.size_height = 150
        self.update_idletasks()
        x_pos = (self.winfo_screenwidth() - self.size_frame - self.size_width - self.winfo_rootx() + self.winfo_x())//2
        y_pos = (self.winfo_screenheight() - self.size_frame - self.size_height - self.winfo_rooty() + self.winfo_y())//2
        self.geometry('{}x{}+{}+{}'.format(str(self.size_frame + self.size_width), str(self.size_frame + self.size_height), str(x_pos), str(y_pos)))
        self.minsize(self.size_frame + self.size_width, self.size_frame + self.size_height)
        # self.resizable(False, False)
        self.lift()
        self.focus_force()
        icon = PhotoImage(file =  __rootf__ + "/Logo MVis.png")
        self.iconphoto(False, icon)
        self.config(bg = "#bfbfbf")


# Style settings
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family = 'TimesNewRoman', size = 12)
        self.option_add("*Font", default_font)  # Default font      

        self.font_title = {'bg' : '#999999', 'fg' : 'blue', 'font' : 'Arial 12 bold'}
        self.font_entry = {'bg' : 'white', 'fg' : 'black', 'font' : 'Verdana 11'}
        self.font_val = {'bg' : '#bfbfbf', 'fg' : 'black', 'font' : 'Verdana 11'}
        self.font_text = {'bg' : '#e6e6e6', 'fg' : 'black', 'font' : 'Verdana 18'}
        self.font_man = {'bg' : 'darkblue', 'fg' : 'white', 'font' : "Arial 11"}

# UI layout
        ''' Organization in three frames: graph panel at the center, an auxiliar frame below for file selection settings,
        and a side frame with the graph options '''
        self.fr_graph = Frame(self, bg = '#e6e6e6')
        self.fr_selector = Frame(self, bg = '#cccccc')
        self.fr_options = Frame(self, bg = "#bfbfbf")
        self.update()
        self.fr_graph.place(relx = 0, rely = 0, width = self.winfo_width() - self.size_width, height = self.winfo_width() - self.size_width)
        self.fr_selector.place(relx = 0, y = self.winfo_height() - self.size_height, width = self.winfo_width() - self.size_width, height = self.size_height)
        self.fr_options.place(x = self.winfo_width() - self.size_width, rely = 0, width = self.size_width, relheight = 1)
        def cf_frames(event):
            self.fr_graph.place_configure(width = self.winfo_width() - self.size_width, height = self.winfo_height() - self.size_height)
            self.fr_selector.place_configure(y = self.winfo_height() - self.size_height, width = self.winfo_width() - self.size_width, height = self.size_height)
            self.fr_options.place_configure(x = self.winfo_width() - self.size_width, width = self.size_width)
        self.bind("<Configure>", cf_frames)

        self.lab_selection = Label(self.fr_graph, text = 'Click to select file', cursor = 'hand2', **self.font_text)
        self.lab_selection.pack(anchor = CENTER, expand = True, fill = BOTH)

        # self.FDC_graph = Figure(figsize=(5, 5), dpi=100)
        # self.canv = FigureCanvasTkAgg(self.FDC_graph, self.fr_6)
        # self.toolbar = NavigationToolbar2Tk(self.canv, self.fr_7)
        # self.canv.get_tk_widget().pack(side = TOP, fill = BOTH, expand = True)
        # self.canv.get_tk_widget().place
        # self.canv._tkcanvas.pack(side = TOP, fill = BOTH, expand = True)




# UI contextual menu
        self.menucontext = Menu(self, tearoff = 0)
        self.menucontext.add_command(label = "About...", command = lambda : print('Author: '
                                    + __author__ + '\nVersion: ' + __version__ + '\nLicense: ' + __license__))
        self.menucontext.add_command(label = "Exit", command = self.exit)

# UI mainloop
        self.mainloop()


    ''' Show contextual menu '''
    def show_menucontext(self, e):
        self.menucontext.post(e.x_root, e.y_root)


    ''' Exit function '''
    def exit(self):
        print('Exiting FF Explorer...')
        self.quit()
        self.destroy()
        for name in dir():
            if not name.startswith('_'):
                del locals()[name]
        gc.collect()
        del self



# ================= UI execution ================

if __name__ == '__main__':
    MVis_UI()