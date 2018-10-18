# -*- coding: utf-8 -*-
"""
/***************************************************************************
 DsgTools
                                 A QGIS plugin
 Brazilian Army Cartographic Production Tools
                             -------------------
        begin                : 2018-09-05
        git sha              : $Format:%H$
        copyright            : (C) 2018 by João P. Esperidião - Cartographic Engineer @ Brazilian Army
        email                : esperidiao.joao@eb.mil.br
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

from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal, pyqtSlot
from qgis.gui import QgsFieldExpressionWidget
from qgis.utils import iface
from qgis.core import QgsProject

from DsgTools.gui.CustomWidgets.BasicInterfaceWidgets.genericDialogLayout import GenericDialogLayout
from DsgTools.gui.CustomWidgets.DatabaseConversionWidgets.datasourceSelectionWidgetFactory import DatasourceSelectionWidgetFactory

import os

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'datasourceContainerWidget.ui'))

class DatasourceContainerWidget(QtWidgets.QWidget, FORM_CLASS):
    """
    Widget resposinble for adequating GUI to chosen data driver.
    """
    # signal to be emitted when deletion button is clicked - emits itself (QWidget)
    removeWidget = pyqtSignal(QtWidgets.QWidget)
    # signal emitted to advise about filtering options change
    filterSettingsChanged = pyqtSignal(QtWidgets.QWidget)


    def __init__(self, source, inputContainer, parent=None):
        """
        Class constructor.
        :param parent: (QWidget) widget parent to newly instantiated DataSourceManagementWidget object.
        :param source: (str) driver codename to have its widget produced.
        :param inputContainer: (bool) indicates whether the chosen database is supposed to be a reading/input widget or writting/output one.
        """
        super(DatasourceContainerWidget, self).__init__()
        self.setupUi(self)
        self.source = source
        self.addDatasourceSelectionWidget()
        if not inputContainer:
            # output widget should not have filtering options
            self.filterPushButton.hide()
        # set filtering config
        self.filterDlg = None
        self.filters = {
            'layer' : dict(),
            'layer_filter' : dict(),
            'spatial_filter' : dict()
            }
        self.filterPushButton.setToolTip(self.tr('Click to set datasource filter options'))
        self.removePushButton.setToolTip(self.tr('Remove this datasource widget'))
        self.layersComboBox = None
        self.filterExpressionWidget = None
        self.topologicalTestWidget = None
        self.topologicalRelationWidget = None

    def setGroupWidgetName(self, name=None):
        """
        Sets the name to the group added.
        :param name: (str) name for the group.
        """
        self.groupBox.setTitle('{0}'.format(name))

    def addDatasourceSelectionWidget(self):
        """
        Adds the widget according to selected datasource on datasource combobox on first page.
        :param source: (str) driver name.
        """
        # in case a valid driver is selected, add its widget to the interface
        self.connectionWidget = DatasourceSelectionWidgetFactory.getSelectionWidget(source=self.source)
        self.driverLayout.addWidget(self.connectionWidget.selectionWidget)

    def getDatasourceConnectionName(self):
        """
        Gets the datasource connection name.
        :return: (str) datasource connection name.
        """
        # temporarily, it'll be set to current db name
        return self.connectionWidget.getDatasourceConnectionName()

    def getDatasource(self):
        """
        Gets the datasource selected on current widget.
        :return: (object) the object representing the target datasource according to its driver. 
        """
        return self.connectionWidget.abstractDb if self.connectionWidget else None

    def setDatasource(self, connectionInfo):
        """
        Sets datasource to selection widget.
        :param connectionInfo: (object) varies according to driver.
        """
        if self.connectionWidget:
            self.connectionWidget.setDatasource(connectionInfo)

    @pyqtSlot(bool)
    def on_removePushButton_clicked(self):
        """
        Emits widget removal signal when remove button is clicked.
        """
        # finally, emits removal signal
        self.removeWidget.emit(self)

    def clearWidget(self, widget):
        """
        Clear a widget before in order to reassign it.
        :param widget: widget to be cleared.
        """
        try:
            widget.blockSignals(True)
            # widget.setParent(None)
            widget = None
        except:
            # in case the python wrapper for a QgsFilterExpressionWidget is deleted before the object
            widget = None

    def getClipRelationParameterWidget(self):
        """
        Gets the widget for a Cut spatial filter.
        :return: (QWidget) the topological relation parameter widget.        
        """
        # widget will ask for a cut mode
        w = QtWidgets.QComboBox()
        w.addItems([self.tr('Choose a region...'), self.tr('Inside Features'), self.tr('Outside Features')])
        return w
        
    def getBufferRelationParameterWidget(self):
        """
        Gets the widget for a Cut spatial filter.
        :return: (QWidget) the topological relation parameter widget.        
        """
        # widget will ask for a double (buffer distance)
        w = QtWidgets.QDoubleSpinBox()
        # colocar regras de preenchimento! > 0...
        return w

    @pyqtSlot(int)
    def setTopologicalParameter(self, idx):
        """
        Sets the widget for capturing the topological relationship comparison parameter.
        :param idx: current topological operation index.
        """
        if self.topologicalRelationWidget:
            try:
                self.filterDlg.outHLayout.removeWidget(self.topologicalRelationWidget)
                self.topologicalRelationWidget.setParent(None)
            except:
                pass
                # problems with a qgis python wrappers for its widgets... 
            self.clearWidget(widget=self.topologicalRelationWidget)
        widgetDict = {
            self.tr('Clip') : lambda : self.getClipRelationParameterWidget(), 
            self.tr('Buffer') : lambda : self.getBufferRelationParameterWidget(), 
            self.tr('Intersects') : lambda : None, # no widget is necessary
            self.tr('Equals (Geometry)') : lambda : None # no widget is necessary
        }
        try:
            if isinstance(idx, int):
                self.topologicalRelationWidget = widgetDict[self.topologicalTestWidget.currentText()]()
            else:
                self.topologicalRelationWidget = widgetDict[idx]()
            if self.topologicalRelationWidget:
                self.filterDlg.outHLayout.addWidget(self.topologicalRelationWidget)
        except:
            return

    @pyqtSlot(int)
    def spatialFilterLayerChanged(self, idx):
        """
        Sets up interface according to a spatial filtering layer selection.
        """
        currentLayer = self.layersComboBox.currentText()
        if currentLayer == self.tr('Select a layer...'):
            return
        vLayer = QgsProject.instance().mapLayersByName(currentLayer)
        if vLayer:
            self.filterExpressionWidget.setLayer(vLayer[0])

    def setupSpatialFilterWidgets(self):
        """
        Sets up widgets into filter dialog.
        """
        # prepare layer selection combo box
        if self.layersComboBox:
            # self.filterDlg.outHLayout.removeWidget(self.layersComboBox)
            # clear layer selection combo box, if it exists 
            self.clearWidget(widget=self.layersComboBox)
        try:
            self.layersComboBox = QtWidgets.QComboBox()
        except:
            # no idea why, but the C++ object gets deleted only after you try using it...
            self.layersComboBox = QtWidgets.QComboBox()
        layerList = [self.tr('Select a layer...')] + sorted([l.name() for l in iface.mapCanvas().layers()])
        self.layersComboBox.addItems(layerList)
        # prepare layer feature filter widget
        if self.filterExpressionWidget:
            # self.filterDlg.outHLayout.removeWidget(self.filterExpressionWidget)
            # clear layer selection combo box, if it exists 
            self.clearWidget(widget=self.filterExpressionWidget)
        self.filterExpressionWidget = QgsFieldExpressionWidget()
        # prepare layer selection combo box
        if self.topologicalTestWidget:
            # self.filterDlg.outHLayout.removeWidget(self.topologicalTestWidget)
            # clear layer selection combo box, if it exists 
            self.clearWidget(widget=self.topologicalTestWidget)
        try:
            self.topologicalTestWidget = QtWidgets.QComboBox()
        except:
            # no idea why, but the C++ object gets deleted only after you try using it...
            self.topologicalTestWidget = QtWidgets.QComboBox()
        # current supported topological relations
        topoRelList = sorted([self.tr('Clip'), self.tr('Buffer'), self.tr('Intersects'), self.tr('Equals (Geometry)')])
        self.topologicalTestWidget.addItems(topoRelList)
        # topological parameter is adjusted accordingly chosen topological relation
        self.topologicalTestWidget.currentIndexChanged.connect(self.setTopologicalParameter)
        # first execution does not activate signal, so use it manually
        self.layersComboBox.currentIndexChanged.connect(self.spatialFilterLayerChanged)
        if self.filterDlg:
            self.filterDlg.outHLayout.addWidget(self.layersComboBox)
            self.filterDlg.outHLayout.addWidget(self.filterExpressionWidget)
            self.filterDlg.outHLayout.addWidget(self.topologicalTestWidget)
            self.setTopologicalParameter(topoRelList[0])

    def fillSpatialFilterInformation(self):
        """
        Fills the filter information set to its GUI.
        """
        if self.filters['spatial_filter']:
            # get index for combo box item that has the layer
            self.layersComboBox.setCurrentText(self.filters['spatial_filter']['layer_name'])
            self.filterExpressionWidget.setExpression(self.filters['spatial_filter']['layer_filter'])
            # get index for combo box item that has the topological test
            self.topologicalTestWidget.setCurrentText(self.filters['spatial_filter']['filter_type'])
            if isinstance(self.topologicalRelationWidget, QtWidgets.QDoubleSpinBox):
                try:
                    self.topologicalRelationWidget.setValue(float(self.filters['spatial_filter']['topological_relation']))
                except:
                    self.topologicalRelationWidget.setValue(0.)
            if isinstance(self.topologicalRelationWidget, QtWidgets.QComboBox):
                # get index for combo box item that has the topological relationship
                # idx = self.topologicalRelationWidget.findText()
                self.topologicalRelationWidget.setCurrentText(self.filters['spatial_filter']['topological_relation'])

    @pyqtSlot(bool)
    def on_filterPushButton_clicked(self):
        """
        Opens filter dialog. Filters are updated as Ok push button on this dialog is clicked. If cancel is pressed,
        no update to filters contents will be made. This dialog is repopulated as filter push button from container
        is pressed. 
        """
        if self.filterDlg:
                # if dialog is already created, old signals must be blocked
                self.filterDlg.blockSignals(True)
                # and clear it
                self.filterDlg = None
        if self.connectionWidget:
            if not self.connectionWidget.getDatasourcePath():
                # in case a connection path is not found, a connection was not made ('generic text' is selected)
                return
            # instantiate a new filter dialog
            filterDlg = GenericDialogLayout()
            # set dialog title to current datasource path
            title = '{0}: {1}'.format(self.groupBox.title(), self.connectionWidget.getDatasourcePath())
            filterDlg.setWindowTitle(title)
            # get layers dict
            layers = self.connectionWidget.getLayersDict()
            # get layouts for checkboxes and filter expression widgets
            checkBoxLayout, filterExpressionLayout = QtWidgets.QVBoxLayout(), QtWidgets.QVBoxLayout()
            filterDlg.hLayout.addLayout(checkBoxLayout)
            filterDlg.hLayout.addLayout(filterExpressionLayout)
            # control dict for each new checkbox added
            widgets = dict()
            for layerName, featCount in layers.items():
                if layerName:
                    widgets[layerName] = dict()
                    widgets[layerName]['checkBox'], widgets[layerName]['fieldExpression'] = QtWidgets.QCheckBox(), QgsFieldExpressionWidget()
                    # set current check box status based on previous filters, if any
                    previousFilters = not self.filters['layer'] or layerName in self.filters['layer']
                    widgets[layerName]['checkBox'].setChecked(previousFilters)
                    # allow filtering option only when layer is marked to be filtered
                    widgets[layerName]['checkBox'].toggled.connect(widgets[layerName]['fieldExpression'].setEnabled)
                    # add a new checkbox widget to layout for each layer found and a field expression widget
                    # widgets[layerName]['checkBox'] = QtWidgets.QCheckBox()
                    # widgets[layerName]['fieldExpression'] = QgsFieldExpressionWidget()
                    msg = self.tr('{0} ({1} features)') if featCount > 1 else self.tr('{0} ({1} feature)')
                    widgets[layerName]['checkBox'].setText(msg.format(layerName, featCount))
                    if previousFilters:
                        # if layer is among the filtered ones, or if there are no previous filters, set it checked.__init__(self, *args, **kwargs):
                        widgets[layerName]['checkBox'].setChecked(True)
                        # in case no filters are added or if layer is among the filtered ones, set it checked
                    if layerName in self.filters['layer_filter']:
                        # if a layer feature filter was set, refill it back to UI
                        widgets[layerName]['fieldExpression'].setExpression(self.filters['layer_filter'][layerName])
                    # # set layer to filter expression
                    # widgets[layerName]['fieldExpression'].setLayer(self.getDatasource().getLayerByName(layerName))
                    checkBoxLayout.addWidget(widgets[layerName]['checkBox'])
                    filterExpressionLayout.addWidget(widgets[layerName]['fieldExpression'])
            self.filterDlg = filterDlg
            # setup spatial filter part
            self.setupSpatialFilterWidgets()
            self.fillSpatialFilterInformation()
            # connect cancel push button to close method
            if not self.filters:
                # if no filters dict was set, set it to initial state
                self.resetLayerFilters()
            closeAlias = lambda : self.filterDlg.close()
            self.filterDlg.cancelPushButton.clicked.connect(closeAlias)
            # connect Ok push button from Filter Dialog to filter dict update method
            self.filterDlg.okPushButton.clicked.connect(self.resetLayerFilters)
            # for last, open dialog            
            self.filterDlg.exec_()

    def getSpatialFilterInformation(self):
        """
        Retrieves spatial filter information from GUI.
        :return: (tuple) spatial filter information (reference layer, feature filter for that layer,
                 topology comparison ,topology relation).
        """
        layer, spatialExpression, topologicalTest, topologyParameter = '', '', '', ''
        if self.layersComboBox and self.layersComboBox.currentText() != self.tr('Select a layer...'):
            layer = self.layersComboBox and self.layersComboBox.currentText()
        if self.filterExpressionWidget:
            spatialExpression = self.filterExpressionWidget.currentText()
        if self.topologicalTestWidget:
            topologicalTest = self.topologicalTestWidget.currentText()
        if self.topologicalRelationWidget:
            if isinstance(self.topologicalRelationWidget, QtWidgets.QDoubleSpinBox):
                topologyParameter = self.topologicalRelationWidget.value()
            if isinstance(self.topologicalRelationWidget, QtWidgets.QComboBox):
                topologyParameter = self.topologicalRelationWidget.currentText()
        return layer, spatialExpression, topologicalTest, topologyParameter

    def clearFilters(self):
        """
        Clear filled filters.
        """
        self.filters = {
            'layer' : dict(),
            'layer_filter' : dict(),
            'spatial_filter' : {
                'layer_name' : '',
                'layer_filter' : '',
                'filter_type' : '',
                'topological_relation' : ''
            }
                # spatial filter dictionaty form
                # {
                #     'layer_name' : (str) reference layer_name,
                #     'layer_filter' : (str) expression for filtering the reference layer
                #     'filter_type' : (str) cut, buffer, intersect, etc
                #     'topological_relation' : (str) rule_string - inside, outside, buffer distance, etc
                # }
            }

    def resetLayerFilters(self):
        """
        Prepares filter dialog for current dataset in a given row.
        """
        # reset filters already set
        self.clearFilters()
        # retrieve layouts
        checkBoxLayout = self.filterDlg.hLayout.itemAt(0).layout()
        filterExpressionLayout = self.filterDlg.hLayout.itemAt(1).layout()
        for widgetIdx in range(checkBoxLayout.count()):
            checkBox = checkBoxLayout.itemAt(widgetIdx).widget()
            filterExpression = filterExpressionLayout.itemAt(widgetIdx).widget()
            if checkBox.isChecked():
                # filters will be applicable only if layer is supposed to be converted 
                # label format is: layer_name (feat_count feature's')
                # for some reason the char '&' got into the labels... i honestly don't know how/why
                label = checkBox.text().replace('&', '')
                featCount = label.split(' (')[1].split(' ')[0]
                layerName = label.split(' (')[0]
                # fill layer selection filter info
                self.filters['layer'].update({ layerName : int(featCount) })
                expression = filterExpression.currentText()
                if expression:
                    # fill layer features filter expression info only if an expression is found
                    self.filters['layer_filter'].update({ layerName : expression })
        # fill spatial filter info
        layer, spatialExpression, topologicalTest, topologyParameter = self.getSpatialFilterInformation()
        if layer:
            # a spatial filter is only available if a layer is selected for it
            self.filters['spatial_filter'] = {
                'layer_name' : layer,
                'layer_filter' : spatialExpression,
                'filter_type' : topologicalTest,
                'topological_relation' : topologyParameter
            }
        # advise about filtering settings change
        self.filterSettingsChanged.emit(self)
        self.filterDlg.close()
