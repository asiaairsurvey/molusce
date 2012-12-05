# -*- coding: utf-8 -*-
# Language versions: Python 2.7.2, Qt 4.2, QGIS 1.8
# Open Source software licensed under the terms of GNU GPL 2
# Developer: Denis Alder Consulting <www.denisalder.com>
# On behalf of: Asian Air Services (www.ajiko.co.jp)
# For futher information contact:
# Project Coordinator: Matteo Gisimondi (mto.gismondi@ajiko.co.jp)
# Version date: November 2012

#-------------------------------------------------------------------------
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.

#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.

#    You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#--------------------------------------------------------------------------


#import PyQT and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
from osgeo import gdal
from gdalconst import *

#import resources
import math, re, time, os, sys, traceback, random, gc
from xml.dom import minidom
import numpy as np, numpy.ma as npm

class molusce:

    def __init__(self, iface):
        #creates an instance of the Molusce plugin.  Called by QGIS when plugin loaded
        self.iface = iface
        global Qgif
        Qgif = iface

    def initGui(self):
        #sets up the Molusce plugin. Called by QGIS plugin interface
        self.pim = self.iface.pluginMenu()
        self.act = QAction("Molusce", self.iface.mainWindow())
        self.pim.addAction(self.act)
        QObject.connect(self.act, SIGNAL("triggered()"), self.run)
        #self.iface.addPluginToMenu("Molusce", self.act)

    def run(self):
        # creates the GUI and displays it.  QGIS requires it to be a property
        # of the plugin, otherwise it does not persist
        self.gui = toolBox(self.iface.mainWindow())
        self.gui.show()

    def unload(self):
        self.pim.removeAction(self.act)
        #self.iface.removePluginMenu("Molusce", self.act)
        self.iface.unregisterMainWindowAction(self.act)
        self.act = None

class toolBox:

    def __init__(self, mainWin):
        # create tab widget, tab change event handler
        self.gui = QTabWidget()
        QObject.connect(self.gui, SIGNAL("currentChanged(int)"), self.tabChanged)
        self.gui.setTabPosition(QTabWidget.South)
        # add message log tab - this must be done first as it is referenced by
        # other tabs in code
        global logTab
        logTab =messageLog()
        self.gui.addTab(logTab.mLog,tr(u'Messages'))
        # get version number for window title from metdata.text
        fp = os.path.dirname(__file__)+"/metadata.txt"
        iniText = QSettings(fp, QSettings.IniFormat)
        global verno
        verno = iniText.value('version', '').toString()
        if verno=='':
            logTab.append("Cannot get <i>version</i> from : <u>%s</u>" % (fp))
        iniText.deleteLater()       # release file lock on metadata.txt
        self.gui.setWindowTitle("MOLUSCE %s - Modules for Land Use Change Evaluation" % (verno))
        # add files tab
        global fTab
        fTab = filesTab()
        self.gui.insertTab(0, fTab.gui,tr(u'Inputs'))
        self.gui.setTabToolTip(0, tr(u'Set initial and final LUC maps and driving factors for model'))
        # retrieve widget size/position from project XML
        wingeo = Config("WindowGeometry", -1 , int)
        (x, y, w, h) = (wingeo["x"], wingeo["y"], wingeo["w"], wingeo["h"])
        if x<=0:
            # not saved with project - set default size position
            w = fTab.gui.width()
            h = fTab.gui.height()+25
            (mx, my, mw, mh) = mainWin.geometry().getRect()
            x = mx+(mw-w)/2
            y = mx+(mh-h)/3
        self.gui.setGeometry(x, y, w, h)
        # add area analysis tab
        global areaTab
        areaTab = areaAnalysis()
        self.gui.insertTab(1, areaTab.gui,tr(u'Area Change'))
        self.gui.setTabToolTip(1, tr(u'Analyse LUC area statistics and transition matrix'))
        # Sample selection tab
        global smplTab
        smplTab = riskSample()
        self.gui.insertTab(2, smplTab.gui, tr(u'Sample Data'))
        self.gui.setTabToolTip(2, tr(u'Define risk classes and select sample points for model calibration'))
        # instantiate model classes (ANN, LR) used by model selector
        global annTab
        annTab = ANN_model()
        global LRtab
        LRtab = LR_model()
        global lastModelSet # referenced when updating display after model change
        lastModelSet = None
        # Method selector and Model calibration tab
        global modTab
        modTab = modelSelector()
        self.gui.insertTab(3, modTab.gui,tr(u'Define Model'))
        self.gui.setTabToolTip(3, tr(u'Select a model type and calibrate it with sample data'))
        # Risk and Simulated change maps
        global simTab
        simTab = Simulator()
        self.gui.insertTab(4, simTab.gui,tr(u'Risk Simulation'))
        self.gui.setTabToolTip(4, tr(u'Risk map and simulated LUC using currently defined model'))
        self.gui.setTabToolTip(5, tr(u'Diagnostic, warning and error messages'))

    def tabChanged(self):
        # called when a tab changes, executes any necessary action routines
        # depending on tab involved
        t = self.gui.currentIndex()
        txt = self.gui.tabText(t)
        if txt == tr(u'Area Change'):
            # if area Tab has been selected, check if layers have changed
            if areaTab.needsUpdate():
                # initialise input layers
                areaTab.initialValid = areaTab.initialise(0, fTab.textInitial.text())
                areaTab.finalValid = areaTab.initialise(1, fTab.textFinal.text())
                # update the area change data
                areaTab.doUpdate()
        # save window geometry to project XML whenever a tab is changed
        (x, y, w, h) = self.gui.geometry().getRect()
        if x>0 :
            wingeo = Config("WindowGeometry", -1 , int)
            (wingeo["x"], wingeo["y"], wingeo["w"], wingeo["h"])= (x, y, w, h)

    def show(self):
        # displays tab widget with first tab selected
        self.gui.setCurrentIndex(0)
        self.gui.show()


class areaAnalysis:
    """
    Implements GUI, analysis algorithms, and output of tables and raster maps
    for changes in land-use classes between two images.
    """

    def __init__(self):
        """
        Sets up the GUI for a table of statistics of area and change and
        a transition matrix between classes, with buttons to update tables,
        copy them to the clipboard, and generate an output map of change classes.
        """
        # creates the Widget for Area Change tab and sets out GUI components
        self.gui = QWidget()
        self.config = Config('AreaChange','',str)
        # set names of Inital (0) and Final (1) layers from QGIS project file
        self.nmInitial = self.config["Initial"]
        self.nmFinal = self.config["Final"]
        self.map = [None, None]  # will contain first and last maps as [0]-[1]
        self.paths = ['', '']  # corresponding full path of files
        self.colors = [None, None]
        self.NDV = [-32767, -32767] # no data values in image bands
        self.tMap = None    # output map - None unless initialised
        # <mustUpdate> is set when the update button is clicked
        # or file names have changed.
        self.mustUpdate = False
        # flags set false if layers cannot be assigned to GDAL/QGIS objects ok
        self.initialValid = True
        self.finalValid = True
        # basic layout : Grid with 3 x 2 panels
        layout=QGridLayout()
        # row 0 are captions
        hdr =QLabel(tr(u'<B>Area change statisics, transition matrix and change map</B><BR>'))
        layout.addWidget(hdr, 0, 0, 1, 2, Qt.AlignLeft)
        layout.addWidget(QLabel(tr(u'Class Statistics')), 1, 0, Qt.AlignLeft and Qt.AlignTop)
        layout.addWidget(QLabel(tr(u'Transition Matrix')), 2, 0, Qt.AlignLeft and Qt.AlignTop)
        # in row 2, col 1, grid for class statistics
        self.tblStats = moTableWidget()
        self.tblStats.setFrameStyle(QFrame.NoFrame)
        self.tblStats.viewport().setBackgroundRole(QPalette.Window)
        layout.addWidget(self.tblStats, 1, 1)
        self.tblStats.setColumnCount(8)
        self.tblStats.setRowCount(2)
        self.tblStats.setHorizontalHeaderLabels([tr('Key'), tr('Description'),\
         tr(u'Yr1 km\u00B2'), tr(u'Yr2 km\u00B2'), tr(u'\u0394 km\u00B2'), tr(u'Yr1 %'), tr(u'Yr2 %'),\
         tr(u'\u0394 %')])
        self.tblStats.setSortingEnabled(False)
        self.tblStats.resizeColumnsToContents()
        self.tblStats.resizeRowsToContents()
        # routine to handle edits to class labels (col 1)
        QObject.connect(self.tblStats, SIGNAL("cellChanged(int,int)"), self.editClassLabel)
        # in row 2, col 2, grid for transition matrix
        self.tblMatrix = moTableWidget()
        #self.tblMatrix.setFixedWidth(int(w*0.33))
        self.tblMatrix.setFrameStyle(QFrame.NoFrame)
        self.tblMatrix.viewport().setBackgroundRole(QPalette.Window)
        layout.addWidget(self.tblMatrix, 2, 1)
        self.tblMatrix.setColumnCount(3)
        self.tblMatrix.setRowCount(3)
        self.tblMatrix.resizeColumnsToContents()
        self.tblMatrix.resizeRowsToContents()
        # in row 3, col 1, message area
        self.lblMsg = QLabel('')
        layout.addWidget(self.lblMsg, 3, 0, 1, 2, Qt.AlignLeft)
        # in row 3, col 3, buttons for copy to clipboard, image output
        buttons = QDialogButtonBox()
        # --- update button
        self.btnUpdate=QPushButton(tr('Update Table'))
        self.btnUpdate.setEnabled(True)
        self.btnUpdate.setToolTip(tr('Updates tables with currently selected imagery'))
        buttons.addButton(self.btnUpdate, QDialogButtonBox.ActionRole)
        QObject.connect(self.btnUpdate, SIGNAL("clicked()"), self.forceUpdate)
        # --- Map button
        self.btnMap=QPushButton(tr(u'Make Change Map'))
        self.btnMap.setEnabled(False)
        self.btnMap.setToolTip(tr('Create raster map of changes and adds to project'))
        buttons.addButton(self.btnMap, QDialogButtonBox.ActionRole)
        QObject.connect(self.btnMap, SIGNAL("clicked()"), self.makeChangeMap)
        # finalise layout and display legend window
        layout.addWidget(buttons, 4, 0, 1, 2, Qt.AlignLeft and Qt.AlignBottom)
        layout.setRowStretch(4,9)
        layout.setColumnStretch(1,9)
        self.gui.setLayout(layout)
        # try and reset Stats and Matrix tables from .qgs project file
        self.onStartup()

    def makeChangeMap(self):
        """
        Generates an output GeoTIFF using the GDAL library, with geometry
        copied from the initial land use map.  The output is a 1-band raster
        with classes corresponding the (r,c) elements of the m-matrix of
        classes transitions, so that if for a given pixel the initial class is r,
        the final class c, and there are m classes, the output pixel will have
        value k = (r-1)*m + c
        """
        # called when <dMap> button clicked.  Generates a GeoTiff of the
        # changes and adds to QGIS project
        mapDefaults=Config("ChangeMapDefaults",'', str)
        try:
            if self.tMap is None:
                self.lblMsg.setText(tr(u'Cannot do <b>\u0394Map</b> now.  Please click <b>Update</b> first'))
                return
            # get a default directory for .qgs or same as initial layer
            idir = mapDefaults["file"]
            if idir=='':
                #k = self.paths[0].index(fTab.textInitial.text())
                #idir = self.paths[0][0:k]
                idir = os.path.dirname(self.paths[0])
            # file save dialog
            opf = str(QFileDialog.getSaveFileName(None, tr(u'Output File'), idir, "GeoTIFF (*.tif)"))
            #logTab.append('getSaveFileName result = %s' % (opf))
            if opf=='':
                raise MolusceError(tr('No output file selected'))
            # this extracts the filename, without .tif extension, from the full path
            laynm = re.search(r".+/(.+)\.tif", opf, re.IGNORECASE).group(1)
            if laynm is None:
                raise MolusceError(tr('Cannot add %s to QGIS registry (may need .tif extension)') % (opf))
            mapDefaults["file"] = opf
            # check if in QGIS layer registry already -
            olay = getMapLayerByName(laynm)
            if olay is not None:
                # remove the layer after saving color map
                ct = colorPipe(olay)        # colour table of output layer
                oldct = ct.getColorMap()
                layid = olay.id()
                QgsMapLayerRegistry.instance().removeMapLayer(layid)
                QApplication.processEvents()
            else:
                oldct = None    # if no existing layer, no old color table defined
            # prepare output map
            drv = self.map[0].GetDriver()
            (ysz, xsz) = self.tMap.shape
            omap = drv.Create(opf, xsz, ysz)
            oband = omap.GetRasterBand(1)
            oband.SetNoDataValue(self.NDV[0]) # use same NDV as layer 0
            proj = self.map[0].GetProjection()
            geo = self.map[0].GetGeoTransform()
            omap.SetProjection(proj)
            omap.SetGeoTransform(geo)
            oband.WriteArray(self.tMap, 0, 0)
            oband.FlushCache()
            omap = None
            # add the map layer QGIS
            olay = QgsRasterLayer(opf, laynm)
            if not olay.isValid():
                raise MolusceError(tr('QGIS says %s is an invalid raster layer<br>path = <u>%s</u>'))\
                 % (laynm, opf)
            # ---- create/re-build output map legend ----
            # get the list of values, colours and labels from input and output maps
            mz = max(self.sv.keys())+1      # maximum value for algorithm
            ctOlay = colorPipe(olay)        # colour table of output layer
            for u in self.tm.keys():
                for v in self.tm[u].keys():
                    uv = u*mz + v
                    # see if there is an existing entry for this value
                    (orgb, otxt) = ctOlay[uv]
                    if orgb==0 and otxt=='':
                        # no entry, so create one
                        (urgb, utxt) = self.cTable[u]
                        (vrgb, vtxt) = self.cTable[v]
                        orgb = int(urgb*0.33+vrgb*0.67)
                        otxt = utxt + u'»' + vtxt
                        ctOlay[uv] = (orgb, otxt)
                    # check output for each entry
                    (orgb, otxt) = ctOlay[uv]
            #refresh the legend
            olay.setDrawingStyle(QgsRasterLayer.SingleBandPseudoColor)
            QgsMapLayerRegistry.instance().addMapLayer(olay)
            ctOlay.refresh()
            self.lblMsg.setText(tr(u'Output map created OK'))
        except MolusceError, msg:
            self.lblMsg.setText(tr('Unable to create output map. See Messages...'))
            logTab.append("Error: %s" % (msg))
            logTab.append("No map output created: Process aborted")

    def needsUpdate(self):
        """
        Tests if the names of the initial or final layers have been changed,
        returns True if so, or false if they are unchanged, and also sets
        a class variable <mustUpdate> to T/F correspondingly.
        """
        # called when Area Tab selected, returns True if either layer name has changed.
        if self.nmInitial != fTab.textInitial.text() or self.nmFinal != fTab.textFinal.text():
            self.mustUpdate=True
        return self.mustUpdate

    def forceUpdate(self):
        """
        Called when the <Update> button is clicked, forces update of statistics
        and transition matrix.
        """
        # used to force updating of area tab during development
        self.needsUpdate()
        self.tblMatrix.clearContents()
        self.tblStats.clearContents()
        QApplication.processEvents()
        self.mustUpdate=True
        # initialise input layers
        self.initialValid = self.initialise(0, fTab.textInitial.text())
        self.finalValid = self.initialise(1, fTab.textFinal.text())
        # update tables
        self.doUpdate()

    def onStartup(self):
        """
        When Molusce is first started, ensures the statistics and transition
        matrix tables are populated with the last saved values from the
        .qgis project file, if any.
        """
        # called on startup, populates stats and matrix tables from .qgs file
        self.mustUpdate = not self.loadStatsMatrix()
        # update tables
        self.doUpdate()

    def initialise(self, L, layerName):
        """
        Opens a map layer defining the initial or final land use state and
        sets intenral variables relating to it, especially the GDAL dataset
        map[L] where L=0 for the initial and L=1 for the final state, and the
        full directory path of the file paths[L].  Rteurns True if a valid map
        layer, false otherwise.  Outputs data on file geometry to the message log.
        """
        # opens the map layer and allocates it as a GDAL dataset to the .map
        # property of the class. Returns True if successful, False otherwise
        #logTab.append('areaAnalysis.initialise(%s, %s)' % (L, layerName))
        layer = getMapLayerByName(layerName)
        if layer is None:
            return
        (ndv, hasNDV) = layer.noDataValue()
        self.NDV[L] = ndv if hasNDV else -32767
        self.paths[L] = str(layer.source()) # gives full path including extension
        self.map[L] = gdal.Open( self.paths[L], GA_ReadOnly )
        if self.map[L] is None:
            logTab.append('GDAL could not open: <u>%s</u>' % (self.paths[L]))
            return False
        # output map info to the log
        xsz = self.map[L].RasterXSize
        ysz = self.map[L].RasterYSize
        nb = self.map[L].RasterCount
        geo = self.map[L].GetGeoTransform()
        x0 = geo[0]
        px = abs(int(geo[1]))
        py = abs(int(geo[5]))
        logTab.append('Layer %s: <u>%s</u> %s band, %s x %s pixels of %s x %s m' % \
                (L, self.paths[L], nb, xsz, ysz, px, py))
        #if hasNDV:
        #    logTab.append('No Data Value for <u>%s</u> = %s' % (layerName, self.NDV[L]))
        if self.map[L].RasterCount != 1 :
            logTab.append('<u>%s</u> is not a single band raster' % (self.paths[L]))
            return False
        # info about color table used from initial layer [L=0]
        if L==0:
            self.cTable = colorPipe(layer)
        # logTab.append('Layer %s : colors = %s' % (L, self.colors[L]))
        # if OK, save layer name details to project and return True
        if L==0:
            self.nmInitial = layerName
            self.config["Initial"] = layerName
        else:
            self.nmFinal = layerName
            self.config["Final"] = layerName
        return True

    def doUpdate(self):
        """
        Updates the Statistics and Transition Matrix tables with internally
        calculated values in arrays sv and tm.  If sv and tm do not contain
        valid data, first calls the BuildMatrix routine to regenerate them.
        """
        try:
            # check validity of input layers
            if not (self.initialValid and self.finalValid):
                # display simple error message
                self.lblMsg.setText(tr(u'One of the input layers is invalid. See Message tab ...'))
                return
            # build the transition matrix
            if self.mustUpdate:
                if not self.buildMatrix():
                    self.lblMsg.setText(tr(u'Unable to build Transition Matrix. See Message tab ...'))
                    return
            # set year titles in columns
            yt1 = fTab.textInitialYear.text()
            yt2 = fTab.textFinalYear.text()
            # year 1 km2 column
            qwi = QTableWidgetItem(yt1 + tr(u' km\u00B2'))
            qwi.setTextAlignment(Qt.AlignCenter)
            self.tblStats.setHorizontalHeaderItem(2, qwi)
            # year 1 % column
            qwi = QTableWidgetItem(yt1 + ' %')
            qwi.setTextAlignment(Qt.AlignCenter)
            self.tblStats.setHorizontalHeaderItem(5, qwi)
            # year 2 km2 column
            qwi = QTableWidgetItem(yt2 + tr(u' km\u00B2'))
            qwi.setTextAlignment(Qt.AlignCenter)
            self.tblStats.setHorizontalHeaderItem(3, qwi)
            # year 2 % column
            qwi = QTableWidgetItem(yt2 + ' %')
            qwi.setTextAlignment(Qt.AlignCenter)
            self.tblStats.setHorizontalHeaderItem(6, qwi)
            # reset table data (headings are not affected)
            self.tblStats.clearContents()
            # calculate pixel totals for each year for percent calculation
            Tots = [0, 0]
            m=1
            for (cv, pc) in self.sv.items():
                Tots[0] += float(pc[0])
                Tots[1] += float(pc[1])
                m += 1 # total rows counter
            if Tots[0]!=Tots[1]:
                self.lblMsg.setText(tr(u'Pixel counts on images differ. See Message tab ...'))
                logTab.append("<B>Warning:</B><BR>Pixel counts on images differ(%s = %s, %s = %s).\
                <BR>They may not be compatible or have same geometry.\
                <BR>Statistics and transition matrix are unreliable."\
                 % (yt1, Tots[0], yt2, Tots[1]))
            self.tblStats.setRowCount(m)
            # area per pixel for km2 calculation
            gt = self.map[0].GetGeoTransform()
            pixkm2 = abs(gt[1]*gt[5]*10e-7)        # pixel size assumed to be metres
            # class labels
            self.cLabels = Config("ClassLabels","-",str)
            # show raw pixel counts {0]-[1] for each class value
            r = 0
            # holds km2 and percent value for each year for difference columns
            km2 = [0.0, 0.0]
            pct = [0.0, 0.0]
            # holds values for Totals row
            Tkm2 = [0.0, 0.0]
            Tpct = [0.0, 0.0]
            for (cv, pc) in self.sv.items():
                # class value as row header
                qwi = QTableWidgetItem(str(cv))
                self.tblStats.setVerticalHeaderItem(r, qwi)
                # add a solid square character and colour it according to class
                qwi = QTableWidgetItem(tr(u'\u2588')) # a solid rectangle character, Unicode 2588
                qwi.setTextAlignment(0x84) # centred (4)
                # get colour and label for this row from QGIS legend
                (crgb, txt) = self.cTable[cv]
                qwi.setTextColor(QColor(crgb))
                qwi.setFlags(Qt.ItemFlags(32))
                self.tblStats.setItem(r, 0, qwi)
                # legend text as an editable field
                qwi = QTableWidgetItem(txt)
                qwi.setTextAlignment(0x81)
                qwi.setFlags(Qt.ItemFlags(39))
                qwi.setBackgroundColor(QColor(0xFFFFFF))
                self.tblStats.setItem(r, 1, qwi)
                # pixels as % of total for each year column (L)
                for L in [0, 1]:
                    if Tots[L]>0:
                        # get km2 and % area from raw pixel count
                        km2[L] = pc[L]*pixkm2
                        pct[L] = float(pc[L])/Tots[L]*100 if Tots[L]>0 else 0
                        # add totals across rows
                        Tkm2[L] += km2[L]
                        Tpct[L] += pct[L]
                        # put km2 values in table cell (columns 2 or 3)
                        setCell(self.tblStats, r, 2+L, "%10.1f" , km2[L])
                        # put % values in table cell (columns 5 or 6)
                        setCell(self.tblStats, r, 5+L, "%6.2f" , pct[L])
                # set km2 and % change
                setCell(self.tblStats, r, 4, "%10.1f" , km2[1]-km2[0])
                setCell(self.tblStats, r, 7, "%6.2f" , pct[1]-pct[0])
                # increment row counter in table
                r += 1
            # add Totals row heading
            qwi = QTableWidgetItem(tr(u'\u03A3'))
            self.tblStats.setVerticalHeaderItem(r, qwi)
            # Total km2 and % area
            for L in [0, 1]:
                # put km2 values in table cell (columns 2 or 3)
                setCell(self.tblStats, r, 2+L, "%10.1f" , Tkm2[L])
                # put % values in table cell (columns 5 or 6)
                setCell(self.tblStats, r, 5+L, "%6.2f" , Tpct[L])
            # Total km2 and % change
            setCell(self.tblStats, r, 4, "%10.1f" , Tkm2[1]-Tkm2[0])
            setCell(self.tblStats, r, 7, "%6.2f" , Tpct[1]-Tpct[0])
            # set row and column sizes to data
            self.tblStats.resizeColumnsToContents()
            self.tblStats.resizeRowsToContents()
            #self.tblStats.hideColumn(1) # description
            #self.tblStats.hideColumn(2) # key
            # Transition Matrix output - reset matrix and define size
            self.tblMatrix.clear()
            self.tblMatrix.setRowCount(m)
            self.tblMatrix.setColumnCount(m)
            # set column and row headings
            i = 0
            for k in self.sv.keys():
                qwi = QTableWidgetItem(str(k))
                self.tblMatrix.setVerticalHeaderItem(i, qwi)
                qwi = QTableWidgetItem(str(k))
                self.tblMatrix.setHorizontalHeaderItem(i, qwi)
                i += 1
            # totals row/column
            qwi = QTableWidgetItem(tr(u'\u03A3')) #Sigma
            self.tblMatrix.setVerticalHeaderItem(i, qwi)
            qwi = QTableWidgetItem(tr(u'\u03A3')) #Sigma
            self.tblMatrix.setHorizontalHeaderItem(i, qwi)
            # set a row of column totals
            cTot = dict.fromkeys(range(0,m), 0.0)
            # loop through rows
            r = 0
            for rv in self.sv.keys():
                # loop to add row totals <rtot>
                rtot = 0.0
                for cv in self.sv.keys():
                    if rv in self.tm and cv in self.tm[rv]: # skip empty cells
                        rtot += float(self.tm[rv][cv])
                # loop to output transition probabilities (sum = 1)
                c = 0
                for cv in self.sv.keys():
                    if rv in self.tm and cv in self.tm[rv]:     # skip empty cells
                        p = float(self.tm[rv][cv])/Tots[0] if Tots[0]>0 else 0  # transition probability
                        setCell(self.tblMatrix, r, c, "%7.4f", p)
                        cTot[c] += p
                    c += 1
                # calculate row total and column total of row total
                ptot = rtot / Tots[0] if Tots[0]>0 else 0
                setCell(self.tblMatrix, r, c, "%7.4f", ptot)
                cTot[c] += ptot
                # increment row counter
                r += 1
            # output totals row
            for c in xrange(0, m):
                setCell(self.tblMatrix, r, c, "%7.4f", cTot[c])
            # adjust row/column height/width to minimize space taken by table
            self.tblMatrix.resizeColumnsToContents()
            self.tblMatrix.resizeRowsToContents()
        except Exception:
            errMsg()
            logTab.append("Transition Matrix update aborted due to error")


    def buildMatrix(self):
        """
        Process the initial-final land use maps to build internal arrays for
        class statistics, transition matrix and the output map.  This version
        uses numpy for fast processing of large arrays.  Returns True for
        normal completion or False on error or if cancelled.
        """
        # builds the transition matrix and class totals.  Creates 3 objects:
        # .tm[i][j]  - total pixels of class [i] on 1st image and [j] on 2nd.
        # .sv[i][L]  - sum of class values [i] for images [L] = 0 or 1.
        # .om[x, y]  - a GDAL compatible numpy array with data for the output map
        # images must have the same geometry. Returns True if ends successfully.
        try:
            # inform user of progress and start process timer
            start_time = time.time()
            # get geometry information about image datasets
            geo = [self.map[0].GetGeoTransform(), self.map[1].GetGeoTransform()]
            imgsz = [{'x': self.map[0].RasterXSize, 'y': self.map[0].RasterYSize } ,
                {'x': self.map[1].RasterXSize, 'y': self.map[1].RasterYSize }]
            # check geometry and size are the same, abort if not
            #if geo[0]!= geo[1] or imgsz[0]!=imgsz[1]:
            if imgsz[0]!=imgsz[1]:
                raise MolusceError(tr('Images have incompatible geometry'))
            # reset variables
            self.sv = {}        # stats values for initial/final images
            aMap = [None, None] # images as numpy arrays
            mMap = [None, None] # images as numpy arrays masked by NDV
            phase = ['initial', 'final']    #processing phases
            vmax = -32767       # highest value encountered on band
            for L in [0, 1]:
                # notify user of processing phase
                self.lblMsg.setText('Analysing %s image ...' % (phase[L]))
                QApplication.processEvents()
                # get each map as numpy array from GDAL dataset object
                aMap[L] = self.map[L].GetRasterBand(1).ReadAsArray(0, 0, imgsz[L]['x'], imgsz[L]['y'])
                mMap[L] = npm.masked_equal(aMap[L], self.NDV[L]) # array masked by NDV
                fmm = mMap[L].compressed()     #  1-d array with masked data removed
                uv = np.unique(fmm)         # list of unique values
                bc = np.bincount(fmm)       # counts by integer bins
                bcc = npm.masked_equal(bc, 0).compressed() # zero values removed
                # save results in sv structure for later processing
                k = 0
                for v in uv:
                    if v not in self.sv:
                        self.sv[v] = [0, 0]
                    self.sv[v][L] = bcc[k]
                    k += 1
            # start transition matrix processing
            self.lblMsg.setText('Generating Transition Matrix ...')
            QApplication.processEvents()
            self.tm = {}                    # saves transition matrix values
            mz = max(self.sv.keys())+1      # maximum value for algorithm
            self.tMap = mMap[0]*mz + mMap[1]# 2-D map of transition values
            fmm = self.tMap.compressed()    #  1-d array with masked data removed
            utv = np.unique(fmm)            # list of unique ransition values
            bc = np.bincount(fmm)           # counts by integer bins
            ctv = npm.masked_equal(bc, 0).compressed() # counts of transition values
            # convert linear form into 2-D tm structure
            k = 0
            for uv in utv:
                u = uv // mz                # integer result = initial value
                v = uv % mz                 # remainder = final value
                if u not in self.tm:        # create dictionary entry for u
                    self.tm[u]= {}
                self.tm[u][v] = ctv[k]      # insert entry for [u][v]
                k += 1
            # finished processing - tidy up
            secs = time.time() - start_time
            self.lblMsg.setText('Update completed : %0.3f secs' % (secs))
            pix = fmt000(imgsz[0]['x'] * imgsz[0]['y'])
            #logTab.append('Area change analysis of %s pixels done in %0.3f secs' % (pix, secs))
            QApplication.processEvents()
            # save stats matrix to .qgs project
            self.saveStatsMatrix()
            self.mustUpdate = False
            # enable map output button
            self.btnMap.setEnabled(True)
            return True
        except MolusceError, msg:
            self.lblMsg.setText('Aborted due to errors. See Messages...')
            logTab.append("Process aborted due to error: %s" % (msg))
            QApplication.processEvents()
            return False

    def editClassLabel(self, row, col):
        """
        Routine activated when class labels in Statistics table are edited.
        Saves edited text to .qgs project file
        """
        # called when label in any row, col 1 is changed
        if col==1:
            v = float(self.tblStats.verticalHeaderItem(row).text())
            txt = self.tblStats.item(row, 1).text()
            self.cLabels["row%s" % (row)] = txt
            #update QGIS legend with change
            (c, t) = self.cTable[v]
            self.cTable[v] = (c, txt)
            self.cTable.refresh()
            #logTab.append('Called editClassLabel(%s, %s) with %s' % (row, col, txt))

    def saveStatsMatrix(self):
        """
        Saves the statistics array sv and the transition matrix tm to the
        .qgs project file
        """
        # Saves the raw stats and transition matrix tables to the project
        cfgStats = Config('StatsMatrix')
        cfgStats['Classes'] = len(self.sv)
        i= 0
        for k in self.sv.keys():
            cfgStats['Class'+str(i)] = k
            cfgStats['sv'+str(k)+'A'] = self.sv[k][0]
            cfgStats['sv'+str(k)+'B'] = self.sv[k][1]
            if k in self.tm.keys():
                for j in self.tm[k].keys():
                    cfgStats['tm'+str(k)+'x'+str(j)] = self.tm[k][j]
            i += 1

    def loadStatsMatrix(self):
        """
        Re-loads the statistics array sv and the transition matrix tm from the
        .qgs project file
        """
        # Tries to load the Stats and transition Matrix from the project
        # XML file.  Returns True if successful, False otherwise
        if self.mustUpdate:
            # this flag is toggled on by the Update button
            logTab.append(tr('Bypassing StatsMatrix in project XML...'))
            self.mustUpdate = False
            return False
        # initialise input layers
        self.initialValid = self.initialise(0, fTab.textInitial.text())
        self.finalValid = self.initialise(1, fTab.textFinal.text())
        # retrieve data from .qgs file
        cfgStats = Config('StatsMatrix')
        n = cfgStats['Classes']
        if n==0:
            # nothing saved, so return with False
            logTab.append(tr('Cannot retrieve StatsMatrix from project XML'))
            return False
        # declare sv and tm as dictionaries
        self.tm = {}
        self.sv = {}
        # populate sv with keys for classes
        for i in xrange(0, n):
            k = cfgStats['Class'+str(i)]
            self.sv[k]=[0, 0]
        # retrieve pixel counts for sv and tm
        for i in self.sv.keys():
            self.sv[i] = [cfgStats['sv'+str(i)+'A'], cfgStats['sv'+str(i)+'B']]
            self.tm[i] = {}
            for j in self.sv.keys():
                self.tm[i][j] = cfgStats['tm'+str(i)+'x'+str(j)]
        return True

class filesTab:
    """
    Implements the GUI for selecting layers (files) representing initial and
    final land use classes, and layers for factors driving land use change.
    Designed to be loaded as one tab in a tabbed dialog <toolBox> that
    implements all the functions of Molusce.
    """

    def __init__(self):
        self.gui = QWidget()
        widthln = 250 # width of layer names
        widthyr = 60 # width of year boxes
        widthtxt = 150 # width of left hand text
        widthbtn = 80 # width of buttons
        widthxtra = 100 # extra bit allowed
        #self.gui.setFixedSize(widthtxt+widthbtn+widthln*2+widthyr+ widthxtra, 200)
        self.gui.setGeometry(0, 0, widthtxt+widthbtn+widthln*2+widthyr+ widthxtra, 300)
        layout=QGridLayout()
        lblInfo=QLabel(tr(u'<B>Select map layers for Initial/Final Land Use Classes and driving factors for change</B>'))
        # cordinates in the grid layout are (row, col, row span, col span)
        layout.addWidget(lblInfo, 0, 0, 1, -1, Qt.AlignLeft)
        # add heading text and list box for possible layers
        lblLayerList = QLabel(tr('Compatible Layers'))
        layout.addWidget(lblLayerList,1,0)
        # list box for layers
        self.layerList = QListWidget()
        #self.layerList.setFixedWidth(widthln)
        layout.addWidget(self.layerList,2, 0, 5, 1)
        # buttons - from, to, ->, <-
        btnInitial=QPushButton(tr(u'Initial'))
        QObject.connect(btnInitial, SIGNAL("clicked()"), self.clickBtnInitial)
        layout.addWidget(btnInitial,2, 1)
        btnFinal=QPushButton(tr(u'Final'))
        QObject.connect(btnFinal, SIGNAL("clicked()"), self.clickBtnFinal)
        layout.addWidget(btnFinal,3, 1)
        btnAdd=QPushButton(tr(u'Add'))
        QObject.connect(btnAdd, SIGNAL("clicked()"), self.clickBtnAdd)
        layout.addWidget(btnAdd,5, 1)
        btnRemove=QPushButton(tr(u'Remove'))
        QObject.connect(btnRemove, SIGNAL("clicked()"), self.clickBtnRemove)
        layout.addWidget(btnRemove,6, 1)
        # heading text and boxes for initial and final area layers
        lblAreaLayers = QLabel(tr('Land Use Classification'))
        layout.addWidget(lblAreaLayers, 1 , 2)
        self.textInitial = QLineEdit()
        #self.textInitial.setFixedWidth(widthln)
        layout.addWidget(self.textInitial, 2 , 2)
        self.textFinal = QLineEdit()
        #self.textFinal.setFixedWidth(widthln)
        layout.addWidget(self.textFinal, 3 , 2)
        # heading and list box for factors driving change
        lblFactorLayers = QLabel(tr('Factors driving land use change'))
        layout.addWidget(lblFactorLayers, 4 , 2, 1, 1, Qt.AlignLeft and Qt.AlignBottom)
        self.listFactorLayers = QListWidget()
        #self.listFactorLayers.setFixedWidth(widthln)
        layout.addWidget(self.listFactorLayers, 5, 2, 2, 1)
        # heading text and boxes for initial and final years
        lblYears = QLabel(tr('Year'))
        layout.addWidget(lblYears, 1 , 3)
        self.textInitialYear = QLineEdit()
        self.textInitialYear.setFixedWidth(widthyr)
        layout.addWidget(self.textInitialYear, 2 , 3)
        self.textFinalYear = QLineEdit()
        self.textFinalYear.setFixedWidth(widthyr)
        layout.addWidget(self.textFinalYear, 3 , 3)
        # set bottom and right as blank space togrow when window expanded
        layout.setRowStretch(7,9)
        layout.setColumnStretch(4,9)
        self.gui.setLayout(layout)
        # refresh the list of layers
        self.updateLayerList()
        # create config object for this tab and re-load any current config
        self.config = Config('Imagery','',str)
        self.loadSettings()

    def clickBtnInitial(self):
        # executed when [Initial] button clicked.  Transfers currently
        # highlighted layer name in layer list to text box for Initial
        # state layer, and tries to extract year from it.
        pick = self.layerList.currentItem()
        if pick is not None: # will ignore button click if no layer selected
            # copy layer name across
            pickt = pick.text()
            self.textInitial.setText(pickt)
            # try and extract a year 1900 to 2099 from the name
            pat = re.compile(r".*((19|20)\d\d).*")
            txt = pat.search(pickt)
            if txt != None :
                yr = txt.group(1)
                self.textInitialYear.setText(yr)
            else:
                self.textInitialYear.setText('?')
            # save this setting to the project
            self.config["Initial"] = self.textInitial.text()
            self.config["InitialYear"] = self.textInitialYear.text()

    def clickBtnFinal(self):
        # executed when [Final] button clicked.  Transfers currently
        # highlighted layer name in layer list to text box for Final
        # state layer, and tries to extract year from it.
        pick = self.layerList.currentItem()
        if pick is not None: # will ignore button click if no layer selected
            # copy layer name across
            pickt = pick.text()
            self.textFinal.setText(pickt)
            # try and extract a year 1900 to 2099 from the name
            pat = re.compile(r".*((19|20)\d\d).*")
            txt = pat.search(pickt)
            if txt != None :
                yr = txt.group(1)
                self.textFinalYear.setText(yr)
            else:
                self.textFinalYear.setText('?')
            # save this setting to the project
            self.config["Final"] = self.textFinal.text()
            self.config["FinalYear"] = self.textFinalYear.text()

    def clickBtnAdd(self):
        # executed when [Add] button clicked.  Transfers currently
        # highlighted layer name in layer list to list Box for driver
        # factor layers.  Does not allow duplicate additions.
        pick = self.layerList.currentItem()
        if pick is not None: # will ignore button click if no layer selected
            # check layer not in list of factors
            pickt = pick.text()
            inlist = self.listFactorLayers.findItems(pickt, Qt.MatchExactly)
            if len(inlist)==0 :
                self.listFactorLayers.addItem(pickt)
                self.saveFactorSettings()

    def clickBtnRemove(self):
        # executed when [Remove] button clicked.  Deletes currently
        # highlighted layer in list of driver factors
        r = self.listFactorLayers.currentRow()
        if r>=0: # will ignore button click if no layer selected
            void = self.listFactorLayers.takeItem(r)
            self.saveFactorSettings()

    def updateLayerList(self):
        # add raster and vector layer names to drop downs
        layers = QgsMapLayerRegistry.instance().mapLayers()
        for name, layer in layers.iteritems():
            # only raster layers shown
            if layer.type() == layer.RasterLayer :
                self.layerList.addItem(layer.name())

    def loadSettings(self):
        # reloads initial, final and driver file names from the project file.
        # Called when widget is initialised.
        self.textInitial.setText(self.config["Initial"])
        self.textFinal.setText(self.config["Final"])
        self.textInitialYear.setText(self.config["InitialYear"])
        self.textFinalYear.setText(self.config["FinalYear"])
        nf_text = self.config["NrFactorLayers"]
        nf = int(nf_text) if nf_text>'' else 0
        #logTab.append("Loading %s factor layers" % (nf))
        for f in range(0, nf):
            self.listFactorLayers.addItem(self.config["FactorLayer%s" % (f)])

    def saveFactorSettings(self):
        # saves factor layer list to project .qgs file
        nf = self.listFactorLayers.count()
        #logTab.append("Saving %s factor layers" % (nf))
        self.config["NrFactorLayers"] = str(nf)
        for f in range(0, nf):
            self.config["FactorLayer%s" % (f)] = self.listFactorLayers.item(f).text()

    def getLayers(self):
        # reads list of layers from Inputs tab into lists of GDAL and QGIS
        # map layer objects.  Used by Modelling functions as input layers.
        try:
            self.mfactG = list()     # map layers as GDAL objects
            self.mfactL = list()    # map layers as Layer objects
            # base map is always factor 0
            self.mfactG.append(areaTab.map[0])
            fln = fTab.textInitial.text()
            layer = getMapLayerByName(fln)
            if layer is None: # unexpected - log message and abort
                logTab.append(tr(u'Warning : Could not find base layer: <u>%s</u>') % (fln))
                return
            self.mfactL.append(layer)
            #logTab.append('Added <u>%s</u> to layer list' % (fln))
            path = str(layer.source())
            # add further factors, if any from FactorLayers list in Input tab
            nf = self.listFactorLayers.count()
            for f in range(0, nf):
                fln = fTab.listFactorLayers.item(f).text()
                layer = getMapLayerByName(fln)
                if layer is None: # unexpected - log message and skip to next layer
                    raise MolusceError('Could not find factor layer: <u>%s</u>' % (fln))
                path = str(layer.source()) # gives full path including extension
                gmap = gdal.Open(path, GA_ReadOnly)
                if gmap is None:
                    raise MolusceError('GDAL could not open: <u>%s</u>' % (path))
                self.mfactG.append(gmap)
                self.mfactL.append(layer)
                #logTab.append('Added <u>%s</u> to layer list' % (fln))
        except Exception:
            errMsg()        # general error handler

    def show(self):
        self.gui.show()

class riskSample():
    """
    Defines risk classes, and selects a sample based on the risk classes.
    Outputs shape file of sample points with factor attributes.  Saves sample
    points in the project file.  Produces transition table of risk classes
    and frequencies in sample.
    """

    def __init__(self, parent=None):
        # sets up user interface for sample selection
        self.gui = QWidget()
        layout=QGridLayout()
        txtBoxWidth = 60    # common width for most of the input boxes
        hdr = QLabel(tr(u'<b>Risk classes and sample selection for model calibration</b>'))
        layout.addWidget(hdr, 0, 0, 1, 4)
        # defaults from QGIS project for options
        self.config = Config("Sample_options",'', str)
        # define risk class labels and values
        lblRisk0Text = QLabel(tr(u'Risk 0 decription'))
        layout.addWidget(lblRisk0Text, 1 ,0)
        lblRisk1Text = QLabel(tr(u'Risk 1 description'))
        layout.addWidget(lblRisk1Text, 3 ,0)
        lblRisk0Lucs = QLabel(tr(u'Land use classes'))
        layout.addWidget(lblRisk0Lucs, 2 ,0)
        lblRisk1Lucs = QLabel(tr(u'Land use classes'))
        layout.addWidget(lblRisk1Lucs, 4 ,0)
        # use default labels from .qgs file or Forest/Non-forest if none set
        if self.config["Risk0Text"]=='':
            txt1 = 'Forest'
            txt2 = 'Non-Forest'
        else:
            txt1 = self.config["Risk0Text"]
            txt2 = self.config["Risk1Text"]
        self.textRisk0 = QLineEdit(txt1)
        self.textRisk0.setFixedWidth(80)
        layout.addWidget(self.textRisk0, 1 , 1)
        self.textRisk1 = QLineEdit(txt2)
        self.textRisk1.setFixedWidth(80)
        layout.addWidget(self.textRisk1, 3 , 1)
        # class values for each category
        txt1 = self.config["Risk0Classes"]
        txt2 = self.config["Risk1Classes"]
        self.textRisk0Lucs = QLineEdit(txt1)
        self.textRisk0Lucs.setFixedWidth(txtBoxWidth)
        layout.addWidget(self.textRisk0Lucs, 2 , 1)
        self.textRisk1Lucs = QLineEdit(txt2)
        self.textRisk1Lucs.setFixedWidth(txtBoxWidth)
        layout.addWidget(self.textRisk1Lucs, 4 , 1)
        # get risk factors as list of integers for use by getRisk() etc.
        self.risk = list()
        csl = re.compile(r"\A\s*\d+(\s*,\s*\d)*\s*\Z")     # match a comma-seprated number list
        if re.match(csl, self.textRisk1Lucs.text()):
            for r in self.textRisk1Lucs.text().split(","):
                self.risk.append(int(r))
        # text box to enter number of samples
        lblNrSamples = QLabel(tr('Number of Samples'))
        layout.addWidget(lblNrSamples, 5 ,0)
        # retrieve number of samples from .qgs or use a default
        if self.config["NrSamples"]=='':
            txt = '100'
        else:
            txt = self.config["NrSamples"]
        self.textNrSamples = QLineEdit(txt)
        self.textNrSamples.setFixedWidth(txtBoxWidth)
        layout.addWidget(self.textNrSamples, 5 , 1)
        # spinner for sample bias factor
        lblBiasFactor = QLabel(tr(u'Sample Bias Factor'))
        layout.addWidget(lblBiasFactor, 6 ,0)
        # retrieve neighbourhood size from .qgs or use a default
        if self.config["SampleBiasFactor"]=='':
            sbf=3
        else:
            sbf = int(self.config["SampleBiasFactor"])
        self.spinSbf = QSpinBox()
        self.spinSbf.setFixedWidth(txtBoxWidth)
        self.spinSbf.setValue(sbf)
        self.spinSbf.setSingleStep(1)
        self.spinSbf.setMinimum(1)
        self.spinSbf.setMaximum(10)
        layout.addWidget(self.spinSbf, 6 , 1)
        # directory for sample workfiles
        self.lblSetDir = QLabel(tr(u'Workfile directory'))
        layout.addWidget(self.lblSetDir, 7 ,0)
        # button to set open director dialog
        btnSetDir=QPushButton(u'...')
        btnSetDir.setFixedWidth(30)
        QObject.connect(btnSetDir, SIGNAL("clicked()"), self.setSampleDir)
        layout.addWidget(btnSetDir, 7 ,1)
        # checkbox to show sample shapefile if ticked
        self.chkShowMap = QCheckBox("Show sample map")
        tick = bool(self.config["ShowMap"])
        self.chkShowMap.setChecked(tick)
        layout.addWidget(self.chkShowMap, 8 ,0)
        # button to set name of sample file
        btnSampleMap=QPushButton(u'...')
        btnSampleMap.setFixedWidth(30)
        QObject.connect(btnSampleMap, SIGNAL("clicked()"), self.setSampleShapeFile)
        layout.addWidget(btnSampleMap, 8 ,1)
        # horizontal line across 2 columns
        hline1 = QFrame()
        hline1.setFrameStyle(QFrame.HLine|QFrame.Sunken)
        layout.addWidget(hline1,9,0,1,2)
        # Training Run button
        lblSelect = QLabel(tr(u'Make sample selection'))
        layout.addWidget(lblSelect , 10 ,0)
        btnSelect=QPushButton(tr(u'OK'))
        btnSelect.setFixedWidth(40)
        QObject.connect(btnSelect, SIGNAL("clicked()"), self.doSelection)
        layout.addWidget(btnSelect, 10, 1)
        # vertical line down 8 rows in column 3
        vline1 = QFrame()
        vline1.setFrameStyle(QFrame.VLine|QFrame.Sunken)
        layout.addWidget(vline1, 1, 2, 10, 1)
        # transition matrix heading
        lblTransMat = QLabel(tr(u'Transition Matrix'))
        layout.addWidget(lblTransMat, 1, 3)
        # transition matrix framework
        self.TransMat = moTableWidget()
        self.TransMat.setFrameStyle(QFrame.NoFrame)
        self.TransMat.viewport().setBackgroundRole(QPalette.Window)
        self.TransMat.setColumnCount(3)
        self.TransMat.setRowCount(3)
        for (i, h) in {0:'0', 1:'1', 2:u'\u03A3'}.items():
            self.TransMat.setVerticalHeaderItem(i, QTableWidgetItem(h))
            self.TransMat.setHorizontalHeaderItem(i, QTableWidgetItem(h))
        self.updateTransMat()
        self.TransMat.resizeColumnsToContents()
        self.TransMat.resizeRowsToContents()
        layout.addWidget(self.TransMat, 2, 3, 4, 1)
        # transition matrix heading
        lblSmplFreq = QLabel(tr(u'Sample Frequency'))
        layout.addWidget(lblSmplFreq, 6, 3)
        # transition matrix framework
        self.SmplFreq = moTableWidget()
        self.SmplFreq.setFrameStyle(QFrame.NoFrame)
        self.SmplFreq.viewport().setBackgroundRole(QPalette.Window)
        self.SmplFreq.setColumnCount(3)
        self.SmplFreq.setRowCount(3)
        for (i, h) in {0:'0', 1:'1', 2:u'\u03A3'}.items():
            self.SmplFreq.setVerticalHeaderItem(i, QTableWidgetItem(h))
            self.SmplFreq.setHorizontalHeaderItem(i, QTableWidgetItem(h))
        # initialise the sample from config data if possible
        self.tempSampleDir = self.config['TempSampleDir']
        if self.tempSampleDir>'':
            self.tempSampleDir = getDefaultPath()
        self.smplPts = self.initSample(mode=0)
        self.updateSmplFreq()
        self.vldnPts = self.initSample(mode=1)
        self.SmplFreq.resizeColumnsToContents()
        self.SmplFreq.resizeRowsToContents()
        layout.addWidget(self.SmplFreq, 7, 3, 4, 1)
        # a bit of space at right
        layout.setRowStretch(11,9)
        #layout.setColumnStretch(2,8)
        layout.setColumnStretch(4,9)
        self.gui.setLayout(layout)

    def initSample(self, mode=0):
        # initialises sample arrays from file if possible
        try:
            keys = ['C','V']    # get Calibration or Validation sample
            pts = self.loadSampleData(keys[mode])
            if pts is not None:
                smplPts = pts.tolist()
                return smplPts
        except Exception:
            errMsg()        # general error handler

    def setSampleDir(self):
        # sets the directory name for temporary files with sample data
        try:
            # config object and dialog title according to type of file
            title = tr(u'Directory for sample data workfiles')
            # use current value as a default, or the
            self.tempSampleDir = self.config['TempSampleDir']
            if self.tempSampleDir>'':
                idir = self.tempSampleDir
            else:
                idir = getDefaultPath()
            # get directory dialog -
            tmpdir = str(QFileDialog.getExistingDirectory(None, title, idir))
            if tmpdir>'':
                # save directory name to class and to .qgs project file
                self.config['TempSampleDir'] = tmpdir
                self.tempSampleDir = tmpdir
                logTab.append('Sample Directory is <u>%s</u>' % tmpdir)
        except Exception:
            errMsg()            # general error handler

    def saveSampleData(self, key, smplPts):
        # saves sample data to a temporary file and stores name
        # in config object with label Sample.key
        try:
            fln = self.tempSampleDir + '/~sample_%s.dat' % key
            logTab.append(tr(u'Sample %s being saved as <u>%s</u>') % (key, fln))
            # save Sample in general format with comma separators
            pts = np.array(smplPts)
            np.savetxt(fln, pts, '%s', ',')
        except Exception:
            errMsg()            # general error handler

    def loadSampleData(self, key):
        # returns a numpy array loaded from a temporary file referenced by <key>
        try:
            # construct file name
            fln = self.tempSampleDir + '/~sample_%s.dat' % key
            logTab.append(tr(u'Sample %s being loaded from <u>%s</u>') % (key, fln))
            pts = np.loadtxt(fln, delimiter=',')
            return pts
        except IOError as e:
            logTab.append('Unable to read sample data : %s' % (e))
        except Exception:
            errMsg()            # general error handler

    def doSelection(self):
        # selection OK button clicked.  Check and save option values
        try:
            # clear frequency table to flag something is happening
            self.clearSmplFreq()
            # validate input fields
            decnr = re.compile(r"^[0-9]+\.?[0-9]+$")     # match a decimal number
            intnr = re.compile(r"^[0-9]+$")             # match an integer number
            nzint = re.compile(r"^[1-9][0-9]*$")             # match a non-zero integer number
            decnre = re.compile(r"^[\-0-9]+\.?[0-9]+$|^$")     # match a decimal or empty string
            if not re.match(intnr, self.textNrSamples.text()):
                raise MolusceError(u"Number of samples invalid: %s" % self.textNrSamples.text())
            # save validated settings to project .qgs file (via Config object)
            self.config["ShowMap"] = '1' if self.chkShowMap.isChecked() else '0'
            self.config["NrSamples"] = self.textNrSamples.text()
            self.config["SampleBiasFactor"] = str(self.spinSbf.value())
            self.config["Risk0Text"] = self.textRisk0.text()
            self.config["Risk1Text"] =  self.textRisk1.text()
            self.config["Risk0Classes"] = self.textRisk0Lucs.text()
            self.config["Risk1Classes"] =  self.textRisk1Lucs.text()
            # validate and update list of risk factors
            self.risk = list()
            csl = re.compile(r"\A\s*\d+(\s*,\s*\d)*\s*\Z")     # match a comma-seprated number list
            if not re.match(csl, self.textRisk1Lucs.text()):
                raise MolusceError(u"Invalid class list: %s" % self.textRisk1Lucs.text())
            for r in self.textRisk1Lucs.text().split(","):
                self.risk.append(int(r))
            # update display transition matrix
            self.updateTransMat()
            # set sample and validation lists
            self.smplPts = self.sampleSelector(mode=0)
            self.updateSmplFreq()
            self.vldnPts = self.sampleSelector(mode=1)
            # output shapefile if requested
            if self.chkShowMap.isChecked():
                self.makeSampleShape()
        except Exception:
            errMsg()

    def sampleSelector(self, mode=0):
        # this function selects a training sample (mode=0) or validation sample
        # (mode=1) proportionately to the trasnition frequencies between initial
        # and final classes, biased by a power factor whose higher values will
        # tend to a more equal sample frequency.
        # --------------------------------
        try:
            # from number of samples and transition matrix, build matrix
            # of sample numbers  per transition class.
            nr = areaTab.tblMatrix.rowCount()-1
            nc = areaTab.tblMatrix.columnCount()-1
            smplReq = {}    # required sample size for each transition class
            ns = float(self.textNrSamples.text())
            if ns<=0:
                raise MolusceError("Number of samples not given")
            psum = 0    # sum of raw proportions
            f = float(self.spinSbf.value())       # adjustment factor for sampling (root f)
            for r in range(0, nr):
                for c in range( 0, nc):
                    if areaTab.tblMatrix.item(r, c) is not None:
                        p = float(areaTab.tblMatrix.item(r, c).text())**(1.0/f)
                        psum += p
                        # get from and two class identifiers
                        fc = int(areaTab.tblMatrix.verticalHeaderItem(r).text())
                        tc = int(areaTab.tblMatrix.horizontalHeaderItem(c).text())
                        # add these classes to the sample rquirement matrix if not yet in
                        if fc not in smplReq:
                            smplReq[fc]={}
                        if tc not in smplReq[fc]:
                            # total sample needed x probability for this class
                            smplReq[fc][tc] = int(ns*p+0.5)
            # adjust sampling frequency by 1/psum (proportions will then total 1)
            for r in smplReq.keys():
                for c in smplReq[r].keys():
                    smplReq[r][c] /= psum
            #logTab.append(u'Sample requirement:\n%s' % (smplReq))
            # load base map data into arrays
            ymax = areaTab.map[0].RasterYSize
            xmax = areaTab.map[0].RasterXSize
            NDV = areaTab.NDV[0]
            # save GeoTransform object for use in makeSampleShape routine
            self.geoTransform = areaTab.map[0].GetGeoTransform()
            # get each map as numpy array from GDAL dataset object
            mapA = areaTab.map[0].GetRasterBand(1).ReadAsArray(0, 0, xmax, ymax)
            mapB = areaTab.map[1].GetRasterBand(1).ReadAsArray(0, 0, xmax, ymax)
            # sequence of valid sample points
            smplPts = []
            # work through the base map picking points at random and add them to
            # the sample list
            smpLeft = ns        # samples remaining to be selected
            seqFail = 0         # counter for sequential sampling failures
            failLimit = 1e6     # total failures allowed
            seqNDV = 0
            while smpLeft>0:
                # pick a random row coordinate
                x = int(random.uniform(0,xmax))
                y = int(random.uniform(0,ymax))
                # get from class, check if it is valid data
                fc = mapA[y,x]
                if fc  != NDV:
                    seqNDV = 0      # end sequence of NDV samples
                    # get to class, see if a sampling requirement
                    tc = mapB[y,x]
                    if smplReq[fc][tc]>0:
                        # add coordinates to list of sample points
                        # with first and last class values and equivalent risk
                        rf = self.getRisk(fc)
                        rt = self.getRisk(tc)
                        smplPts.append((x, y, fc, tc, rf, rt))
                        # decrement sample counters
                        smplReq[fc][tc] -= 1
                        smpLeft -= 1
                        # reset sequential failure counter
                        seqFail = 0
                    else:
                        # increment failure counter and retry
                        seqFail += 1
                else:
                    seqNDV += 1
                if seqFail>failLimit:
                    ns -= smpLeft
                    logTab.append(tr(u'Could not allocate %s samples after %s retries.  Sample size adjusted to %s')
                        % (smpLeft, failLimit, ns))
                    #adjust sample number in text box
                    self.textNrSamples.setText(str(ns))
                    break
            # randomize order of sample (otherwise rare transitions occur later)
            smplPts.sort(key=lambda x: random.random())
            # save sample to file
            keys = ['C', 'V']
            self.saveSampleData(keys[mode], smplPts)
            return smplPts
        except Exception:
            # general error handler
            errMsg()

    def setSampleShapeFile(self):
        # pops up dialog for name of sample shape file
        # default file name - retrieve from project or use standard name if empty
        shpFile = self.config["SampleShapeFile"]
        if shpFile =='':
            shpFile = getDefaultPath() +  "/Training_Sample"
        shpFile = QFileDialog.getSaveFileName(None, "Save Sample as ShapeFile",
            shpFile, "ShapeFiles (*.shp);;All files (*.*)")
        if shpFile > '':
            self.sampleShapeFile = shpFile
            self.config["SampleShapeFile"] = shpFile
            logTab.append("Calibration sample will be saved to <u>%s</u>" % (shpFile))
        else:
            logTab.append("Calibration sample Save dialog cancelled by user")

    def makeSampleShape(self):
        # generates a shape file with Point topology giving sample points and
        # their corresponding attributes
        try:
            # remove shape file if already in QGIS registry
            # first extract layer name from the filepath
            shpFile = self.config["SampleShapeFile"]
            laynm = extract_text(r".+/(.+)\.shp", shpFile)
            if laynm is None:
                raise MolusceError('Cannot get layer name from %s' % (shpFile))
            # check if in QGIS layer registry already -
            lyr = getMapLayerByName(laynm)
            if lyr is not None:
                # remove the layer
                QgsMapLayerRegistry.instance().removeMapLayer(lyr.id())
            # create field list for shape file
            fields = {  0: QgsField("id", QVariant.Int),
                        1: QgsField("ix", QVariant.Int),
                        2: QgsField("iy", QVariant.Int),
                        3: QgsField("luc_0", QVariant.Int),
                        4: QgsField("luc_1", QVariant.Int),
                        5: QgsField("risk_0", QVariant.Int),
                        6: QgsField("risk_1", QVariant.Int)}
            # get the coordinate reference system from the base layer as 'prj'
            baselyr = getMapLayerByName(areaTab.nmInitial)
            prj = baselyr.crs()
            # open the file write and test for errors
            shp = QgsVectorFileWriter(shpFile,"UTF-8", fields, QGis.WKBPoint, prj)
            if shp.hasError():
                raise MolusceError("Could not write <u>%s</u> because: %s" %
                    (shpFile, shp.errorMessage()))
            # get coordinate offsets and scales from GDAL geoTransform
            # map origin
            x0 = self.geoTransform[0]
            y0 = self.geoTransform[3]
            # pixel size
            px = self.geoTransform[1]
            py = self.geoTransform[5]
            # create feature for each sample point
            for k in xrange(0, len(self.smplPts)):
                fpt = QgsFeature()
                # feature geographical coordinates
                (x, y, fc, lc, fr, lr) = self.smplPts[k]
                xb = float(x+1) * px + x0-px/2
                yb = float(y+1) * py + y0+px/2
                fxy = QgsGeometry.fromPoint(QgsPoint(xb, yb))
                fpt.setGeometry(fxy)
                fpt.addAttribute(0, QVariant(k))
                # coordinates on GDAL raster, initial and final LUC classes
                for j in range(0, 6):
                    fpt.addAttribute(j+1, QVariant(int(self.smplPts[k][j])))
                shp.addFeature(fpt)
            # close shape file by deleting object
            del shp
            # add the map layer QGIS
            lyr = QgsVectorLayer(shpFile, laynm,"ogr")
            if not lyr.isValid():
                raise MolusceError('<u>%s</u> is an invalid vector layer' % (shpFile))
            #refresh the legend
            QgsMapLayerRegistry.instance().addMapLayer(lyr)
        except Exception:
            errMsg()            # general error handler

    def getRisk(self, luc):
        # given a land use class (luc) returns 1 if it is in the risk
        # list, otherwise 0.
        risk = 0
        for r in self.risk:
            if luc==r:
                risk = 1
                break
        return risk

    def updateTransMat(self):
        # updates the transition matrix table TransMat by recombining classes
        # from the areaTab TM array.
        try:
            lucs = areaTab.sv.keys()
            tm = np.zeros((2,2), dtype=float)
            # work through First and Last classes getting initial/final risk i,j
            gt = 0.0
            for F in areaTab.tm.keys():
                i = self.getRisk(F)
                for L in areaTab.tm[F].keys():
                    j = self.getRisk(L)
                    tm[i,j] += areaTab.tm[F][L]
                    gt += areaTab.tm[F][L]
            #logTab.append('Risk TM = %s' % (tm))
            #logTab.append('GT = %s' % (gt))
            # copy into QTable with totals in column 2
            for i in [0,1]:
                for j in [0,1]:
                    setCell(self.TransMat,i,j,'%6.4f',tm[i,j]/gt)
                setCell(self.TransMat,i,2,'%6.4f',(tm[i,0]+tm[i,1])/gt)
            #total bottom row
            for j in [0,1]:
                setCell(self.TransMat,2,j,'%6.4f',(tm[0,j]+tm[1,j])/gt)
            # grand total
            setCell(self.TransMat,2,2,'%6.4f',1.0)
            # adjust table size
            self.TransMat.resizeColumnsToContents()
            self.TransMat.resizeRowsToContents()
        except AttributeError as msg:
            logTab.append('Warning: %s' % (msg))
        except KeyError:
            debug_values(1413, F=F, L=L, i=i, j=j, risk=self.risk)
            errMsg()
        except Exception:
            errMsg()            # general error handler

    def updateSmplFreq(self):
        # updates the current sample frequency from the SmplPts list
        #work through sample points counting into risk classes
        try:
            if self.smplPts is None:
                return
            ns = len(self.smplPts)
            sf = np.zeros((2,2), dtype=float)
            for (x, y, F, L, i, j) in self.smplPts:
                #i = self.getRisk(F)
                #j = self.getRisk(L)
                sf[i,j] += 1.0
            gt = float(ns)
            # copy into QTable with totals in column 2
            for i in [0,1]:
                for j in [0,1]:
                    setCell(self.SmplFreq,i,j,'%6.4f',sf[i,j]/gt)
                setCell(self.SmplFreq,i,2,'%6.4f',(sf[i,0]+sf[i,1])/gt)
            #total bottom row
            for j in [0,1]:
                setCell(self.SmplFreq,2,j,'%6.4f',(sf[0,j]+sf[1,j])/gt)
            # grand total
            setCell(self.SmplFreq,2,2,'%6.4f',1.0)
            # adjust table size
            self.SmplFreq.resizeColumnsToContents()
            self.SmplFreq.resizeRowsToContents()
        except Exception:
            errMsg()            # general error handler

    def clearSmplFreq(self):
        # resets the sample frequency tables to blanks
        T = range(0,3)
        for i in T:
            for j in T:
                setCell(self.SmplFreq,i,j,'%s','')
        QApplication.processEvents()



class modelSelector():
    """
    Displays model selector drop down, then based on choice, implements
    interfaces for different ypes of model
    """
    def __init__(self, parent=None):
        # sets up user interface for model choice in a two tier layout, the top
        # level simply being two containers, for upper and lower part of the screen.
        # The lower part layout will vary according to the choice in the
        # upper part.
        self.gui = QWidget()
        self.lytMain = QVBoxLayout()
        # defaults from QGIS project for drop down
        self.config = Config("modelSelector",0, int)
        lytTop=QGridLayout()
        # form heading
        lbl = QLabel(tr(u'<B>Model Selection and Calibration</B>'))
        lytTop.addWidget(lbl, 0, 0, 1, 2, Qt.AlignLeft)
        # drop down for simulation method
        lblMethod = QLabel(tr(u'Method'))
        lytTop.addWidget(lblMethod, 1, 0)
        self.ddMethod = QComboBox()
        self.ddMethod.addItem("Artificial Neural Network (ANN)")
        self.ddMethod.addItem("Logistic Regression (LR)")
        m = self.config["Index"]
        self.ddMethod.setCurrentIndex(m)
        QObject.connect(self.ddMethod, SIGNAL("activated(int)"), self.method_selected)
        lytTop.addWidget(self.ddMethod, 1, 1, 1, 1, Qt.AlignLeft)
        lytTop.setColumnStretch(2,9)
        self.lytMain.addLayout(lytTop)
        #self.lytMain.addStretch(1)
        self.gui.setLayout(self.lytMain)
        self.method_selected()

    def method_selected(self):
        # called when selection made from Method selected drop down.
        # at the moment, does nothing
        global lastModelSet
        mtd = self.ddMethod.currentText()
        m = self.ddMethod.currentIndex()
        #logTab.append("Modelling method selected is (%d) %s" % (m, mtd))
        self.config["Index"]= m
        # list of possible widgets for lower pane
        models= [annTab, LRtab]
        # remove current occupant of lower pane
        if lastModelSet is not None:
            self.lytMain.takeAt(2)
            self.lytMain.takeAt(1)
            self.lytMain.removeWidget(lastModelSet)
            lastModelSet.hide()
        # add new occupant
        lastModelSet = models[m].gui
        self.lytMain.addWidget(lastModelSet)
        self.lytMain.addStretch(2)
        lastModelSet.show()



class LR_model():
    """
    Implements Logistic Regression model definition and calibration
    (maximum liklihood parameter estimation).
    """
    def __init__(self, parent=None):
        # sets up user interface for model choice in a two tier layout, the top
        # level simply being two containers, for upper and lower part of the screen.
        # The lower part layout will vary according to the choice in the
        # upper part.
        self.gui = QWidget()
        layout = QGridLayout()
        txtBoxWidth = 60
        # defaults from QGIS project for drop down
        self.config = Config("LR_model",0, int)
        self.lbl1 = QLabel(tr('Logistic Regression Model Coefficient Fitting'))
        layout.addWidget(self.lbl1, 0, 0, 1, 4)
        # spinner for neighbourhood size in pixels
        lblNeighborhood = QLabel(tr(tr(u'Neighbourhood (px)')))
        layout.addWidget(lblNeighborhood, 1 ,0)
        # retrieve neighbourhood size from .qgs or use a default
        nbh= self.config["Neighborhood"]
        self.spinNbh = QSpinBox()
        self.spinNbh.setFixedWidth(txtBoxWidth)
        self.spinNbh.setSingleStep(1)
        self.spinNbh.setRange(0, 9)
        self.spinNbh.setValue(nbh)
        layout.addWidget(self.spinNbh, 1 , 1)
        #self.gui.setLayout(layout)
        # Training Run button
        lblFitModel = QLabel(tr(u'Fit Model'))
        layout.addWidget(lblFitModel , 2 ,0)
        self.btnFitModel=QPushButton(tr(u'OK'))
        self.btnFitModel.setFixedWidth(40)
        QObject.connect(self.btnFitModel, SIGNAL("clicked()"), self.fitModel)
        layout.addWidget(self.btnFitModel, 2, 1)
        # R-squared text box (for output only)
        lblRsq = QLabel(tr(u'R-squared'))
        layout.addWidget(lblRsq , 3 ,0)
        self.textRsq = QLineEdit()
        self.textRsq.setFixedWidth(txtBoxWidth)
        self.textRsq.setDisabled(True)
        layout.addWidget(self.textRsq , 3 ,1)
        # Kappa text box (for output only)
        lblKappa = QLabel(tr(u'Kappa'))
        layout.addWidget(lblKappa , 4 ,0)
        self.textKappa = QLineEdit()
        self.textKappa.setFixedWidth(txtBoxWidth)
        self.textKappa.setDisabled(True)
        layout.addWidget(self.textKappa , 4 ,1)
        # Percent Map Agreement text box (for output only)
        lblPctMapAgr = QLabel(tr(u'Map Agreement %'))
        layout.addWidget(lblPctMapAgr , 5 ,0)
        self.textPctMapAgr = QLineEdit()
        self.textPctMapAgr.setFixedWidth(txtBoxWidth)
        self.textPctMapAgr.setDisabled(True)
        layout.addWidget(self.textPctMapAgr , 5 ,1)
        # vertical line down 6 rows in column 3
        vline1 = QFrame()
        vline1.setFrameStyle(QFrame.VLine|QFrame.Sunken)
        layout.addWidget(vline1, 1, 2, 6, 1)
        # table of coefficients - heading
        lblCoeff = QLabel(tr(u'Fitted Coefficients'))
        layout.addWidget(lblCoeff, 1, 3)
        # table of coefficients
        self.tblCoeff = moTableWidget()
        self.tblCoeff.setFrameStyle(QFrame.NoFrame)
        self.tblCoeff.viewport().setBackgroundRole(QPalette.Window)
        self.tblCoeff.setColumnCount(4)
        self.tblCoeff.setRowCount(2)
        for (i, h) in { 0:tr(u'Layer[band]'), 1:tr(u'Coefficient'), 2:tr(u'Std. Dev.'), 3:tr(u'Sig.')}.items():
            self.tblCoeff.setHorizontalHeaderItem(i, QTableWidgetItem(h))
        fTab.getLayers()
        self.updateTableLabels()
        self.loadBeta() # reload coefficients saved with project, if any
        self.tblCoeff.resizeColumnsToContents()
        self.tblCoeff.resizeRowsToContents()
        layout.addWidget(self.tblCoeff, 1, 3, 6, 1)
        # a bit of space at right
        layout.setColumnStretch(3,9)
        layout.setRowStretch(6,9)
        self.gui.setLayout(layout)

    def updateTableLabels(self):
        # adds labels rows of coefficients table for Logistic Regression
        try:
            nz = self.spinNbh.value()   #neighborhood size
            t = self.tblCoeff # shorthand reference to table object
            t.setRowCount(1)
            # constant term
            t.setVerticalHeaderItem(0, QTableWidgetItem(u'\u03B20')) # beta 0
            setCell(t, 0, 0, '%s', 'Constant', align=Qt.AlignLeft)
            # loop through layers getting names and band counts
            nL = len(fTab.mfactL)   # number of layers
            #logTab.append('Number of Layers for LR = %s' % (nL))
            if nL<=0:
                return              # exit - not initialised yet
            row = 1                 # table row pointer
            for L in range(0, nL):
                gmap = fTab.mfactG[L]       # GDAL dataset for raster image
                qlyr = fTab.mfactL[L]       # QGIS layer of same image
                nb = gmap.RasterCount       # band count from GDAL info
                lyrnm = str(qlyr.name())    # layer name from QGIS info
                if L==0:
                    # row zero is the base layer itself.  This may be represented by
                    # a number of zones equal to the neighborhood size
                    # beta(row) in left heading, layer name + zone in column 0
                    for z in range(0, nz+1):
                        if row>=t.rowCount():
                            t.setRowCount(row+1)
                        t.setVerticalHeaderItem(row, QTableWidgetItem(u'\u03B2%d' % (row)))
                        text = '%s {z%d}' % (lyrnm, z)
                        setCell(t, row, 0, '%s', text, align=Qt.AlignLeft)
                        row += 1            # increment row counter
                else: # remaining layers, other than 0
                    if nb>1:
                        for i in range(1, nb+1):
                            txt = '%s[%d]' % (lyrnm, i)
                            # beta(row) in left heading, layer and [band] in column 0
                            if row>=t.rowCount():
                                t.setRowCount(row+1)
                            t.setVerticalHeaderItem(row, QTableWidgetItem(u'\u03B2%d' % (row)))
                            setCell(t, row, 0, '%s', txt, align=Qt.AlignLeft)
                            row += 1            # increment row counter
                    else:
                        # output one row without band subscript
                        # beta(row) in left heading, layer name in column 0
                        if row>=t.rowCount():
                            t.setRowCount(row+1)
                        t.setVerticalHeaderItem(row, QTableWidgetItem(u'\u03B2%d' % (row)))
                        setCell(t, row, 0, '%s', lyrnm, align=Qt.AlignLeft)
                        row += 1            # increment row counter
        except Exception:
            errMsg()            # general error handler

    def fitModel(self):
        # fits LR model and updates statistics on GUI
        try:
            # save current parameters to .qgs project
            self.config["Neighborhood"] = str(self.spinNbh.value())
            # refresh lists of GDAL and QGIS layer objects
            fTab.getLayers()
            # update the labels on the output table from these lists
            self.updateTableLabels()
            # get the LR regression data from the calibration sample
            data = self.getModelData(smplTab.smplPts)
            # fit the logistic model
            y = data[:, 0].T
            x = data[:, 1:].T
            (b, se, rsq, p) = self.fitLogistic(x,y)
            self.beta = b       # save coefficents as class attribute
            # put results in the output table
            tbl = self.tblCoeff
            n = b.shape[0]
            for i in range(0,n):
                setCell(tbl, i, 1, '%11.4e', b[i])        # b coefficient
                setCell(tbl, i, 2, '%11.4e', se[i])       # std. err. of b
                # approx. significance test, * = 95%, ** = 99%, - = n.s.
                q = abs(b[i]/se[i])
                if q>2.5758:
                    sig="**"
                elif q>1.96:
                    sig ="*"
                else:
                    sig="-"
                setCell(tbl, i, 3, '%s', sig)
            # adjust table size to contents
            tbl.resizeColumnsToContents()
            tbl.resizeRowsToContents()
            # display R-squared
            self.textRsq.setDisabled(False)
            self.textRsq.setText('%6.4f' % rsq)
            # calculate kappa and % map agreement
            # get observed risk values from sample data - already 0-1 values
            Yo = np.array(smplTab.smplPts)  # observed risk values
            Yo = Yo[:,5]                    # in column 5 of sample data
            # get scaling factors, re-scale probabilities 0-1
            (p0, p1) = (np.nanmin(p), np.nanmax(p))
            p = (p - p0)/(p1 - p0)
            # convert expected probabilities from regression (p) to 0-1 array
            flim = np.frompyfunc(lambda x: 0 if x<0.5 else 1, 1, 1)
            Ye = np.array(flim(p), dtype=int)
            # calculate kappa, % map agreement
            (kp, pma) = kappa(Yo, Ye)      # get kappa and PMA
            # update values in GUI
            self.textKappa.setDisabled(False)
            self.textPctMapAgr.setDisabled(False)
            self.textKappa.setText('%7.4f' % kp)
            self.textPctMapAgr.setText('%7.1f%%' % (pma*100.0))
            # save coefficients to the project
            self.saveBeta()
        except Exception:
            errMsg()            # general error handler

    def getModelData(self, smplPts):
        # Gets data for logistic modelling based on the sample points supplied.
        # Returns an array with Risk final state in column 0 (Y), initial state
        # in column 1 to Nz (X0-Xnz) and other input factors in columns 2+.
        try:
            nL = len(fTab.mfactG)   #layer count
            # create data array to be output
            data = list()
            # get neighborhood size
            nz = self.spinNbh.value()
            # array function for risk class
            riskSet = set(smplTab.risk)
            frisk = np.frompyfunc(lambda x: 1 if x in riskSet else 0, 1, 1)
            # loop through layers
            for L in range(0, nL):
                gmap = fTab.mfactG[L]   # GDAL dataset for raster image
                qlyr = fTab.mfactL[L]   # QGIS layer of same image
                # retrieve layer geometry
                geo = gmap.GetGeoTransform()
                xsz = gmap.RasterXSize
                ysz = gmap.RasterYSize
                nb = gmap.RasterCount
                # origin in projection units
                x0 = geo[0]
                y0 = geo[3]
                rotn = geo[2]  # rotation, zero = north, no rotation
                # pixel size
                px = geo[1]
                py = geo[5]
                lyrnm = str(qlyr.name())
                # handle files with non-zero rotation (ignore them unless it becomes an issue)
                if rotn != 0:
                    raise MolusceError(tr(u'Layer %s has non-zero rotation') % (lyrnm))
                # if base layer, set base geometry
                if L==0:
                    (xsz0, ysz0, px0, py0, x00, y00) = (xsz, ysz, px, py, x0, y0)
                # no data value
                (ndv, hasNDV) = qlyr.noDataValue()
                if not hasNDV:
                    ndv =-32767   # use an unlikely value if no NDV set (1-2^15)
                # offset factor in pixels from neighborhood size
                (apx, apy) = (abs(px), abs(py))
                # process each band of the layer as a separate factor, band 0 will be split
                # into two inputs - count of 0's and count of 1's within
                for b in range(0, nb):
                    # get layer into masked numpy array (y is first dimension, x is second in array)
                    aMap = gmap.GetRasterBand(b+1).ReadAsArray(0, 0, xsz, ysz)
                    mMap = npm.masked_equal(aMap, ndv) # array masked by NDV
                    (my, mx) = np.shape(aMap)   # upper sizes of each dimension
                    if L==0 and b==0:   # convert base map to risk values
                        rMap = frisk(mMap)
                    ptc = 0  # point counter
                    # work through sample points calculating factors for this band
                    for pt in smplPts:
                        (x, y, fc, lc, fr, lr) = pt
                        # calculate target coordinates in layer
                        xb = float(x) * px0 + x00
                        yb = float(y) * py0 + y00
                        xt = (xb - x0) / px
                        yt = (yb - y0) / py
                         # if the base layer and band, add a new entry to the factor
                        # list for each sample point
                        if L==0 and b==0:
                            # when processing layer 0, band 0, add a variables
                            # for each neighbourhood layer, counting out from
                            # the central pixel
                            data.append([lr])
                            zr = avgZoneRings(rMap, xt, yt, nz)
                            fl = zr.tolist()    # convert to Python list
                            data[ptc] += fl     # append to list for this point
                        else:
                            # get factor value at pixel centre
                            fv = mMap[yt, xt]
                            # null points are treated as zero
                            if not fv:
                                fv = 0
                            # adds factor value to list for an existing point
                            data[ptc].append(fv)
                        ptc += 1
            # check output first 20 rows of data
            logTab.append("--- Data Dump ---" )
            for i in range(0,20):
                (x, y, fc, lc, fr, lr) = smplPts[i]
                txt = ""
                for j in range(0,nz+2):
                    txt += '\t%5.3f' % data[i][j]
                logTab.append("%d (%d, %d) = %s" % (i, x, y, txt))
            logTab.append("--- ********** ---" )
            # convert to an numpy floating point array and return
            (n, m) = (len(data), len(data[0]))
            return np.array(data, dtype=float)
        except Exception:
            # general error handler
            errMsg()

    def fitLogistic(self, x,y):
        """
        Fits a logistic regression to data.  x and y are numpy arrays of type float.
        y[m] values are 0-1 values for m points.  x[n,m] represents n variables
        predicting probablity p[m] for a 1 outcome for the m'th point.  The equation
        for the model is:
            logit(p[m]) = b0 + b1.x[1,m]+...+bn.x[n,m]
        where logit(x) = ln (x/(1-x)), the logistic transform
        The model returns B - the vector of B values, and SE, their estimated standard
        errors, and R-squared.  Algorithm source: Draper & Smith (1966), pp 56 ff.
        """
        try:
            # get no. of parameters n and data points m
            (n,m) = x.shape
            # generate a y_ vector assuming underlying p for y=1 and 0 values have
            # logit(y) = 1 and -1 respectively
            Y = np.empty((m), dtype=float)
            for i in xrange(m):
                Y[i] = 1 if y[i]>0.5 else -1
            # augment the x matrix with a column of 1's, xt is its transpose
            X = np.ones((n+1, m), dtype=float)
            X[1:, :] = x
            Xt = np.transpose(X)
            XtX = np.dot(X, Xt)                 # cross-product matrix X'X
            C = np.linalg.inv(XtX)              # inverse cross product matrix
            XtY = np.dot(X, Y)                 # X'Y matrix
            b = np.dot(C, XtY)                  # coefficients
            Tss = np.inner(Y, Y)                # total sum of squares Y'Y
            Rss = np.dot(b.T, XtY)              # regression sum of squares
            Uss = Tss - Rss                     # residual sum of squares
            rv = Uss/(m-n-1)                    # residual variance
            bv = np.diag(C*rv)                  # variances of coefficients
            nY2 = m*np.mean(Y)**2               # correction factor for mean
            rsq = (Rss - nY2)/(Tss - nY2)       # Coeff. of Determination
            eY = np.exp(np.dot(Xt, b))           # exponents of estimated Y's
            p = eY/(1.0 + eY)                   # predicted probabilities
            # return Coefficients, their variances, R-squared and predicted P's
            return (b, bv, rsq, p)
        except Exception:
            #debug_values(1785, XtX=XtX)
            errMsg()            #general error handler
            return (None, None, None, None)

    def saveBeta(self):
        # save LR beta coefficients in the .qgs project file
        try:
            params = Config("LR_beta",0.0,float)
            n = self.beta.shape[0]
            params['n'] = n
            for i in range(0, n):
                txt = 'b%s' % (i)
                params[txt] = self.beta[i]
        except Exception:
            errMsg()            # general error handler

    def loadBeta(self):
        # retrieves LR beta coefficients from the .qgs project file
        try:
            tbl = self.tblCoeff
            params = Config("LR_beta",0.0,float)
            # load inner layer coefficients
            n = int(params['n'])
            self.beta = np.zeros((n), dtype=float)
            for i in range(0, n):
                txt = 'b%s' % (i)
                self.beta[i]= float(params[txt])
                # display in table
                setCell(tbl, i, 1, '%11.4e', self.beta[i])
        except Exception:
            errMsg()            # general error handler

class ANN_model():
    """
    Calibration options and controls for the ANN  model
    """

    def __init__(self, parent=None):
        # sets up user interface for neural model, retrieves any existing
        # settings from QGIS model, and initialises state of ANN for learning
        self.gui = QWidget()
        layout=QGridLayout()
        txtBoxWidth = 60    # common width for most of the input boxes
        # defaults from QGIS project for options
        self.ANN_options = Config("ANN_options",'', str)
        # spinner for neighbourhood size in pixels
        lblNeighborhood = QLabel(tr(tr(u'Neighbourhood (px)')))
        layout.addWidget(lblNeighborhood, 0 ,0)
        # retrieve neighbourhood size from .qgs or use a default
        if self.ANN_options["Neighborhood"]=='':
            nbh=1
        else:
            nbh = int(self.ANN_options["Neighborhood"])
        self.spinNbh = QSpinBox()
        self.spinNbh.setFixedWidth(txtBoxWidth)
        self.spinNbh.setValue(nbh)
        self.spinNbh.setSingleStep(1)
        self.spinNbh.setRange(0, 9)
        layout.addWidget(self.spinNbh, 0 , 1)
        # text box to enter learning rate
        lblLearnRate = QLabel(tr(u'Learning Rate \u03b7'))
        layout.addWidget(lblLearnRate, 1 ,0)
        # set learing rate default or retrieve from .qgs if set
        if self.ANN_options["LearningRate"]=='':
            txt = '1'
        else:
            txt = self.ANN_options["LearningRate"]
        self.textLearnRate = QLineEdit(txt)
        self.textLearnRate.setFixedWidth(txtBoxWidth)
        layout.addWidget(self.textLearnRate, 1 , 1)
        # text box for maximum iterations
        lblMaxIter = QLabel(tr('Maximum iterations'))
        layout.addWidget(lblMaxIter , 2 ,0)
        # set max iterations default or retrive from .qgs if set
        if self.ANN_options["MaxIterations"]=='':
            txt = '1000'
        else:
            txt = self.ANN_options["MaxIterations"]
        self.textMaxIter = QLineEdit(txt)
        self.textMaxIter.setFixedWidth(txtBoxWidth)
        layout.addWidget(self.textMaxIter , 2 ,1)
        maxiter = int(txt)
        # textbox for Delta RMS
        lblStopRule = QLabel(tr(u'Stop when \u0394RMS% <'))
        layout.addWidget(lblStopRule , 3 ,0)
        # set stopping rule default or retrive from .qgs if set
        txt = self.ANN_options["MinDeltaRMS"]
        self.textStopRule = QLineEdit(txt)
        self.textStopRule.setFixedWidth(txtBoxWidth)
        layout.addWidget(self.textStopRule , 3 ,1)
        # check box for ANN report
        self.chkANNreport = QCheckBox("Make report")
        layout.addWidget(self.chkANNreport, 4 ,0)
        QObject.connect(self.chkANNreport, SIGNAL("clicked()"), self.setParamsOutputFile)
        self.chkSampleData = QCheckBox("+ sample data")
        layout.addWidget(self.chkSampleData, 4 ,1)
        # Validation check box
        lblValidn = QLabel(tr(u'Show validation (<span style="color: olive">\u2501\u2501</span>)'))
        layout.addWidget(lblValidn , 5 ,0)
        self.chkValidRun=QCheckBox()
        layout.addWidget(self.chkValidRun, 5, 1)
        # Training Run button
        lblTraining = QLabel(tr(u'Training (<span style="color: red">\u2501\u2501</span>)'))
        layout.addWidget(lblTraining , 6 ,0)
        self.btnTrainRun=QPushButton(tr(u'Start'))
        self.btnTrainRun.setFixedWidth(40)
        self.btnTrainRun.setCheckable(True)
        self.cancelTrainingFlag = False
        QObject.connect(self.btnTrainRun, SIGNAL("clicked()"), self.runTraining)
        layout.addWidget(self.btnTrainRun, 6, 1)
        # R-squared text box (for output only)
        lblRsq = QLabel(tr(u'R-squared (<span style="color: teal">\u2501\u2501</span>)'))
        layout.addWidget(lblRsq , 7 ,0)
        self.textRsq = QLineEdit()
        self.textRsq.setFixedWidth(txtBoxWidth)
        layout.addWidget(self.textRsq , 7 ,1)
        # Kappa text box (for output only)
        lblKappa = QLabel(tr(u'Kappa'))
        layout.addWidget(lblKappa , 8 ,0)
        self.textKappa = QLineEdit()
        self.textKappa.setFixedWidth(txtBoxWidth)
        layout.addWidget(self.textKappa , 8 ,1)
        # Percent Map Agreement text box (for output only)
        lblPctMapAgr = QLabel(tr(u'Map Agreement %'))
        layout.addWidget(lblPctMapAgr , 9 ,0)
        self.textPctMapAgr = QLineEdit()
        self.textPctMapAgr.setFixedWidth(txtBoxWidth)
        layout.addWidget(self.textPctMapAgr , 9 ,1)
        # graph of learning curve in centre panel (lcg=learning curve graphic)
        lblLcgCaption = QLabel(tr('Neural Network Learning Curve'))
        layout.addWidget(lblLcgCaption , 0 ,2, 1, 1, Qt.AlignCenter)
        self.lcg = Graph()
        #self.lcg.setFixedWidth(250)
        self.lcg.setXaxis(tr(u'Iterations'), 0, 100, 10)
        self.lcg.setYaxis(tr(u'\n\u0394RMS or R\u00B2'), 0, 1.0, 0.1)
        self.lcg.setLine(0, color=Qt.red)           # training delta RMS
        self.lcg.setLine(1, color=Qt.darkYellow)    # validation delta RMS
        self.lcg.setLine(2, width=1, color=Qt.darkCyan)     # R-squared
        layout.addWidget(self.lcg,1, 2, -1, 1)
        # a bit of space at right and bottom
        layout.setRowStretch(10,9)
        layout.setColumnStretch(2,9)
        self.gui.setLayout(layout)

    def runTraining(self):
        # starts ANN learning process
        try:
            # if  button has already been clicked, just set the cancel flag and exit
            if not self.btnTrainRun.isChecked():
                self.cancelTrainingFlag = True
                # forces ANN learning process to stop early
                if self.ann is not None:
                    self.ann.endRun = True
                return
            self.btnTrainRun.setText(tr(u'Stop'))
            QApplication.processEvents()
            # validate input fields
            decnr = re.compile(r"^[0-9]+\.?[0-9]+$")     # match a decimal number
            intnr = re.compile(r"^[0-9]+$")             # match an integer number
            nzint = re.compile(r"^[1-9][0-9]*$")             # match a non-zero integer number
            decnre = re.compile(r"^[\-0-9]+\.?[0-9]+$|^$")     # match a decimal or empty string
            errmsg = ""
            if smplTab.smplPts is None:
                errmsg += u"No training sample: Run sample selection first"
            if not re.match(decnr, self.textLearnRate.text()):
                errmsg += u"\nLearning Rate must be a positive decimal number"
            if not re.match(intnr, self.textMaxIter.text()):
                errmsg += u"\nMaximum Iterations must be a positive integer"
            if not re.match(decnre, self.textStopRule.text()):
                errmsg += u"\nDelta RMS should be empty or a decimal value"
            if errmsg:
                logTab.append(u"Errors in ANN options %s" % (errmsg))
                QMessageBox.warning(self.gui, "ANN Options", "Error in options: %s" % (errmsg))
                self.btnTrainRun.setText(tr(u'Start'))
                self.btnTrainRun.setChecked(False)
                return
            # save validated settings to project .qgs file (via Config object)
            self.ANN_options["Neighborhood"] = str(self.spinNbh.value())
            self.ANN_options["LearningRate"] = self.textLearnRate.text()
            self.ANN_options["MaxIterations"] = self.textMaxIter.text()
            self.ANN_options["MinDeltaRMS"] = self.textStopRule.text()
            # set up layers for import factors
            fTab.getLayers()
            # calculate sample input values from factor layers
            (self.smplPtsF, self.smplPtsG) = self.calcInputFactors(smplTab.smplPts)
            if self.chkValidRun.isChecked():
                (self.smplPtsV, void1) = self.calcInputFactors(smplTab.vldnPts)
            # reset chart scales and data
            maxiter = int(self.textMaxIter.text())
            self.xmag = int(math.log10(maxiter)-1.0) if maxiter>=1000 else 0
            ptext = 'iterations x %s' % (int(10**self.xmag))
            imax = int(maxiter * 10**(-self.xmag))
            self.lcg.setXaxis(ptext, 0, imax, int(imax/10))
            self.lcg.setLine(0,color=Qt.red)
            self.lcg.setLine(1,color=Qt.darkYellow)
            self.lcg.setLine(2, width=1, color=Qt.darkCyan)
            self.lcg.repaint()
            # initialise the neural model
            self.ann = Perceptron()
            if self.ann.doTraining():
                # if training was OK, save parameters to .qgs file
                self.ann.saveANNparams()
                if self.chkANNreport.isChecked():
                    # output report file if requested
                    self.outputANNparams()
            # rest training button to its original state
            self.btnTrainRun.setText(tr(u'Start'))
            self.btnTrainRun.setChecked(False)
            self.cancelTrainingFlag = False
        except Exception:
            errMsg()

    def clickBtnStop(self):
        # forces ANN learning process to stop early
        self.ann.endRun = True

    def show(self):
        self.gui.show()


    def setInputFactorLayers(self):
        # reads list of input factors, including the base layer itself
        # into lists of GDAL and QGIS map layer objects
        fTab.mfactG = list()     # map layers as GDAL objects
        fTab.mfactL = list()    # map layers as Layer objects
        # base map is always factor 0
        fTab.mfactG.append(areaTab.map[0])
        fln = fTab.textInitial.text()
        layer = getMapLayerByName(fln)
        if layer is None: # unexpected - log message and abort
            logTab.append('Could not find base layer: <u>%s</u>' % (fln))
            return False
        fTab.mfactL.append(layer)
        path = str(layer.source())
        logTab.append('ANN Factor Layer added: <u>%s</u>' % (path))
        # add further factors, if any from FactorLayers list in Input tab
        nf = fTab.listFactorLayers.count()
        for f in range(0, nf):
            fln = fTab.listFactorLayers.item(f).text()
            layer = getMapLayerByName(fln)
            if layer is None: # unexpected - log message and skip to next layer
                logTab.append('Could not find factor layer: <u>%s</u>' % (fln))
                continue
            path = str(layer.source()) # gives full path including extension
            gmap = gdal.Open(path, GA_ReadOnly)
            if gmap is None:
                logTab.append('GDAL could not open: <u>%s</u>' % (path))
                continue
            fTab.mfactG.append(gmap)
            fTab.mfactL.append(layer)
            logTab.append('ANN Factor Layer added: <u>%s</u>' % (path))



    def calcInputFactors(self, smplPts):
        # works through sample points, calculating input factors from each layer.
        # Outputs three lists:
        # smplPtsF - list of input factors
        # smplPtsG - geographic coordinates, for shapefile generator
        # smplFieldNames - list of shape file attribute names
        try:
            nL = len(fTab.mfactG)   #layer count
            #logTab.append('Calculating input factors for %s layers' % (nL))
            # create/reset list of sample point factors and geographical coordinates
            smplPtsF = list()
            smplPtsG = list()
            # list of field names for the sample point factors (used by makeSampleShape)
            smplFieldNames = list()
            # get neighborhood size
            nz = self.spinNbh.value()
            # array function for risk factor conversion
            riskSet = set(smplTab.risk)
            frisk = np.frompyfunc(lambda x: 1 if x in riskSet else 0, 1, 1)
            # loop through layers
            for L in range(0, nL):
                gmap = fTab.mfactG[L]   # GDAL dataset for raster image
                qlyr = fTab.mfactL[L]   # QGIS layer of same image
                # retrieve layer geometry
                geo = gmap.GetGeoTransform()
                xsz = gmap.RasterXSize
                ysz = gmap.RasterYSize
                nb = gmap.RasterCount
                # origin in projection units
                x0 = geo[0]
                y0 = geo[3]
                rotn = geo[2]  # rotation, zero = north, no rotation
                # pixel size
                px = geo[1]
                py = geo[5]
                lyrnm = str(qlyr.name())
                # handle files with non-zero rotation (ignore them unless it becomes an issue)
                if rotn != 0:
                    raise MolusceError(tr(u'Layer %s has non-zero rotation') % (lyrnm))
                # if base layer, set base geometry
                if L==0:
                    (xsz0, ysz0, px0, py0, x00, y00) = (xsz, ysz, px, py, x0, y0)
                # no data value
                (ndv, hasNDV) = qlyr.noDataValue()
                if not hasNDV:
                    ndv =-32767   # use an unlikely value if no NDV set (1-2^15)
                # offset factor in pixels from neighborhood size
                (apx, apy) = (abs(px), abs(py))
                # process each band of the layer as a separate factor, band 0 will be split
                # into two inputs - count of 0's and count of 1's within
                for b in range(0, nb):
                    # get layer into masked numpy array (y is first dimension, x is second in array)
                    aMap = gmap.GetRasterBand(b+1).ReadAsArray(0, 0, xsz, ysz)
                    mMap = npm.masked_equal(aMap, ndv) # array masked by NDV
                    if L==0 and b==0:   # convert base map to risk values
                        rMap = frisk(mMap)
                    (my, mx) = np.shape(aMap)   # upper sizes of each dimension
                    ptc = 0  # point counter
                    # work through sample points calculating factors for this band
                    for pt in smplPts:
                        (x, y, fc, lc, fr, lr) = pt
                        # calculate target coordinates in layer
                        xb = float(x) * px0 + x00
                        yb = float(y) * py0 + y00
                        xt = (xb - x0) / px
                        yt = (yb - y0) / py
                         # if the base layer and band, add a new entry to the factor
                        # list for each neighborhood layer
                        if L==0 and b==0:
                            # get average neigborhood ring values
                            zr = avgZoneRings(rMap, xt, yt, nz)
                            fl = zr.tolist()    # convert to Python list
                            # add a new point to list and set first nz+1 factor values
                            smplPtsF.append(fl)
                            # save the points geographic coordinates for shape file generator
                            smplPtsG.append((xb, yb))
                        else:
                           # get factor value at pixel centre
                            fv = mMap[yt, xt]
                            # null points should not occur and may mean bug in algorithm
                            if not fv:
                                 fv = 0
                            # adds factor value to list for an existing point
                            smplPtsF[ptc].append(fv)
                        ptc += 1
            # and that should be that!
            return (smplPtsF, smplPtsG)
        except Exception:
            # general error handler
            errMsg()


    def setParamsOutputFile(self):
        # SLOT for checkbox 'ANN report'.  Gets the file name for output
        try:
            if self.chkANNreport.isChecked():
                # get a default directory for .qgs or same as initial layer
                idir = self.ANN_options['ANNreport']
                if idir=='':
                    idir = getDefaultPath() +  "/ANN.txt"
                # file save dialog
                opf = str(QFileDialog.getSaveFileName(None, tr(u'ANN Report File'),
                    idir, "Text files (*.txt);;All files (*.*)"))
                if opf=='':
                    # if no file name, clear checkbox
                    self.ANNreportFile = ''
                    self.chkANNreport.setChecked(False)
                else:
                    # set file path and save to project
                    self.ANNreportFile = opf
                    self.ANN_options['ANNreport'] = opf
        except Exception:
            # general error handler
            errMsg()

    def outputANNparams(self):
        # creates a text file ANN weights and structure, input value
        # stats (min, max, mean, SD), using a tab-separated format
        # intended for import into a workbook
        try:
            # open default output file
            fn = self.ANN_options['ANNreport']
            fh = open(fn, 'w')
            # specification of model inputs
            fh.write(tr(u'\n---------------------- ANN Inputs ---------------------\n'))
            fh.write(tr(u'Input\tLayer Name\t\tModifer\tMinimum\tMaximum\n'))
            nF = 0
            basenm = str(fTab.mfactL[0].name())
            if len(basenm)<10 : # pad shorter names with a tab character
                basenm += '\t'
            nz = self.spinNbh.value()   #neighborhood size
            # details of neighborhood zones on base layer
            for z in range(0, nz+1):
                fh.write(tr(u'X%d\t%s\tZone %d\t%13.6e\t%13.6e\n') %
                    (nF, basenm, z, self.ann.rawMin[nF], self.ann.rawMax[nF]))
                nF += 1
            # details of other layers
            for L in range(1, len(fTab.mfactL)):
                lyrnm = str(fTab.mfactL[L].name())    # layer name from QGIS info
                if len(lyrnm)<10 : # pad shorter names with a tab character
                    lyrnm += '\t'
                nb = fTab.mfactG[L].RasterCount       # band count from GDAL info
                for b in range(0, nb):
                    fh.write(tr(u'X%d\t%s\tBand %d\t%13.6e\t%13.6e\n') %
                        (nF, lyrnm, b+1, self.ann.rawMin[nF], self.ann.rawMax[nF]))
                    nF += 1
            # output model coefficients
            fh.write(tr(u'\n------------------- ANN Coefficients ------------------\n'))
            (n, m) = self.ann.Wmid.shape
            fh.write(tr(u'\nInput scaling factors (%s x %s matrix)\n') % (n, m))
            for i in range(0, n):
                for j in range(0, m):
                    fh.write('%13.6e\t' % (self.ann.Wmid[i,j]))
                fh.write('\n')
            fh.write(tr(u'\nInner layer weights (%s x %s matrix)\n') % (n, m))
            for i in range(0, n):
                for j in range(0, m):
                    fh.write('%13.6e\t' % (self.ann.Wmid[i,j]))
                fh.write('\n')
            # write outer layer weights
            (n, m) = self.ann.Wout.shape
            fh.write(tr(u'\nOuter layer weights (%s x %s matrix)\n') % (n, m))
            for i in range(0, n):
                for j in range(0, m):
                    fh.write('%13.6e\t' % (self.ann.Wout[i,j]))
                fh.write('\n')
            # listing of data is optional according to checkbox on GUI
            if self.chkSampleData.isChecked():
                # write headings for training data
                fh.write(tr(u'\n\n------------------ Training Data ---------------------\n'))
                fh.write(tr(u'PtNo\t'))
                nF = len(self.smplPtsF[0])
                for f in range(0,nF):
                    fh.write(tr(u'X%d\t') % (f))
                fh.write(tr(u'Y\tANN(out)\n'))
                # write out data and predicted value for each point
                nP=len(smplTab.smplPts)
                for p in xrange(0,nP):
                    # coordinates, initial and final LUC
                    (x, y, fc, lc, fr, lr) = smplTab.smplPts[p]
                    lr = int(lr)
                    fh.write("%d\t" % (p))
                    # input factors
                    for f in range(0,nF):
                        fh.write(tr(u'%0.3f\t') % (self.smplPtsF[p][f]))
                    # output factor and ANN response
                    Ipr = np.array(self.smplPtsF[p])
                    prisk = self.ann.response(Ipr)
                    fh.write(tr(u'%d\t%s\n') % (lr, prisk))
            fh.close()
        except Exception:
            # general error handler
            errMsg()


    def getRisk(self, luc):
        # given a land use class (luc) returns 1 if it is in the risk
        # list, otherwise 0.  Value is returned as a 1 x 1 np array
        # for compatability with ANN calculations
        return np.array([[smplTab.getRisk(luc)]], dtype=np.float)

class Perceptron():
    """
    This class implements perceptron initialisation and training as a separate
    thread, to be launched and controlled from the ANN_model class.
    """

    def __init__(self, parent=None):
        # initialises the perceptron.
        # flag set externally to end run
        self.endRun = False

    def calcOutputs(self, Ip, Wt, limit=True):
        # sums input values (a row vector) times weights for the m'th output
        # and calculates tanh function of result which is returned as a
        # vector of values in range -1 to +1
        try:
            # add a 1 to the input vector to allow for the bias weight
            # and reshape as a row vector
            Iv = self.augmentVector(Ip)
            # multiply inputs by weights to get output column vector
            Op = np.dot(Iv, Wt)
            if limit:
                # transform output values via sigmoid function
                # see  Picton, P (2000) Neural Networks, pp 45. on this
                Op = 1.0/(1.0+np.exp(-Op))
        except Exception:
            # log error message, dump values for debugging
            errMsg()
            debug_values(1476, Wt=Wt, Iv=Iv, Ip=Ip, limit=limit)
            Op = None
        return Op

    def augmentVector(self, V, column=False):
        # adds a 1 element on to the start of a vector.  Use in matrix
        # multiplications to allow for bias weights which have no corresponding
        # input value.  If column is True, returns a column vector, otherwise
        # returns a row vector by default
        one = np.array([1], dtype=np.float)
        U = np.concatenate((one, V.flatten()))
        if column:
            # shape as a column vector
            R = np.reshape(U, (-1, 1))
        else:
            # shape as row vector
            R = np.reshape(U, (1, -1))
        return R

    def doTraining(self):
        # this does the perceptron training in a loop until stopped
        # externally or termination conditions are met.  Revised version
        # from version 1.9w applies training algorithm to whole sample
        # at each iteration
        try:
            # ------ get external options and parameters
            eta = float(annTab.textLearnRate.text())  # learning rate (Greek eta)
            maxiter = int(annTab.textMaxIter.text())  # maximum iterations
            vchk = annTab.chkValidRun.isChecked()     # status of validation checkbox
            # function used to hard-limit ANN output probabilities
            flim = np.frompyfunc(lambda x: 0.0 if x<0.5 else 1.0, 1, 1)
            # delta RMS stopping limit - disabled (-1e20) if input is blank
            txt = annTab.textStopRule.text()
            if txt > "":
                deltaRMS = float(annTab.textStopRule.text())
            else:
                deltaRMS = -1.0e20
            #logTab.append(u'Stopping \u0394RMS%% =%.6f ' % (deltaRMS))
            # sample points working array and stats
            Ipr = np.array(annTab.smplPtsF) # raw sample factors as np array
            self.rawMin = np.min(Ipr,0)
            self.rawMax = np.max(Ipr,0)
            # re-scale inputs from zeros to 1.
            Ipr = (Ipr - self.rawMin)/(self.rawMax - self.rawMin)
            # make augmented input vectors (a column of 1's pre-pended)
            # n= no. sample (rows), m is factors+1 (columns)
            (n, m) = Ipr.shape
            m = m + 1
            Iv = np.ones((n, m))
            Iv[:,1:] = Ipr
            # Training vector of observed risk factors is 6'th column in smplPts
            Tv = np.array(smplTab.smplPts)
            Tv = Tv[:,5]
            Tv = np.reshape(Tv, (-1, 1))
            # Yo is vector of observed ouputs used for Kappa calculation
            # from either calibration points (if no validation) or validation sample
            if vchk:
                Yo = np.array(smplTab.vldnPts)
                Yo = Yo[:,5]
                Yo = np.reshape(Yo, (-1, 1))
                # create array for validation input data
                Iprv = np.array(annTab.smplPtsV)   # raw sample factors as np array
                # re-scale inputs using same factors as the sample
                Iprv = (Iprv - self.rawMin)/(self.rawMax - self.rawMin)
                Ivv = np.ones((n, m))
                Ivv[:,1:] = Iprv
            else:
                Yo = Tv
            # ----- initial conditions -------
            itc = 0                          # iteration counter
            rmse = list()                    # RMS data series for graph
            sfig = float(10**annTab.xmag)    # scale factor for iterations on graph
            # number in middle layer is same as number of inputs
            self.nM = m-1
            # weights for output and middle layers, random from -0.05 to +0.05
            f = 0.1
            self.Wout = (np.random.rand(m, 1) - 0.5)*f
            self.Wmid = (np.random.rand(m, m-1) - 0.5)*f
            # initialise variables used for Delta RMS stopping rule
            lev = 1e20
            # ------- training loop -------
            while itc < maxiter:        # loop  over training iterations
                # ******** Building site for new algorithm ********
                # vector of raw mid-layer outputs {n x m . m x m-1 => n x m-1}
                Mv = np.dot(Iv, self.Wmid)
                # sigmoid transform of mid-layer outputs
                Mv = 1.0/(1.0+np.exp(-Mv))
                # augment mid-layer outputs with 1's in column 0
                Mz = np.ones((n, m))
                Mz[:,1:] = Mv   # {n x m}
                # outer layer calculation {n x m . m x 1 => n x 1}
                Ov = np.dot(Mz, self.Wout)
                # sigmoid transform of outer layer outputs
                Ov = 1.0/(1.0+np.exp(-Ov))
                # error vector {n x 1}
                Ev = Tv - Ov
                # adjusment terms (delta) for outer layer (n x 1 vector)
                Od = Ov*(1-Ov)* Ev
                # calculate middle layer delta terms
                # (m-1 x 1) . (1 x n) => (m-1 x n)
                Wd = np.dot(self.Wout[1:,], Od.T)
                Md = Mv*(1-Mv)*Wd.T     #{n x m-1}
                # outer layer adjustment { m x n. n x 1 => m x 1}
                mxo = np.dot(Mz.T, Od) /float(n)
                self.Wout += eta*mxo
                # new middle layer adjustment {m x n . n x m-1 => m x m-1}
                ixm = np.dot(Iv.T, Md) /float(n)
                self.Wmid += eta*ixm
                # calculate root-mean square error
                ssq = np.dot(Ev.T, Ev)
                rms = math.sqrt(ssq/float(n))
                # raw minimum and maximum values of outputs before scaling
                ovMin = np.min(Ov)
                ovMax = np.max(Ov)
                # update graph with R-squared between outputs and observed values
                Ov = (Ov - ovMin)/(ovMax - ovMin)
                rr = np.corrcoef(Ov.T, Tv.T)
                rsq = rr[0,1]**2
                #logTab.append("r-squared %s Correlation matrix %s" % (rsq, rr))
                annTab.lcg.addPoint(2, float(itc)/sfig, rsq)
                annTab.textRsq.setText('%6.4f' % rsq)
                # if validation, calculate RMSE for validation sample and graph it
                if vchk:
                    Ye = self.multi_response(Ivv)
                    Evv = Yo - Ye
                    ssq = np.dot(Evv.T, Evv)
                    rmsv = math.sqrt(ssq/float(n))
                    # output probabilities actualized as zero or 1
                    Ye = (Ye - np.min(Ye))/(np.max(Ye) - np.min(Ye))
                    Yeh = flim(Ye)
                    # do kappa calculation
                    (kp, pma) = kappa(Yo, Yeh)
                else:
                    # alternative kappa based on training sample
                    Ovh = flim(Ov)
                    #debug_values(2484, Tv_shape=Tv.shape,Ovh_shape=Ovh.shape)
                    (kp, pma) = kappa(Tv, Ovh)
                # display kappa and PMA
                annTab.textKappa.setText('%7.4f' % kp)
                annTab.textPctMapAgr.setText('%7.1f%%' % (pma*100.0))
                # initialise delta RMS (diff) calculation at first cycle:
                if itc<2:
                    if itc>0:
                        dPct = oldRMS - rms  # base for calculating %Delta RMS
                else:
                    # check for termination rule based on delta RMS
                    diff = (oldRMS-rms)/dPct
                    annTab.lcg.addPoint(0, float(itc)/sfig, diff)
                    if vchk:
                        vdiff = (oldRMSv-rmsv)/dPct
                        annTab.lcg.addPoint(1, float(itc)/sfig, vdiff)
                    if diff<deltaRMS:
                        # exit as change in RMS below threshold
                        logTab.append(tr(u'Training halted by RMS convergence. \u0394RMS%% =%.6f after iteration %s')
                             % (diff, itc))
                        break
                oldRMS = rms
                if vchk:
                    oldRMSv = rmsv
                if self.endRun: # toggled on by the Stop button on the GUI
                    logTab.append(tr(u'Training halted by manual Stop after iteration %s. \u0394RMS%% =%.6f')
                        % (itc, diff))
                    break
                # update chart
                annTab.lcg.repaint()
                QApplication.processEvents()
                itc += 1
            else:
                #----- end of training loop -------
                logTab.append(tr(u'Training loop completed after %s iterations. \u0394RMS%% =%.6f') % (itc, diff))
            # final refresh of chart
            annTab.lcg.repaint()
            QApplication.processEvents()
            return True
        except Exception:
            errMsg()
            logTab.append("ANN training aborted due to error")
            return False

    def response(self, Iv):
        # given a vector of raw inputs, calculates outputs according to current calibration
        try:
            # calculate perceptron output with current weights
            Mv = self.calcOutputs(Iv, self.Wmid)
            Ov = self.calcOutputs(Mv, self.Wout)
            Ov = (Ov - self.rawMin)/(self.rawMax - self.rawMin)
            return Ov
        except Exception:
            errMsg()
            return None

    def multi_response(self, Im):
        # calculate perceptron response vector for multiple cases.
        # Im is an np m x p matrix, m being no. of cases, p being input values
        # If limit is True, the result vector is hard limited to 0 or 1,
        # otherwise it will be between -1 and +1.  If verbose is True,
        # data is output to CSV workfiles for checking.  If augment is True,
        # a column of 1's is prepended to Im, otherwise it is not.
        try:
            (n, m) = Im.shape
            Mz = np.ones((n, m))
            # raw outputs from the first stage
            Mv = np.dot(Im, self.Wmid)
            # scale mid-layer outputs (mv = 1/(1+exp(-mv))
            Mv = -Mv
            Mv = np.exp(Mv)
            Mv = 1.0 + Mv
            Mv = 1.0 / Mv
            gc.collect()
            # augment mid-layer outputs
            Mz[:,1:] = Mv
            # outer layer calculation
            Ov = np.dot(Mz, self.Wout)
            # scaled outer layer outputs
            Ov = np.exp(-Ov)
            Ov = 1.0/(1.0 + Ov)
            return Ov
        except Exception:
            # general error handler
            errMsg()


    def saveANNparams(self):
        # save ANN weights in the .qgs project file
        try:
            params = Config("ANN_Weights",0.0,float)
            # save inner layer coefficients
            (n, m) = self.Wmid.shape
            params['Wmid-N'] = n
            params['Wmid-M'] = m
            for i in range(0, n):
                for j in range(0, m):
                    txt = 'Wmid-%s-%s' % (i, j)
                    params[txt] = self.Wmid[i,j]
            # write outer layer weights
            (n, m) = self.Wout.shape
            params['Wout-N'] = n
            params['Wout-M'] = m
            for i in range(0, n):
                for j in range(0, m):
                    txt = 'Wout-%s-%s' % (i, j)
                    params[txt] = self.Wout[i,j]
            # write input scaling factors
            L = self.rawMin.shape[0]
            #debug_values(2626, rawMin_shape=self.rawMin.shape, values=self.rawMin)
            params['ScaleFactors'] = L
            for i in range(0, L):
                txt = 'ScaleMin-%s' % (i)
                params[txt] = self.rawMin[i]
                txt = 'ScaleMax-%s' % (i)
                params[txt] = self.rawMax[i]
        except Exception:
            # general error handler
            errMsg()

    def loadANNparams(self):
        # retrives ANN weights from the .qgs project file
        try:
            params = Config("ANN_Weights",0.0,float)
            # load inner layer coefficients
            n = int(params['Wmid-N'])
            m = int(params['Wmid-M'])
            self.Wmid = np.zeros((n, m), dtype=float)
            for i in range(0, n):
                for j in range(0, m):
                    txt = 'Wmid-%s-%s' % (i, j)
                    self.Wmid[i,j]= params[txt]
            # load outer layer coefficients
            n = int(params['Wout-N'])
            m = int(params['Wout-M'])
            self.Wout = np.zeros((n, m), dtype=float)
            for i in range(0, n):
                for j in range(0, m):
                    txt = 'Wout-%s-%s' % (i, j)
                    self.Wout[i,j]= params[txt]
            # load scaling factors
            L = int(params['ScaleFactors'])
            self.rawMin = np.zeros((L), dtype=float)
            self.rawMax = np.zeros((L), dtype=float)
            for i in range(0, L):
                txt = 'ScaleMin-%s' % (i)
                self.rawMin[i] = params[txt]
                txt = 'ScaleMax-%s' % (i)
                self.rawMax[i] = params[txt]
        except Exception:
            # general error handler
            errMsg()

class Simulator():
    """
    Based on current model, controls simulation via cellular automaton
    over a number of cycles
    """
    def __init__(self, parent=None):
        # sets up user interface for simulator tab, which outputs the risk map
        # or runs simulations according to the various models
        self.gui = QWidget()
        layout=QGridLayout()
        # defaults from QGIS project for options
        self.config = Config("Simulator",'', str)
        txtBoxWidth = 60    # common width for most of the input boxes
        # form heading
        lbl00 = QLabel(tr(u'<B>Land Use Change Risk Map and Simulated Projections</B>'))
        layout.addWidget(lbl00,0,0,1,3,Qt.AlignLeft)
        # headings for map options
        lblMapOf = QLabel(tr(u'Produce map of'))
        layout.addWidget(lblMapOf,1,0)
        lblFile = QLabel(tr(u'File'))
        layout.addWidget(lblFile,1,1)
        # button group for alternative functions (Risk Maps or Simulation)
        grpAction = QButtonGroup()
        grpAction.setExclusive(True)
        self.mapLabels = [tr(u'Risk Function'), tr(u'Observed Risk Classes'),
                tr(u'Risk Class Validation'), tr(u'Monte Carlo Simulations')]
        yr = fTab.textFinalYear.text()
        mapTips = [tr(u'Makes 1-band GeoTiff+legend of risk probability at final year (%s)')
             % (yr), tr(u'Makes 1-band GeoTiff+legend of observed risk class in %s') % (yr),
             tr(u'Makes 1-band GeoTiff of correct (transparent) and incorrect (red) risk class in %s')
             % (yr), tr(u'Makes 1-band GeoTiffs for each period to designated end year %s using current model')]
        self.optChoice = int(self.config["MapOption"]) if self.config["MapOption"] else 0
        m = len(self.mapLabels)      # number of options
        self.optBtn = list()         # list of option buttons
        self.btnFile = list()        # list of file buttons
        for k in range(0, m):
            # add an option button
            self.optBtn.append(QRadioButton(self.mapLabels[k]))
            if k == self.optChoice:
                 self.optBtn[k].setChecked(True)
            self.optBtn[k].setToolTip(mapTips[k])
            QObject.connect(self.optBtn[k], SIGNAL("clicked()"), partial(self.setOption, k))
            grpAction.addButton(self.optBtn[k])
            layout.addWidget(self.optBtn[k], k + 2, 0)
            # add a file selection button
            self.btnFile.append(QPushButton(u'...'))
            self.btnFile[k].setFixedWidth(30)
            self.btnFile[k].setToolTip(tr(u'Set or change filename for output map'))
            QObject.connect(self.btnFile[k], SIGNAL("clicked()"), partial(self.getFile, k))
            layout.addWidget(self.btnFile[k], k + 2, 1)
        # get projection interval from input tab - use 1 period if undefined
        try:
            fyr = int(fTab.textFinalYear.text())
            lyr = int(fTab.textInitialYear.text())
            iyr = fyr - lyr
        except (ValueError):
            fyr = 10
            lyr = 1
            iyr = 1
        # retrieve value for current year and use it if in range,  otherwise
        # use the final year
        ayr = int(self.config['EndYear']) if self.config['EndYear'] >'' else fyr
        # set up spinner for end year
        self.spinYr = QSpinBox()
        self.spinYr.setFixedWidth(50)
        self.spinYr.setValue(ayr)
        self.spinYr.setSingleStep(iyr)
        self.spinYr.setMinimum(lyr)
        try:
            self.spinYr.setMaximum(lyr + (100//iyr+1)*iyr) # at least 100 years
        except ZeroDivisionError:
            self.spinYr.setMaximum(100)
        self.spinYr.setToolTip(tr(u'Last year for projected Land Use Change'))
        # simulation end year label and spinner
        lblEndYr = QLabel(tr(u'<SMALL>end<BR>year</SMALL>'))
        layout.addWidget(lblEndYr, 5, 2, Qt.AlignRight)
        layout.addWidget(self.spinYr, 5,  3, Qt.AlignLeft)
        # horizontal line across 3 columns
        hline2 = QFrame()
        hline2.setFrameStyle(QFrame.HLine|QFrame.Sunken)
        layout.addWidget(hline2, 6, 0, 1, 4)
        layout2 = QHBoxLayout()
        # add a checkbox for re-calculating the input matrix
        self.chkReuseMatrix = QCheckBox(tr(u'Re-use input matrix'))
        self.chkReuseMatrix.setToolTip(
            tr(u'Re-use last calculated input matrix if compatible with current model'))
        self.chkReuseMatrix.setDisabled(self.config['InputMatrixFile']=='')
        layout.addWidget(self.chkReuseMatrix, 7, 0)
        # initialize object for later tests of its existence
        self.inputMatrix = None
        # add a file selection button
        self.btnFile.append(QPushButton(u'...'))
        k = len(self.btnFile) - 1
        self.btnFile[k].setFixedWidth(30)
        self.btnFile[k].setToolTip(tr(u'Directory for caching matrix data'))
        QObject.connect(self.btnFile[k], SIGNAL("clicked()"), self.setMatrixDir)
        layout.addWidget(self.btnFile[k], 7, 1)
        # default for temporary dir
        self.tempMatrixDir = self.config['TempMatrixDir']
        # start button and action link
        self.btnRun=QPushButton(tr(u'Start'))
        self.btnRun.setToolTip(tr(u'Start/stop generation of map'))
        self.btnRun.setFixedWidth(40)
        #self.btnRun.setCheckable(True)
        self.cancelRunFlag = False
        QObject.connect(self.btnRun, SIGNAL("clicked()"), self.startRun)
        layout2.addWidget(self.btnRun)
        self.lblJobPhase = QLabel()
        layout2.addWidget(self.lblJobPhase)
        # label and text box for time left
        layout2.addStretch(1)
        self.lblTimeLeft = QLabel(tr(u'Time left(min:sec)'))
        layout2.addWidget(self.lblTimeLeft)
        self.txtTimeLeft = QLineEdit()
        self.txtTimeLeft.setToolTip(tr(u'Estimated time left for process to complete'))
        self.txtTimeLeft.setFixedWidth(txtBoxWidth)
        layout2.addWidget(self.txtTimeLeft)
        self.lblTimeLeft.hide()
        self.txtTimeLeft.hide()
        layout.addLayout(layout2, 8, 0, 1, 4)
        # stretch right column and bottom row
        layout.setRowStretch(9,9)
        layout.setColumnStretch(0,8)
        layout.setColumnStretch(4,9)
        self.gui.setLayout(layout)

    def startRun(self):
        # Manages risk map generation or simulation process.  This routine either
        # generates, retrieves from file, or re-uses the Input Matrix, applies
        # to it one of the defined models, generates an output vector of
        # probabilities, then uses this to generate one of the designated map types.
        # As these processes may be slow, it updates the user with messages at
        # each job phase.
        try:
            if self.btnRun.text() == tr(u'Start'):
                self.btnRun.setText(tr(u'Stop'))
                self.cancelRunFlag = False     # if flag was set earlier, clears it
                self.config['MapOption']= self.optChoice
                self.config['EndYear'] = self.spinYr.value()
                self.msgUpdate('Initializing...')
                # get the neighbourhood size, according to model type
                models= [annTab, LRtab]
                m = modTab.ddMethod.currentIndex()
                nz = models[m].spinNbh.value()
                #logTab.append("Neighborhood size = %d" % nz)
                # get input matrix where required (all except option 1)
                if self.optChoice in set([0,2,3]):
                    fTab.getLayers()
                    # see if existing data matrix is to be re-used
                    if self.chkReuseMatrix.isChecked():
                        # if not defined internally, reload from file
                        if self.inputMatrix is None:
                            self.msgUpdate('Loading matrices : Y index ...')
                            idy = self.loadMatrixData('idy')
                            self.msgUpdate('Loading matrices : X index ...')
                            idx = self.loadMatrixData('idx')
                            self.msgUpdate('Loading matrices : Inputs ...')
                            ida = self.loadMatrixData('ida')
                            # test for success of re-load based on ida matrix
                            self.inputMatrix = None if ida is None else (idy, idx, ida)
                    else:
                        # new build  of data matrix required
                        self.inputMatrix = self.getInputs(nz)
                        if self.inputMatrix is not None:
                            (idy, idx, ida) = self.inputMatrix
                    # by this point, the inputMatrix should either (a) already exist
                    # or (b) have been re-loaded from disk or (c) been re-built
                    # if (a) or (b) have failed, do try re-buliding here
                    if self.inputMatrix is None:
                        self.inputMatrix = self.getInputs(nz)
                        if self.inputMatrix is None:
                            raise MolusceError('Unable to re-load or create Input Matrix')
                    (idy, idx, ida) = self.inputMatrix
                    # these options also require the vector of predicted risk
                    self.msgUpdate('Calculating risk probabilities ...')
                    gc.collect()
                    # generate vector of risk probabilities according to type of model
                    vrp = self.applyModel(ida)
                # get output vector where needed (options 1 and 2)
                if self.optChoice in set([1, 2, 3]):
                    if self.chkReuseMatrix.isChecked():
                        self.msgUpdate('Loading Output Vector ...')
                        opv = self.loadMatrixData('opv')
                        if opv is None:
                            opv = self.getOutput()
                    else:
                        opv = self.getOutput()
                    if opv is None:
                        raise MolusceError('Unable to re-load or create Output Vector')
                # now run required type of map output
                self.msgUpdate('Generating map layer ...')
                if self.optChoice==0:       # risk probability map
                    self.makeMap(1, pv=vrp)
                elif self.optChoice==1:     # observed risk map
                    self.makeMap(2, opv=opv)
                if self.optChoice==2:       # validation map
                    self.makeMap(3, opv=opv, pv=vrp)
                if self.optChoice==3:       # project risk over several periods
                    # array-wise Monte Carlo realization of risk function to 0-1 risk classes
                    flim = np.frompyfunc(lambda x: 0 if x<random.random() else 1, 1, 1)
                    #flim = np.frompyfunc(lambda x: 0 if x<0.5 else 1, 1, 1)
                    # initial year, from spinner control
                    yr = self.spinYr.minimum()+self.spinYr.singleStep()
                    # loop through the periods
                    while not self.cancelRunFlag:
                        self.msgUpdate('Simulating map for %s ...' % yr)
                        # output the current map
                        self.makeMap(4, opv=opv, year=yr)
                        # exit loop when final year reached
                        if yr>=self.spinYr.value():
                            break
                        # diagnostic output
                        logTab.append("%d Input means\n%s" % (yr, np.mean(ida, 0)))
                        logTab.append("%d Input minimum\n%s" % (yr, np.min(ida, 0)))
                        logTab.append("%d Input maximum\n%s" % (yr, np.max(ida, 0)))
                        # update inputs with previous outputs
                        ida[:,1:nz+2] = self.inputOutput(nz, opv)
                        # get new vector of output risk probabilities
                        gc.collect()
                        vrp = self.applyModel(ida)
                        # replace probabilities by Monte Carlo actualization
                        opv[:,0] = flim(vrp)
                        # update period
                        yr += self.spinYr.singleStep()
                self.resetRun()
                self.msgUpdate('Completed OK')
            else:
                # flag process to be stopped
                self.cancelRunFlag = True
                self.msgUpdate('Cancelling Run...')
        except Exception:
            errMsg()
            self.resetRun()

    def resetRun(self):
        # after the process has stopped, resets the run status for a
        # normal restart next time
        try:
            self.btnRun.setText(tr(u'Start'))
            self.cancelRunFlag = False
            logTab.append('Run status reset')
            QApplication.processEvents()
        except Exception:
            errMsg()

    def msgUpdate(self, msg):
        # progress messages for this widget...
        self.lblJobPhase.setText(msg)
        logTab.append(msg)  # comment out if too verbose - allows timing to be benchmarked
        QApplication.processEvents()

    def setOption(self, m):
        # called when option button is clicked, m is button ID
        self.optChoice=m

    def getFile(self, m):
        # gets the name for the risk map and updates value stored in config object
        # if no m parameter given, requests filename to save/reload the
        # input matrix.
        try:
            # config object and dialog title according to type of file
            mapFile = 'MapFile%s' % m
            title = tr(u'Output File for %s') % (self.mapLabels[m])
            ftype = "GeoTIFF (*.tif)"
            ext = u'.tif'
            # use as default (a) name from config, or (b) default path
            if self.config[mapFile]>'':
                idir = self.config[mapFile]
            else:
                idir = getDefaultPath()
            # file save dialog
            opf = str(QFileDialog.getSaveFileName(None, title, idir, ftype))
            if opf>'':
                # check for extension and add it if not given (Linux issue)
                if opf[-4:] != ext:
                    opf += ext
                # set file name to label and config
                self.config[mapFile] = opf
        except Exception:
            # general error handler
            errMsg()

    def setMatrixDir(self):
        # sets the directory name for temporary files with matrix data
        try:
            # config object and dialog title according to type of file
            title = tr(u'Set directory for caching matrix files')
            # use current value as a default, or the
            self.tempMatrixDir = self.config['TempMatrixDir']
            if self.tempMatrixDir>'':
                idir = self.tempMatrixDir
            else:
                idir = getDefaultPath()
            # get directory dialog -
            tmpdir = str(QFileDialog.getExistingDirectory(None, title, idir))
            if tmpdir>'':
                # save directory name to class and to .qgs project file
                self.config['TempMatrixDir'] = tmpdir
                self.tempMatrixDir = tmpdir
                logTab.append('Temporary Directory is <u>%s</u>' % tmpdir)
        except Exception:
            # general error handler
            errMsg()

    def saveMatrixData(self, key, mtx):
        # saves a numpy array <mtx> to a temporary file and stores name
        # in config object with label Matrix.key
        try:
            # retrieve or construct file name
            fullkey = 'Matrix.'+key
            tmpfile = self.config[fullkey]
            if tmpfile=='':
                tmpfile = '~' + str(random.randrange(1000000,9999999)) + '.tmp'
                self.config[fullkey] = tmpfile
            fln = self.tempMatrixDir + '/' + tmpfile
            logTab.append(tr(u'Matrix %s being saved as <u>%s</u>') % (key, fln))
            # save matrix in format +0.123456e+00 with comma separators
            np.savetxt(fln, mtx, '%13.6e', ',')
        except Exception:
            # general error handler
            errMsg()

    def loadMatrixData(self, key):
        # returns a numpy array loaded from a temporary file referenced by <key>
        try:
            # construct file name
            fullkey = 'Matrix.'+key
            tmpfile = self.config[fullkey]
            fln = self.tempMatrixDir + '/' + tmpfile
            logTab.append(tr(u'Matrix %s being loaded from <u>%s</u>') % (key, fln))
            a = np.loadtxt(fln, delimiter=',')
            return a
        except Exception:
            # general error handler
            errMsg()


    def getInputs(self, nz=0):
        # returns a 2-d array representing the input vector for each point
        # together with corresponding indices to the x-y point on the base layer
        # <nz> is the neighbourhood size, from ANN or LR parameter screens.
        try:
            self.lblJobPhase.setText('Converting base LUCs to Risk...')
            logTab.append('getInputs started')
            QApplication.processEvents()
            nL = len(fTab.mfactG)   #layer count
            fMaps = list()          # list of factors as masked arrays
            fGeos = list()          # list of geometry tuples for each factor array
            # loop through layers bulding list of data arrays and layer geometries
            for L in range(0, nL):
                gmap = fTab.mfactG[L]   # GDAL dataset for raster image
                qlyr = fTab.mfactL[L]   # QGIS layer of same image
                # retrieve layer geometry
                geo = gmap.GetGeoTransform()
                xsz = gmap.RasterXSize
                ysz = gmap.RasterYSize
                nb = gmap.RasterCount
                # origin in projection units
                x0 = geo[0]
                y0 = geo[3]
                rotn = geo[2]  # rotation, zero = north, no rotation
                # pixel size
                px = geo[1]
                py = geo[5]
                lyrnm = str(qlyr.name())
                # handle layers with non-zero rotation in their geometry
                if rotn != 0:
                    raise MolusceError(tr(u'Layer %s has non-zero rotation') % (lyrnm))
                # no data value
                (ndv, hasNDV) = qlyr.noDataValue()
                if not hasNDV:
                    ndv =-32767   # use an unlikely value if no NDV set (1-2^15)
                # offset factor in pixels from neighborhood size
                (apx, apy) = (abs(px), abs(py))
                # process each band of the layer as a separate factor
                for b in range(0, nb):
                    # get layer into masked numpy array (y is first dimension, x is second in array)
                    aMap = gmap.GetRasterBand(b+1).ReadAsArray(0, 0, xsz, ysz)
                    mMap = npm.masked_equal(aMap, ndv) # array masked by NDV
                    fMaps.append(mMap)
                    fGeos.append((xsz, ysz, px, py, x0, y0))
            # number of factors
            nF = len(fMaps) + nz
            # index generator for factor maps
            fList = range(1, len(fMaps))
            # reference geometries in base layer
            (xsz0, ysz0, px0, py0, x00, y00) = fGeos[0]
            # Get indices of non-masked pixels on base layer
            bMap = fMaps[0]                     # base map
            bmask = npm.getmaskarray(bMap)      # its mask
            umask = np.logical_not(bmask)       # logically inverted
            (rows,cols) = np.nonzero(umask)     # indices of unmasked values
            L = len(rows)                       # no of coordinates in index
            self.setTimer(L)                    # reset count down timer
            # input data array to be generated, points by factors
            ida = np.zeros(shape=(L, nF+1), dtype=float)
            # array function for risk factor conversion
            riskSet = set(smplTab.risk)
            fRisk = np.frompyfunc(lambda x: 1 if x in riskSet else 0, 1, 1)
            # convert base map values to risk 0 or 1
            rMap = fRisk(bMap)
            logTab.append('Risk Map array generated')
            self.lblJobPhase.setText('Making %s x %s matrix ...' % (L, nF))
            self.lblTimeLeft.show()
            self.txtTimeLeft.show()
            QApplication.processEvents()
            # base map input factors - one factor for each 'ring' of neighboring
            # pixels, being mean risk pixel count in the ring
            for i in xrange(0,L):
                ix = cols[i]
                iy = rows[i]
                # constant term and total for base pixel neighbourhood
                ida[i,0] = 1.0
                ida[i, 1:nz+2] = avgZoneRings(rMap, ix, iy, nz)
                self.timeIt()
            logTab.append('Base Map inputs done')
            # if other driving factors, calculate them here
            if nF>1:
                self.setTimer(L)                    # reset count down timer
                 # work through list of factor layers
                for f in fList:
                    # get the layer geometry
                    (xsz, ysz, px, py, x0, y0) = fGeos[f]
                    # reference to current layer
                    mMap = fMaps[f]
                    # work through base map pixels
                    for i in xrange(0,L):
                        ix = cols[i]
                        iy = rows[i]
                        # calculate target coordinates in layer
                        xb = float(ix) * px0 + x00
                        yb = float(iy) * py0 + y00
                        xt = (xb - x0) / px
                        yt = (yb - y0) / py
                        # use factor pixel value.
                        ida[i,f+1+nz] = mMap[yt, xt]
                        self.timeIt()
                    logTab.append('Factor Layer %s inputs done' % (f))
            # clean up the ida array for any NaN values
            ida = np.nan_to_num(ida)
            # save results to file for later re-use
            # idy, idx are external names used for rows and cols indexing arrays
            self.msgUpdate('Saving input matrix files ...')
            self.saveMatrixData('idy', rows)
            self.saveMatrixData('idx', cols)
            self.saveMatrixData('ida', ida)
            # set default option to re-use matrix
            self.chkReuseMatrix.setDisabled(False)
            self.chkReuseMatrix.setChecked(True)
            # return column and row indices, calculated data values
            result = (rows, cols, ida)
        except Exception:
            # general error handler
            errMsg()
            self.lblJobPhase.setText('Process aborted ...')
            result = None
        self.lblTimeLeft.hide()
        self.txtTimeLeft.hide()
        QApplication.processEvents()
        return result

    def getOutput(self):
        # returns a vector of zero-one points representing risk classes, using
        # the same indexes as created by the getInputs routine.  Because this routine
        # was an afterthought, there is some duplication in file opening etc
        # getInputs and filesTab.getLayers relative to the Final layer
        try:
            logTab.append('getOutput started')
            self.msgUpdate('Converting final LUCs to Risk...')
            gmap = areaTab.map[1]
            ndv = areaTab.NDV[1]
            # retrieve layer geometry
            geo = gmap.GetGeoTransform()
            xsz = gmap.RasterXSize
            ysz = gmap.RasterYSize
            # get layer into masked numpy array (y is first dimension, x is second in array)
            bMap = gmap.GetRasterBand(1).ReadAsArray(0, 0, xsz, ysz)
            mMap = npm.masked_equal(bMap, ndv) # array masked by NDV
            # Get indices of non-masked pixels on base layer
            bmask = npm.getmaskarray(mMap)      # its mask
            umask = np.logical_not(bmask)       # logically inverted
            (rows,cols) = np.nonzero(umask)     # indices of unmasked values
            L = len(rows)                       # no of coordinates in index
            # convert base map values to risk 0 or 1
            fRisk = np.frompyfunc(smplTab.getRisk, 1, 1)
            rMap = fRisk(mMap)
            ov = np.zeros((L, 3), dtype=int)
            QApplication.processEvents()
            # loop over indexed pixels adding to output vector
            for i in xrange(0,L):
                ix = cols[i]
                iy = rows[i]
                ov[i, 0] = rMap[iy, ix]
                ov[i, 1] = iy
                ov[i, 2] = ix
            logTab.append('Risk Map generated')
            # save results to file for later re-use
            self.msgUpdate('Saving output vector file ...')
            self.saveMatrixData('opv', ov)
            # return output vector
            result = ov
        except Exception:
            # general error handler
            errMsg()
            result = None
        self.msgUpdate('')
        return result

    def inputOutput(self, nz, opv):
        # Given neighborhood size nz and output vector opv, converts it onto the
        # equivalent input vector by summing risk values over the neighborhood for
        # each pixel.
        try:
            if nz==0:
                # no calculation needed - equate inputs with outputs
                result = opv[:, 0]
            else:
                # update display to show progress as this may take a minute or two
                self.msgUpdate('Converting outputs to inputs...')
                self.lblTimeLeft.show()
                self.txtTimeLeft.show()
                QApplication.processEvents()
                # get base layer geometry
                gmap = fTab.mfactG[0]   # GDAL dataset for raster image
                geo = gmap.GetGeoTransform()
                xsz = gmap.RasterXSize
                ysz = gmap.RasterYSize
                # re-build data as a 2-D grid from indices
                rMap = np.zeros((ysz, xsz), dtype=int)
                # retrieve index arrays.
                ov = opv[:, 0]
                idy = opv[:, 1]
                idx = opv[:, 2]
                L = len(idx)
                # set progress counter limit
                self.setTimer(L)
                self.msgUpdate('Make 2-D grid of outputs')
                # copy data into 2-D grid
                for j in xrange(0, L):
                    x = idx[j]
                    y = idy[j]
                    rMap[y, x] = ov[j]
                    self.timeIt()
                # create empty input matrix (outputs summed over neighborhoods)
                ipv = np.zeros((L, nz+1), dtype=int)
                self.setTimer(L)
                self.msgUpdate('Switch outputs to next inputs')
                # loop through list of points summing totals over neighborhoods
                # base map input factors - risk counts over neighbourhood pixels
                for i in xrange(0,L):
                    ix = idx[i]
                    iy = idy[i]
                    ida[i, 1:nz+2] = avgZoneRings(rMap, ix, iy, nz)
                    self.timeIt()
                # return result matrix
                result = ipv
        except Exception:
            errMsg()        # general error handler
            self.lblJobPhase.setText('Process aborted ...')
            result = None
        self.lblTimeLeft.hide()
        self.txtTimeLeft.hide()
        QApplication.processEvents()
        return result

    def setTimer(self, iMax):
        # initialize counter and timer variables for 'time left' display
        self.ctr = 0                        # progress counter
        self.ctrMax = iMax                  # maximum for counter
        self.ctrStart = time.time()         # start time for counter
        self.ctrLast = self.ctrStart        # time of last counter call

    def timeIt(self, w=0):
        # update progress counter and prints time-left estimate every second
        # w is the weight index for first and second loops (different speeds)
        # --- increment counter
        self.ctr += 1
        t = time.time()
        # --- see if a second has elapsed since last call, just return if not
        if t-self.ctrLast>1:
            # estimate of time required to complete
            trq = int((t-self.ctrStart)*(self.ctrMax/float(self.ctr)-1))
            # output figure to GUI in minutes and seconds
            self.txtTimeLeft.setText("%d:%02d" % (trq // 60, trq % 60))
            # update time for 1-second interval check
            self.ctrLast = t
            # allow OS to update GUI
            QApplication.processEvents()
            # check for abort flag, raise error if set
            if self.cancelRunFlag:
                self.resetRun()     # reset status flag and button label
                pct = float(self.ctr)/float(self.ctrMax)*100.0
                raise MolusceError(tr(u'Map output aborted by user, %5.1f%% done') % (pct))

    def applyModel(self, ida):
        # applies LR or ANN models to the input matrix to gnerate a vector of
        # of predicted risk probabilities.  ida is (pixels x parameters),
        # with the first column presenting 1's for the constant term.
        try:
            # see what type of model (LR or ANN) has been selected
            m = modTab.ddMethod.currentIndex()
            acronym = ["ANN", "LR"]
            if m == 0:
                # --- ANN calculations ---
                # Retrieve settings and instantiate coefficient matrices
                ann = Perceptron()
                ann.loadANNparams()
                # re-scale inputs
                max_min = ann.rawMax - ann.rawMin
                ida[:,1:] = ida[:,1:] - ann.rawMin
                ida[:,1:] = ida[:,1:] / max_min
                # calculate outputs as probabilities
                vpr = ann.multi_response(ida)
            elif m == 1:
                # --- LR calculations ---
                # retrieve coefficients
                b = np.array(LRtab.beta)
                bv = np.reshape(b, (-1, 1))
                y = np.dot(ida, b)
                ey = np.exp(y)
                vpr = ey/(1+ey)
            else:
                raise MolusceError(tr(u'Model type unspecified [%s]') % m)
            # re-scale and return predicted values
            (p0, p1) = (np.nanmin(vpr), np.nanmax(vpr))
            vpr = (vpr - p0)/(p1 - p0)
            return vpr
        except Exception:
            errMsg()            # general error handler

    def makeMap(self, mode, pv=None, opv=None, year=0):
        # Generates an output map with the same geometry as the base map and
        # adds it to the QGIS legend.  The mode determines type of map:
        # (1) Risk map. pv is required, representing probable risk 0-1
        # (2) Observed risk class. opv is required, a risk class from 0-1 in
        #     column 0, iy in col. 1, ix in col 2
        # (3) Validation.  NDV (transparent) if risk as predicted otherwise 1.
        #     Both pv and ov required.
        # (4) Simulated (projected) risk classes, pv required, values 0-1.
        # pv and ov have dimensions of idy and idx which mayeach value to a
        # pixel.
        try:
            # get output file name - should be set, but if not, request it
            mapFile = 'MapFile%s' % (mode-1)
            opf = self.config[mapFile]
            # if mode=4, add the year before the extension
            if mode==4:
                yrtext = '_%s.tif' % year
                opf = re.sub(r'\.tif', yrtext, opf)
            # extract the filename, without extension, from the full path
            result = re.search(r".+/(.+)\.tif", opf, re.IGNORECASE)
            if result is None:
                raise MolusceError('Cannot parse output filename : %s\nMake sure it has .tif extension' % opf)
            laynm = result.group(1)
            # get base map geometry
            gmap = fTab.mfactG[0]   # GDAL dataset for raster image
            qlyr = fTab.mfactL[0]   # QGIS layer of same image
            # retrieve layer geometry
            geo = gmap.GetGeoTransform()
            proj = gmap.GetProjection()
            # image size
            xsz = gmap.RasterXSize
            ysz = gmap.RasterYSize
            # origin in projection units
            x0 = geo[0]
            y0 = geo[3]
            # pixel size
            px = geo[1]
            py = geo[5]
            # no data value
            (ndv, hasNDV) = qlyr.noDataValue()
            if not hasNDV:
                ndv =-32767   # use an unlikely value if no NDV set (1-2^15)
            # arrays for (risk) map initialised to NDV
            rMap = np.zeros((ysz, xsz), dtype=int) + ndv
            # retrieve index arrays.  In mode 2 these are stored with opv,
            # otherwise they are in inputMatrix
            if mode in set([2, 4]):
                ov = opv[:, 0]
                idy = opv[:, 1]
                idx = opv[:, 2]
            else:
                (idy, idx, void) = self.inputMatrix
            # loop through pixels doing operation according to mode
            nerr=0
            for j in xrange(0, len(idy)):
                x = idx[j]
                y = idy[j]
                try:
                    if mode==1:      # risk map, coded 1-9
                        rMap[y, x] = int(pv[j]*9+1) if pv[j]<1.0 else 10
                    elif mode==2:    # actual (observed) risk
                        rMap[y, x] = 1 if ov[j]<0.5 else 2
                    elif mode==3:    # validation, unchanged if OK, 1 if wrong
                        if pv[j]<0.5 and opv[j, 0]>=0.5:
                            # predicted 0, should be 1, code 2
                            rMap[y, x] = 2
                        elif  pv[j]>=0.5 and opv[j, 0]<0.5:
                            # predicted 1, should be 0, code 0
                            rMap[y, x] = 1
                        else:
                            # prediction OK => transparent
                            rMap[y, x] = ndv
                    elif mode==4:            # predicted risk class
                        rMap[y, x] = 1 if ov[j]<0.5 else 2
                    else:
                        raise MolusceError(tr(u'Unknown mode=%s, expecting 1-4') % mode)
                except ValueError:
                    # handle undefined values in data, but abort if more than 100
                    logTab.append('ValueError: point %s  value %s' % (j, pv(j)))
                    nerr += 1
                    if nerr>100:
                        raise MolusceError(tr(u'Too many value errors in data - aborting'))
                continue
            # check if in QGIS layer registry already -
            olay = getMapLayerByName(laynm)
            if olay is not None:
                # remove the layer
                layid = olay.id()
                QgsMapLayerRegistry.instance().removeMapLayer(layid)
                QApplication.processEvents()
            # prepare output map
            drv = gmap.GetDriver()
            omap = drv.Create(opf, xsz, ysz)
            omap.SetProjection(proj)
            omap.SetGeoTransform(geo)
            oband = omap.GetRasterBand(1)
            oband.SetNoDataValue(ndv)
            oband.WriteArray(rMap, 0, 0)
            oband.FlushCache()
            omap = None
            # add map to QGIS legend with symbology according to mode
            olay = QgsRasterLayer(opf, laynm)
            if not olay.isValid():
                raise MolusceError(tr(u'<u>%s</u> is not a valid map layer') % (opf))
            # set up colour scheme
            ct = colorPipe(olay)
            if mode == 1:
                # risk map - pale green to pink values in 10 steps
                for k in range(1,11):
                    c = (k-1)*14 ;  r = 129 + c;  g = 255 - c ; b=128
                    p1 = (k-1)*10; p2 = k*10
                    txt = "Risk %d-%d%%" % (p1, p2)
                    ct[k] = (QColor(r,g,b), txt)
                ct[ndv] = (QColor(255, 255,255), "not classified")
                olay.setDrawingStyle(QgsRasterLayer.SingleBandPseudoColor)
                # below results in intermediate pixel values being interpolated between classes
                #olay.rasterShader.setColorRampType(QgsColorRampShader.INTERPOLATED)
            elif mode == 3:
                # mode 3 produces a validation map, red if 1, transparent (NDV) elswhere
                ct[ndv] = (QColor(255, 255,255), "Correctly classified")
                ct[1] = (QColor(170,0,255),"Risk overestimated (1 for 0)")
                ct[2] = (QColor(255,85,0),"Risk underestimated (0 for 1)")
                olay.setDrawingStyle(QgsRasterLayer.SingleBandPseudoColor)
                #olay.rasterShader().setColorRampType(QgsColorRampShader.EXACT)
            else:
                # modes 2 and 4 produce exact 0 or 1 risk classes
                ct[ndv] = (QColor(255, 255,255), "not classified")
                ct[1] = (QColor(128,255,128),"Risk 0: %s" % smplTab.textRisk0.text())
                ct[2] = (QColor(255,128,128),"Risk 1: %s" % smplTab.textRisk1.text())
                olay.setDrawingStyle(QgsRasterLayer.SingleBandPseudoColor)
                #olay.rasterShader().setColorRampType(QgsColorRampShader.EXACT)
            ct.refresh()
            QgsMapLayerRegistry.instance().addMapLayer(olay)
            logTab.append('Output map <u>%s</u> completed OK' % (opf))
        except Exception:
            errMsg()            # general error handler

    def show(self):
        self.gui.show()


class messageLog:
    """
    Defines a widget with a text area to receive logging of diagnostic,
    warning and error messages.  Has only one method 'append' which adds
    a timestamped message to the log.  The widget is added as a tab 'Log'
    to the Molusce main widget.
    """
    def __init__(self):
        # sets up the message log widget, with a label on top of a text area
        self.mLog = QWidget()
        self.label = QLabel(tr('Log of Molusce warning and diagnostic messages'))
        self.textbox = QTextEdit()
        layout=QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.textbox)
        self.mLog.setLayout(layout)
        self.append(tr(u'MOLUSCE log initialised'))

    def append(self, msg):
        #adds a time stamped message to the message log
        self.textbox.append("%s- %s" % (time.strftime("%H:%M:%S"), msg))

class Config:
    """
    Loads and saves plugin settings from QGIS project XML file.  Different
    Config objects can be created to refer to settings for different tabs
    etc.  Each Config object <cobj> has three implicit methods:

        cobj = Config('context', default, type)
            creates cobj with an XML context (tag), optional default value
            and datatype. default is 0 and type is int if not given.

        cobj['item'] = value
            sets item to value.  This will be written in the QGIS project
            XML file at the time it is executed.

        var = cobj['item']
            returns value of item and assigns to var
    """

    def __init__(self, context, default=0, convert=int, verbose=False):
        # sets context string for subsequent set/get operations
        # and default values and type conversions
        self.plugin = "Molusce"
        self.context = context
        self.default = default
        self.convert = convert
        self.verbose = verbose    # set true to output messages

    def __setitem__(self, key, value):
        # sets a specified value to project setting 'context.key'
        try:
            thiskey = "%s.%s" % (self.context, key)
            v = str(value)
            QgsProject.instance().writeEntry(self.plugin, thiskey, v)
            if self.verbose:
                logTab.append("Config: --> <%s> = %s" % (thiskey, v))
        except Exception, msg:
            logTab.append("*** %s:%s" % ("Config.__setitem__", msg))

    def __getitem__(self, key):
        # tries to retrieve a specified key value.  If it cannot, returns <default>
        # result is converted to type <convert> eg int()
        try:
            thiskey = "%s.%s" % (self.context, key)
            (value, ok) = QgsProject.instance().readEntry(self.plugin, thiskey)
            if ok:
                if self.verbose:
                    logTab.append("Config: <-- <%s> = %s" % (thiskey, value))
                return self.convert(value)
            else:
                if self.verbose:
                    logTab.append("Config: ??? <%s>" % (thiskey))
        except Exception, msg:
            logTab.append("*** %s:%s" % ("Config.__getitem__", msg))
        return self.convert(self.default)

class colorPipe:
    """
    Simplifies access to the QGIS color table for single-band rasters.  A
    colorPipe is created for rasters.  Writing to the pipe will update the QGIS
    legend, while reading from it provides RGB color, and text label for
    a specified entry.
    """
    def __init__(self, rlayer):
        """
        Creates a colorPipe instance for a specified raster layer <rlayer) with:
            cpipe = colorPipe(myRasterlayer)
        Returns None if rlayer is not a valid single-band raster layer
        """
        try:
            # create colour table.  Error will occur if wrong type of object or layer
            lnm = rlayer.name()
            self.layer = rlayer
            self.shf = rlayer.rasterShader().rasterShaderFunction()
            self.cTbl = self.shf.colorRampItemList()
        except AttributeError, msg:
            # handle situation of no color table
            #logTab.append('Making new color table for layer <u>%s</u>' % (lnm))
            # try creating a single intial entry for 0=black, no legend text
            self.cTbl =[QgsColorRampShader.ColorRampItem(0.0, QColor(0), QString(''))]
            rlayer.setColorShadingAlgorithm(QgsRasterLayer.ColorRampShader)
            rlayer.rasterShader().setRasterShaderFunction(QgsColorRampShader())
            self.shf = rlayer.rasterShader().rasterShaderFunction()
            self.shf.setColorRampItemList(self.cTbl)
        except Exception:
            # general error handler
            errMsg()
            return None

    def __setitem__(self, value, data):
        """
        Sets a value in the raster color table to the rgb colour code.  If a
        label is gien it will be used, otherwise it is set to a string copy of
        the value. Used as:
            cpipe[value] = (color[, text])
        """
        try:
            # if a label parameter is given, use it, otherwise apply default
            if len(data)>1 :
                color = data[0]
                text = data[1]
            else:
                color = data[0]
                text = str(value)
            # search for value in the table
            found = False
            for i in xrange(0, len(self.cTbl)):
                if self.cTbl[i].value == value:
                    self.cTbl[i].color = QColor(color)
                    self.cTbl[i].label = QString(text)
                    found = True
            if not found:
                # not in list - add it
                self.cTbl.append(QgsColorRampShader.ColorRampItem(value,
                            QColor(color), QString(text)))
            self.shf.setColorRampItemList(self.cTbl)
            return True
        except Exception:
            # general error handler
            errMsg()
            return False

    def __getitem__(self, value):
        """
        Returns a tuple of (color, text) from raster layer's color table for
        entry 'value', used as:
            (color, text) = cpipe[value]
        """
        try:
            # search for entry
            for i in xrange(0, len(self.cTbl)):
                if self.cTbl[i].value == value:
                    return (self.cTbl[i].color.rgb(), unicode(self.cTbl[i].label))
            # will drop through here if not found
            raise MolusceError('Value %s not found in color table' % (value))
        except MolusceError, msg:
            # simply return null result
            return (0, '')
        except Exception:
            # general error handler
            errMsg()
            return (0, '')

    def getColorMap(self):
        """
        Returns the color map as <ColorRampItemList> object.  Intended to allow
        color map to be transferred to other layers
        """
        return self.cTbl

    def setColorMap(self, cTbl):
        """
        Sets the color map from a <ColorRampItemList> object.  Used with
        colorPipe.getColorMap() to transfer a color map from one layer to another.
        """
        self.cTbl = cTbl
        self.shf.setColorRampItemList(self.cTbl)
        return

    def refresh(self):
        """
        Refreshes the raster layer's symbology after updates.  Note that updates
        written by __setitem__ don't appear immediately until the refresh method
        is done.  Usage:
            cpipe.refresh()
        """
        try:
            Qgif.legendInterface().refreshLayerSymbology(self.layer)
        except Exception:
            # general error handler
            errMsg()

    def debug(self):
        # prints information about the colour table onto the message log
        try:
            lnm = self.layer.name()
            logTab.append(tr(u'Colour table for layer: <u>%s</u>') % (lnm))
            L = len(self.cTbl)
            if L>0:
                logTab.append(tr(u'Entry\tValue\tRGB\tLegend'))
                for i in range(0,L):
                    v = self.cTbl[i].value
                    c = self.cTbl[i].color.rgb()
                    t = self.cTbl[i].label
                    h = rgb2hex(int2rgb(c))
                    logTab.append(u'%s\t%s\t%s\t%s' % (i,v,h,t))
            else:
                logTab.append(tr(u'Color table is empty'))
        except Exception:
            errMsg()                # general error handler


class progressMeter:
    """
    Opens a window a window with a progress bar that is updated during long
    processes.  Closing the window will cancel the process.
    """
    def __init__(self, title, maxval):
        #opens progress bar as non-modal widget.  Sets title and maximum value
        global wPB
        wPB = moWidget()
        wPB.setWindowTitle(title)
        wPB.resize(QSize(400, 50))
        layout=QHBoxLayout()
        self.pb=QProgressBar()
        layout.addWidget(self.pb)
        self.pb.setRange(0, maxval)
        self.pb.setValue(0)
        wPB.setLayout(layout)
        wPB.show()

    def update(self, value):
        #updates the progress bar, returns true if not cancelled
        self.pb.setValue(value)

    def close(self):
        #closes the progress bar window
        global wPB
        if wPB is not None:
            wPB.close()
            wPB = None

class moWidget(QWidget):
    # This extends QWidget so that the events can be intercepted and processed

    def __init__(self, parent=None):
        super(moWidget, self).__init__(parent)
        self.closed = False

    def closeEvent(self, event):
        #QMessageBox.warning(self, "FMT Message", "Window close event")
        logTab.append("'%s' closed" % (self.windowTitle()))
        self.closed = True
        pass

    def isClosed(self):
        # allows 'closed' status to be queried
        return self.closed

class moTableWidget(QTableWidget):
    # This extends QTableWidget so that a double click copies the table to the
    # Windows clipboard.

    def __init__(self, parent=None):
        super(moTableWidget, self).__init__(parent)

    def mouseDoubleClickEvent(self, e):
        self.copyToClipboard()

    def copyToClipboard(self):
        #copies the whole table to the clipbaord.  Also returns copied text
        # loop through transposed table t appending cell data row by row
        clip = "\t"
        # add column headings in first row
        n = self.columnCount()
        for c in xrange(0, n):
            clip += self.horizontalHeaderItem(c).text() + "\t"
        # work through rows in tables
        m = self.rowCount()
        for r in xrange(0, m):
            clip += "\n"+ self.verticalHeaderItem(r).text() + "\t"
            # add data from both tables for current row
            for c in xrange(0, n):
                if self.item(r,c) is not None:
                    clip += self.item(r,c).text() + "\t"
                else:
                    clip +="\t"
        clip += "\n"
        # send text to System clipboard
        clbd = QApplication.clipboard()
        clbd.setText(clip)
        logTab.append(tr(u'Table copied to clipboard:\n%s') % (clip))
        QMessageBox.information(QWidget(), 'Molusce', tr("Table copied to clipboard"))

class Graph(QWidget):
    """
    Generates a simple QT x-y line graph widget, with axes at left and bottom.
    The graph has a pale blue background grid, 2 axes, and can draw multiple
    lines in different styles and colours.  It can be re-sized and rescaled
    dynamically.  Size is determined by the container in which it is embedded.
    --    g = Graph()
    Creates an instance of the widget.  There are no parameters.  The following
    methods must be called before any data is plotted:
    --    g.setXaxis(xtext, xmin, xmax, xtic)
    xtext is the label for the X axis.  xmin and xmax are the end points of the
    axis, and xtic is the tick mark intervale.
    --    g.setYaxis(ytext, ymin, ymax, ytic)
    similarly, for the y axis.  The X or Y scales can be changed dynamically
    while the chart is displayed.
    --    g.setLine(n, [width, [color, [style]]])
    Initialises line number n.  Width, Color and Style are optional.  Width is
    in pixels, and defaults to 2.  Color uses Qt color constants eg Qt.red, or
    QColor() values, eg QColor("#00FF00").  Default is red.  Styles are
    Qt.PenStyle constants, eg Qt.SolidLine, Qt.DotLine.  Default is solid.
    --    g.addPoint(n, x, y)
    Adds a point to line n, with coordinates x-y in the current axis space.
    """
    def __init__(self):
        # initialise QWidget
        super(Graph, self).__init__()
        self.xaxis = None
        self.yaxis = None
        self.autoScale = False
        # preset dimensions
        self.axisMarginRatio = 0.15
        self.topMarginRatio = 0.05
        self.lineColor = QColor("#99CCCC")
        self.borderColor = QColor(Qt.darkGray)
        self.textColor = QColor(Qt.black)
        self.lineStyles= {}
        self.lineData = {}

    def setXaxis(self, xtext, xmin, xmax, xtic):
        # sets X axis text and scale
        self.xaxis = (xtext, xmin, xmax, xtic)

    def setYaxis(self, ytext, ymin, ymax, ytic):
        # sets Y axis teyt and scale
        self.yaxis = (ytext, ymin, ymax, ytic)

    def setScaleFactors(self):
        # sets the scale factors - needs to be called whenever widget re-sized
        # X axis scale factors
        xw = self.width()*(1-self.axisMarginRatio-self.topMarginRatio)
        self.xscale = (self.xaxis[2]-self.xaxis[1])/xw
        self.xoffset = self.width()*self.axisMarginRatio
        # Y axis scale factors
        yw = self.height()*(1-self.axisMarginRatio-self.topMarginRatio)
        self.yscale = -(self.yaxis[2]-self.yaxis[1])/yw
        self.yoffset = self.height()*self.topMarginRatio+yw

    def scale(self, x, y):
        # scales (x,y) tuple to pixel coordinates (px, py)
        try:
            px = int(round((x - self.xaxis[1])/self.xscale+self.xoffset))
            py = int(round((y - self.yaxis[1])/self.yscale+self.yoffset))
            return (px, py)
        except Exception:
            debug_values(x=x, y=y)
            errMsg()
            return None

    def setLine(self, n, width=2, color=Qt.red, style=Qt.SolidLine):
        # initialises a new line.  Width, line colour and style can be set
        self.lineStyles[n] = QPen(color, width, style)
        self.lineData[n] = []

    def addPoint(self, n, x, y):
        # adds a point to a line initialised with setLine(n)
        self.checkScale(x, y)
        self.lineData[n].append((x, y))

    def checkScale(self, x,y):
        # sees if current point fits on axes.  If not, adjusts them
        if self.autoScale:
            self.adjustAxis(x, self.xaxis, self.setXaxis)
            self.adjustAxis(y, self.yaxis, self.setYaxis)

    def adjustAxis(self, v, axis, setAxis):
        # checks value v against axis limits, adjusts them if necessary
        # and resets relevant class values via function setAxis
        (vtext, vmin, vmax, vtic) = axis
        # finish this later - not needed for basic testing
        pass

    def paintEvent(self, event):
        # draw/redraw graph when needed
        qp = QPainter()
        qp.begin(self)
        #white background for graph
        qp.setBrush(QColor(Qt.white))
        qp.setPen(self.borderColor)
        w = self.width()
        h = self.height()
        qp.drawRect(0, 0, w, h)
        fnt = QFont('Arial',7)
        qp.setFont(fnt)
        self.setScaleFactors()
        # --- x axis construction ----
        # coordinates of rectangle for axis label
        ax = w*self.axisMarginRatio
        xw = w*(1-self.axisMarginRatio-self.topMarginRatio)
        ay = h*(1-self.axisMarginRatio)
        yw = h*self.axisMarginRatio
        # write axis label
        qp.setPen(self.textColor)
        rct = QRect(ax, ay, xw, yw)
        label = self.xaxis[0]
        qp.drawText(rct, Qt.AlignHCenter+Qt.AlignBottom, label)
        # draw axis line
        qp.setPen(self.lineColor)
        x0 = ax; x1 = ax + xw; y0 = ay; y1 = y0
        qp.drawLine(x0, y0, x1, y1)
        # draw grid lines at tick points
        v = self.xaxis[1]   #tick mark initial value
        y1 = h*self.topMarginRatio
        tw = self.xaxis[3] /self.xscale # tick mark width
        # loop through tick marks
        while v <= self.xaxis[2]:
            # draw grid line at tick mark
            x = ax + (v - self.xaxis[1]) / self.xscale
            qp.setPen(self.lineColor)
            qp.drawLine(x, ay, x, y1)
            # construct rectangle for label
            rct = QRect(x-tw/2, ay+2, tw, yw)
            qp.setPen(self.textColor)
            qp.drawText(rct, Qt.AlignHCenter+Qt.AlignTop, str(v))
            v += self.xaxis[3]
        # --- y axis construction ----
        # tick mark rectangle height and width
        th = self.yaxis[3] /self.yscale
        tw = w*self.axisMarginRatio
        # loop through tick marks
        v = self.yaxis[1]   #tick mark initial value
        while v <= self.yaxis[2]:
            # draw grid line at tick mark
            y = y0 + (v - self.yaxis[1]) / self.yscale
            qp.setPen(self.lineColor)
            qp.drawLine(x0, y, x1, y)
            # construct rectangle for label
            rct = QRect(0, y-th/2, tw-2, th)
            qp.setPen(self.textColor)
            qp.drawText(rct, Qt.AlignVCenter+Qt.AlignRight, str(v))
            v += self.yaxis[3]
        # coordinates for rectangle of axis label in rotated frame of reference
        ax = -h*(1-self.axisMarginRatio)
        xw = h*(1-self.axisMarginRatio-self.topMarginRatio)
        ay = 0
        yw = w*self.axisMarginRatio
        rct = QRect(ax, ay, xw, yw)
        # write vertically rotated axis then restore rotation to normal
        qp.rotate(-90)
        label = self.yaxis[0]
        qp.setPen(self.textColor)
        qp.drawText(rct, Qt.AlignHCenter+Qt.AlignTop, label)
        qp.rotate(90)
        # draw lines on the graph
        for L in self.lineStyles.keys():
            qp.setPen(self.lineStyles[L])
            if len(self.lineData[L])>0:
                u = self.lineData[L][0]
                p0 = self.scale(u[0], u[1])
                for u in self.lineData[L][1:]:
                    p = self.scale(u[0], u[1])
                    # avoid error condition if singularities occur
                    if not (p is None or p0 is None):
                        qp.drawLine(p0[0], p0[1], p[0], p[1])
                    p0 = p


#---------- global utility functions used in module ------------
def tr(text):
    #wrapper for QApplication translator with default context
    btext = text
    return btext

def partial(func, arg):
    # lets function with a single argument to be assigned to an action
    def callme():
        return func(arg)
    return callme

def getMapLayerByName(myName):
    # Return QgsMapLayer from a layer name ( as string )
    layermap = QgsMapLayerRegistry.instance().mapLayers()
    for name, layer in layermap.iteritems():
        if layer.name() == myName:
            if layer.isValid():
                return layer
            else:
                return None

def getDefaultPath():
    # returns the path of the first map on the QGIS legend as a default
    adir = '.'
    try:
        # list of QGIS layers in legend
        layers = QgsMapLayerRegistry.instance().mapLayers()
        # pick the top one, get its key and path name
        L = layers.keys()[0]
        fullpath = layers[L].source()
        # extract directory from full path
        info = QFileInfo(fullpath)
        adir = str(info.absolutePath())
    except AttributeError, msg:
        # likely to occur if nothing in QGIS legend
        logTab.append('getDefaultPath - AttributeError: %s' % (msg))
    return adir

def extract_text(rgx, text):
    # extracts text matching the pattern rgx from 'text'
    # allows for the case where there is no match, returns None
    result = re.search(rgx, text, re.IGNORECASE)
    if result is not None:
        return result.group(1)
    else:
        return None

def setCell(tbw, r, c, fmt, v, align=Qt.AlignRight):
    # Sets a cell at row r, column c in QTableWidget tbw with value v
    # using format v.  Cell background set to white
    qwi = QTableWidgetItem(fmt % v)
    qwi.setBackgroundColor(QColor(0xFFFFFF))
    qwi.setTextAlignment(align)
    qwi.setFlags(Qt.NoItemFlags)
    tbw.setItem(r, c, qwi)
    #--------
    # Note on QGIS/Qt bug:  Assigning the same QTableWidgetItem to different
    # cells does not generate an error but causes QGIS to become unstable.
    # Make sure a new instance of each QTableWidgetItem is created before
    # assigning to a QTableWidget cell. Above routine does this.
    #--------

def fmt000(x):
    # converts an integer x to a string with comma thousands seprators
    fmt =""
    while x>=1000:
        rem = x % 1000
        fmt = "," + str(rem)+fmt
        x = x // 1000
    fmt = str(x) +fmt
    return fmt

def method_selector(self, selectedFunction, m = 0):
    # creates the method selector drop down and sets the default selection to
    # index m.  This occurs in a GUI version for each of the methods listed.
    method_dd = QComboBox()
    method_dd.addItem("Artificial Neural Network (ANN)")
    method_dd.addItem("Monte Carlo - Transition Matrix")
    #method_dd.addItem("Multiple Criteria Evaluation (MCE)")
    #method_dd.addItem("Logistic Regression (LR)")
    method_dd.setCurrentIndex(m)
    #QObject.connect( method_dd, SIGNAL("activated(int)"), selectedFunction)
    return method_dd

def makeBinArray(a, L):
    # converts integer a into np array in binary form [0 1 0 1 1] etc
    b = np.zeros(L)
    k=0
    n=1
    for k in xrange(0, L):
        if a & n:
            b[k] = 1
        n *= 2
    return b

def evalBinArray(b):
    # converts np array in binary form [0 1 0 1 1] into an integer
    # real values below 0.5 are treated as zero, those above as 1
    a = 0
    n = 1
    c= b.flatten()
    for k in xrange(0,len(c)):
        if c[k]>0.5:
            a += n
        n = n * 2
    return a

def fixBinArray(b):
    # converts np array in of values in range 0-1 into a binary
    # array by rounding values down or up at 0.5
    c= b.flatten()
    for k in xrange(0,len(c)):
        c[k] = 1 if c[k]>0.5 else 0
    return c

def csv2int(p, f=int):
    # converts a string of comma separated values p to a list of integers
    s = p.split(",")
    d = list()
    for k in range(0,len(s)):
        d.append(f(s[k]))
    return d

def rgb2hex(rgb):
    # converts rgb tuple to a hex string for a colour in range 000000 to FFFFFF
    (r, g, b) = rgb
    r = int(r)
    g = int(g)
    b = int(b)
    v = int(b + 256*g+ 65536*r)
    # I struggled with this code for a long time.  There is a nasty bug in PyQt
    # which shadows the simple hex() function so that it doesn't work -
    # but found with lot of T&E the more primitive version below still works ok
    try:
        h = v.__hex__()     #convert to hex avoiding PyQt bug with hex()
        h = h[2:].upper()   #strip 0x from left
        h = "000000" + h    #pad with 6 zeroes
        h = h[-6:]          #take 6 rightmost characters
        return h
    except Exception:
        errMsg()                # general error handler
        return ""

def hex2rgb(rgb):
    # converts rgb as a hex string AABBCC to tuple of ints (r,g,b)
    r = int(rgb[0:2], 16)
    g = int(rgb[2:4], 16)
    b = int(rgb[4:6], 16)
    return (r,g,b)

def int2rgb(iv):
    # converts an int value to rgb tuple.
    r = (iv & 0xFF0000) >> 16
    g = (iv & 0xFF00) >> 8
    b = iv & 0xFF
    return (r, g, b)

def avgZoneRings(aMap, ix, iy, nz):
    # calculates average of pixel values in rings around a central point (ix, iy)
    # on map array aMap.  Pixels with ndv value are ignored.  Rings extend out
    # nz pixels. nz=0 is trivial case of the (ix,iy) pixel itself.
    # returns numpy float vector of length nz+1 with averages for each ring.
    zavg = np.zeros((nz+1), dtype=float)    # result - vector of zone averages
    zavg[0] = aMap[iy, ix]                  # result for the central pixel only
    if nz>0:
        # cases with one or more zones around central pixel
        zwt = np.zeros((nz+1), dtype=float)     # valid pixels in each zone
        ztot = np.zeros((nz+1), dtype=float)    # totals for each zone
        zwt[0]=1 ; ztot[0] = zavg[0]            # initialise for central pixel
        (ysz, xsz) = aMap.shape                 # upper bounds of map array
        for jz in xrange(1, nz+1):
            # get slice limits for neighborhood offset
            jx = ix-jz if jz<= ix else 0
            kx = ix+jz+1 if ix+jz+1<xsz else xsz
            jy = iy-jz if jz<= iy else 0
            ky = iy+jz+1 if iy+jz+1<ysz else ysz
            # total and counts (weighting) within whole zone
            zone = aMap[jy:ky, jx:kx]
            ztot[jz] = npm.sum(zone)
            zwt[jz] = npm.count(zone)
        # calculate zone averages from differences in successive totals
        for jz in xrange(1, nz+1):
            if zwt[jz]>zwt[jz-1]:
                zavg[jz] = (ztot[jz]-ztot[jz-1])/(zwt[jz]-zwt[jz-1])
            else:
                zavg[jz] = 0.0
        #debug_values(4036, ix=ix, iy=iy, nz=nz, ztot=ztot, zwt=zwt, zavg=zavg)
    return zavg

def kappa(yo , yp):
    # calculates Kappa statistic (K) and % map agreement (pma) for a 0-1 x 0-1 array.
    # paramters yo, yp are np arrays of zero-one risk values.  In the confusion matrix
    # (cm) rows are counts of predicted values and columns are counts of actual (observed)
    # values. Method from Gao (2009) Remotely Sensed Imagery, McGraw-Hill, 645 pp,
    # pages 516-521.
    cm = np.zeros((2,2), dtype=float)
    z1 = set([0,1])
    for i in xrange(0, len(yo)):
        r = int(yp[i])
        c = int(yo[i])
        # check values in set 0 or 1
        if r*c not in z1:
            raise MolusceError(tr(u'Kappa data not 0-1 at %d: obs= %s, exp= %s') %
                (i, yo[i], yp[i]))
        cm[r,c] += 1.0
    n = np.sum(cm)
    rs = np.sum(cm, axis=0)                 # row sum
    cs = np.sum(cm, axis=1)                 # column sum
    xrc = np.outer(rs, cs)                  # products of row and column sums
    ev = np.sum(np.diag(xrc))/np.sum(xrc)   # expected value
    ov = np.sum(np.diag(cm))/n              # observed value
    K = (ov - ev)/(1.0-ev)                  # kappa
    pma = np.sum(np.diag(cm))/n             # map agreement ratio
    return (K, pma)

# used to trap only errors defined in the program
class MolusceError(Exception): pass

def errMsg():
    # outputs details of last error to message log
    (err, msg, tb) = sys.exc_info()
    # extract error type from string
    errText = re.search(r"^.+\.([a-zA-Z]+)'.+$", str(err)).group(1)
    # get traceback list
    tlist = traceback.extract_tb(tb)
    # output error message and line where it occurred
    logTab.append("%s: <i>%s</i>" % (errText, msg))
    # output traceback details
    for tl in tlist:
        (line, func) = tl[1:3]
        logTab.append("@line %s in #%s#" % (line, func))
    # process pending events to allow GUI update
    QApplication.processEvents()
    QMessageBox.warning(QWidget(), "Molusce",
        "%s: %s\n(See messages tab for more details)" % (errText, msg))

def debug_values(lno, **args):
    # outputs any arbitrary list of arguments, given as nx=x, ny=y,...
    # where nx is the variable name as it will be output and y is the
    # variable,  to the message logger. lno should be the line number of the call
    logTab.append("---- debug output ref# %s ----" % (lno))
    params = args.keys()
    # output in alphabetic order (otherwise Python uses arbitrary order)
    params.sort()
    for k in params:
        v = args[k]
        # get the type name without its text wrapper
        t =     errText = re.search(r"^.+\'(.+)\'.+$", str(type(v))).group(1)
        # output type, variable name, and value
        logTab.append("%s (%s) = %s" % (k, t, v))


#--------- initialisation of globals -----------

wPB = None
Qgif = None