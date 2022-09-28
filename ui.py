from PySide2.QtCore import Qt
from PySide2.QtGui import QIcon, QPixmap, QColor
from PySide2.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QGridLayout
from maya import OpenMayaUI, cmds
import shiboken2
from functools import partial


def setOverrideColor(dag, color=None):
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

    for s in cmds.listRelatives(dag, shapes=True) or list():
        cmds.setAttr('{}.overrideEnabled'.format(s), False)


def setOverrideColorOnSelected(color):
    print(color)
    [setOverrideColor(c, color) for c in cmds.ls(sl=True)]

###


def getMayaMainWindow():
    pointer = OpenMayaUI.MQtUtil.mainWindow()
    return shiboken2.wrapInstance(long(pointer), QMainWindow)


class ColorButton(QPushButton):

    def __init__(self, color):
        super(ColorButton, self).__init__()

        self.color = color
        self.clicked.connect(partial(setOverrideColorOnSelected, self.color))

        if color:
            pixmap = QPixmap(10, 10)
            pixmap.fill(QColor(*color))

            icon = QIcon()
            icon.addPixmap(pixmap)

            self.setIcon(icon)


class CtrlShaper(QMainWindow):

    def __init__(self, parent=getMayaMainWindow()):
        super(CtrlShaper, self).__init__(parent=parent)
        self.setWindowTitle('Ctrl Shaper')

        colorLayout = QGridLayout()
        colorLayout.addWidget(ColorButton(None), 0, 0)
        colorLayout.addWidget(ColorButton((255, 0, 0)), 0, 1)
        colorLayout.addWidget(ColorButton((0, 255, 0)), 0, 2)
        colorLayout.addWidget(ColorButton((0, 0, 255)), 0, 3)
        colorLayout.addWidget(ColorButton((255, 255, 0)), 1, 0)
        colorLayout.addWidget(ColorButton((0, 255, 255)), 1, 1)
        colorLayout.addWidget(ColorButton((255, 0, 255)), 1, 2)

        mainLayout = QVBoxLayout()
        mainLayout.setAlignment(Qt.AlignTop)
        mainLayout.addLayout(colorLayout)

        w = QWidget()
        w.setLayout(mainLayout)

        self.setCentralWidget(w)