# -*- coding: utf-8 -*-

# Form implementation generated from reading ui file 'ui/multicriteriaevaluationwidgetbase.ui'
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
        Widget.resize(660, 376)
        Widget.setWindowTitle(_fromUtf8(""))
        self.gridLayout = QtGui.QGridLayout(Widget)
        self.gridLayout.setObjectName(_fromUtf8("gridLayout"))
        self.tblMatrix = MolusceTableWidget(Widget)
        self.tblMatrix.setObjectName(_fromUtf8("tblMatrix"))
        self.tblMatrix.setColumnCount(0)
        self.tblMatrix.setRowCount(0)
        self.gridLayout.addWidget(self.tblMatrix, 0, 0, 1, 2)
        self.label = QtGui.QLabel(Widget)
        self.label.setObjectName(_fromUtf8("label"))
        self.gridLayout.addWidget(self.label, 1, 0, 1, 1)
        self.spnInitialClass = QtGui.QSpinBox(Widget)
        self.spnInitialClass.setObjectName(_fromUtf8("spnInitialClass"))
        self.gridLayout.addWidget(self.spnInitialClass, 1, 1, 1, 1)
        self.label_2 = QtGui.QLabel(Widget)
        self.label_2.setObjectName(_fromUtf8("label_2"))
        self.gridLayout.addWidget(self.label_2, 2, 0, 1, 1)
        self.spnFinalClass = QtGui.QSpinBox(Widget)
        self.spnFinalClass.setObjectName(_fromUtf8("spnFinalClass"))
        self.gridLayout.addWidget(self.spnFinalClass, 2, 1, 1, 1)
        self.btnTrainModel = QtGui.QPushButton(Widget)
        self.btnTrainModel.setObjectName(_fromUtf8("btnTrainModel"))
        self.gridLayout.addWidget(self.btnTrainModel, 3, 0, 1, 2)

        self.retranslateUi(Widget)
        QtCore.QMetaObject.connectSlotsByName(Widget)

    def retranslateUi(self, Widget):
        self.label.setText(QtGui.QApplication.translate("Widget", "Initial class", None, QtGui.QApplication.UnicodeUTF8))
        self.label_2.setText(QtGui.QApplication.translate("Widget", "Final class", None, QtGui.QApplication.UnicodeUTF8))
        self.btnTrainModel.setText(QtGui.QApplication.translate("Widget", "Train model", None, QtGui.QApplication.UnicodeUTF8))

from molusce.moluscetablewidget import MolusceTableWidget
