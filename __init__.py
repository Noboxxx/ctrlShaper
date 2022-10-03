from PySide2.QtCore import Qt, QSize
from PySide2.QtGui import QIcon, QPixmap, QColor
from PySide2.QtWidgets import QMainWindow, QHBoxLayout, QVBoxLayout, QPushButton, QGridLayout, QColorDialog, \
    QComboBox, QLabel, QDoubleSpinBox, QDialog, QMenu, QMenuBar, QAction, QCheckBox, QFrame, qApp, QLineEdit, \
    QFileDialog
from maya import OpenMayaUI, cmds
import shiboken2
from functools import partial
import json
import os

# 1.0
# TODO: Save / import
# TODO: comment code / doc
#

# 2.0
# TODO: manage shape list
# TODO: manage color palette
# TODO: replace shape with auto-scale
# TODO: dockable window
#

from maya.api.OpenMaya import MMatrix

dpiF = qApp.desktop().logicalDpiX() / 96.0


class Chunk(object):

    def __init__(self, name=''):
        self.name = str(name)

    def __enter__(self):
        cmds.undoInfo(openChunk=True, chunkName=self.name)

    def __exit__(self, exc_type, exc_val, exc_tb):
        cmds.undoInfo(closeChunk=True)


def chunk(func):
    def wrapper(*args, **kwargs):
        with Chunk(name=func.__name__):
            return func(*args, **kwargs)

    return wrapper


###


@chunk
def scaleShapes(ctrl, factor):
    for s in cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve', fullPath=True) or list():
        scaledPoints = [[v * factor for v in p] for p in getNurbsCurveData(s)[0]]
        [cmds.xform('{}.cv[{}]'.format(s, i), translation=p) for i, p in enumerate(scaledPoints)]


@chunk
def setOverrideColorOnSelected(color):
    selection = cmds.ls(sl=True, long=True, type='transform')
    [setOverrideColor(dag, color) for dag in selection]

###


def getNurbsCurveData(shape, objectSpace=True):
    spans = cmds.getAttr('{}.spans'.format(shape))
    cvCount = spans if cmds.getAttr('{}.form'.format(shape)) == 2 else cmds.getAttr('{}.degree'.format(shape)) + spans

    degree = cmds.getAttr('{}.degree'.format(shape))
    periodic = cmds.getAttr('{}.form'.format(shape)) == 2
    points = [cmds.xform('{}.cv[{}]'.format(shape, i), q=True, translation=True, objectSpace=objectSpace, worldSpace=not objectSpace) for i in range(cvCount)]

    return points, degree, periodic


@chunk
def createNurbsCurve(parent, points=tuple(), degree=1, periodic=False, color=None, scale=1.0, axes=''):
    points = [[v * scale for v in p] for p in points] if scale != 1 else points

    # normal
    if axes == 'x':
        points = [(y, z, x) for x, y, z in points]
    elif axes == 'y':
        points = [(x, y, z) for x, y, z in points]
    elif axes == 'z':
        points = [(z, x, y) for x, y, z in points]
    elif not axes:
        pass
    else:
        raise ValueError('\'x\', \'y\' or \'z\' excepted as axes. Got {}'.format(repr(axes)))

    # curve
    curve = cmds.curve(point=points, degree=degree)
    cmds.closeCurve(curve, ch=False, preserveShape=False, replaceOriginal=True) if periodic else None
    cmds.parent(cmds.listRelatives(curve, shapes=True), parent, r=True, s=True)
    cmds.delete(curve)
    ctrlShortName = parent.split('|')[-1]
    shapes = cmds.listRelatives(parent, shapes=True, type='nurbsCurve')
    [cmds.rename(s, '{}Shape#'.format(ctrlShortName)) for s in shapes or list()]
    setOverrideColor(parent, color)
    cmds.select(parent)


@chunk
def clearNurbsCurves(ctrl):
    shapes = cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve')
    cmds.delete(shapes) if shapes else None


@chunk
def setShapes(ctrl, data, applyColor=True):
    oldShapes = cmds.listRelatives(ctrl, shapes=True, fullPath=True, type='nurbsCurve')
    oldColor = getOverrideColor(oldShapes[0]) if oldShapes else None

    clearNurbsCurves(ctrl)
    for i, d in enumerate(data):
        if not applyColor:
            d['color'] = oldColor
        createNurbsCurve(ctrl, **d)


def getShapesData(ctrl, objectSpace=True):
    data = list()

    for shape in cmds.listRelatives(ctrl, shapes=True, fullPath=True, type='nurbsCurve'):
        shapeData = dict()
        shapeData['points'], shapeData['degree'], shapeData['periodic'] = getNurbsCurveData(shape, objectSpace=objectSpace)
        shapeData['color'] = getOverrideColor(shape)
        data.append(shapeData)

    return data


def getOverrideColor(dag):
    enabled = cmds.getAttr('{}.overrideEnabled'.format(dag))

    if not enabled:
        return None

    mode = cmds.getAttr('{}.overrideRGBColors'.format(dag))

    if mode == 1:
        return cmds.getAttr('{}.overrideColorRGB'.format(dag))[0]

    return cmds.getAttr('{}.overrideColor'.format(dag))


@chunk
def setOverrideColor(ctrl, color=None):
    if isinstance(color, QColor):
        color = [c/255.0 for c in color.getRgb()]

    if color is None:
        enabled = False
        isRgb = False
        rgbColor = 0, 0, 0
        indexColor = 0
    else:
        enabled = True
        isRgb = not isinstance(color, int)
        rgbColor = color if isRgb else (0, 0, 0)
        indexColor = 0 if isRgb else color

    for shape in cmds.listRelatives(ctrl, shapes=True, fullPath=True, type='nurbsCurve') or list():
        cmds.setAttr('{}.overrideEnabled'.format(shape), enabled)
        cmds.setAttr('{}.overrideRGBColors'.format(shape), isRgb)
        cmds.setAttr('{}.overrideColorRGB'.format(shape), *rgbColor)
        cmds.setAttr('{}.overrideColor'.format(shape), indexColor)


###


def killOtherInstances(self):
    for child in self.parent().children():
        if child == self:
            continue
        if child.__class__.__name__ != self.__class__.__name__:
            continue
        child.deleteLater()


def getMayaMainWindow():
    pointer = OpenMayaUI.MQtUtil.mainWindow()
    return shiboken2.wrapInstance(long(pointer), QMainWindow)


def exportShapes(dags, filePath):
    dags = cmds.ls(dags, type='transform')

    if not dags:
        cmds.warning('Nothing valid selected. Skip...')
        return

    data = {x: getShapesData(x) for x in dags}

    with open(filePath, 'w') as f:
        json.dump(data, f)


@chunk
def importShapes(filePath, selectionFilter=tuple()):
    with open(filePath, 'r') as f:
        data = json.load(f)

    for n, d in data.items():
        if selectionFilter:
            if n not in selectionFilter:
                continue

        if not cmds.objExists(n):
            cmds.warning('Unable to find {}. Skip...'.format(repr(n)))
            continue
        setShapes(n, d)


class ColorButton(QPushButton):

    def __init__(self, color):
        super(ColorButton, self).__init__()

        self.color = [c/255.0 for c in color]
        self.clicked.connect(partial(setOverrideColorOnSelected, self.color))

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
        with open('{}/shapes.json'.format(shapesDir), 'r') as f:
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
        resetColorBtn.clicked.connect(partial(setOverrideColorOnSelected, None))

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

        mirrorBtn = QPushButton('Mirror')
        mirrorBtn.clicked.connect(self.mirrorShapes)

        mirrorLayout = QVBoxLayout()
        mirrorLayout.addLayout(mirrorReplaceLayout)
        mirrorLayout.addWidget(mirrorBtn)

        # menu
        printShapeAct = QAction('Print Shape\'s Points', self)
        printShapeAct.triggered.connect(self.printShapePoints)

        editMenu = QMenu('Edit')
        editMenu.addAction(printShapeAct)

        m = QMenuBar()
        m.addMenu(editMenu)

        # main layout
        mainLayout = QVBoxLayout(self)
        mainLayout.setAlignment(Qt.AlignTop)
        mainLayout.setMenuBar(m)

        mainLayout.addWidget(QLabel('<b>Color Override</b>'))
        mainLayout.addLayout(colorLayout)

        mainLayout.addWidget(self.createSeparator())
        mainLayout.addWidget(QLabel('<b>Replace Shape</b>'))
        mainLayout.addLayout(shapeLayout)

        mainLayout.addWidget(self.createSeparator())
        mainLayout.addWidget(QLabel('<b>Copy/Export Shapes</b>'))
        mainLayout.addLayout(copyPasteLayout)

        mainLayout.addWidget(self.createSeparator())
        mainLayout.addWidget(QLabel('<b>Transform Shape</b>'))
        mainLayout.addLayout(scaleLayout)

        mainLayout.addWidget(self.createSeparator())
        mainLayout.addWidget(QLabel('<b>Mirror Shape</b>'))
        mainLayout.addLayout(mirrorLayout)

    def createSeparator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator

    def printShapePoints(self):
        for dag in cmds.ls(sl=True, type='transform'):
            for s in cmds.listRelatives(dag, shapes=True, type='nurbsCurve', fullPath=True):
                print(getNurbsCurveData(s))

    def openColorDialog(self):
        colorDialog = QColorDialog(self)
        colorDialog.colorSelected.connect(setOverrideColorOnSelected)
        colorDialog.show()

    @chunk
    def replaceShape(self):
        selection = cmds.ls(sl=True, long=True, type='transform')

        if not selection:
            cmds.warning('Nothing valid is selected.')
            return

        data = self.shapeCombo.currentData()
        data['axes'] = self.axeShapeCombo.currentText()
        data['scale'] = self.shapeScale.value()

        [setShapes(dag, [data]) for dag in selection]
        cmds.select(selection)

    @chunk
    def scaleShape(self, scaleUp=True):
        off = self.scaleFactor.value()
        factor = 1 + off if scaleUp else 1 - off
        [scaleShapes(c, factor) for c in cmds.ls(sl=True, type='transform', long=True)]

    def copyShapes(self):
        selection = cmds.ls(sl=True, long=True, type='transform')
        if not selection:
            cmds.warning('Nothing valid is selected.')
            return
        self.copiedShapeData = getShapesData(selection[-1])
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

        if applyShape:
            [setShapes(dag, self.copiedShapeData, applyColor=applyColor) for dag in selection]
        else:
            setOverrideColorOnSelected(self.copiedShapeData[0]['color'])

    @chunk
    def mirrorShapes(self):
        selection = cmds.ls(sl=True, type='transform')
        for dag in selection:
            mirrorName = dag.replace(self.searchFor.text(), self.replaceBy.text())
            if not cmds.objExists(mirrorName) or mirrorName == dag:
                cmds.warning('No mirror object found')
                continue

            data = getShapesData(dag, objectSpace=False)

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

            setShapes(mirrorName, data, applyColor=False)
        cmds.select(selection)

    def swapSearchReplace(self):
        searchFor = self.searchFor.text()
        replaceBy = self.replaceBy.text()

        self.searchFor.setText(replaceBy)
        self.replaceBy.setText(searchFor)

    @chunk
    def importShapes(self):
        path, _ = QFileDialog.getOpenFileName(self, caption='Import File', filter='Controller Shapes (*.ctrl)')

        if not path:
            cmds.warning('No valid path selected. Skip...')
            return

        importShapes(path, selectionFilter=cmds.ls(sl=True))

    def exportShapes(self):
        path, _ = QFileDialog.getSaveFileName(self, caption='Export Shapes', filter='Controller Shapes (*.ctrl)')

        if not path:
            cmds.warning('No valid path selected. Skip...')
            return

        exportShapes(cmds.ls(sl=True), path)
