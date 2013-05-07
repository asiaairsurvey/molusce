# -*- coding: utf-8 -*-

#******************************************************************************
#
# MOLUSCE
# ---------------------------------------------------------
# Modules for Land Use Change Simulations
#
# Copyright (C) 2012-2013 NextGIS (info@nextgis.org)
#
# This source is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 2 of the License, or (at your option)
# any later version.
#
# This code is distributed in the hope that it will be useful, but WITHOUT ANY
# WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# A copy of the GNU General Public License is available on the World Wide Web
# at <http://www.gnu.org/licenses/>. You can also obtain it by writing
# to the Free Software Foundation, 51 Franklin Street, Suite 500 Boston,
# MA 02110-1335 USA.
#
#******************************************************************************

from PyQt4.QtCore import *
from PyQt4.QtGui import *

from qgis.core import *

from algorithms.models.mce.mce import MCE

from ui.ui_multicriteriaevaluationwidgetbase import Ui_Widget

class MultiCriteriaEvaluationWidget(QWidget, Ui_Widget):
  def __init__(self, plugin, parent=None):
    QWidget.__init__(self, parent)
    self.setupUi(self)

    self.plugin = plugin
    self.inputs = plugin.inputs

    self.settings = QSettings("NextGIS", "MOLUSCE")

    self.manageGui()

    self.btnTrainModel.clicked.connect(self.trainModel)
    self.tblMatrix.cellChanged.connect(self.__checkValue)

  def manageGui(self):
    self.spnInitialClass.setValue(self.settings.value("ui/MCE/initialClass", 0).toInt()[0])
    self.spnFinalClass.setValue(self.settings.value("ui/MCE/finalClass", 0).toInt()[0])

    gradations = self.inputs["initial"].getBandStat(1)['gradation']
    self.spnInitialClass.setRange(min(gradations), max(gradations))
    gradations = self.inputs["final"].getBandStat(1)['gradation']
    self.spnFinalClass.setRange(min(gradations), max(gradations))

    self.__prepareTable()

  def trainModel(self):
    self.settings.setValue("ui/MCE/initialClass", self.spnInitialClass.value())
    self.settings.setValue("ui/MCE/finalClass", self.spnFinalClass.value())

    matrix = self.__checkMatrix()
    if len(matrix) == 0:
      QMessageBox.warning(self.plugin,
                          self.tr("Incorrect matrix"),
                          self.tr("Please fill the matrix with values")
                         )
      return

    self.model = MCE(self.inputs["factors"].values(),
                     matrix,
                     self.spnInitialClass.value(),
                     self.spnFinalClass.value()
                    )

    self.inputs["model"] = self.model

  def __prepareTable(self):
    bandCount = self.inputs["bandCount"]
    self.tblMatrix.clear()
    self.tblMatrix.setRowCount(bandCount)
    self.tblMatrix.setColumnCount(bandCount)

    for row in xrange(bandCount):
      for col in xrange(bandCount):
        item = QTableWidgetItem()
        if row == col:
          item.setText("1")

        if col <= row:
          item.setFlags(item.flags() ^ Qt.ItemIsEditable)

        self.tblMatrix.setItem(row, col, item)

    self.tblMatrix.resizeRowsToContents()
    self.tblMatrix.resizeColumnsToContents()

  def __checkValue(self, row, col):
    item = self.tblMatrix.item(row, col)
    value = float(item.text())
    if value > 9 or value < 1:
      item.setText("")
      return

    self.tblMatrix.blockSignals(True)
    self.tblMatrix.item(col, row).setText(unicode(1.0/value))
    self.tblMatrix.blockSignals(False)

    self.tblMatrix.resizeRowsToContents()
    self.tblMatrix.resizeColumnsToContents()

  def __checkMatrix(self):
    bandCount = self.inputs["bandCount"]
    matrix = []
    for row in xrange(bandCount):
      mrow = []
      for col in xrange(bandCount):
        if self.tblMatrix.item(row, col).text().isEmpty():
          return []

        mrow.append(float(self.tblMatrix.item(row, col).text()))

      matrix.append(mrow)

    return matrix
