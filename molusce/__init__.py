# -*- coding: utf-8 -*-
# Open Source software licensed under the terms of GNU GPL 2
# Entries required for QGIS plugin protocol

from molusce import molusce

def name():
	return "Molusce"

def description():
	return "Modules for Land Use Change Evaluation"

def qgisMinimumVersion():
	return "1.8"

def authorName():
	return "Denis Alder"

def classFactory( iface ):
	return molusce( iface )
