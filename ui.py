from PySide2.QtCore import Qt, QSize
from PySide2.QtGui import QIcon, QPixmap, QColor
from PySide2.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QGridLayout, QColorDialog, \
    QComboBox, QLineEdit, QLabel
from maya import OpenMayaUI, cmds
import shiboken2
from functools import partial
import json

with open(r'C:\Users\plaurent\Documents\repo\ctrlShaper\shapes.json', 'r') as f:
    shapes = json.load(f)


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
def setShape(ctrl, points=tuple(), degree=1, periodic=False):
    curve = cmds.curve(point=points, degree=degree, periodic=periodic)
    cmds.delete(cmds.listRelatives(ctrl, shapes=True, type='nurbsCurve'))
    cmds.parent(cmds.listRelatives(curve, shapes=True), ctrl, r=True, s=True)
    cmds.delete(curve)


@chunk
def setShapeOnSelected(points=tuple(), degree=1, periodic=False):
    ctrls = cmds.ls(sl=True, long=True, type='transform')
    [setShape(ctrl, points=points, degree=degree, periodic=periodic) for ctrl in ctrls]


@chunk
def setOverrideColor(dag, color=None):
    if isinstance(color, QColor):
        color = color.getRgb()[0:3]
    if not cmds.objExists('{}.overrideEnabled'.format(dag)):
        cmds.warning('Unable to set override color for \'{}\''.format(dag))
        return
    if color:
        color = [c/255.0 for c in color]
        cmds.setAttr('{}.overrideEnabled'.format(dag), True)
        cmds.setAttr('{}.overrideRGBColors'.format(dag), True)
        cmds.setAttr('{}.overrideColorRGB'.format(dag), *color)
    else:
        cmds.setAttr('{}.overrideEnabled'.format(dag), False)

    [cmds.setAttr('{}.overrideEnabled'.format(s), False) for s in cmds.listRelatives(dag, shapes=True, fullPath=True) or list()]


@chunk
def setOverrideColorOnSelected(color):
    [setOverrideColor(c, color) for c in cmds.ls(sl=True, long=True)]

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
        self.clicked.connect(partial(setOverrideColorOnSelected, self.color))

        if color:
            pixmap = QPixmap(20, 20)
            pixmap.fill(QColor(*color))

            icon = QIcon()
            icon.addPixmap(pixmap)

            self.setIcon(icon)
        else:
            self.setIcon(QIcon(':error.png'))


class CtrlShaper(QMainWindow):

    def __init__(self, parent=getMayaMainWindow()):
        super(CtrlShaper, self).__init__(parent=parent)
        killOtherInstances(self)
        self.setWindowTitle('Ctrl Shaper')

        replaceBtn = QPushButton('replace')
        replaceBtn.clicked.connect(self.replaceShape)

        self.shapeCombo = QComboBox()
        [self.shapeCombo.addItem(name, userData=data) for name, data in shapes.items()]

        shapeLayout = QHBoxLayout()
        shapeLayout.addWidget(self.shapeCombo)
        shapeLayout.addWidget(replaceBtn)

        colorDialogBtn = QPushButton()
        colorDialogBtn.setIcon(QIcon(':colorProfile.png'))
        colorDialogBtn.clicked.connect(self.openColorDialog)

        colorLayout = QGridLayout()
        colorLayout.addWidget(ColorButton((255, 0, 0)), 0, 0)
        colorLayout.addWidget(ColorButton((0, 255, 0)), 0, 1)
        colorLayout.addWidget(ColorButton((0, 0, 255)), 0, 2)
        colorLayout.addWidget(ColorButton((255, 255, 0)), 0, 3)
        colorLayout.addWidget(ColorButton((0, 255, 255)), 1, 0)
        colorLayout.addWidget(ColorButton((255, 0, 255)), 1, 1)
        colorLayout.addWidget(ColorButton(None), 1, 2)
        colorLayout.addWidget(colorDialogBtn, 1, 3)

        mainLayout = QVBoxLayout()
        mainLayout.setAlignment(Qt.AlignTop)
        mainLayout.addWidget(QLabel('Shape'))
        mainLayout.addLayout(shapeLayout)
        mainLayout.addWidget(QLabel('Color'))
        mainLayout.addLayout(colorLayout)

        w = QWidget()
        w.setLayout(mainLayout)

        self.setCentralWidget(w)

    def openColorDialog(self):
        colorDialog = QColorDialog(self)
        colorDialog.colorSelected.connect(setOverrideColorOnSelected)
        colorDialog.show()

    def replaceShape(self):
        data = self.shapeCombo.currentData()
        setShapeOnSelected(**data)
