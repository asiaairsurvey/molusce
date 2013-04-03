# encoding: utf-8

'''
Some array utilites
'''

import numpy as np

class UtilsError(Exception):
    '''Base class for exceptions in this module.'''
    def __init__(self, msg):
        self.msg = msg



def binaryzation( raster, trueList ):
    '''Raster binarization.
    
    @param trueList     List of raster values converted into true
    @return raster      Binary raster
    '''
    f = np.vectorize(lambda x: True if x in trueList else False )
    return f(raster)


def get_gradations(band):
    return list(np.unique(np.array(band)))


def masks_identity(X, Y):
    '''
    Each raster has a mask. This function verify the identity of masks.
    If the mask is not equal, we have to do both raster mask identical
    by combining masks. Function return updated arrays
    @param X    First raster's array
    @param Y    Second raster's array
    '''
    maskX = X.mask
    maskY = Y.mask
    mask = np.ma.mask_or(maskX, maskY)

    X = np.ma.array(X, mask = mask)
    Y = np.ma.array(Y, mask = mask)
    return X, Y

def reclass(X, bins):
        '''Reclass X to new categories.
        @param bins     List of bins (category bounds):
                Interval         ->   New Class Number
                (-Inf,   bin[0]) ->     1
                [bin[0], bin[1]) ->     2
                [bin[1], bin[2]) ->     3
                ...
                [bin[n-1], bin[n]) ->   n
                [bin[n],      Inf) ->   n+1
        '''
        def findClass(x):
            try:
                m = max([t for t in bins if t<=x])
                result = bins.index(m) + 2
            except ValueError:
                return 1
            return result

        tmp = bins[:]
        tmp.sort()
        if bins!=tmp:
            raise UtilsError('Reclassification error: bins must be sorted!')
        f = np.vectorize(findClass)
        return f(X)

def sizes_equal(X, Y):
    '''
    Define equality dimensions of the two rasters
    @param X    First raster
    @param Y    Second raster
    '''

    return (np.shape(X) == np.shape(Y))

