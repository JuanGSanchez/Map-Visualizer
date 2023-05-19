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
        self.geometry('235x385+800+350')
        self.resizable(False, False)
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
        self.font_text = {'bg' : '#bfbfbf', 'fg' : 'black', 'font' : 'Verdana 12'}
        self.font_man = {'bg' : 'darkblue', 'font' : "Arial 11", 'fg' : 'white'}

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