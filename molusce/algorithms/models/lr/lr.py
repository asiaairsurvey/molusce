# encoding: utf-8


# TODO: make abstract class for all models/managers
# to prevent code coping of common methods (for example _predict method)



import numpy as np

from molusce.algorithms.dataprovider import Raster, ProviderError
from molusce.algorithms.models.sampler.sampler import Sampler


class LRError(Exception):
    '''Base class for exceptions in this module.'''
    def __init__(self, msg):
        self.msg = msg

class LR(object):
    """
    Implements Logistic Regression model definition and calibration
    (maximum liklihood parameter estimation).
    """

    def __init__(self, ns=0, logreg=None):

        from sklearn import linear_model as lm


        if logreg:
            self.logreg = logreg
        else:
            self.logreg = lm.LogisticRegression()

        self.ns = ns            # Neighbourhood size of training rasters.
        self.data = None        # Training data
        self.classlist = None   # List of unique output values of the output raster

        # Results of the LR prediction
        self.prediction = None  # Raster of the LR prediction results
        self.confidence = None  # Raster of the LR results confidence


    def getCoef(self):
        return self.logreg.coef_

    def getConfidence(self):
        return self.confidence

    def getIntercept(self):
        return self.logreg.intercept_

    def getPrediction(self, state, factors):
        self._predict(state, factors)
        return self.prediction

    def _outputConfidence(self, input):
        '''
        Return confidence (difference between 2 biggest probabilities) of the LR output.
        '''
        out_scl = self.logreg.predict_proba(input)[0]
        # Calculate the confidence:
        out_scl.sort()
        return out_scl[-1] - out_scl[-2]

    def _predict(self, state, factors):
        '''
        Calculate output and confidence rasters using LR model and input rasters
        @param state            Raster of the current state (classes) values.
        @param factors          List of the factor rasters (predicting variables).
        '''
        geodata = state.getGeodata()
        rows, cols = geodata['ySize'], geodata['xSize']
        for r in factors:
            if not state.geoDataMatch(r):
                raise LRError('Geometries of the input rasters are different!')

        # Normalize factors before prediction:
        for f in factors:
            f.normalize(mode = 'mean')

        predicted_band  = np.zeros([rows, cols])
        confidence_band = np.zeros([rows, cols])

        sampler = Sampler(state, factors, ns=self.ns)
        mask = state.getBand(1).mask.copy()
        for i in xrange(rows):
            for j in xrange(cols):
                if not mask[i,j]:
                    input = sampler.get_inputs(state, factors, i,j)
                    if input != None:
                        out = self.logreg.predict(input)
                        predicted_band[i,j] = out
                        confidence = self._outputConfidence(input)
                        confidence_band[i, j] = confidence
                    else: # Input sample is incomplete => mask this pixel
                        mask[i, j] = True
        predicted_bands  = [np.ma.array(data = predicted_band, mask = mask)]
        confidence_bands = [np.ma.array(data = confidence_band, mask = mask)]

        self.prediction = Raster()
        self.prediction.create(predicted_bands, geodata)
        self.confidence = Raster()
        self.confidence.create(confidence_bands, geodata)

    def read(self):
        pass

    def save(self):
        pass

    def setTrainingData(self, state, factors, output, mode='All', samples=None):
        '''
        @param state            Raster of the current state (classes) values.
        @param factors          List of the factor rasters (predicting variables).
        @param output           Raster that contains classes to predict.
        @param mode             Type of sampling method:
                                    All             Get all pixels
                                    Normal          Get samples. Count of samples in the data=samples.
                                    Balanced        Undersampling of major classes and/or oversampling of minor classes.
        @samples                Sample count of the training data (doesn't used in 'All' mode).
        '''
        if not self.logreg:
            raise LRError('You must create a Logistic Regression model before!')

        # Normalize factors before sampling:
        for f in factors:
            f.normalize(mode = 'mean')

        sampler = Sampler(state, factors, output, ns=self.ns)
        sampler.setTrainingData(state, factors, output, shuffle=False, mode=mode, samples=samples)

        outputVecLen  = sampler.outputVecLen
        stateVecLen   = sampler.stateVecLen
        factorVectLen = sampler.factorVectLen
        size = len(sampler.data)

        self.data = sampler.data

    def train(self):
        X = np.column_stack( (self.data['state'], self.data['factors']) )
        Y = self.data['output']
        self.logreg.fit(X, Y)


