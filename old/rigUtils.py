from maya import cmds


class Ctrl(object):

    def __init__(self, name):
        if not self.is_one(name):
            cmds.error('The given name \'{0}\' is not a ctrl.'.format(name))
        self.__name = name

    def __str__(self):
        return self.get_name()

    def __repr__(self):
        return self.get_name()

    def get_name(self):
        return self.__name

    def __eq__(self, other):
        return str(self) == str(other)

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def get_all(cls):
        nodes = cmds.ls('*_ctl') or list()
        nodes += cmds.ls('*:*_ctl') or list()

        ctrls = list()
        for node in nodes:
            if cls.is_one(node):
                ctrls.append(cls(node))
        return ctrls

    @classmethod
    def get_selected(cls):
        items = list()
        for node in cmds.ls(sl=True) or list():
            if cls.is_one(node):
                items.append(cls(node))
        return items

    @classmethod
    def is_one(cls, name):
        if cmds.objExists(name):
            if cmds.objectType(name) == 'transform':
                if name.endswith('_ctl'):
                    shapes = [cmds.nodeType(shape) for shape in cmds.listRelatives(name, shapes=True) or list()]
                    if 'nurbsCurve' in shapes:
                        return True
        return False
