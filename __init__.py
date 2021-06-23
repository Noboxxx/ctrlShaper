from maya import cmds
from . import pathUtils


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


def hold_selection(func):
    def wrapper(*args, **kwargs):
        with HoldSelection():
            return func(*args, **kwargs)
    return wrapper


class HoldSelection(object):

    def __init__(self):
        self.selection = list()

    def __enter__(self):
        self.selection = cmds.ls(sl=True) or list()

    def __exit__(self, exc_type, exc_val, exc_tb):
        cmds.select(self.selection)


class NurbsCurvesFile(pathUtils.JsonFile):

    @classmethod
    def transform_as_dict(cls, transform):
        attributes = (
            'degree',
            'form',
            'overrideColor',
            'overrideEnabled',
        )

        data = list()
        shapes = [shape for shape in (cmds.listRelatives(transform, shapes=True) or list()) if cmds.objectType(shape, isAType='nurbsCurve')]
        for shape in shapes:
            info = dict()

            # controlPoints
            control_points = list()
            control_points_plug = '{0}.{1}'.format(shape, 'controlPoints')
            control_points_size = cmds.getAttr(control_points_plug, size=True)
            for index in range(control_points_size):
                compound_attr = '{0}[{1}]'.format(control_points_plug, index)
                control_points.append(cmds.getAttr(compound_attr)[0])

            # info
            info['controlPoints'] = control_points
            info['name'] = shape
            for attr in attributes:
                info[attr] = cmds.getAttr('{0}.{1}'.format(shape, attr))

            # Gather info
            data.append(info)

        return data

    @classmethod
    def replace_shapes(cls, parent_transform, shapes_info, scale=1.0):
        old_nurbs_curves = [shape for shape in (cmds.listRelatives(parent_transform, shapes=True) or list()) if cmds.objectType(shape, isAType='nurbsCurve')]
        for curve in old_nurbs_curves:
            cmds.delete(curve)

        for shape_info in shapes_info:
            degree = shape_info['degree']
            form = shape_info['form']
            overrideColor = shape_info['overrideColor']
            overrideEnabled = shape_info['overrideEnabled']

            # Scale control points
            controlPoints = list()
            for cp in shape_info['controlPoints']:
                controlPoints.append(
                    (
                        cp[0] * scale,
                        cp[1] * scale,
                        cp[2] * scale,
                    )
                )

            periodic = True if form == 3 else False
            knots = range(len(controlPoints) + degree - 1)  # Works but aint probably right :shrug:

            # Create curve
            curve_transform = cmds.curve(degree=degree, point=controlPoints, periodic=periodic, knot=knots)
            curve_shape = cmds.listRelatives(curve_transform, shapes=True)[0]

            # OverrideColor
            cmds.setAttr('{0}.{1}'.format(curve_shape, 'overrideEnabled'), overrideEnabled)
            cmds.setAttr('{0}.{1}'.format(curve_shape, 'overrideColor'), overrideColor)

            #
            cmds.parent(curve_shape, parent_transform, r=True, s=True)
            cmds.rename(curve_shape, '{0}Shape#'.format(parent_transform))
            cmds.delete(curve_transform)

    @classmethod
    def create(cls, transforms, location=None, file_name=None, force=False):
        transforms = [str(trs) for trs in transforms]
        data = dict()

        for transform in transforms:
            data[transform] = cls.transform_as_dict(transform)

        return cls.create_file(data=data, location=location, file_name=file_name, force=force)

    @chunk
    @hold_selection
    def load(self, nodes_filter=None, scale=1.0):
        data = self.read()

        for transform, shapes_info in data.items():
            if nodes_filter is not None:
                if transform not in nodes_filter:
                    continue

            if cmds.objExists(transform):
                self.replace_shapes(transform, shapes_info, scale=scale)
            else:
                cmds.warning('\'{0}\' does not exist.'.format(transform))