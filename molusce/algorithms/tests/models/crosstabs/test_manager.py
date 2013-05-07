# encoding: utf-8

import sys
sys.path.insert(0, '../../../../../')

import unittest
import math

import numpy as np
from numpy import ma as ma

from molusce.algorithms.models.crosstabs.manager  import CrossTableManager
from molusce.algorithms.dataprovider import Raster


class TestCrossTableManager(unittest.TestCase):
    def setUp(self):
        self.init = Raster('../../examples/init.tif')
        self.final  = Raster('../../examples/final.tif')


    def test_getTransitionMatrix(self):
        table = CrossTableManager(self.init, self.final)

        m = table.getTransitionMatrix()
        for i in range(2):
            self.assertAlmostEqual(sum(m[i,:]), 1.0)

        #~ print table.getCrosstable().T
        #~ [[ 4065     4     2     1]
         #~ [ 1657 62871   260   364]
         #~ [  514   539 80689  1969]
         #~ [    2    15     7  8677]]
        #~ print table.pixelArea
        #~ {'unit': 'metre', 'area': 624.5137844096937}

        stat = table.getTransitionStat()
        initArea = [2543020.1301162727, 40688322.08186036, 52278673.40671987, 5433894.43814875]
        finalArea = [3895716.9871476693, 39612284.83132246, 50559386.95823998, 6876521.28013514]
        np.testing.assert_almost_equal(initArea, stat['init'])
        np.testing.assert_almost_equal(finalArea, stat['final'])


if __name__ == "__main__":
    unittest.main()
