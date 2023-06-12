# Map-Visualizer
Training software, visualizer of 2D arrays saved in .txt and .dat file formats.

Inside the program, it is possible to change the range of the map's values and colormap separately. Also, colormap and interpolation used can be modified. All these settings are changed in real time.

Pixel position and value numbers are displayed at the upper left corner of the software's bottom panel while mouse pointer is moved over the map. Also, for range values below 0.01 and above 1000 are expressed with scientific notation in the settings; the exponent of these numbers is also displayed at the upper right corner of this panel.

**MVis_utils.py** contains the reading functions of the software, together with other auxiliar functions of the UI.

*example column.txt*, *example row.txt*, *example.dat* and *example.txt* are dummy examples of arrays to test the capabilities of the program.