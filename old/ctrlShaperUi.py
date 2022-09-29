from PySide2 import QtWidgets, QtCore, QtGui
import webbrowser
from functools import partial
from maya import cmds
import ctrlShaper
import rigUtils
from maya import OpenMayaUI
import shiboken2


def getMayaMainWindow():
    pointer = OpenMayaUI.MQtUtil.mainWindow()
    return shiboken2.wrapInstance(long(pointer), QtWidgets.QMainWindow)


class CtrlShaperUi(QtWidgets.QDialog):

    doc_link = 'https://docs.google.com/document/d/1TQQerXmn9M__IR1iDTgoGQIuoMctUibw0WDZnf62eG0/edit?usp=sharing'
    get_selected_ctrls = rigUtils.Ctrl.get_selected
    get_all_ctrls = rigUtils.Ctrl.get_all

    def __init__(self, parent=None):
        # Kill the window if it already exists
        object_name = self.__class__.__name__
        try:
            cmds.deleteUI(object_name)
        except RuntimeError:
            pass

        parent = getMayaMainWindow() if parent is None else parent
        super(CtrlShaperUi, self).__init__(parent)

        self.setObjectName(object_name)
        self.setWindowTitle(object_name)

        doc_action = QtWidgets.QAction('Doc', self)
        doc_action.setIcon(QtGui.QIcon(":help.png"))
        doc_action.triggered.connect(partial(webbrowser.open, self.doc_link))

        help_menu = QtWidgets.QMenu('Help')
        help_menu.addAction(doc_action)

        menu_bar = QtWidgets.QMenuBar()
        menu_bar.addMenu(help_menu)

        import_btn = QtWidgets.QPushButton('import')
        import_btn.clicked.connect(self.import_)

        export_btn = QtWidgets.QPushButton('export')
        export_btn.clicked.connect(self.export)

        self.scale_ctrls_dsb = QtWidgets.QDoubleSpinBox()
        self.scale_ctrls_dsb.setMinimum(-100.0)
        self.scale_ctrls_dsb.setMaximum(100.0)
        self.scale_ctrls_dsb.setSingleStep(.1)
        self.scale_ctrls_dsb.setValue(1.0)

        scale_ctrls_lab = QtWidgets.QLabel('scale')

        scale_ctrls_lay = QtWidgets.QHBoxLayout()
        scale_ctrls_lay.addWidget(scale_ctrls_lab)
        scale_ctrls_lay.addWidget(self.scale_ctrls_dsb)

        import_lay = QtWidgets.QVBoxLayout()
        import_lay.setAlignment(QtCore.Qt.AlignTop)
        import_lay.addWidget(import_btn)
        import_lay.addLayout(scale_ctrls_lay)

        export_lay = QtWidgets.QVBoxLayout()
        export_lay.setAlignment(QtCore.Qt.AlignTop)
        export_lay.addWidget(export_btn)

        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)

        main_lay = QtWidgets.QHBoxLayout(self)
        main_lay.setMenuBar(menu_bar)
        main_lay.addLayout(export_lay)
        main_lay.addWidget(separator)
        main_lay.addLayout(import_lay)

    def export(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, caption='Export File')

        if not path:
            cmds.warning('No valid path selected. Skip...')
            return

        location, file_name = self.decompose_file_path(path)
        ctrls = self.get_selected_ctrls() or self.get_all_ctrls()
        ctrlShaper.NurbsCurvesFile.create(transforms=ctrls, location=location, file_name=file_name, force=True)

    def import_(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(self, caption='Import File')

        if not ctrlShaper.NurbsCurvesFile.is_one(path):
            cmds.warning('No valid path selected. Skip...')
            return

        ctrls_filter = self.get_selected_ctrls() or None
        scale = self.scale_ctrls_dsb.value()
        ctrlShaper.NurbsCurvesFile(path).load(nodes_filter=ctrls_filter, scale=scale)

    @classmethod
    def decompose_file_path(cls, path):
        path_split = path.split('/')

        file_name = path_split.pop()
        location = '/'.join(path_split)
        return location, file_name