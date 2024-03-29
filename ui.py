import webbrowser

from PySide2.QtCore import Qt, QSize
from PySide2.QtGui import QIcon, QPixmap, QColor
from PySide2.QtWidgets import QMainWindow, QHBoxLayout, QVBoxLayout, QPushButton, QGridLayout, QColorDialog, \
    QComboBox, QLabel, QDoubleSpinBox, QDialog, QCheckBox, QFrame, QApplication, QLineEdit, QFileDialog, QMenuBar,\
    QMenu, QAction
from ctrlShaper.core import setOverrideColors, chunk, replaceCurves, scaleCurves, getCurvesData, importCurves, \
    exportCurves
from maya import OpenMayaUI, cmds
import shiboken2
from functools import partial
import json
import os
from maya.api.OpenMaya import MMatrix


dpiF = QApplication.desktop().logicalDpiX() / 96.0


def killOtherInstances(self):
    for child in self.parent().children():
        if child == self:
            continue
        if child.__class__.__name__ != self.__class__.__name__:
            continue
        child.deleteLater()


def getMayaMainWindow():
    pointer = OpenMayaUI.MQtUtil.mainWindow()
    return shiboken2.wrapInstance(int(pointer), QMainWindow)


def createSeparator():
    separator = QFrame()
    separator.setFrameShape(QFrame.HLine)
    separator.setFrameShadow(QFrame.Sunken)
    return separator


class ColorButton(QPushButton):

    def __init__(self, color):
        super(ColorButton, self).__init__()

        self.color = [c / 255.0 for c in color]
        self.clicked.connect(partial(setOverrideColors, self.color))

        if color:
            pixmap = QPixmap(20 * dpiF, 20 * dpiF)
            pixmap.fill(QColor(*color))

            icon = QIcon()
            icon.addPixmap(pixmap)

            self.setIcon(icon)
        else:
            self.setIcon(QIcon(':error.png'))


class CtrlShaper(QDialog):

    def __init__(self, parent=getMayaMainWindow()):
        super(CtrlShaper, self).__init__(parent=parent)
        killOtherInstances(self)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setWindowTitle('Controller Shaper 1.0')

        # shapes
        shapesDir = os.path.dirname(os.path.abspath(__file__))
        with open('{}/src/shapes.json'.format(shapesDir), 'r') as f:
            shapesData = json.load(f)

        # shape
        self.axeShapeCombo = QComboBox()
        [self.axeShapeCombo.addItem(i) for i in ('x', 'y', 'z')]

        self.shapeCombo = QComboBox()
        [self.shapeCombo.addItem(name, userData=data) for name, data in sorted(shapesData.items())]

        self.shapeScale = QDoubleSpinBox()
        self.shapeScale.setMinimum(0)
        self.shapeScale.setMaximum(1000)
        self.shapeScale.setValue(1)
        self.shapeScale.setSingleStep(.1)

        shapeOptionsLayout = QGridLayout()
        shapeOptionsLayout.addWidget(QLabel('Shape'), 0, 0)
        shapeOptionsLayout.addWidget(self.shapeCombo, 0, 1)
        shapeOptionsLayout.addWidget(QLabel('Normal'), 1, 0)
        shapeOptionsLayout.addWidget(self.axeShapeCombo, 1, 1)
        shapeOptionsLayout.addWidget(QLabel('Scale'), 2, 0)
        shapeOptionsLayout.addWidget(self.shapeScale, 2, 1)

        replaceBtn = QPushButton('Replace')
        replaceBtn.clicked.connect(self.replaceShape)

        shapeLayout = QVBoxLayout()
        shapeLayout.addLayout(shapeOptionsLayout)
        shapeLayout.addWidget(replaceBtn)

        # Create Controller
        createCtrlBtn = QPushButton('Create')
        createCtrlBtn.clicked.connect(self.createControllers)

        self.nameLineEdit = QLineEdit('{n}_C{i}_ctl')
        self.creationMode = QComboBox()
        [self.creationMode.addItem(i) for i in ('normal', 'on selected objects', 'on gizmo')]

        nameLayout = QGridLayout()
        nameLayout.addWidget(QLabel('Name'))
        nameLayout.addWidget(self.nameLineEdit, 0, 1)
        nameLayout.addWidget(QLabel('Mode'), 1, 0)
        nameLayout.addWidget(self.creationMode, 1, 1)
        nameLayout.setColumnStretch(0, 1)
        nameLayout.setColumnStretch(1, 1)

        createControllerLayout = QVBoxLayout()
        createControllerLayout.addLayout(nameLayout)
        createControllerLayout.addWidget(createCtrlBtn)

        # tag
        selectAllBtn = QPushButton('Select All')
        selectAllBtn.clicked.connect(self.selectTaggedControllers)

        setTagBtn = QPushButton('Tag')
        setTagBtn.clicked.connect(self.setTag)

        tagLayout = QGridLayout()
        tagLayout.addWidget(setTagBtn)
        tagLayout.addWidget(selectAllBtn, 0, 1)

        # copy paste
        self.copiedShapeData = None

        self.applyColor = QCheckBox()
        self.applyColor.setChecked(True)

        self.applyShape = QCheckBox()
        self.applyShape.setChecked(True)

        copyBtn = QPushButton('Copy')
        copyBtn.clicked.connect(self.copyShapes)

        self.pasteBtn = QPushButton('Paste')
        self.pasteBtn.setEnabled(False)
        self.pasteBtn.clicked.connect(self.pasteShapes)

        export = QPushButton('Export')
        export.setIcon(QIcon(':fileSave.png'))
        export.clicked.connect(self.exportShapes)

        import_ = QPushButton('Import')
        import_.setIcon(QIcon(':fileOpen.png'))
        import_.clicked.connect(self.importShapes)

        copyPasteLayout = QGridLayout()
        copyPasteLayout.addWidget(QLabel('Apply Color'), 0, 0)
        copyPasteLayout.addWidget(self.applyColor, 0, 1)
        copyPasteLayout.addWidget(QLabel('Apply Shape'), 1, 0)
        copyPasteLayout.addWidget(self.applyShape, 1, 1)
        copyPasteLayout.addWidget(copyBtn, 2, 0)
        copyPasteLayout.addWidget(self.pasteBtn, 2, 1)
        copyPasteLayout.addWidget(export, 3, 0)
        copyPasteLayout.addWidget(import_, 3, 1)

        # search and replace
        self.searchLine = QLineEdit('search')
        self.replaceLine = QLineEdit('replace')
        searchReplaceBtn = QPushButton('Replace')
        searchReplaceBtn.clicked.connect(self.searchReplace)

        searchReplaceLayout = QGridLayout()
        searchReplaceLayout.addWidget(self.searchLine, 0, 0)
        searchReplaceLayout.addWidget(self.replaceLine, 0, 1)
        searchReplaceLayout.addWidget(searchReplaceBtn, 1, 0)

        # color
        colorDialogBtn = QPushButton('Custom')
        colorDialogBtn.setIcon(QIcon(':colorProfile.png'))
        colorDialogBtn.clicked.connect(self.openColorDialog)

        favColorLayout = QGridLayout()
        favColorLayout.addWidget(ColorButton((255, 0, 0)), 0, 0)
        favColorLayout.addWidget(ColorButton((0, 255, 0)), 0, 1)
        favColorLayout.addWidget(ColorButton((0, 0, 255)), 0, 2)
        favColorLayout.addWidget(ColorButton((255, 255, 0)), 0, 3)
        favColorLayout.addWidget(ColorButton((0, 255, 255)), 0, 4)
        favColorLayout.addWidget(ColorButton((255, 0, 255)), 0, 5)

        favColorLayout.addWidget(ColorButton((127, 0, 0)), 1, 0)
        favColorLayout.addWidget(ColorButton((0, 127, 0)), 1, 1)
        favColorLayout.addWidget(ColorButton((0, 0, 127)), 1, 2)
        favColorLayout.addWidget(ColorButton((127, 127, 0)), 1, 3)
        favColorLayout.addWidget(ColorButton((0, 127, 127)), 1, 4)
        favColorLayout.addWidget(ColorButton((127, 0, 127)), 1, 5)

        resetColorBtn = QPushButton('Default')
        resetColorBtn.setIcon(QIcon(':error.png'))
        resetColorBtn.clicked.connect(partial(setOverrideColors, None))

        colorSpecialLayout = QHBoxLayout()
        colorSpecialLayout.addWidget(resetColorBtn)
        colorSpecialLayout.addWidget(colorDialogBtn)

        colorLayout = QVBoxLayout()
        colorLayout.addLayout(favColorLayout)
        colorLayout.addLayout(colorSpecialLayout)

        # transform
        scaleMinusBtn = QPushButton('-')
        scaleMinusBtn.setFixedSize(QSize(16 * dpiF, 16 * dpiF))
        scaleMinusBtn.clicked.connect(partial(self.scaleShape, False))

        scalePlusBtn = QPushButton('+')
        scalePlusBtn.setFixedSize(QSize(16 * dpiF, 16 * dpiF))
        scalePlusBtn.clicked.connect(partial(self.scaleShape, True))

        self.scaleFactor = QDoubleSpinBox()
        self.scaleFactor.setValue(.1)
        self.scaleFactor.setSingleStep(.05)
        self.scaleFactor.setMaximum(.95)

        scaleValueLayout = QHBoxLayout()
        scaleValueLayout.addWidget(scaleMinusBtn)
        scaleValueLayout.addWidget(self.scaleFactor)
        scaleValueLayout.addWidget(scalePlusBtn)

        scaleLayout = QGridLayout()
        scaleLayout.addWidget(QLabel('Scale'), 0, 0)
        scaleLayout.addLayout(scaleValueLayout, 0, 1)

        # mirror
        self.mirrorAxes = QComboBox()
        [self.mirrorAxes.addItem(axes) for axes in ('x', 'y', 'z', '')]

        self.searchFor = QLineEdit('_L')

        self.replaceBy = QLineEdit('_R')

        self.swap = QPushButton()
        self.swap.setMaximumSize(QSize(16 * dpiF, 16 * dpiF))
        self.swap.setIcon(QIcon(':doubleVertArrow.png'))
        self.swap.clicked.connect(self.swapSearchReplace)

        searchForLayout = QHBoxLayout()
        searchForLayout.addWidget(self.searchFor)
        searchForLayout.addWidget(self.swap)

        mirrorReplaceLayout = QGridLayout()
        mirrorReplaceLayout.addWidget(QLabel('Mirror Axes'), 0, 0)
        mirrorReplaceLayout.addWidget(self.mirrorAxes, 0, 1)
        mirrorReplaceLayout.addWidget(QLabel('Search for'), 1, 0)
        mirrorReplaceLayout.addLayout(searchForLayout, 1, 1)
        mirrorReplaceLayout.addWidget(QLabel('Replace by'), 2, 0)
        mirrorReplaceLayout.addWidget(self.replaceBy, 2, 1)
        mirrorReplaceLayout.setColumnStretch(0, 1)
        mirrorReplaceLayout.setColumnStretch(1, 1)

        mirrorBtn = QPushButton('Mirror')
        mirrorBtn.clicked.connect(self.mirrorShapes)

        mirrorLayout = QVBoxLayout()
        mirrorLayout.addLayout(mirrorReplaceLayout)
        mirrorLayout.addWidget(mirrorBtn)

        # menu
        documentationUrl = 'https://github.com/Noboxxx/ctrlShaper'
        docAction = QAction('Documentation', self)
        docAction.setIcon(QIcon(':help.png'))
        docAction.triggered.connect(partial(webbrowser.open, documentationUrl))

        helpMenu = QMenu('Help')
        helpMenu.addAction(docAction)

        menuBar = QMenuBar()
        menuBar.addMenu(helpMenu)

        # main layout
        mainLayout = QVBoxLayout(self)
        mainLayout.setMenuBar(menuBar)
        mainLayout.setAlignment(Qt.AlignTop)

        mainLayout.addWidget(QLabel('<b>Color</b>'))
        mainLayout.addLayout(colorLayout)

        mainLayout.addWidget(createSeparator())
        mainLayout.addWidget(QLabel('<b>Shape</b>'))
        mainLayout.addLayout(shapeLayout)

        mainLayout.addWidget(createSeparator())
        mainLayout.addWidget(QLabel('<b>Controller</b>'))
        mainLayout.addLayout(createControllerLayout)

        mainLayout.addWidget(createSeparator())
        mainLayout.addWidget(QLabel('<b>Tag</b>'))
        mainLayout.addLayout(tagLayout)

        mainLayout.addWidget(createSeparator())
        mainLayout.addWidget(QLabel('<b>Transform</b>'))
        mainLayout.addLayout(scaleLayout)

        mainLayout.addWidget(createSeparator())
        mainLayout.addWidget(QLabel('<b>Copy/Export</b>'))
        mainLayout.addLayout(copyPasteLayout)

        mainLayout.addWidget(createSeparator())
        mainLayout.addWidget(QLabel('<b>Search and Replace</b>'))
        mainLayout.addLayout(searchReplaceLayout)

        mainLayout.addWidget(createSeparator())
        mainLayout.addWidget(QLabel('<b>Mirror</b>'))
        mainLayout.addLayout(mirrorLayout)

    def setTag(self):
        selection = cmds.ls(sl=True, type='transform', long=True)
        if not selection:
            return cmds.warning('Nothing valid selected.')
        cmds.controller(selection)

    def selectTaggedControllers(self):
        ctrls = cmds.controller(q=True, allControllers=True)
        cmds.select(ctrls)

    def getUniqueName(self, pattern, dag=''):
        name = ''
        index = 0
        for n in range(1000):
            name = pattern.format(i=index, n=dag)
            if not cmds.objExists(name):
                break
            index += 1
        return name

    @chunk
    def createController(self, namePattern, shapeData, translation=(0, 0, 0), rotation=(0, 0, 0), dagName='default'):
        name = ''
        index = 0
        for n in range(1000):
            name = namePattern.format(i=index, n=dagName)
            if not cmds.objExists(name):
                break
            index += 1

        if cmds.objExists(name):
            cmds.warning('Unable to create -> {}. It already exists.'.format(name))
            return

        ctl = cmds.group(empty=True, name=name)
        bfr_ = cmds.group(empty=True, name='{}Bfr'.format(name))
        cmds.parent(ctl, bfr_)

        cmds.controller(ctl)

        replaceCurves(ctl, [shapeData], applyColor=False)

        cmds.xform(bfr_, translation=translation, rotation=rotation)

        return ctl, bfr_

    @chunk
    def createControllers(self):
        namePattern = self.nameLineEdit.text()

        data = self.shapeCombo.currentData()
        data['axes'] = self.axeShapeCombo.currentText()
        data['scale'] = self.shapeScale.value()

        mode = self.creationMode.currentIndex()

        if mode == 0:
            ctl, bfr_ = self.createController(namePattern, data)
            cmds.select(bfr_) 

        elif mode == 1:
            buffers = list()
            for dag in cmds.ls(sl=True, long=True, type='transform'):
                shortDagName = dag.split('|')[-1]

                t = cmds.xform(dag, q=True, translation=True, worldSpace=True)
                # t = cmds.xform(dag, q=True, matrix=True, worldSpace=True)[12:15]
                p = cmds.xform(dag, q=True, pivots=True, worldSpace=True)[:4]
                r = cmds.xform(dag, q=True, rotation=True, worldSpace=True)
                # m = cmds.xform(dag, q=True, matrix=True)

                rt = [x + y for x, y in zip(t, p)]

                ctl, bfr_ = self.createController(namePattern, data, translation=t, rotation=r, dagName=shortDagName)
                buffers.append(bfr_)

            cmds.select(buffers) if buffers else None

        elif mode == 2:
            t = cmds.manipMoveContext('Move', q=True, p=True)

            if t:
                ctl, bfr_ = self.createController(namePattern, data, translation=t)
                cmds.select(bfr_)
            else:
                cmds.warning('You should be using the Move Tool to proceed.')

    def openColorDialog(self):
        colorDialog = QColorDialog(self)
        colorDialog.colorSelected.connect(self.colorDialogSetOverrideColors)
        colorDialog.show()

    def colorDialogSetOverrideColors(self, color):
        setOverrideColors([c / 255.0 for c in color.getRgb()])

    @chunk
    def replaceShape(self):
        selection = cmds.ls(sl=True, long=True, type='transform')

        if not selection:
            cmds.warning('Nothing valid is selected.')
            return

        for dag in selection:
            data = self.shapeCombo.currentData()
            data['axes'] = self.axeShapeCombo.currentText()
            data['scale'] = self.shapeScale.value()

            replaceCurves(dag, [data], applyColor=False)

        cmds.select(selection)

    @chunk
    def scaleShape(self, scaleUp=True):
        off = self.scaleFactor.value()
        factor = 1 + off if scaleUp else 1 - off
        scaleCurves(cmds.ls(sl=True, dag=True, long=True), factor)

    def copyShapes(self):
        selection = cmds.ls(sl=True, long=True, type='transform')
        if not selection:
            cmds.warning('Nothing valid is selected.')
            return
        self.copiedShapeData = getCurvesData(selection[-1])
        self.pasteBtn.setEnabled(True)

    @chunk
    def pasteShapes(self):
        selection = cmds.ls(sl=True, long=True, type='transform')

        if not selection:
            cmds.warning('Nothing selected.')
            return

        if not self.copiedShapeData:
            cmds.warning('Nothing to paste.')
            return

        applyColor = self.applyColor.isChecked()
        applyShape = self.applyShape.isChecked()

        if not applyColor and not applyShape:
            cmds.warning('Color and Shape are disabled.')
            return

        [replaceCurves(dag, self.copiedShapeData, applyColor=applyColor, applyShapes=applyShape) for dag in selection]

    @chunk
    def searchReplace(self):
        sourceNodes = cmds.ls(sl=True, type='transform') or cmds.ls(type='transform')

        search = self.searchLine.text()
        replace = self.replaceLine.text()

        applyColor = self.applyColor.isChecked()
        applyShape = self.applyShape.isChecked()

        for sourceNode in sourceNodes:
            if search not in sourceNode:
                continue

            destNode = sourceNode.replace(search, replace)

            if not cmds.objExists(destNode):
                print('{} not found.'.format(destNode))
                continue

            shapeData = getCurvesData(sourceNode)
            replaceCurves(destNode, shapeData, applyColor=applyColor, applyShapes=applyShape)

    @chunk
    def mirrorShapes(self):
        selection = cmds.ls(sl=True, type='transform')
        for dag in selection:
            mirrorName = dag.replace(self.searchFor.text(), self.replaceBy.text())
            if not cmds.objExists(mirrorName) or mirrorName == dag:
                cmds.warning('No mirror object found')
                continue

            data = getCurvesData(dag, objectSpace=False)

            mirrorAxis = self.mirrorAxes.currentText()

            mirrorMatrix = MMatrix(cmds.xform(mirrorName, q=True, matrix=True, worldSpace=True)).inverse()
            for d in data:
                points = list()
                for x, y, z in d['points']:
                    if mirrorAxis == 'x':
                        worldPoint = MMatrix((1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -x, y, z, 1))
                    elif mirrorAxis == 'y':
                        worldPoint = MMatrix((1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, -y, z, 1))
                    elif mirrorAxis == 'z':
                        worldPoint = MMatrix((1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, -z, 1))
                    elif mirrorAxis == '':
                        worldPoint = MMatrix((1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1))
                    else:
                        raise ValueError
                    resultMatrix = worldPoint * mirrorMatrix
                    points.append((list(resultMatrix)[12:15]))
                d['points'] = points

            replaceCurves(mirrorName, data, applyColor=False)
        cmds.select(selection)

    def swapSearchReplace(self):
        searchFor = self.searchFor.text()
        replaceBy = self.replaceBy.text()

        self.searchFor.setText(replaceBy)
        self.replaceBy.setText(searchFor)

    @chunk
    def importShapes(self):
        applyColor = self.applyColor.isChecked()
        applyShape = self.applyShape.isChecked()

        if not applyColor and not applyShape:
            cmds.warning('Color and Shape are disabled.')
            return

        path, _ = QFileDialog.getOpenFileName(self, caption='Import File', filter='Controller Shapes (*.ctrl)')

        if not path:
            cmds.warning('No valid path selected. Skip...')
            return

        selection = cmds.ls(sl=True)
        importCurves(path, selectionFilter=selection, shapes=applyShape, color=applyColor)
        cmds.select(selection)

        print('{} imported.'.format(path))

    def exportShapes(self):
        path, _ = QFileDialog.getSaveFileName(self, caption='Export Shapes', filter='Controller Shapes (*.ctrl)')

        if not path:
            cmds.warning('No valid path selected. Skip...')
            return

        exportCurves(cmds.ls(sl=True), path)

        print('{} saved.'.format(path))
