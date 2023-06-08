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
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import os
import gc

import MVis_utils as MV_utils



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
        self.update_idletasks()
        size_ref = int(self.winfo_screenheight()*0.90)
        size_width = 300
        size_height = 150
        if (600 + size_height - self.winfo_rooty() + self.winfo_y()) < size_ref:
            size_frame = 600
        else:
            size_frame = size_ref  - self.winfo_rooty() + self.winfo_y() - size_height
        x_pos = (self.winfo_screenwidth() - size_frame - size_width - self.winfo_rootx() + self.winfo_x())//2
        y_pos = (self.winfo_screenheight() - size_frame - size_height - self.winfo_rooty() + self.winfo_y())//2
        self.geometry('{}x{}+{}+{}'.format(str(size_frame + size_width), str(size_frame + size_height), str(x_pos), str(y_pos)))
        self.minsize(size_frame + size_width, size_frame + size_height)
        self.lift()
        self.focus_force()
        icon = PhotoImage(file =  __rootf__ + "/Logo MVis.png")
        self.iconphoto(False, icon)
        self.config(bg = "#bfbfbf")
        self.check_fullscreen = False # Variable to check if window is in fullscreen mode


# Style settings
        default_font = font.nametofont("TkDefaultFont")
        default_font.configure(family = 'TimesNewRoman', size = 12)
        self.option_add("*Font", default_font)  # Default font      

        self.syle_scale = {'bg' : '#bfbfbf', 'troughcolor' : '#e6e6e6', 'highlightbackground' : '#bfbfbf'}
        self.font_title = {'bg' : '#999999', 'fg' : 'blue', 'font' : 'Arial 14 bold'}
        self.font_subtitle = {'bg' : '#bfbfbf', 'fg' : 'black', 'font' : 'Arial 12 bold'}
        self.font_entry = {'bg' : 'white', 'fg' : 'black', 'font' : 'Verdana 11'}
        self.font_button = {'bg' : 'white', 'fg' : 'black', 'font' : 'Verdana 14'}
        self.font_lab = {'bg' : '#cccccc', 'fg' : 'black', 'font' : 'Verdana 12'}
        self.font_text = {'bg' : '#e6e6e6', 'fg' : 'black', 'font' : 'Verdana 18'}
        self.font_man = {'bg' : 'darkblue', 'fg' : 'white', 'font' : "Arial 11"}

# UI variables
        self.source = StringVar(value = '')   # Root path variable
        self.rootmin = DoubleVar(value = 0)
        self.rootmax = DoubleVar(value = 100)
        self.val_min = DoubleVar(value = 0)
        self.val_min_old = DoubleVar(value = self.val_min.get())
        self.val_sweep1 = DoubleVar(value = self.val_min.get())
        self.val_max = DoubleVar(value = self.rootmax.get())
        self.val_max_old = DoubleVar(value = self.val_max.get())
        self.val_sweep2 = DoubleVar(value = self.val_max.get())
        self.rootmin = DoubleVar(value = 0)
        self.rootmax = DoubleVar(value = 100)
        self.col_min = DoubleVar(value = 0)
        self.col_min_old = DoubleVar(value = self.col_min.get())
        self.col_sweep1 = DoubleVar(value = self.col_min.get())
        self.col_max = DoubleVar(value = self.rootmax.get())
        self.col_max_old = DoubleVar(value = self.col_max.get())
        self.col_sweep2 = DoubleVar(value = self.col_max.get())
        self.g_itp = sorted(list(plt.matplotlib.image.interpolations_names))

# UI frame organization
        ''' Organization in three frames: graph panel at the center, an auxiliar frame below for file selection settings,
        and a side frame with the graph options '''
        self.fr_graph = Frame(self, bg = '#e6e6e6')
        fr_selector = Frame(self, bg = '#cccccc')
        fr_options = Frame(self, bg = "#bfbfbf")
        self.update()
        self.fr_graph.place(relx = 0, rely = 0)
        fr_selector.place(relx = 0)
        fr_options.place(rely = 0, width = size_width, relheight = 1)

        # Automatic readjustment of frames with changes in window's size
        def cf_frames(event):
            self.fr_graph.place_configure(width = self.winfo_width() - size_width, height = self.winfo_height() - size_height)
            fr_selector.place_configure(y = self.winfo_height() - size_height, width = self.winfo_width() - size_width, height = size_height)
            fr_options.place_configure(x = self.winfo_width() - size_width)
            # self.MV_fig.tight_layout(pad = 1.0, w_pad = 1.0, h_pad = 1.0)
        self.bind("<Configure>", cf_frames)

        # Incorporation of a scrollbar in the options frame
        fr_sdb = Scrollbar(fr_options, activebackground = 'blue', orient = VERTICAL, bg = 'blue', bd = 5)
        fr_sdb.pack(side = RIGHT, fill = Y)
        fr_cv = Canvas(fr_options, yscrollcommand = fr_sdb.set, bg = "#bfbfbf", highlightthickness = 0)
        fr_cv.pack(expand = True, side = LEFT, fill = BOTH, anchor = CENTER)
        fr_sdb.config(command = fr_cv.yview)
        fr_sf = Frame(fr_cv, bg = "#bfbfbf")
        fr_cv.create_window((0,0), window = fr_sf, anchor = NW)
        fr_sf.bind("<Configure>", lambda event: fr_cv.configure(scrollregion = fr_cv.bbox("all")))
        fr_sf.bind("<MouseWheel>", lambda event: fr_cv.yview_scroll(int(-2*np.sign(event.delta)) if fr_sdb.get() != (0,1) else 0, "units"))
        fr_cv.bind("<MouseWheel>", lambda event: fr_cv.yview_scroll(int(-2*np.sign(event.delta)) if fr_sdb.get() != (0,1) else 0, "units"))

# UI layout
        '''Graph frame's initial label'''
        self.lab_selection = Label(self.fr_graph, text = 'Click to select file', cursor = 'hand2', **self.font_text)
        self.lab_selection.pack(anchor = CENTER, expand = True, fill = BOTH)
        self.lab_selection.bind("<1>", self.source_selection)

        '''Auxiliar frame widgets'''
        self.Bt_reset = Button(fr_selector, text = 'Open new map', command = self.source_selection, cursor = 'hand2', **self.font_button, state = DISABLED)
        self.Bt_reset.pack(anchor = CENTER, expand = False, pady = 10)

        self.lab_xpixel = Label(fr_selector, text = 'X = ', **self.font_lab)
        self.lab_ypixel = Label(fr_selector, text = 'Y = ', **self.font_lab)
        self.lab_value = Label(fr_selector, text = 'val =  ', **self.font_lab)

        '''Options frame'''
        # Map value range section, title
        Title_val = Label(fr_sf, text = 'Map values range', justify = CENTER, **self.font_title)
        Title_val.grid(row = 0, column = 0, columnspan = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5)

        # Subsection for changing map's minimum value
        Subtitle_val1 = Label(fr_sf, text = 'Min.', justify = CENTER, relief = RIDGE, **self.font_subtitle)
        Subtitle_val1.grid(row = 1, rowspan = 2, column = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = N+S)
        self.Sc_val1 = Scale(fr_sf, from_ = self.rootmin.get(), to = self.rootmax.get(), variable = self.val_sweep1, command = lambda event: self.sweep_values(self.En_val1.winfo_name(), self.val_sweep1, self.val_min), bd = 2, orient = HORIZONTAL, **self.syle_scale)
        self.Sc_val1.grid(row = 1, column = 0, columnspan = 2, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W+E)
        self.En_val1 = Entry(fr_sf, name = 'val_1', textvariable = self.val_min, **self.font_entry, width = 11)
        self.En_val1.grid(row = 2, column = 0, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_val1 = Label(fr_sf, text = "...", bg = 'white', relief = GROOVE, width = 2)
        self.Lb_val1.grid(row = 2, column = 1, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = E)

        # Subsection for changing map's maximum value
        Subtitle_val2 = Label(fr_sf, text = 'Max.', justify = CENTER, relief = RIDGE, **self.font_subtitle)
        Subtitle_val2.grid(row = 3, rowspan = 2, column = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = N+S)
        self.Sc_val2 = Scale(fr_sf, from_ = self.rootmin.get(), to = self.rootmax.get(), variable = self.val_sweep2, command = lambda event: self.sweep_values(self.En_val2.winfo_name(), self.val_sweep2, self.val_max), bd = 2, orient = HORIZONTAL, **self.syle_scale)
        self.Sc_val2.grid(row = 3, column = 0, columnspan = 2, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W+E)
        self.En_val2 = Entry(fr_sf, name = 'val_2', textvariable = self.val_max, **self.font_entry, width = 11)
        self.En_val2.grid(row = 4, column = 0, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_val2 = Label(fr_sf, text = "...", bg = 'white', relief = GROOVE, width = 2)
        self.Lb_val2.grid(row = 4, column = 1, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = E)

        # Spacing between sections
        Lb_sep1 = Label(fr_sf, bg = '#bfbfbf')
        Lb_sep1.grid(row = 5, column = 0, padx = 10, pady = 2, ipadx = 5, ipady = 2)

        # Colormap value range section, title
        Title_col = Label(fr_sf, text = 'Map colours range', justify = CENTER, **self.font_title)
        Title_col.grid(row = 6, column = 0, columnspan = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5)

        # Subsection for changing colormap's minimum value
        Subtitle_col1 = Label(fr_sf, text = 'Min.', justify = CENTER, relief = RIDGE, **self.font_subtitle)
        Subtitle_col1.grid(row = 7, rowspan = 2, column = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = N+S)
        self.Sc_col1 = Scale(fr_sf, from_ = self.rootmin.get(), to = self.rootmax.get(), variable = self.col_sweep1, command = lambda event: self.sweep_values(self.En_col1.winfo_name(), self.col_sweep1, self.col_min), bd = 2, orient = HORIZONTAL, **self.syle_scale)
        self.Sc_col1.grid(row = 7, column = 0, columnspan = 2, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W+E)
        self.En_col1 = Entry(fr_sf, name = 'col_1', textvariable = self.col_min, **self.font_entry, width = 11)
        self.En_col1.grid(row = 8, column = 0, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_col1 = Label(fr_sf, text = "...", bg = 'white', relief = GROOVE, width = 2)
        self.Lb_col1.grid(row = 8, column = 1, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = E)

        # Subsection for changing colormap's maximum value
        Subtitle_col2 = Label(fr_sf, text = 'Max.', justify = CENTER, relief = RIDGE, **self.font_subtitle)
        Subtitle_col2.grid(row = 9, rowspan = 2, column = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = N+S)
        self.Sc_col2 = Scale(fr_sf, from_ = self.rootmin.get(), to = self.rootmax.get(), variable = self.col_sweep2, command = lambda event: self.sweep_values(self.En_col2.winfo_name(), self.col_sweep2, self.col_max), bd = 2, orient = HORIZONTAL, **self.syle_scale)
        self.Sc_col2.grid(row = 9, column = 0, columnspan = 2, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W+E)
        self.En_col2 = Entry(fr_sf, name = 'col_2', textvariable = self.col_max, **self.font_entry, width = 11)
        self.En_col2.grid(row = 10, column = 0, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = W)
        self.Lb_col2 = Label(fr_sf, text = "...", bg = 'white', relief = GROOVE, width = 2)
        self.Lb_col2.grid(row = 10, column = 1, padx = 10, pady = 3, ipadx = 5, ipady = 5, sticky = E)

        # Spacing between sections
        Lb_sep2 = Label(fr_sf, bg = '#bfbfbf')
        Lb_sep2.grid(row = 11, column = 0, padx = 10, pady = 2, ipadx = 5, ipady = 5)

        # Other colormap settings, title
        Title_set = Label(fr_sf, text = 'Map settings', justify = CENTER, **self.font_title)
        Title_set.grid(row = 12, column = 0, columnspan = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5)

        # Subsection for the change of colormap used
        Lb_map = Label(fr_sf, text = 'Colormap', **self.font_subtitle)
        Lb_map.grid(row = 13, column = 0, columnspan = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W)
        self.Cb_map = ttk.Combobox(fr_sf, values = plt.colormaps(), background = "#e6e6e6", state = "readonly", width = 10)
        self.Cb_map.set(plt.colormaps()[2])
        self.Cb_map.grid(row = 14, column = 0, columnspan = 2, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W+E)

        # Spacing between sections
        Lb_sep3 = Label(fr_sf, bg = '#bfbfbf')
        Lb_sep3.grid(row = 15, column = 0, padx = 10, pady = 2, ipadx = 5, ipady = 2)

        # Subsection for the change of interpolation among pixels
        Lb_map = Label(fr_sf, text = 'Interpolation', **self.font_subtitle)
        Lb_map.grid(row = 16, column = 0, columnspan = 3, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W)
        self.Cb_itp = ttk.Combobox(fr_sf, values = self.g_itp, background = "#e6e6e6", state = "readonly", width = 10)
        self.Cb_itp.set(self.g_itp[0])
        self.Cb_itp.grid(row = 17, column = 0, columnspan = 2, padx = 10, pady = 5, ipadx = 5, ipady = 5, sticky = W+E)

# UI figure
        # self.MV_fig = Figure(dpi = 100, facecolor = 'white', tight_layout = True)
        # # self.MV_plot = self.MV_fig.add_subplot()
        # data = np.zeros((10,10))
        # self.MV_show = plt.imshow(data, vmin = 0, vmax = 1, origin = 'upper')

# UI contextual menu
        self.menucontext = Menu(self, tearoff = 0)
        self.menucontext.add_command(label = "Fullscreen", command = self.toggle_fullscreen)
        self.menucontext.add_command(label = "About...", command = lambda: print('Author: '
                                    + __author__ + '\nVersion: ' + __version__ + '\nLicense: ' + __license__))
        self.menucontext.add_command(label = "Exit", command = self.exit)

# UI bindings
        self.En_val1.bind("<Up>", lambda event: self.change_values(event, 1, [self.rootmin.get(), self.rootmax.get(), self.val_min], self.En_val1.winfo_name(), self.Lb_val1))
        self.En_val1.bind("<Down>", lambda event: self.change_values(event, -1, [self.rootmin.get(), self.rootmax.get(), self.val_min], self.En_val1.winfo_name(), self.Lb_val1))
        self.En_val1.bind("<MouseWheel>", lambda event: self.change_values(event, (event.delta/120), [self.rootmin.get(), self.rootmax.get(), self.val_min], self.En_val1.winfo_name(), self.Lb_val1))
        self.En_val1.bind("<KeyRelease>", lambda event: self.set_values(self.En_val1.winfo_name()))

        self.Lb_val1.bind("<MouseWheel>", lambda event: self.change_sweep(event, self.Lb_val1))
        self.Lb_val1.bind('<1>', lambda event: self.Lb_val1.config(text = '...'))

        self.En_val2.bind("<Up>", lambda event: self.change_values(event, 1, [self.rootmin.get(), self.rootmax.get(), self.val_max], self.En_val2.winfo_name(), self.Lb_val2))
        self.En_val2.bind("<Down>", lambda event: self.change_values(event, -1, [self.rootmin.get(), self.rootmax.get(), self.val_max], self.En_val2.winfo_name(), self.Lb_val2))
        self.En_val2.bind("<MouseWheel>", lambda event: self.change_values(event, (event.delta/120), [self.rootmin.get(), self.rootmax.get(), self.val_max], self.En_val2.winfo_name(), self.Lb_val2))
        self.En_val2.bind("<KeyRelease>", lambda event: self.set_values(self.En_val2.winfo_name()))

        self.Lb_val2.bind("<MouseWheel>", lambda event: self.change_sweep(event, self.Lb_val2))
        self.Lb_val2.bind('<1>', lambda event: self.Lb_val2.config(text = '...'))

        self.En_col1.bind("<Up>", lambda event: self.change_values(event, 1, [self.rootmin.get(), self.rootmax.get(), self.col_min], self.En_col1.winfo_name(), self.Lb_col1))
        self.En_col1.bind("<Down>", lambda event: self.change_values(event, -1, [self.rootmin.get(), self.rootmax.get(), self.col_min], self.En_col1.winfo_name(), self.Lb_col1))
        self.En_col1.bind("<MouseWheel>", lambda event: self.change_values(event, (event.delta/120), [self.rootmin.get(), self.rootmax.get(), self.col_min], self.En_col1.winfo_name(), self.Lb_col1))
        self.En_col1.bind("<KeyRelease>", lambda event: self.set_values(self.En_col1.winfo_name()))

        self.Lb_col1.bind("<MouseWheel>", lambda event: self.change_sweep(event, self.Lb_col1))
        self.Lb_col1.bind('<1>', lambda event: self.Lb_col1.config(text = '...'))

        self.En_col2.bind("<Up>", lambda event: self.change_values(event, 1, [self.rootmin.get(), self.rootmax.get(), self.col_max], self.En_col2.winfo_name(), self.Lb_col2))
        self.En_col2.bind("<Down>", lambda event: self.change_values(event, -1, [self.rootmin.get(), self.rootmax.get(), self.col_max], self.En_col2.winfo_name(), self.Lb_col2))
        self.En_col2.bind("<MouseWheel>", lambda event: self.change_values(event, (event.delta/120), [self.rootmin.get(), self.rootmax.get(), self.col_max], self.En_col2.winfo_name(), self.Lb_col2))
        self.En_col2.bind("<KeyRelease>", lambda event: self.set_values(self.En_col2.winfo_name()))

        self.Lb_col2.bind("<MouseWheel>", lambda event: self.change_sweep(event, self.Lb_col2))
        self.Lb_col2.bind('<1>', lambda event: self.Lb_col2.config(text = '...'))

        self.Cb_map.bind("<<ComboboxSelected>>", lambda event: self.map_cmap())
        self.Cb_itp.bind("<<ComboboxSelected>>", lambda event: self.map_interpolation())

        fr_sf.bind("<3>", self.show_menucontext)
        self.bind("<Control_R>", lambda event: self.exit())

# UI mainloop
        self.mainloop()



# Additional functions of the class

    ''' Main function of the app, allocate map in the figure in graph frame '''
    def map_visualizer(self, map_values, map_type):

        # Setting a global variable to work with the map array throughout the functions
        self.map_array = map_values
        # Axis extension of the map
        map_extent = [1, np.shape(map_values)[0] + 1, 1, np.shape(map_values)[1] + 1]

        # Setting variables to the given array
        self.rootmin.set(np.nanmin(map_values))
        self.rootmax.set(np.nanmax(map_values))
        self.val_min.set(self.rootmin.get())
        self.val_min_old.set(self.val_min.get())
        self.val_sweep1.set(self.val_min.get())
        self.val_max.set(self.rootmax.get())
        self.val_max_old.set(self.val_max.get())
        self.val_sweep2.set(self.val_max.get())
        self.col_min.set(self.rootmin.get())
        self.col_min_old.set(self.col_min.get())
        self.col_sweep1.set(self.col_min.get())
        self.col_max.set(self.rootmax.get())
        self.col_max_old.set(self.col_max.get())
        self.col_sweep2.set(self.col_max.get())

        # Setting scale widgets to the given array
        self.Sc_val1.config(from_ = self.rootmin.get(), to = self.rootmax.get())
        self.Sc_val2.config(from_ = self.rootmin.get(), to = self.rootmax.get())
        self.Sc_col1.config(from_ = self.rootmin.get(), to = self.rootmax.get())
        self.Sc_col2.config(from_ = self.rootmin.get(), to = self.rootmax.get())

        self.MV_fig = Figure(dpi = 100, facecolor = 'white', tight_layout = True)
        self.MV_plot = self.MV_fig.add_subplot()
        # data = np.zeros((10,10))
        # self.MV_show = plt.imshow(data, vmin = 0, vmax = 1, origin = 'upper')

        # self.MV_fig.clf()
        # self.MV_show = plt.imshow((map_values - self.rootmin.get())/(self.rootmax.get() - self.rootmin.get()), vmin = 0, vmax = 1, origin = 'upper')
        # # self.MV_show.set_data((map_values - self.rootmin.get())/(self.rootmax.get() - self.rootmin.get()))
        self.MV_show = self.MV_plot.imshow(map_values, cmap = self.Cb_map.get(), vmin = self.rootmin.get(), vmax = self.rootmax.get(), origin = 'lower', interpolation = self.Cb_itp.get(), extent = map_extent)
        self.MV_plot.tick_params(bottom = False, left = False, labelbottom = False, labelleft = False)
        # self.MV_plot.set_ylabel('y (\u03bcm)', fontname = 'Arial', fontsize = 20, labelpad = 10)
        # MV_plot.xaxis.set_tick_params(labelsize = 15)
        # MV_plot.yaxis.set_tick_params(labelsize = 15)

        self.MV_mp = plt.cm.ScalarMappable(norm = None, cmap = self.Cb_map.get())
        self.MV_mp.set_clim(vmin = self.rootmin.get(), vmax = self.rootmax.get())
        self.MV_bar = self.MV_fig.colorbar(self.MV_mp, ax = self.MV_plot, orientation = 'vertical', format = '%.2f')
        self.MV_bar.ax.yaxis.set_tick_params(labelsize = 15)

        self.canv = FigureCanvasTkAgg(self.MV_fig, self.fr_graph)
        self.toolbar = NavigationToolbar2Tk(self.canv, self.fr_graph)
        self.toolbar.children['!button4'].pack_forget()
        # Para revelar sólo números de píxel, necesito sobreescribir el método de la clase...
        # self.toolbar.mouse_move([3,4])
        self.canv.draw()
        self.toolbar.update()
        self.canv.get_tk_widget().pack(side = TOP, fill = BOTH, expand = True)
        self.canv._tkcanvas.pack(side = TOP, fill = BOTH, expand = True)   # This must be the graph

        self.lab_xpixel.place(x = 10, y = 20)
        self.lab_ypixel.place(x = 10, y = 50)
        self.lab_value.place(x = 10, y = 80)

        self.canv.mpl_connect('motion_notify_event', self.map_pixelinfo)


    ''' Function to get and show information from pixels in graph '''
    def map_pixelinfo(self, event):
        value = self.MV_show.get_cursor_data(event)
        if None not in [event.xdata, value]:
            self.lab_xpixel.config(text = 'X = {}'.format(int(event.xdata)))
            self.lab_ypixel.config(text = 'Y = {}'.format(int(event.ydata)))
            self.lab_value.config(text = 'val = {}'.format(value))
        else:
            self.lab_xpixel.config(text = 'X = ')
            self.lab_ypixel.config(text = 'Y = ')
            self.lab_value.config(text = 'val = ')


    ''' Function to change array's value range '''
    def map_range(self):
        try:
            map_copy = np.where(self.map_array < self.val_min.get(), self.val_min.get(), self.map_array)
            map_copy = np.where(map_copy > self.val_max.get(), self.val_max.get(), map_copy)
            self.MV_show.set_data(map_copy)
            self.canv.draw()
        except:
            pass


    ''' Function to change array's colormap range '''
    def map_colorange(self):
        try:
            self.MV_mp.set_clim(vmin = self.col_min.get(), vmax = self.col_max.get())
            self.MV_show.set_clim(vmin = self.col_min.get(), vmax = self.col_max.get())
            self.canv.draw()
        except:
            pass


    ''' Function to change array's cmap'''
    def map_cmap(self):
        try:
            self.MV_show.set_cmap(self.Cb_map.get())
            self.MV_mp.set_cmap(self.Cb_map.get())
            self.canv.draw()
        except:
            pass


    ''' Function to change array's interpolation '''
    def map_interpolation(self):
        try:
            self.MV_show.set_interpolation(self.Cb_itp.get())
            self.canv.draw()
        except:
            pass


    ''' Source directory selection function '''
    def source_selection(self, event = 0):
        adress = filedialog.askopenfilename(initialdir = "", title = "FF Explorer, root path selection", filetypes = [('Text file', '.txt .dat')])
        if adress != '':
            self.source.set(adress)
            self.lab_selection.pack_forget()
            self.Bt_reset.config(state = NORMAL)
            MV_map, type_map = MV_utils.MV_reader(adress)
            self.map_visualizer(MV_map, type_map)


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


    ''' Change input values with up and down keys, and mousewheel scrolling '''
    def change_values(self, event, e, values, label, order):
        decimals = len(str(values[2].get()).split('.')[-1]) if order['text'] == '...' else -int(order['text'])
        new_val = np.round(values[2].get() + e*10**(-decimals), decimals)
        if values[0] <= new_val <= values[1]:
            values[2].set(new_val)
            self.set_values(label)


    ''' Function to execute the changes in range values from the Scale widgets '''
    def sweep_values(self, lab, sweep_val, val):
        val.set(sweep_val.get())
        self.set_values(lab)


    ''' Function to check if there is a number in the tkinter variable '''
    def check_value(self, new_val, old_val):
        try:
            new_val.get()
        except:
            new_val.set(old_val.get())


    ''' Main function to apply the change of range values from the given widgets '''
    def set_values(self, label):
        match label:
            case 'val_1':
                self.check_value(self.val_min, self.val_min_old)
                if self.val_min.get() >= self.val_max.get():
                    self.val_min.set(self.val_min_old.get())
                else:
                    self.val_min_old.set(self.val_min.get())
                self.val_sweep1.set(self.val_min.get())
                self.map_range()
            case 'val_2':
                self.check_value(self.val_max, self.val_max_old)
                if self.val_min.get() >= self.val_max.get():
                    self.val_max.set(self.val_max_old.get())
                else:
                    self.val_max_old.set(self.val_max.get())
                self.val_sweep2.set(self.val_max.get())
                self.map_range()
            case 'col_1':
                self.check_value(self.col_min, self.col_min_old)
                if self.col_min.get() >= self.col_max.get():
                    self.col_min.set(self.col_min_old.get())
                else:
                    self.col_min_old.set(self.col_min.get())
                self.col_sweep1.set(self.col_min.get())
                self.map_colorange()
            case 'col_2':
                self.check_value(self.col_max, self.col_max_old)
                if self.col_min.get() >= self.col_max.get():
                    self.col_max.set(self.col_max_old.get())
                else:
                    self.col_max_old.set(self.col_max.get())
                self.col_sweep2.set(self.col_max.get())
                self.map_colorange()


    ''' Show contextual menu '''
    def show_menucontext(self, e):
        self.menucontext.post(e.x_root, e.y_root)


    ''' Function to activate the fullscreen mode '''
    def toggle_fullscreen(self):
        if self.check_fullscreen:
            self.check_fullscreen = False
            self.attributes('-fullscreen', self.check_fullscreen)
        else:
            self.check_fullscreen = True
            self.attributes('-fullscreen', self.check_fullscreen)


    ''' Exit function '''
    def exit(self):
        print('Exiting Map Visualizer...')
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