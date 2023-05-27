"""
Juan García Sánchez, 2023
"""

###############################################################################
#                                                                             #
# Magnitudes' unit converter: U Converter                                     #
# UI                                                                          #
#                                                                             #
###############################################################################

import numpy as np
import os
import zipfile
import gc



def MV_reader(file):
    if file.endswith('.txt'):
        return reader_txt(file)
    else:
        return print('Error, file format not supported.')
    

def reader_txt(fl):
    try:
        map_result = np.loadtxt(fl)
        return map_result, 0
    except:
        print('Error, map format not supported.')
        return [], -1