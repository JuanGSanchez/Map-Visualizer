"""
Juan García Sánchez, 2023
"""

###############################################################################
#                                                                             #
# Magnitudes' unit converter: U Converter                                     #
# Utilities                                                                   #
#                                                                             #
###############################################################################

import numpy as np
import os
import gc



def MV_reader(file):
    if file.endswith(('.txt', '.dat')):
        return reader_txt(file)
    else:
        print('Error, file format not supported.')
        return [], -1
    

def reader_txt(fl):
    try:
        map_result = np.loadtxt(fl)
        try:
            map_result[0,0]
        except:
            map_result= np.array([map_result.flatten()])
            print(map_result)
        return map_result, 0
    except:
        return [], -1