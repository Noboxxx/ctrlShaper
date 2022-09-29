from PySide2.QtCore import Qt, QSize
from PySide2.QtGui import QIcon, QPixmap, QColor
from PySide2.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QGridLayout, QColorDialog, \
    QComboBox, QLineEdit, QLabel, QDoubleSpinBox, QToolBox, QDialog, QApplication, QSpinBox
from maya import OpenMayaUI, cmds
import shiboken2
from functools import partial
import json

with open(r'C:\Users\plaurent\Documents\repo\ctrlShaper\shapes.json', 'r') as f:
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


def getCurvePoints(shape):
    spans = cmds.getAttr('{}.spans'.format(shape))
    cvCount = spans if cmds.getAttr('{}.form'.format(shape)) == 2 else cmds.getAttr('{}.degree'.format(shape)) + spans
    return [cmds.xform('{}.cv[{}]'.format(shape, i), q=True, translation=True) for i in range(cvCount)]


@chunk
def scaleShapes(ctrl, factor):
    for s in cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve') or list():
        scaledPoints = [[v * factor for v in p] for p in getCurvePoints(s)]
        [cmds.xform('{}.cv[{}]'.format(s, i), translation=p) for i, p in enumerate(scaledPoints)]


@chunk
def scaleShapesOnSelected(factor):
    [scaleShapes(c, factor) for c in cmds.ls(sl=True, type='transform', long=True)]


@chunk
def setShape(ctrl, points=tuple(), degree=1, periodic=False):
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
def setOverrideColor_(dag, color):
    cmds.setAttr('{}.overrideEnabled'.format(dag), True)
    cmds.setAttr('{}.overrideRGBColors'.format(dag), True)
    cmds.setAttr('{}.overrideColorRGB'.format(dag), *color)


@chunk
def resetOverrideColor(dag):
    cmds.setAttr('{}.overrideRGBColors'.format(dag), False)
    cmds.setAttr('{}.overrideColorRGB'.format(dag), 0, 0, 0)
    cmds.setAttr('{}.overrideColor'.format(dag), 0)


@chunk
def setShapeOnSelected(points=tuple(), degree=1, periodic=False):
    ctrls = cmds.ls(sl=True, long=True, type='transform')
    [setShape(ctrl, points=points, degree=degree, periodic=periodic) for ctrl in ctrls]
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

    shapes = cmds.listRelatives(dag, shapes=True) or list()
    [setOverrideColor_(s, color) for s in shapes] if shapes else setOverrideColor_(dag, color)


@chunk
def setColorOnSelected(color):
    [setColor(c, color) for c in cmds.ls(sl=True, long=True)]


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
            pixmap = QPixmap(20, 20)
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
        xNormalSpinBox = QDoubleSpinBox()
        xNormalSpinBox.setValue(1)
        xNormalSpinBox.setMinimum(-1)
        xNormalSpinBox.setMaximum(1)

        yNormalSpinBox = QDoubleSpinBox()
        yNormalSpinBox.setMinimum(-1)
        yNormalSpinBox.setMaximum(1)

        zNormalSpinBox = QDoubleSpinBox()
        zNormalSpinBox.setMinimum(-1)
        zNormalSpinBox.setMaximum(1)

        normalLayout = QHBoxLayout()
        normalLayout.addWidget(QLabel('Normal'))
        normalLayout.addWidget(xNormalSpinBox)
        normalLayout.addWidget(yNormalSpinBox)
        normalLayout.addWidget(zNormalSpinBox)

        replaceBtn = QPushButton('replace')
        replaceBtn.clicked.connect(self.replaceShape)

        self.shapeCombo = QComboBox()
        [self.shapeCombo.addItem(name, userData=data) for name, data in shapesData.items()]

        shapeLayout = QVBoxLayout()
        shapeLayout.addWidget(self.shapeCombo)
        shapeLayout.addLayout(normalLayout)
        shapeLayout.addWidget(replaceBtn)

        # color
        colorDialogBtn = QPushButton('Color Dialog')
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

        colorLayout = QVBoxLayout()
        colorLayout.addLayout(favColorLayout)
        colorLayout.addWidget(resetColorBtn)
        colorLayout.addWidget(colorDialogBtn)

        # transform
        scaleMinusBtn = QPushButton('-')
        scaleMinusBtn.setFixedSize(QSize(16, 16))
        scaleMinusBtn.clicked.connect(partial(self.scaleShape, False))

        scalePlusBtn = QPushButton('+')
        scalePlusBtn.setFixedSize(QSize(16, 16))
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

        # main layout
        mainLayout = QVBoxLayout(self)
        mainLayout.setAlignment(Qt.AlignTop)
        mainLayout.addWidget(QLabel('<b>Replace Shape</b>'))
        mainLayout.addLayout(shapeLayout)
        mainLayout.addSpacing(20)
        mainLayout.addWidget(QLabel('<b>Color Override</b>'))
        mainLayout.addLayout(colorLayout)
        mainLayout.addSpacing(20)
        mainLayout.addWidget(QLabel('<b>Transform Shape</b>'))
        mainLayout.addLayout(scaleLayout)

    def openColorDialog(self):
        colorDialog = QColorDialog(self)
        colorDialog.colorSelected.connect(setColorOnSelected)
        colorDialog.show()

    def replaceShape(self):
        data = self.shapeCombo.currentData()
        setShapeOnSelected(**data)

    def scaleShape(self, scaleUp=True):
        off = self.scaleFactor.value()
        factor = 1 + off if scaleUp else 1 - off
        scaleShapesOnSelected(factor)
