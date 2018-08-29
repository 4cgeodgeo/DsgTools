# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DsgTools
                                 A QGIS plugin
 Brazilian Army Cartographic Production Tools
                              -------------------
        begin                : 2018-06-08
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

from PyQt5.QtCore import QCoreApplication
from qgis.core import (QgsDataSourceUri, QgsFeature, QgsFeatureSink,
                       QgsProcessing, QgsProcessingAlgorithm,
                       QgsProcessingOutputVectorLayer,
                       QgsProcessingParameterBoolean,
                       QgsProcessingParameterFeatureSink,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterVectorLayer, QgsWkbTypes,
                       QgsProcessingMultiStepFeedback)

from ...algRunner import AlgRunner
from .validationAlgorithm import ValidationAlgorithm


class RemoveSmallLinesAlgorithm(ValidationAlgorithm):
    FLAGS = 'FLAGS'
    INPUT = 'INPUT'
    SELECTED = 'SELECTED'
    TOLERANCE = 'TOLERANCE'

    def initAlgorithm(self, config):
        """
        Parameter setting.
        """
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                self.INPUT,
                self.tr('Input layer'),
                [QgsProcessing.TypeVectorAnyGeometry ]
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
                self.tr('Line length tolerance'),
                type=QgsProcessingParameterNumber.Double,
                minValue=0,
                defaultValue=5
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
        algRunner = AlgRunner()
        inputLyr = self.parameterAsVectorLayer(parameters, self.INPUT, context)
        if inputLyr is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))
        onlySelected = self.parameterAsBool(parameters, self.SELECTED, context)
        tol = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        multiStepFeedback = QgsProcessingMultiStepFeedback(3, feedback)
        multiStepFeedback.setCurrentStep(0)
        multiStepFeedback.pushInfo(self.tr('Identifying small lines in layer {0}...').format(inputLyr.name()))
        flagLyr = algRunner.runIdentifySmallLines(inputLyr, tol, context, feedback = multiStepFeedback, onlySelected=onlySelected)

        multiStepFeedback.setCurrentStep(1)
        multiStepFeedback.pushInfo(self.tr('Removing small lines from layer {0}...').format(inputLyr.name()))
        self.removeFeatures(inputLyr, flagLyr, multiStepFeedback)

        multiStepFeedback.setCurrentStep(2)
        multiStepFeedback.pushInfo(self.tr('Identifying remaining small lines in layer {0}...').format(inputLyr.name()))
        flagLyr = algRunner.runIdentifySmallLines(inputLyr, tol, context, feedback = multiStepFeedback, onlySelected=onlySelected)

        return {self.INPUT: inputLyr, self.FLAGS : flagLyr}
    
    def removeFeatures(self, inputLyr, flagLyr, feedback, progressDelta = 100):
        featureList, total = self.getIteratorAndFeatureCount(flagLyr)
        currentProgress = feedback.progress()
        localTotal = progressDelta/total if total else 0
        inputLyr.startEditing()
        idRemoveList = []
        for current, feat in enumerate(featureList):
            # Stop the algorithm if cancel button has been clicked
            if feedback.isCanceled():
                break
            idRemoveList += [int(feat['reason'].split('=')[-1].split(' ')[0])]
            feedback.setProgress(currentProgress + (current * localTotal))
        inputLyr.deleteFeatures(idRemoveList)
        

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'removesmalllines'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Remove Small Lines')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('Validation Tools (Correction Processes)')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'DSGTools: Validation Tools (Correction Processes)'

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return RemoveSmallLinesAlgorithm()
