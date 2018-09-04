# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DsgTools
                                 A QGIS plugin
 Brazilian Army Cartographic Production Tools
                              -------------------
        begin                : 2018-05-01
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
from __future__ import absolute_import
from builtins import range
from qgis.core import QgsMessageLog, QgsVectorLayer, QgsGeometry, QgsField, QgsVectorDataProvider, \
                      QgsFeatureRequest, QgsExpression, QgsFeature, QgsSpatialIndex, Qgis, QgsCoordinateTransform, QgsWkbTypes
from qgis.PyQt.Qt import QObject

from .geometryHandler import GeometryHandler
from .attributeHandler import AttributeHandler

class FeatureHandler(QObject):
    def __init__(self, iface = None, parent = None):
        super(FeatureHandler, self).__init__()
        self.parent = parent
        self.iface = iface
        if iface:
            self.canvas = iface.mapCanvas()
        self.geometryHandler = GeometryHandler(iface)
        self.attributeHandler = AttributeHandler(iface)
    
    def reclassifyFeatures(self, featureList, destinationLayer, reclassificationDict, coordinateTransformer, parameterDict):
        newFeatList = []
        deleteList = []
        for feat in featureList:
            geom = self.geometryHandler.reprojectWithCoordinateTransformer(feat.geometry(), coordinateTransformer)
            geomList = self.geometryHandler.adjustGeometry(geom, parameterDict)
            newFeatList += self.createFeaturesWithAttributeDict(geomList, feat, reclassificationDict, destinationLayer)
            deleteList.append(feat.id())
        return newFeatList, deleteList
    
    def createFeaturesWithAttributeDict(self, geomList, originalFeat, attributeDict, destinationLayer):
        """
        Creates a newFeatureList using each geom from geomList. attributeDict is used to set attributes
        """
        newFeatureList = []
        fields = destinationLayer.fields()
        for geom in geomList:
            newFeature = QgsFeature(fields)
            newFeature.setGeometry(geom)
            newFeature = self.attributeHandler.setFeatureAttributes(newFeature, attributeDict, oldFeat = originalFeat)
            newFeatureList.append(newFeature)
        return newFeatureList

    def createUnifiedFeature(self, unifiedLyr, feature, classname, bList = [], attributeTupple = False, coordinateTransformer = None, parameterDict = {}):
        newFeats = []
        for geom in self.geometryHandler.handleGeometry(feature.geometry(), parameterDict=parameterDict, coordinateTransformer=coordinateTransformer):
            newfeat = QgsFeature(unifiedLyr.fields())
            newfeat.setGeometry(feature.geometry())
            newfeat['featid'] = feature.id()
            newfeat['layer'] = classname
            if attributeTupple:
                newfeat['tupple'] = self.attributeHandler.getTuppleAttribute(feature, unifiedLyr, bList=bList)
            newFeats.append(newfeat)
        return newFeats
    
    def getNewFeatureWithoutGeom(self, referenceFeature, lyr):
        newFeat = QgsFeature(referenceFeature)
        provider = lyr.dataProvider()
        for idx in lyr.primaryKeyAttributes():
            newFeat.setAttribute(idx, None)
        return newFeat
    
    def handleFeature(self, featList, featureWithoutGeom, lyr, parameterDict = {}, coordinateTransformer = None):
        geomList = []
        for feat in featList:
            geomList += self.geometryHandler.handleGeometry(feat.geometry(), parameterDict)
        geomToUpdate = None
        newFeatList = []
        if not geomList:
            return geomToUpdate, [], True
        for idx, geom in enumerate(geomList):
            if idx == 0:
                geomToUpdate = geom
                continue
            else:
                newFeat = self.getNewFeatureWithoutGeom(featureWithoutGeom, lyr)
                newFeat.setGeometry(geom)
                newFeatList.append(newFeat)
        return geomToUpdate, newFeatList, False
    
    def getFeatureOuterShellAndHoles(self, feat, isMulti):
        geom = feat.geometry()
        
        outershells, donutholes = self.geometryHandler.getOuterShellAndHoles(geom, isMulti)
        outershellList = []
        for shell in outershells:
            outerShellFeat = QgsFeature(feat)
            outerShellFeat.setGeometry(shell)
            outershellList.append(outerShellFeat)

        donutHoleList = []
        for hole in donutholes:
            newFeat = QgsFeature(feat)
            newFeat.setGeometry(hole)
            donutHoleList.append(newFeat)
        return outershellList, donutHoleList
    
    def mergeLineFeatures(self, featList, lyr, idsToRemove, parameterDict = {}, feedback = None):
        for feat_a in featList:
            if feedback:
                if feedback.isCanceled():
                    break
            if feat_a.id() in idsToRemove:
                continue
            for feat_b in featList:
                if feedback:
                    if feedback.isCanceled():
                        break
                if feat_a.id() == feat_b.id():
                    continue
                if feat_b.id() in idsToRemove:
                    continue
                geom = feat_a.geometry()
                if geom.touches(feat_b.geometry()):
                    newGeom = geom.combine(feat_b.geometry())
                    newGeom = newGeom.mergeLines()
                    newGeom = self.geometryHandler.handleGeometry(newGeom, parameterDict)[0] #only one candidate is possible because features are touching
                    feat_a.setGeometry(newGeom)
                    idsToRemove.append(feat_b.id())
                    lyr.updateFeature(feat_a)    
    