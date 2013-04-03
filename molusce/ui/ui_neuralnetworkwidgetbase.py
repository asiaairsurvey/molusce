# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/neuralnetworkwidgetbase.ui'
#
# Created: Wed Mar 20 10:55:43 2013
#      by: PyQt4 UI code generator 4.9.1
#
# WARNING! All changes made in this file will be lost!

from PyQt4 import QtCore, QtGui

try:
    _fromUtf8 = QtCore.QString.fromUtf8
except AttributeError:
    _fromUtf8 = lambda s: s

class Ui_Widget(object):
    def setupUi(self, Widget):
        Widget.setObjectName(_fromUtf8("Widget"))
        Widget.resize(660, 412)
        Widget.setWindowTitle(_fromUtf8(""))
        self.gridLayout_2 = QtGui.QGridLayout(Widget)
        self.gridLayout_2.setObjectName(_fromUtf8("gridLayout_2"))
        spacerItem = QtGui.QSpacerItem(20, 77, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.gridLayout_2.addItem(spacerItem, 1, 0, 1, 1)
        self.layoutPlot = QtGui.QVBoxLayout()
        self.layoutPlot.setObjectName(_fromUtf8("layoutPlot"))
        self.gridLayout_2.addLayout(self.layoutPlot, 0, 1, 2, 1)
        self.gridLayout = QtGui.QGridLayout()
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.btnSelectSamples = QtGui.QPushButton(Widget)
        self.btnSelectSamples.setEnabled(False)
        self.btnSelectSamples.setObjectName(_fromUtf8("btnSelectSamples"))
        self.gridLayout.addWidget(self.btnSelectSamples, 8, 3, 1, 1)
        self.leMapAgreement = QtGui.QLineEdit(Widget)
        self.leMapAgreement.setObjectName(_fromUtf8("leMapAgreement"))
        self.gridLayout.addWidget(self.leMapAgreement, 12, 1, 1, 3)
        self.spnNeigbourhood = QtGui.QSpinBox(Widget)
        self.spnNeigbourhood.setMinimum(1)
        self.spnNeigbourhood.setObjectName(_fromUtf8("spnNeigbourhood"))
        self.gridLayout.addWidget(self.spnNeigbourhood, 0, 1, 1, 3)
        self.btnSelectReport = QtGui.QPushButton(Widget)
        self.btnSelectReport.setEnabled(False)
        self.btnSelectReport.setObjectName(_fromUtf8("btnSelectReport"))
        self.gridLayout.addWidget(self.btnSelectReport, 7, 3, 1, 1)
        self.label_6 = QtGui.QLabel(Widget)
        self.label_6.setObjectName(_fromUtf8("label_6"))
        self.gridLayout.addWidget(self.label_6, 10, 0, 1, 1)
        self.label_7 = QtGui.QLabel(Widget)
        self.label_7.setObjectName(_fromUtf8("label_7"))
        self.gridLayout.addWidget(self.label_7, 11, 0, 1, 1)
        self.label_8 = QtGui.QLabel(Widget)
        self.label_8.setObjectName(_fromUtf8("label_8"))
        self.gridLayout.addWidget(self.label_8, 12, 0, 1, 1)
        self.btnTrainNetwork = QtGui.QPushButton(Widget)
        self.btnTrainNetwork.setObjectName(_fromUtf8("btnTrainNetwork"))
        self.gridLayout.addWidget(self.btnTrainNetwork, 9, 0, 1, 4)
        self.leKappa = QtGui.QLineEdit(Widget)
        self.leKappa.setObjectName(_fromUtf8("leKappa"))
        self.gridLayout.addWidget(self.leKappa, 11, 1, 1, 3)
        self.label_3 = QtGui.QLabel(Widget)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)
        self.spnMaxIterations = QtGui.QSpinBox(Widget)
        self.spnMaxIterations.setMinimum(1)
        self.spnMaxIterations.setMaximum(1000000)
        self.spnMaxIterations.setObjectName(_fromUtf8("spnMaxIterations"))
        self.gridLayout.addWidget(self.spnMaxIterations, 2, 1, 1, 3)
        self.leRSquared = QtGui.QLineEdit(Widget)
        self.leRSquared.setObjectName(_fromUtf8("leRSquared"))
        self.gridLayout.addWidget(self.leRSquared, 10, 1, 1, 3)
        self.spnLearnRate = QtGui.QDoubleSpinBox(Widget)
        self.spnLearnRate.setDecimals(2)
        self.spnLearnRate.setMinimum(0.01)
        self.spnLearnRate.setMaximum(1.0)
        self.spnLearnRate.setSingleStep(0.01)
        self.spnLearnRate.setProperty("value", 0.1)
        self.spnLearnRate.setObjectName(_fromUtf8("spnLearnRate"))
        self.gridLayout.addWidget(self.spnLearnRate, 1, 1, 1, 3)
        self.leSamplesPath = QtGui.QLineEdit(Widget)
        self.leSamplesPath.setEnabled(False)
        self.leSamplesPath.setObjectName(_fromUtf8("leSamplesPath"))
        self.gridLayout.addWidget(self.leSamplesPath, 8, 1, 1, 2)
        self.label = QtGui.QLabel(Widget)
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)
        self.chkSaveSamples = QtGui.QCheckBox(Widget)
        self.chkSaveSamples.setObjectName(_fromUtf8("chkSaveSamples"))
        self.gridLayout.addWidget(self.chkSaveSamples, 8, 0, 1, 1)
        self.label_2 = QtGui.QLabel(Widget)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)
        self.chkCreateReport = QtGui.QCheckBox(Widget)
        self.chkCreateReport.setObjectName(_fromUtf8("chkCreateReport"))
        self.gridLayout.addWidget(self.chkCreateReport, 7, 0, 1, 1)
        self.leReportPath = QtGui.QLineEdit(Widget)
        self.leReportPath.setEnabled(False)
        self.leReportPath.setObjectName(_fromUtf8("leReportPath"))
        self.gridLayout.addWidget(self.leReportPath, 7, 1, 1, 2)
        self.leTopology = QtGui.QLineEdit(Widget)
        self.leTopology.setObjectName(_fromUtf8("leTopology"))
        self.gridLayout.addWidget(self.leTopology, 3, 1, 1, 3)
        self.label_5 = QtGui.QLabel(Widget)
        self.label_5.setObjectName(_fromUtf8("label_5"))
        self.gridLayout.addWidget(self.label_5, 3, 0, 1, 1)
        self.label_4 = QtGui.QLabel(Widget)
        self.label_4.setObjectName(_fromUtf8("label_4"))
        self.gridLayout.addWidget(self.label_4, 5, 0, 1, 1)
        self.leDeltaRMS = QtGui.QLineEdit(Widget)
        self.leDeltaRMS.setReadOnly(True)
        self.leDeltaRMS.setObjectName(_fromUtf8("leDeltaRMS"))
        self.gridLayout.addWidget(self.leDeltaRMS, 5, 1, 1, 3)
        self.label_9 = QtGui.QLabel(Widget)
        self.label_9.setObjectName(_fromUtf8("label_9"))
        self.gridLayout.addWidget(self.label_9, 4, 0, 1, 1)
        self.spnMomentum = QtGui.QDoubleSpinBox(Widget)
        self.spnMomentum.setMinimum(0.01)
        self.spnMomentum.setMaximum(1.0)
        self.spnMomentum.setSingleStep(0.01)
        self.spnMomentum.setProperty("value", 0.05)
        self.spnMomentum.setObjectName(_fromUtf8("spnMomentum"))
        self.gridLayout.addWidget(self.spnMomentum, 4, 1, 1, 3)
        self.label_10 = QtGui.QLabel(Widget)
        self.label_10.setObjectName(_fromUtf8("label_10"))
        self.gridLayout.addWidget(self.label_10, 6, 0, 1, 1)
        self.leValidationError = QtGui.QLineEdit(Widget)
        self.leValidationError.setReadOnly(True)
        self.leValidationError.setObjectName(_fromUtf8("leValidationError"))
        self.gridLayout.addWidget(self.leValidationError, 6, 1, 1, 3)
        self.gridLayout_2.addLayout(self.gridLayout, 0, 0, 1, 1)

        self.retranslateUi(Widget)
        QtCore.QMetaObject.connectSlotsByName(Widget)

    def retranslateUi(self, Widget):
        self.btnSelectSamples.setText(QtGui.QApplication.translate("Widget", "Browse...", None, QtGui.QApplication.UnicodeUTF8))
        self.spnNeigbourhood.setSuffix(QtGui.QApplication.translate("Widget", " px", None, QtGui.QApplication.UnicodeUTF8))
        self.btnSelectReport.setText(QtGui.QApplication.translate("Widget", "Browse...", None, QtGui.QApplication.UnicodeUTF8))
        self.label_6.setText(QtGui.QApplication.translate("Widget", "R-squared", None, QtGui.QApplication.UnicodeUTF8))
        self.label_7.setText(QtGui.QApplication.translate("Widget", "Kappa", None, QtGui.QApplication.UnicodeUTF8))
        self.label_8.setText(QtGui.QApplication.translate("Widget", "Map agreement", None, QtGui.QApplication.UnicodeUTF8))
        self.btnTrainNetwork.setText(QtGui.QApplication.translate("Widget", "Train neural network", None, QtGui.QApplication.UnicodeUTF8))
        self.label_3.setText(QtGui.QApplication.translate("Widget", "Maximum iterations", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("Widget", "Neighbourhood", None, QtGui.QApplication.UnicodeUTF8))
        self.chkSaveSamples.setText(QtGui.QApplication.translate("Widget", "Save samples", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("Widget", "Learning rate", None, QtGui.QApplication.UnicodeUTF8))
        self.chkCreateReport.setText(QtGui.QApplication.translate("Widget", "Create report", None, QtGui.QApplication.UnicodeUTF8))
        self.label_5.setText(QtGui.QApplication.translate("Widget", "Network topology", None, QtGui.QApplication.UnicodeUTF8))
        self.label_4.setText(QtGui.QApplication.translate("Widget", "Δ RMS", None, QtGui.QApplication.UnicodeUTF8))
        self.label_9.setText(QtGui.QApplication.translate("Widget", "Momentum", None, QtGui.QApplication.UnicodeUTF8))
        self.label_10.setText(QtGui.QApplication.translate("Widget", "Validation RMS error", None, QtGui.QApplication.UnicodeUTF8))

