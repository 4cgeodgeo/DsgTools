# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DsgTools
                                 A QGIS plugin
 Brazilian Army Cartographic Production Tools
                              -------------------
        begin                : 2018-08-28
        git sha              : $Format:%H$
        copyright            : (C) 2018 by Philipe Borba - Cartographic Engineer @ Brazilian Army
        email                : borba.philipe@eb.mil.br
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
from DsgTools.core.GeometricTools.layerHandler import LayerHandler
from .validationAlgorithm import ValidationAlgorithm
from ...algRunner import AlgRunner
import processing
from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsProcessing,
                       QgsFeatureSink,
                       QgsProcessingAlgorithm,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink,
                       QgsFeature,
                       QgsDataSourceUri,
                       QgsProcessingOutputVectorLayer,
                       QgsProcessingParameterVectorLayer,
                       QgsWkbTypes,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterEnum,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterMultipleLayers,
                       QgsProcessingUtils,
                       QgsSpatialIndex,
                       QgsGeometry,
                       QgsProject)

class CleanGeometriesAlgorithm(ValidationAlgorithm):
    INPUT = 'INPUT'
    SELECTED = 'SELECTED'
    TOLERANCE = 'TOLERANCE'
    MINAREA = 'MINAREA'
    FLAGS = 'FLAGS'
    

    def initAlgorithm(self, config):
        """
        Parameter setting.
        """
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT,
                self.tr('Input Layer'),
                [QgsProcessing.TypeVectorAnyGeometry]
            )
        )
        self.addParameter(
            QgsProcessingParameterBoolean(
                self.SELECTED,
                self.tr('Process only selected features')
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.TOLERANCE,
                self.tr('Snap radius'),
                minValue=0,
                defaultValue=1,
                type=QgsProcessingParameterNumber.Double
            )
        )
        self.addParameter(
            QgsProcessingParameterNumber(
                self.MINAREA,
                self.tr('Minimum area'),
                minValue=0,
                defaultValue=0.0001,
                type=QgsProcessingParameterNumber.Double
            )
        )
        
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.FLAGS,
                self.tr('{0} Flags').format(self.displayName())
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        layerHandler = LayerHandler()
        algRunner = AlgRunner()

        inputLyr = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if inputLyr is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        onlySelected = self.parameterAsBool(parameters, self.SELECTED, context)
        snap = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        minArea = self.parameterAsDouble(parameters, self.MINAREA, context)
        self.prepareFlagSink(parameters, inputLyr, inputLyr.type(), context)

        auxLyr = layerHandler.createAndPopulateUnifiedVectorLayer([inputLyr], geomType=inputLyr.type(), onlySelected = onlySelected, feedback=feedback, progressDelta=30)
        cleanedLyr, error = algRunner.runClean(auxLyr, \
                                                    [algRunner.RMSA, algRunner.Break, algRunner.RmDupl, algRunner.RmDangle], \
                                                    context, \
                                                    returnError=True, \
                                                    snap=snap, \
                                                    minArea=minArea)

        layerHandler.updateOriginalLayersFromUnifiedLayer([inputLyr], cleanedLyr, feedback=feedback, progressDelta=70)
        self.flagCoverageIssues(cleanedLyr, error, feedback)

        return {self.INPUTLAYERS : inputLyrList, self.FLAGS : self.flagSink}

    def flagCoverageIssues(self, cleanedCoverage, error, feedback):
        overlapDict = dict()
        for feat in cleanedCoverage.getFeatures():
            if feedback.isCanceled():
                break
            geom = feat.geometry()
            geomKey = geom.asWkb()
            if geomKey not in overlapDict:
                overlapDict[geomKey] = []
            overlapDict[geomKey].append(feat)
        for geomKey, featList in overlapDict.items():
            if feedback.isCanceled():
                break
            if len(featList) > 1:
                txtList = []
                for i in featList:
                    txtList += ['{0} (id={1})'.format(i['layer'], i['featid'])]
                txt = ', '.join(txtList)
                self.flagFeature(featList[0].geometry(), self.tr('Features from {0} overlap').format(txt))
            elif len(featList) == 1:
                attrList = featList[0].attributes()
                if attrList == len(attrList)*[None]:
                    self.flagFeature(featList[0].geometry(), self.tr('Gap in layer.'))

        if error:
            for feat in error.getFeatures():
                if feedback.isCanceled():
                    break
                self.flagFeature(feat.geometry(), self.tr('Clean error on layer.'))

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'cleangeometries'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Clean Geometries Geometries')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('Validation Tools (Manipulation Processes)')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'DSGTools: Validation Tools (Manipulation Processes)'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return CleanGeometriesAlgorithm()