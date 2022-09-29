from PySide2.QtCore import Qt, QSize
from PySide2.QtGui import QIcon, QPixmap, QColor
from PySide2.QtWidgets import QMainWindow, QHBoxLayout, QVBoxLayout, QPushButton, QGridLayout, QColorDialog, \
    QComboBox, QLabel, QDoubleSpinBox, QDialog, QMenu, QMenuBar, QAction, QCheckBox, QFrame, qApp
from maya import OpenMayaUI, cmds
import shiboken2
from functools import partial
import json
import os

# 1.0
# TODO: Save / import
# TODO: copy / paste
# TODO: mirror and mirror batch
# TODO: comment code / doc
# 2.0
# TODO: manage shape list
# TODO: manage color palette
# TODO: replace shape with auto-scale
# TODO: dockable window

dpiF = qApp.desktop().logicalDpiX() / 96.0

shapesDir = os.path.dirname(os.path.abspath(__file__))
with open('{}/shapes.json'.format(shapesDir), 'r') as f:
    shapesData = json.load(f)


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


def getCurveData(shape):
    spans = cmds.getAttr('{}.spans'.format(shape))
    cvCount = spans if cmds.getAttr('{}.form'.format(shape)) == 2 else cmds.getAttr('{}.degree'.format(shape)) + spans
    degree = cmds.getAttr('{}.degree'.format(shape))
    periodic = cmds.getAttr('{}.form'.format(shape)) == 2
    points = [cmds.xform('{}.cv[{}]'.format(shape, i), q=True, translation=True) for i in range(cvCount)]
    return dict(
        degree=degree,
        periodic=periodic,
        points=points
    )


@chunk
def scaleShapes(ctrl, factor):
    for s in cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve') or list():
        scaledPoints = [[v * factor for v in p] for p in getCurveData(s)]
        [cmds.xform('{}.cv[{}]'.format(s, i), translation=p) for i, p in enumerate(scaledPoints)]


@chunk
def scaleShapesOnSelected(factor):
    [scaleShapes(c, factor) for c in cmds.ls(sl=True, type='transform', long=True)]


@chunk
def setShape(ctrl, points=tuple(), degree=1, periodic=False, axes='x', scale=1.0):
    points = [[v * scale for v in p] for p in points]
    if axes == 'x':
        points = [(y, z, x) for x, y, z in points]
    elif axes == 'y':
        points = [(x, y, z) for x, y, z in points]
    elif axes == 'z':
        points = [(z, x, y) for x, y, z in points]
    else:
        raise ValueError('\'x\', \'y\' or \'z\' excepted as axes. Got {}'.format(repr(axes)))
    curve = cmds.curve(point=points, degree=degree)
    cmds.closeCurve(curve, ch=False, preserveShape=False, replaceOriginal=True) if periodic else None
    sh = cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve')
    cmds.delete(sh) if sh else None
    cmds.parent(cmds.listRelatives(curve, shapes=True), ctrl, r=True, s=True)
    cmds.delete(curve)
    ctrlShortName = ctrl.split('|')[-1]
    [cmds.rename(s, '{}Shape#'.format(ctrlShortName)) for s in cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve') or list()]
    cmds.select(ctrl)


@chunk
def setOverrideColor(dag, color):
    cmds.setAttr('{}.overrideEnabled'.format(dag), True)
    cmds.setAttr('{}.overrideRGBColors'.format(dag), True)
    cmds.setAttr('{}.overrideColorRGB'.format(dag), *color)


@chunk
def resetOverrideColor(dag):
    cmds.setAttr('{}.overrideRGBColors'.format(dag), False)
    cmds.setAttr('{}.overrideColorRGB'.format(dag), 0, 0, 0)
    cmds.setAttr('{}.overrideColor'.format(dag), 0)


def getOverrideColor(dag):
    enabled = cmds.getAttr('{}.overrideEnabled'.format(dag))
    mode = cmds.getAttr('{}.overrideRGBColors'.format(dag))
    rgbColor = cmds.getAttr('{}.overrideColorRGB'.format(dag))
    indexColor = cmds.getAttr('{}.overrideColor'.format(dag))
    return dict(
        enabled=enabled,
        mode=mode,
        rgbColor=rgbColor,
        indexColor=indexColor
    )


@chunk
def setShapeOnSelected(points=tuple(), degree=1, periodic=False, axes='x', scale=1.0):
    ctrls = cmds.ls(sl=True, long=True, type='transform')
    [setShape(ctrl, points=points, degree=degree, periodic=periodic, axes=axes, scale=scale) for ctrl in ctrls]
    cmds.select(ctrls)


@chunk
def setColor(dag, color=None):
    if not cmds.objExists('{}.overrideEnabled'.format(dag)):
        cmds.warning('Unable to set override color for \'{}\''.format(dag))
        return

    resetOverrideColor(dag)
    [resetOverrideColor(s) for s in cmds.listRelatives(dag, shapes=True, fullPath=True) or list()]

    if not color:
        return

    color = color.getRgb()[0:3] if isinstance(color, QColor) else color
    color = [c/255.0 for c in color]

    shapes = cmds.listRelatives(dag, shapes=True, fullPath=True) or list()
    [setOverrideColor(s, color) for s in shapes] if shapes else setOverrideColor(dag, color)


@chunk
def setColorOnSelected(color):
    [setColor(c, color) for c in cmds.ls(sl=True, long=True)]


def getShapeData(shape):
    curveData = getCurveData(shape)
    colorData = getOverrideColor(shape)
    curveData.update(colorData)

    return dict(
        curve=curveData,
        color=colorData
    )

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


class ColorButton(QPushButton):

    def __init__(self, color):
        super(ColorButton, self).__init__()

        self.color = color
        self.clicked.connect(partial(setColorOnSelected, self.color))

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
        self.setWindowTitle('Ctrl Shaper')

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

        copyColor = QCheckBox()
        copyColor.setChecked(True)

        copyShape = QCheckBox()
        copyShape.setChecked(True)

        copyBtn = QPushButton('Copy')
        copyBtn.clicked.connect(self.copyShapes)

        self.pasteBtn = QPushButton('Paste')
        self.pasteBtn.setEnabled(False)
        self.pasteBtn.clicked.connect(self.pasteShapes)

        copyPasteLayout = QGridLayout()
        copyPasteLayout.addWidget(QLabel('Apply Color'), 0, 0)
        copyPasteLayout.addWidget(copyColor, 0, 1)
        copyPasteLayout.addWidget(QLabel('Apply Shape'), 1, 0)
        copyPasteLayout.addWidget(copyShape, 1, 1)
        copyPasteLayout.addWidget(copyBtn, 2, 0)
        copyPasteLayout.addWidget(self.pasteBtn, 2, 1)

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
        resetColorBtn.clicked.connect(partial(setColorOnSelected, None))

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

        scaleLayout = QHBoxLayout()
        scaleLayout.addWidget(QLabel('Scale'))
        scaleLayout.addWidget(scaleMinusBtn)
        scaleLayout.addWidget(self.scaleFactor)
        scaleLayout.addWidget(scalePlusBtn)

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
        mainLayout.addWidget(QLabel('<b>Replace Shape</b>'))
        mainLayout.addWidget(self.createSeparator())
        mainLayout.addLayout(shapeLayout)
        mainLayout.addSpacing(30)
        mainLayout.addWidget(QLabel('<b>Copy/Paste Shape</b>'))
        mainLayout.addWidget(self.createSeparator())
        mainLayout.addLayout(copyPasteLayout)
        mainLayout.addSpacing(30)
        mainLayout.addWidget(QLabel('<b>Color Override</b>'))
        mainLayout.addWidget(self.createSeparator())
        mainLayout.addLayout(colorLayout)
        mainLayout.addSpacing(30)
        mainLayout.addWidget(QLabel('<b>Transform Shape</b>'))
        mainLayout.addWidget(self.createSeparator())
        mainLayout.addLayout(scaleLayout)
        mainLayout.setMenuBar(m)

    def createSeparator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        return separator

    def printShapePoints(self):
        for dag in cmds.ls(sl=True, type='transform'):
            for s in cmds.listRelatives(dag, shapes=True, type='nurbsCurve', fullPath=True):
                print(getCurveData(s))

    def openColorDialog(self):
        colorDialog = QColorDialog(self)
        colorDialog.colorSelected.connect(setColorOnSelected)
        colorDialog.show()

    def replaceShape(self):
        data = self.shapeCombo.currentData()
        data['axes'] = self.axeShapeCombo.currentText()
        data['scale'] = self.shapeScale.value()
        setShapeOnSelected(**data)

    def scaleShape(self, scaleUp=True):
        off = self.scaleFactor.value()
        factor = 1 + off if scaleUp else 1 - off
        scaleShapesOnSelected(factor)

    def copyShapes(self):
        selection = cmds.ls(sl=True, long=True, type='transform')
        if not selection:
            return
        shapes = cmds.listRelatives(selection[-1], shapes=True, type='nurbsCurve', fullPath=True)
        self.copiedShapeData = [getShapeData(s) for s in shapes]
        print(self.copiedShapeData)
        self.pasteBtn.setEnabled(True)

    def pasteShapes(self):
        selection = cmds.ls(sl=True, long=True, type='transform')
        for dag in selection:
            setShape(dag, **self.copiedShapeData[0]['curve'])
