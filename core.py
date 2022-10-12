from maya import cmds
import json
import itertools


class Chunk(object):
    """
    Make sure a group of maya instructions gets undone together. To use with 'with' statement
    """
    def __init__(self, name=''):
        self.name = str(name)

    def __enter__(self):
        cmds.undoInfo(openChunk=True, chunkName=self.name)

    def __exit__(self, exc_type, exc_val, exc_tb):
        cmds.undoInfo(closeChunk=True)


def chunk(func):
    """
    Chunk's decorator
    :param func:
    :return:
    """
    def wrapper(*args, **kwargs):
        with Chunk(name=func.__name__):
            return func(*args, **kwargs)

    return wrapper


@chunk
def scaleCurves(dags, factor):
    curves = cmds.ls(dags, type='nurbsCurve', long=True)
    [scaleCurve(x, factor) for x in curves]

    transforms = cmds.ls(dags, type='transform', long=True)
    for t in transforms:
        [scaleCurve(x, factor) for x in cmds.listRelatives(t, shapes=True, type='nurbsCurve') or list()]


@chunk
def scaleCurve(curve, factor):
    scaledPoints = [[v * factor for v in p] for p in getCurveData(curve)[0]]
    [cmds.xform('{}.cv[{}]'.format(curve, i), translation=p) for i, p in enumerate(scaledPoints)]


@chunk
def setOverrideColors(color, dags=tuple()):
    """
    Set Override color onto given curves and curves under given transforms.
    :param color: rgb color (List[float, float, float])
    :param dags: if dags is empty, selected object will be taken (list)
    :return:
    """
    # selection
    selection = cmds.ls(sl=True, long=True) if not dags else dags

    # color trs
    trs = cmds.ls(selection, type='transform', long=True)
    [[setOverrideColor(x, color) for x in cmds.listRelatives(t, shapes=True, type='nurbsCurve') or list()] for t in trs]

    # color curves
    curves = cmds.ls(selection, type='nurbsCurve', long=True)
    [setOverrideColor(x, color) for x in curves]


def getCurveData(curve, objectSpace=True):
    """
    Get curve data such as points, degree and periodicity.
    :param curve: nurbsCurve
    :param objectSpace: if True points coordinates will be calculated in objectSpace else worldSpace (bool)
    :return: points (List[List[float, float, float]]), degree (int), periodic (bool)
    """
    spans = cmds.getAttr('{}.spans'.format(curve))
    cvCount = spans if cmds.getAttr('{}.form'.format(curve)) == 2 else cmds.getAttr('{}.degree'.format(curve)) + spans

    degree = cmds.getAttr('{}.degree'.format(curve))
    periodic = cmds.getAttr('{}.form'.format(curve)) == 2
    points = [cmds.xform('{}.cv[{}]'.format(curve, i), q=True, translation=True, objectSpace=objectSpace, worldSpace=not objectSpace) for i in range(cvCount)]

    return points, degree, periodic


@chunk
def addCurve(parent, points=tuple(), degree=1, periodic=False, scale=1.0, normal=''):
    """
    Add curve to the given parent
    :param parent: parent of the new curve (str)
    :param points: (List[List[float, float, float]])
    :param degree: (int)
    :param periodic: (bool)
    :param scale: (int)
    :param normal: controller's facing axes (str) -> '', 'x', 'y', 'z'
    :return: shapes (List[str])
    """
    points = [[v * scale for v in p] for p in points] if scale != 1 else points

    # normal
    if normal == 'x':
        points = [(y, z, x) for x, y, z in points]
    elif normal == 'y':
        points = [(x, y, z) for x, y, z in points]
    elif normal == 'z':
        points = [(z, x, y) for x, y, z in points]
    elif not normal:
        pass
    else:
        raise ValueError('\'x\', \'y\' or \'z\' excepted as axes. Got {}'.format(repr(normal)))

    # Create Curve
    curve = cmds.curve(point=points, degree=degree)
    cmds.closeCurve(curve, ch=False, preserveShape=False, replaceOriginal=True) if periodic else None

    # Parent Curve
    cmds.parent(cmds.listRelatives(curve, shapes=True) or list(), parent, r=True, s=True)
    cmds.delete(curve)

    # Rename Curve
    shapes = cmds.listRelatives(parent, shapes=True, type='nurbsCurve') or list()
    ctrlShortName = parent.split('|')[-1]
    [cmds.rename(s, '{}Shape#'.format(ctrlShortName)) for s in shapes or list()]

    # Select
    cmds.select(parent)
    return shapes


@chunk
def replaceCurves(ctrl, data, applyColor=True, applyShapes=True):
    """
    Replace controller's curves.
    :param ctrl: (str)
    :param data: (List[dict])
    :param applyColor: choose to apply color or not (bool)
    :param applyShapes: choose to apply shapes or not (bool)
    :return:
    """
    oldShapes = cmds.listRelatives(ctrl, shapes=True, fullPath=True, type='nurbsCurve') or list()
    oldColors = [getOverrideColor(s) for s in oldShapes]

    if applyShapes:
        cmds.delete(oldShapes) if oldShapes else None
        for d in data:
            addCurve(
                ctrl, points=d.get('points', tuple()), degree=d.get('degree', 1), periodic=d.get('periodic', False),
                normal=d.get('axes', ''), scale=d.get('scale', 1.0)
            )

    newShapes = cmds.listRelatives(ctrl, shapes=True, fullPath=True, type='nurbsCurve') or list()
    colors = [d.get('color', None) for d in data]
    for s, o, c in itertools.zip_longest(newShapes, oldColors, colors):
        if not s:
            continue
        setOverrideColor(s, c) if applyColor else setOverrideColor(s, o)


def getCurvesData(ctrl, objectSpace=True):
    """
    Get curves data of the given ctrl
    :param ctrl: (str)
    :param objectSpace: (bool)
    :return: dict containing points, degree, periodic, color (dict)
    """
    data = list()

    for shape in cmds.listRelatives(ctrl, shapes=True, fullPath=True, type='nurbsCurve') or list():
        shapeData = dict()
        shapeData['points'], shapeData['degree'], shapeData['periodic'] = getCurveData(shape, objectSpace=objectSpace)
        shapeData['color'] = getOverrideColor(shape)
        data.append(shapeData)

    return data


def getOverrideColor(dag):
    """
    Get override color
    :param dag: (str)
    :return: indexColor (int) or rgbColor (List[float, float, float])
    """
    enabled = cmds.getAttr('{}.overrideEnabled'.format(dag))

    if not enabled:
        return None

    mode = cmds.getAttr('{}.overrideRGBColors'.format(dag))

    if mode == 1:
        return cmds.getAttr('{}.overrideColorRGB'.format(dag))[0]

    return cmds.getAttr('{}.overrideColor'.format(dag))


@chunk
def setOverrideColor(dag, color=None):
    """
    Set override color
    :param dag: (str)
    :param color: indexColor (int) or rgbColor (List[float, float, float])
    :return:
    """

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

    cmds.setAttr('{}.overrideEnabled'.format(dag), enabled)
    cmds.setAttr('{}.overrideRGBColors'.format(dag), isRgb)
    cmds.setAttr('{}.overrideColorRGB'.format(dag), *rgbColor)
    cmds.setAttr('{}.overrideColor'.format(dag), indexColor)


def exportCurves(dags, filePath):
    """
    Export curves to a json file
    :param dags: list of 'controllers' (List[str])
    :param filePath: (str)
    :return:
    """
    dags = cmds.ls(dags, type='transform')

    if not dags:
        cmds.warning('Nothing valid selected. Skip...')
        return

    data = {x: getCurvesData(x) for x in dags}

    with open(filePath, 'w') as f:
        json.dump(data, f)


@chunk
def importCurves(filePath, selectionFilter=tuple(), shapes=True, color=True):
    """
    Import curves from a json file
    :param filePath: (str)
    :param selectionFilter: list of objects that will be affected by the importation (List[str])
    :param shapes: apply shapes (bool)
    :param color: apply colors (bool)
    :return:
    """
    with open(filePath, 'r') as f:
        data = json.load(f)

    for n, d in data.items():
        if selectionFilter:
            if n not in selectionFilter:
                continue

        if not cmds.objExists(n):
            cmds.warning('Unable to find {}. Skip...'.format(repr(n)))
            continue

        replaceCurves(n, d, applyColor=color, applyShapes=shapes)
