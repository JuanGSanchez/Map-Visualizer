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



''' Main function to read the file format and redirect
to the suitable reading function '''
def MV_reader(file):
    if file.endswith(('.txt', '.dat')):
        return reader_txt(file)
    else:
        print('Error, file format not supported.')
        return [], -1
    

''' Reading function for arrays in .txt and .dat files '''
def reader_txt(fl):
    try:
        map_result = np.loadtxt(fl)
        try:
            map_result[0,0]
        except:
            map_result= np.array([map_result.flatten()])
        return map_result, 0
    except:
        return [], -1


''' Function from Stack Overflow to get number's exponent of its scientific notation form'''
def sci_exp(number):
    base = np.log10(number)
    return int(np.floor(base))


''' Function to check if there is a number in the tkinter variable '''
def check_value(new_val, old_val):
    try:
        new_val.get()
    except:
        new_val.set(old_val.get())