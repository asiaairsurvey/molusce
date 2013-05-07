# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/logisticregressionwidgetbase.ui'
#
# Created: Wed Apr  3 14:07:34 2013
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
        Widget.resize(569, 162)
        Widget.setWindowTitle(_fromUtf8(""))
        self.verticalLayout = QtGui.QVBoxLayout(Widget)
        self.verticalLayout.setObjectName(_fromUtf8("verticalLayout"))
        self.splitter = QtGui.QSplitter(Widget)
        self.splitter.setOrientation(QtCore.Qt.Horizontal)
        self.splitter.setObjectName(_fromUtf8("splitter"))
        self.layoutWidget = QtGui.QWidget(self.splitter)
        self.layoutWidget.setObjectName(_fromUtf8("layoutWidget"))
        self.gridLayout = QtGui.QGridLayout(self.layoutWidget)
        self.gridLayout.setMargin(0)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.label_4 = QtGui.QLabel(self.layoutWidget)
        self.label_4.setObjectName(_fromUtf8("label_4"))
        self.gridLayout.addWidget(self.label_4, 3, 0, 1, 1)
        self.btnFitModel = QtGui.QPushButton(self.layoutWidget)
        self.btnFitModel.setObjectName(_fromUtf8("btnFitModel"))
        self.gridLayout.addWidget(self.btnFitModel, 4, 0, 1, 2)
        self.label = QtGui.QLabel(self.layoutWidget)
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout.addWidget(self.label, 0, 0, 1, 1)
        self.label_3 = QtGui.QLabel(self.layoutWidget)
        self.label_3.setObjectName(_fromUtf8("label_3"))
        self.gridLayout.addWidget(self.label_3, 2, 0, 1, 1)
        self.spnNeighbourhood = QtGui.QSpinBox(self.layoutWidget)
        self.spnNeighbourhood.setObjectName(_fromUtf8("spnNeighbourhood"))
        self.gridLayout.addWidget(self.spnNeighbourhood, 0, 1, 1, 1)
        self.label_2 = QtGui.QLabel(self.layoutWidget)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.gridLayout.addWidget(self.label_2, 1, 0, 1, 1)
        self.leKappa = QtGui.QLineEdit(self.layoutWidget)
        self.leKappa.setObjectName(_fromUtf8("leKappa"))
        self.gridLayout.addWidget(self.leKappa, 2, 1, 1, 1)
        self.leRSquared = QtGui.QLineEdit(self.layoutWidget)
        self.leRSquared.setObjectName(_fromUtf8("leRSquared"))
        self.gridLayout.addWidget(self.leRSquared, 1, 1, 1, 1)
        self.leAgreement = QtGui.QLineEdit(self.layoutWidget)
        self.leAgreement.setObjectName(_fromUtf8("leAgreement"))
        self.gridLayout.addWidget(self.leAgreement, 3, 1, 1, 1)
        spacerItem = QtGui.QSpacerItem(20, 40, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        self.gridLayout.addItem(spacerItem, 5, 0, 1, 2)
        self.tblCoefficients = MolusceTableWidget(self.splitter)
        self.tblCoefficients.setObjectName(_fromUtf8("tblCoefficients"))
        self.tblCoefficients.setColumnCount(0)
        self.tblCoefficients.setRowCount(0)
        self.verticalLayout.addWidget(self.splitter)

        self.retranslateUi(Widget)
        QtCore.QMetaObject.connectSlotsByName(Widget)

    def retranslateUi(self, Widget):
        self.label_4.setText(QtGui.QApplication.translate("Widget", "Map agreement", None, QtGui.QApplication.UnicodeUTF8))
        self.btnFitModel.setText(QtGui.QApplication.translate("Widget", "Fit model", None, QtGui.QApplication.UnicodeUTF8))
        self.label.setText(QtGui.QApplication.translate("Widget", "Neighbourhood", None, QtGui.QApplication.UnicodeUTF8))
        self.label_3.setText(QtGui.QApplication.translate("Widget", "Kappa", None, QtGui.QApplication.UnicodeUTF8))
        self.spnNeighbourhood.setSuffix(QtGui.QApplication.translate("Widget", " px", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("Widget", "R-squared", None, QtGui.QApplication.UnicodeUTF8))

from molusce.moluscetablewidget import MolusceTableWidget
