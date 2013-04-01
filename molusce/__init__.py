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

def name():
  return "MOLUSCE"

def description():
  return "Modules for Land Use Change Simulations"

def category():
  return "Raster"

def version():
  return "0.0.1"

def qgisMinimumVersion():
  return "1.9.0"

def author():
  return "NextGIS"

def email():
  return "info@nextgis.org"

def icon():
  return "icons/molusce.png"

def classFactory(iface):
  from molusce import MoluscePlugin
  return MoluscePlugin(iface)
