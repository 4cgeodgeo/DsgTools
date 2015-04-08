# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DsgTools
                                 A QGIS plugin
 Brazilian Army Cartographic Production Tools
                              -------------------
        begin                : 2015-03-29
        git sha              : $Format:%H$
        copyright            : (C) 2014 by Luiz Andrade - Cartographic Engineer @ Brazilian Army
        email                : luiz.claudio@dsg.eb.mil.br
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import osgeo.gdal
import osgeo.osr
import numpy

# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *

from qgis.core import QgsMessageLog

import os, codecs

from DsgTools.Factories.ThreadFactory.genericThread import GenericThread

class DpiMessages(QObject):
    def __init__(self, thread):
        super(DpiMessages, self).__init__()

        self.thread = thread

    def getProblemMessage(self):
        return self.tr('Problem processing image: ')

    def getProblemFeedbackMessage(self):
        return self.tr('Problem processing images. Check log for details.')

    def getUserCanceledFeedbackMessage(self):
        return self.tr('User canceled image processing!')

    def getSuccessFeedbackMessage(self):
        return self.tr("Successful image processing.")

    @pyqtSlot()
    def progressCanceled(self):
        self.thread.stopped[0] = True

class DpiThread(GenericThread):
    def __init__(self):
        """Constructor.
        """
        super(DpiThread, self).__init__()

        self.messenger = DpiMessages(self)

    def setParameters(self, filesList, rasterType, minOutValue, maxOutValue, outDir, percent, epsg, stopped, bands = []):
        self.filesList = filesList
        self.rasterType = rasterType
        self.minOutValue = minOutValue
        self.maxOutValue = maxOutValue
        self.outDir = outDir
        self.percent = percent
        self.epsg = epsg
        self.stopped = stopped
        self.bands = bands

    def run(self):
        # Actual process
        (ret, msg) = self.processImages(self.filesList)
        self.signals.processingFinished.emit(ret, msg, self.getId())

    def processImages(self, filesList):
        # Progress bar steps calculated
        self.signals.rangeCalculated.emit(len(filesList), self.getId())

        problemOcurred = False
        for file in self.filesList:
            ret = self.stretchImage(file, self.outDir, self.percent, self.epsg, self.bands)
            if ret == 1:
                # Updating progress
                self.signals.stepProcessed.emit(self.getId())
            elif ret == 0:
                problemOcurred = True
            else:
                return (-1, self.messenger.getUserCanceledFeedbackMessage())

        if problemOcurred:
            return (0, self.messenger.getProblemFeedbackMessage())
        else:
            return (1, self.messenger.getSuccessFeedbackMessage())

    def stretchImage(self, inFile, outDir, percent, epsg, bands):
        """Method that applies a specific histogram stretching to a group of images.
            The method also performs a conversion changing the raster type.
        """
        #Getting the output raster type
        (rasterType, minOutValue, maxOutValue) = (self.rasterType, self.minOutValue, self.maxOutValue)

        #Open image
        imgIn = osgeo.gdal.Open(inFile)
        if not imgIn:
            QgsMessageLog.logMessage(self.messenger.getProblemMessage() + inFile, "DSG Tools Plugin", QgsMessageLog.INFO)
            return 0

        #Setting the output file name
        fileName = inFile.split("/")[-1]
        split = fileName.split(".")
        baseName = split[0]
        extension = '.' + split[-1]

        #Defining the output driver
        outDriver = imgIn.GetDriver()
        createOptions = ['PHOTOMETRIC=RGB', 'ALPHA=NO']

        #creating temp file for contrast stretch
        outFileTmp = os.path.join(outDir, baseName+'_tmp'+extension)
        #creating output file for contrast stretch
        outFile = os.path.join(outDir, baseName+'_stretch'+extension)

        #if bands is empty, make a new file with the same band size
        if bands == []:
            bands = range(0, imgIn.RasterCount)

        #Creating a temp image, with the same input parameters, to store the converted input image to 8 bits
        imgOut = outDriver.Create(outFileTmp,imgIn.RasterXSize, imgIn.RasterYSize, len(bands), rasterType, options = createOptions)
        imgOut.SetProjection(imgIn.GetProjection())
        imgOut.SetGeoTransform(imgIn.GetGeoTransform())

        #Linear stretching
        topPercent = 100.-percent/2.
        bottomPercent = percent/2.
        outBandNumber = 1
        for bandNumber in bands:
            if not self.stopped[0]:
                b1 = imgIn.GetRasterBand(bandNumber+1)
                matrix = b1.ReadAsArray()
                arr = numpy.array(matrix)

                minValue, maxValue = numpy.percentile(matrix, [bottomPercent, topPercent])

                #Transformation parameters
                #Rouding the values out of bounds
                numpy.putmask(arr, arr>maxValue,maxValue)
                numpy.putmask(arr, arr<minValue,minValue)

                #The maxOutValue and the minOutValue must be set according to the convertion that will be applied (e.g. 8 bits, 16 bits, 32 bits)
                a = (maxOutValue-minOutValue)/(maxValue-minValue)
                newArr = numpy.floor((arr-minValue)*a+minOutValue)

                outB = imgOut.GetRasterBand(outBandNumber)
                outBandNumber += 1
                outB.WriteArray(newArr)
                outB.FlushCache()

                QgsMessageLog.logMessage(self.tr("Band "+ str(bandNumber)+ ": "+str(minValue)+" , "+str(maxValue)),"DSG Tools Plugin", QgsMessageLog.INFO)
            else:
                QgsMessageLog.logMessage(self.messenger.getUserCanceledFeedbackMessage(), "DSG Tools Plugin", QgsMessageLog.INFO)
                return -1

        #creating final image for reprojection
        outRasterSRS = osgeo.osr.SpatialReference()
        outRasterSRS.ImportFromEPSG(epsg)

        #this code uses virtual raster to compute the parameters of the output image
        vrt = osgeo.gdal.AutoCreateWarpedVRT(imgOut, None, outRasterSRS.ExportToWkt(), osgeo.gdal.GRA_NearestNeighbour,  0.0)
        imgWGS = outDriver.CreateCopy(outFile, vrt, options = createOptions)

        #Checking if the output file was created with success
        if os.path.exists(outFile):
            QgsMessageLog.logMessage(self.tr("File successfully created: ") + outFile, "DSG Tools Plugin", QgsMessageLog.INFO)

        #Deleting the objects
        del imgWGS
        del imgOut
        del imgIn

        #Unlinking the temp file
        os.unlink(outFileTmp)

        return 1