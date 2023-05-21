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

        self.syle_scale = {'bg' : '#bfbfbf', 'troughcolor' : '#e6e6e6', 'highlightbackground' : '#bfbfbf'}
        self.font_title = {'bg' : '#999999', 'fg' : 'blue', 'font' : 'Arial 14 bold'}
        self.font_subtitle = {'bg' : '#bfbfbf', 'fg' : 'black', 'font' : 'Arial 12 bold'}
        self.font_entry = {'bg' : 'white', 'fg' : 'black', 'font' : 'Verdana 11'}
        self.font_button = {'bg' : 'white', 'fg' : 'black', 'font' : 'Verdana 14'}
        self.font_text = {'bg' : '#e6e6e6', 'fg' : 'black', 'font' : 'Verdana 18'}
        self.font_man = {'bg' : 'darkblue', 'fg' : 'white', 'font' : "Arial 11"}

# UI variables
        self.source = StringVar(value = '')   # Root path variable
        self.val_rootmin = DoubleVar(value = 0)
        self.val_rootmax = DoubleVar(value = 100)
        self.val_min = DoubleVar(value = 0)
        self.val_sweep1 = DoubleVar(value = 0)
        self.val_max = DoubleVar(value = 0)
        self.val_sweep2 = DoubleVar(value = 0)
        self.col_rootmin = DoubleVar(value = 0)
        self.col_rootmax = DoubleVar(value = 100)
        self.col_min = DoubleVar(value = 0)
        self.col_sweep1 = DoubleVar(value = 0)
        self.col_max = DoubleVar(value = 0)
        self.col_sweep2 = DoubleVar(value = 0)

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

        '''Graph frame's initial label'''
        self.lab_selection = Label(self.fr_graph, text = 'Click to select file', cursor = 'hand2', **self.font_text)
        self.lab_selection.pack(anchor = CENTER, expand = True, fill = BOTH)
        self.lab_selection.bind("<1>", self.source_selection)

        '''Auxiliar frame widgets'''
        self.Bt_reset = Button(self.fr_selector, text = 'Open new map', command = self.source_selection, cursor = 'hand2', **self.font_button, state = DISABLED)
        self.Bt_reset.pack(anchor = CENTER, expand = False, pady = 10)

        '''Options frame'''
        Title_val = Label(self.fr_options, text = 'Map values range', justify = CENTER, **self.font_title)
        Title_val.grid(row = 0, column = 0, columnspan = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5)

        Subtitle_val1 = Label(self.fr_options, text = 'Min.', justify = CENTER, relief = RIDGE, **self.font_subtitle)
        Subtitle_val1.grid(row = 1, rowspan = 2, column = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = N+S)
        Sc_val1 = Scale(self.fr_options, from_ = self.val_rootmin.get(), to = self.val_rootmax.get(), variable = self.val_sweep1, bd = 2, orient = HORIZONTAL, **self.syle_scale)
        Sc_val1.grid(row = 1, column = 0, columnspan = 2, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W+E)
        self.En_val1 = Entry(self.fr_options, textvariable = self.val_min, **self.font_entry, width = 11)
        self.En_val1.grid(row = 2, column = 0, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_val1 = Label(self.fr_options, text = "...", bg = 'white', relief = GROOVE, width = 2)
        self.Lb_val1.grid(row = 2, column = 1, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = E)
        self.Lb_val1.bind("<MouseWheel>", lambda event: self.change_sweep(event, self.Lb_val1))
        self.Lb_val1.bind('<1>', lambda event: self.Lb_val1.config(text = '...'))

        Subtitle_val2 = Label(self.fr_options, text = 'Max.', justify = CENTER, relief = RIDGE, **self.font_subtitle)
        Subtitle_val2.grid(row = 3, rowspan = 2, column = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = N+S)
        Sc_val2 = Scale(self.fr_options, from_ = self.val_rootmin.get(), to = self.val_rootmax.get(), variable = self.val_sweep1, bd = 2, orient = HORIZONTAL, **self.syle_scale)
        Sc_val2.grid(row = 3, column = 0, columnspan = 2, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W+E)
        self.En_val2 = Entry(self.fr_options, textvariable = self.val_min, **self.font_entry, width = 11)
        self.En_val2.grid(row = 4, column = 0, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_val2 = Label(self.fr_options, text = "...", bg = 'white', relief = GROOVE, width = 2)
        self.Lb_val2.grid(row = 4, column = 1, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = E)
        self.Lb_val2.bind("<MouseWheel>", lambda event: self.change_sweep(event, self.Lb_val2))
        self.Lb_val2.bind('<1>', lambda event: self.Lb_val2.config(text = '...'))

        Title_col = Label(self.fr_options, text = 'Map colours range', justify = CENTER, **self.font_title)
        Title_col.grid(row = 5, column = 0, columnspan = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5)

        Subtitle_col1 = Label(self.fr_options, text = 'Min.', justify = CENTER, relief = RIDGE, **self.font_subtitle)
        Subtitle_col1.grid(row = 6, rowspan = 2, column = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = N+S)
        Sc_col1 = Scale(self.fr_options, from_ = self.val_rootmin.get(), to = self.val_rootmax.get(), variable = self.val_sweep1, bd = 2, orient = HORIZONTAL, **self.syle_scale)
        Sc_col1.grid(row = 6, column = 0, columnspan = 2, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W+E)
        self.En_col1 = Entry(self.fr_options, textvariable = self.val_min, **self.font_entry, width = 11)
        self.En_col1.grid(row = 7, column = 0, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_col1 = Label(self.fr_options, text = "...", bg = 'white', relief = GROOVE, width = 2)
        self.Lb_col1.grid(row = 7, column = 1, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = E)
        self.Lb_col1.bind("<MouseWheel>", lambda event: self.change_sweep(event, self.Lb_col1))
        self.Lb_col1.bind('<1>', lambda event: self.Lb_col1.config(text = '...'))

        Subtitle_col2 = Label(self.fr_options, text = 'Max.', justify = CENTER, relief = RIDGE, **self.font_subtitle)
        Subtitle_col2.grid(row = 8, rowspan = 2, column = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = N+S)
        Sc_col2 = Scale(self.fr_options, from_ = self.val_rootmin.get(), to = self.val_rootmax.get(), variable = self.val_sweep1, bd = 2, orient = HORIZONTAL, **self.syle_scale)
        Sc_col2.grid(row = 8, column = 0, columnspan = 2, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W+E)
        self.En_col2 = Entry(self.fr_options, textvariable = self.val_min, **self.font_entry, width = 11)
        self.En_col2.grid(row = 9, column = 0, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_col2 = Label(self.fr_options, text = "...", bg = 'white', relief = GROOVE, width = 2)
        self.Lb_col2.grid(row = 9, column = 1, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = E)
        self.Lb_col2.bind("<MouseWheel>", lambda event: self.change_sweep(event, self.Lb_col2))
        self.Lb_col2.bind('<1>', lambda event: self.Lb_col2.config(text = '...'))

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

# UI bindings
        self.En_val1.bind("<Up>", lambda event: self.change_values(event, 1, [self.val_rootmin.get(), self.val_rootmax.get(), self.val_min], self.En_val1, self.Lb_val1))
        self.En_val1.bind("<Down>", lambda event: self.change_values(event, -1, [self.val_rootmin.get(), self.val_rootmax.get(), self.val_min], self.En_val1, self.Lb_val1))
        self.bind("<3>", self.show_menucontext)
        self.bind("<Control_R>", lambda event: self.exit())

# UI mainloop
        self.mainloop()



# Additional functions of the class
    ''' Source directory selection function '''
    def source_selection(self, event = 0):
        adress = filedialog.askdirectory(initialdir = "", title = "FF Explorer, root path selection")
        if adress != '':
            self.source.set(adress)
            self.lab_selection.pack_forget()
            self.Bt_reset.config(state = NORMAL)


    ''' Change input values with up and down keys '''
    def change_values(self, event, e, values, lab, order):
        decimals = len(str(values[2].get()).split('.')[-1]) if order['text'] == '...' else -int(order['text'])
        new_val = np.round(values[2].get() + e*10**(-decimals), decimals)
        if values[0] <= new_val <= values[1]:
            values[2].set(new_val)


    ''' Change decimal position to sweep with up and down keys '''
    def change_sweep(self, e, lab):
        init = lab["text"]
        match init:
            case '...':
                init = str(int(e.delta/120)) if e.delta < 0 else '0'
            case '0':
                init = '...' if e.delta < 0 else '1'
            case '-1':
                init = '-2' if e.delta < 0 else '...'
            case '99':
                init = str(int(init) + int(e.delta/120)) if e.delta < 0 else '99'
            case '-99':
                init = '-99' if e.delta < 0 else str(int(init) + int(e.delta/120))
            case _:
                init = str(int(init) + int(e.delta/120))
        lab.config(text = init)


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