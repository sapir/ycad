#!/usr/bin/env python

from __future__ import print_function
from itertools import count, chain
from collections import defaultdict, namedtuple
from functools import wraps, partial
from math import *
import copy
import os
import numpy as np
from OCC.gp import *
from OCC.BRep import BRep_Builder
from OCC.BRepMesh import *
from OCC.BRepBuilderAPI import *
from OCC.BRepPrimAPI import *
from OCC.BRepAlgoAPI import *
from OCC.BRepOffsetAPI import *
from OCC.BRepTopAdaptor import BRepTopAdaptor_FClass2d
from OCC.StlAPI import StlAPI_Reader, StlAPI_Writer
from OCC.GC import *
from OCC.GCE2d import *
from OCC.Geom import *
from OCC.TColgp import *
from OCC.TopAbs import *
from OCC.TopExp import *
from OCC.TopoDS import *
from OCC.Precision import Precision_Confusion, Precision_PConfusion
import textimpl


def topoExplorerIter(*args, **kwargs):
    """Iterates over contents of a TopoDS shape, using a TopExp_Explorer."""
    exp = TopExp_Explorer(*args, **kwargs)
    while exp.More():
        yield exp.Current()
        exp.Next()

def isInnerWireOfFace(wire, face):
    # recipe from http://opencascade.wikidot.com/recipes
    newface = TopoDS_face(face.EmptyCopied().Oriented(TopAbs_FORWARD))
    BRep_Builder().Add(newface, wire)
    FClass2d = BRepTopAdaptor_FClass2d(newface, Precision_PConfusion())
    return FClass2d.PerformInfinitePoint() != TopAbs_OUT


class ReturnException(BaseException):
    def __init__(self, value=None):
        self.value = value

class Module(object):
    def __init__(self, scope):
        self.scope = scope

    def __getattr__(self, name):
        return self.scope[name]

class Block(object):
    def __init__(self, blockStmt):
        self.stmt = blockStmt

    def run(self, ctx):
        values = []
        ctx.pushBlock(self, values)
        
        try:
            self.stmt.exec_(ctx)
        finally:
            ctx.popBlock()

        return values

    def _accept(self, values, value):
        values.append(value)

class Context:
    _BlockInfo = namedtuple('_BlockInfo', 'block helperValue')

    def __init__(self, outputFilename, dbTitle='ycad database'):
        self.scopeChains = [[builtins]]
        self.blocks = []

        self.modules = {}

        self.textShapeMaker = textimpl.TextShapeMaker()

    def execProgram(self, srcPath, parsedProgram, moduleObjName):
        try:
            self.pushScope()
            self.setVar('__path', [os.path.dirname(srcPath)])

            output = Combination.fromBlock(self, 'add',
                block=Block(parsedProgram), name=moduleObjName)

            scope = self.popScope()
            return scope, output

        except ReturnException:
            raise RuntimeError("return from main scope!")

    @property
    def curScopeChain(self):
        return self.scopeChains[-1]
    
    @property
    def curScope(self):
        return self.curScopeChain[-1]

    def pushScope(self, scopeChain=None):
        if scopeChain is None:
            scopeChain = self.curScopeChain + [{}]

        self.scopeChains.append(scopeChain)

    def popScope(self):
        # pop current scope chain, and return the current scope
        scope = self.curScope
        self.scopeChains.pop()
        return scope

    def getVar(self, name):
        for scope in reversed(self.curScopeChain):
            try:
                return scope[name]
            except LookupError:
                continue

        raise NameError("variable {0} not found".format(name))

    def setVar(self, name, value):
        self.curScope[name] = value

    @property
    def curBlockInfo(self):
        return self.blocks[-1]

    def pushBlock(self, block, helperValue):
        self.blocks.append(self._BlockInfo(block, helperValue))

    def popBlock(self):
        return self.blocks.pop().block

    def sendToBlock(self, value):
        info = self.curBlockInfo
        info.block._accept(info.helperValue, value)

    def findModuleInPath(self, moduleName):
        exts = ['.ycad']
        for dirname in self.getVar('__path'):
            for ext in exts:
                path = os.path.join(dirname, moduleName + ext)
                if os.path.isfile(path):
                    return path

        raise ValueError("Module '{0}' not found!".format(moduleName))


_autoNameCounters = defaultdict(lambda: count(1))
def _autoname(basename):
    counter = _autoNameCounters[basename]
    return '{0}.{1}'.format(basename, next(counter))

class Object3D(object):
    def __init__(self, shape=None, name=None, basename='obj'):
        self.shape = shape
        self._name = _autoname(basename) if name is None else name

    def applyTransform(self, transform, apiClass=BRepBuilderAPI_Transform,
            copy=False):

        if self.shape is None:
            return

        self.shape = apiClass(self.shape, transform, copy).Shape()

    def withTransform(self, transform, apiClass=BRepBuilderAPI_Transform):
        newObj = copy.copy(self)
        newObj.applyTransform(transform, apiClass, copy=True)
        return newObj

    def _moveApply(self, vec):
        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(*vec))
        self.applyTransform(transform)

    def move(self, ctx, vec=None, x=0, y=0, z=0):
        if vec is None:
            vec = [x,y,z]
        elif len(vec) == 2:
            vec += [0]

        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(*vec))
        return self.withTransform(transform)

    def scale(self, ctx, vec=None, x=1, y=1, z=1):
        if vec is not None:
            if len(vec) == 3:
                x, y, z = vec
            elif len(vec) == 2:
                x, y = vec
                z = 1

        transform = gp_GTrsf(
            gp_Mat(
                x, 0, 0,
                0, y, 0,
                0, 0, z),
            gp_XYZ())
        return self.withTransform(transform, apiClass=BRepBuilderAPI_GTransform)

    def rotate(self, ctx, angle=None, axis=None, x=None, y=None, z=None):
        # TODO: support 2d version
        assert ((angle is not None and axis is not None)
            ^ (x is not None) ^ (y is not None) ^ (z is not None))

        if x is not None:
            angle = x
            axis = [1, 0, 0]
        elif y is not None:
            angle = y
            axis = [0, 1, 0]
        elif z is not None:
            angle = z
            axis = [0, 0, 1]

        gpAxis = gp_Ax1(gp_Pnt(), gp_Dir(*axis))

        transform = gp_Trsf()
        transform.SetRotation(gpAxis, radians(angle))
        return self.withTransform(transform)

    def extrude(self, ctx, *args, **kwargs):
        return LinearExtrusion(ctx, self, *args, **kwargs)

    def revolve(self, ctx, *args, **kwargs):
        return Revolution(ctx, self, *args, **kwargs)

    def _tesselate(self, tolerance):
        BRepMesh_IncrementalMesh(self.shape, tolerance)

class Cube(Object3D):
    def __init__(self, ctx, s):
        Object3D.__init__(self, basename='cube')

        if isinstance(s, float):
            x = y = z = s
        else:
            x, y, z = s

        self.shape = BRepPrimAPI_MakeBox(x, y, z).Shape()

class Cylinder(Object3D):
    def __init__(self, ctx, h, d=None, d1=None, d2=None, r=None,
            r1=None, r2=None, center=False):

        Object3D.__init__(self, basename='cylinder')

        if r is not None: d = r * 2
        if r1 is not None: d1 = r1 * 2
        if r2 is not None: d2 = r2 * 2
        
        assert isinstance(h, float)
        assert d is None or isinstance(d, float)
        assert d1 is None or isinstance(d1, float)
        assert d2 is None or isinstance(d2, float)
        assert (d is not None) ^ (d1 is not None and d2 is not None)

        if d is not None:
            self.shape = BRepPrimAPI_MakeCylinder(d/2., h).Shape()
        else:
            self.shape = BRepPrimAPI_MakeCone(d1/2., d2/2., h).Shape()

        if center:
            self._moveApply([0, 0, -h / 2.])

class Sphere(Object3D):
    def __init__(self, ctx, r=None, d=None):
        Object3D.__init__(self, basename='sphere')

        if d is not None:
            r = d / 2.

        assert isinstance(r, float)

        self.shape = BRepPrimAPI_MakeSphere(r).Shape()

class Polyhedron(Object3D):
    def __init__(self, ctx, points, triangles):
        Object3D.__init__(self, basename='polyhedron')

        raise NotImplementedError

class Torus(Object3D):
    def __init__(self, ctx, r1=None, r2=None, angle=None, d1=None, d2=None):
        if d1 is not None:
            r1 = d1 / 2.

        if d2 is not None:
            r2 = d2 / 2.

        assert r1 is not None and r2 is not None

        #assert (angle1 is None) == (angle2 is None)

        assert r2 > r1
        args = [r1, r2 - r1]
        
        if angle is not None:
            args.append(radians(angle))

        #if angle1 is not None:
        #    args += [radians(angle1), radians(angle2)]

        self.shape = BRepPrimAPI_MakeTorus(*args).Shape()

class Combination(Object3D):
    OP_CLASSES = {
            'add' : BRepAlgoAPI_Fuse,
            'sub' : BRepAlgoAPI_Cut,
            'mul' : BRepAlgoAPI_Common,
        }

    def __init__(self, ctx, op, objs, name=None):
        Object3D.__init__(self, name=name, basename='comb')
        self.op = op
        self.objs = objs

        opClass = self.OP_CLASSES[self.op]
        if self.objs:
            # BRepAlgoAPI seems not to like handling compounds containing
            # solids so we convert them to single solids. (docs say that
            # compsolids aren't handled either, so we fix those, too).
            def fixCompounds(shape):
                if shape.ShapeType() == TopAbs_COMPSOLID:
                    return self.compSolidToSolid(compSolid)

                elif shape.ShapeType() == TopAbs_COMPOUND:
                    compoundType = self._getCompoundType(shape)
                    if compoundType == TopAbs_SOLID:
                        return self.consolidateCompoundSolids(shape)

                return shape

            shapes = [fixCompounds(obj.shape) for obj in objs
                if obj.shape is not None]
            self.shape = reduce(lambda a, b: opClass(a, b).Shape(), shapes)
        else:
            self.shape = None

    @staticmethod
    def fromBlock(ctx, op, block, **kwargs):
        objs = [obj for obj in block.run(ctx) if isinstance(obj, Object3D)]
        return Combination(ctx, op, objs, **kwargs)

    @staticmethod
    def _getCompoundType(compound):
        assert compound.ShapeType() == TopAbs_COMPOUND

        hasSolids = False
        for obj in topoExplorerIter(compound, TopAbs_SOLID):
            hasSolids = True
            break

        hasExtraFaces = False
        # look for faces that aren't in solids
        for obj in topoExplorerIter(compound, TopAbs_FACE, TopAbs_SOLID):
            hasExtraFaces = True
            break

        assert hasSolids ^ hasExtraFaces

        if hasSolids:
            return TopAbs_SOLID
        else:
            assert hasExtraFaces
            return TopAbs_FACE

    @staticmethod
    def compSolidToSolid(compSolid):
        return BRepBuilderAPI_MakeSolid(compSolid).Shape()

    @staticmethod
    def consolidateCompoundSolids(compound):
        '''Assumes _getCompoundType(compound) is TopAbs_SOLID.'''

        builder = TopoDS_Builder()

        compSolid = TopoDS_CompSolid()
        builder.MakeCompSolid(compSolid)

        for solid in topoExplorerIter(compound, TopAbs_SOLID):
            builder.Add(compSolid, TopoDS_solid(solid))

        return Combination.compSolidToSolid(compSolid)


def regPoly(ctx, sides, r):
    assert sides == int(sides)
    sides = int(sides)

    # angle to each of the vertices around the center
    angles = [i*2*pi/sides for i in xrange(sides)]

    points = [[cos(a) * r, sin(a) * r] for a in angles]

    return Polygon(ctx, points)

def regPrism(ctx, sides, r, *args, **kwargs):
    return regPoly(ctx, sides, r).extrude(ctx, *args, **kwargs)

class Circle(Object3D):
    def __init__(self, ctx, r=None, d=None):
        Object3D.__init__(self)

        assert (r is not None) ^ (d is not None)

        if d is not None:
            r = d / 2.

        circ = GC_MakeCircle(gp_Ax2(), r).Value()
        edge = BRepBuilderAPI_MakeEdge(circ).Edge()
        wire = BRepBuilderAPI_MakeWire(edge).Wire()
        self.shape = BRepBuilderAPI_MakeFace(wire).Shape()

class Polygon(Object3D):
    def __init__(self, ctx, points, paths=None):
        Object3D.__init__(self)

        occPoints = [gp_Pnt(x, y, 0) for (x, y) in points]

        if paths is None:
            paths = [range(len(occPoints)) + [0]]
        else:
            # close loops and convert floats to ints
            paths = [map(int, p + [p[0]]) for p in paths]

        def makeWireFromPath(path):
            wireMaker = BRepBuilderAPI_MakeWire()

            for i, j in zip(path, path[1:]):
                p1 = occPoints[i]
                p2 = occPoints[j]
                seg = GC_MakeSegment(p1, p2).Value()
                edge = BRepBuilderAPI_MakeEdge(seg).Edge()
                wireMaker.Add(edge)

            return wireMaker.Wire()

        # first wire has to be passed directly to constructor,
        # otherwise a segfault occurs for some reason
        faceMaker = BRepBuilderAPI_MakeFace(makeWireFromPath(paths[0]))
        for path in paths[1:]:
            wire = makeWireFromPath(path)
            faceMaker.Add(wire)

        self.shape = faceMaker.Shape()

class Square(Polygon):
    def __init__(self, ctx, size=None, x=None, y=None, center=False):
        assert (size is not None) ^ (x is not None and y is not None)

        if size is not None:
            if isinstance(size, float):
                x = y = size
            else:
                x, y = size

        points = [[0, 0], [0, y], [x, y], [x, 0]]

        if center:
            points = [(x0 - x / 2, y0 - y / 2) for (x0, y0) in points]

        Polygon.__init__(self, ctx, points)

class Text(Object3D):
    def __init__(self, ctx, string, fontName="Sans", fontSize=12,
            bold=False, italic=False):

        Object3D.__init__(self)

        self.shape = ctx.textShapeMaker.make(string,
            fontName, fontSize, bold=bold, italic=italic)

class LinearExtrusion(Object3D):
    def __init__(self, ctx, obj, h, twist=0, center=False):

        Object3D.__init__(self)
        if twist == 0:
            self._makeStraight(obj.shape, h)
        else:
            self._makeTwisted(obj.shape, h, twist)

        if center:
            self._moveApply([0, 0, -h / 2.])

    def _makeStraight(self, baseShape, height):
        self.shape = BRepPrimAPI_MakePrism(
            baseShape, gp_Vec(0, 0, height), True).Shape()

    def _makeTwisted(self, baseShape, height, twist):
        # TODO: handle multiple wires in face
        for wire in topoExplorerIter(baseShape, TopAbs_WIRE):
            profile = TopoDS_wire(wire)
            break

        # split height into segments. each segment will twist no more than
        # 90 degrees.
        numTwistSegments = int(abs(twist) // 90 + 1)
        segmentHeight = float(height) / numTwistSegments
        segmentTwistRad = radians(float(twist) / numTwistSegments)

        auxSurf = Geom_BezierSurface(TColgp_Array2OfPnt(1, 2, 1, numTwistSegments + 1))
        for i in xrange(numTwistSegments + 1):
            z = segmentHeight * i
            angle = segmentTwistRad * i
            auxSurf.SetPole(1, i + 1, gp_Pnt(0, 0, z))
            auxSurf.SetPole(2, i + 1, gp_Pnt(cos(angle), sin(angle), z))

        auxSurfHandle = Handle_Geom_Surface()
        auxSurfHandle.Set(auxSurf)

        auxFace = BRepBuilderAPI_MakeFace(auxSurfHandle, 0, 1, 0, 1, Precision_Confusion()).Face()

        edge = BRepBuilderAPI_MakeEdge(
            GCE2d_MakeSegment(gp_Pnt2d(0, 0), gp_Pnt2d(0, 1)).Value(),
            auxSurfHandle).Edge()
        spine = BRepBuilderAPI_MakeWire(edge).Wire()

        pipeShellMaker = BRepOffsetAPI_MakePipeShell(spine)
        
        res = pipeShellMaker.SetMode(auxFace)
        if res != 1:
            raise StandardError(
                "failed setting twisted surface-normal for PipeShell")

        pipeShellMaker.Add(wire)
        pipeShellMaker.Build()
        pipeShellMaker.MakeSolid()
        self.shape = pipeShellMaker.Shape()

class Revolution(Object3D):
    def __init__(self, ctx, obj, angle=360):
        Object3D.__init__(self)

        self.shape = BRepPrimAPI_MakeRevol(
            obj.shape, gp_OY(), radians(angle), True).Shape()

def extrude(ctx, *args, **kwargs):
    block = kwargs.pop('block')
    fusedExtrusionProfile = Combination.fromBlock(ctx, 'add', block)
    return fusedExtrusionProfile.extrude(ctx, *args, **kwargs)

def revolve(ctx, *args, **kwargs):
    block = kwargs.pop('block')
    fusedExtrusionProfile = Combination.fromBlock(ctx, 'add', block)
    return fusedExtrusionProfile.revolve(ctx, *args, **kwargs)


def wrapPythonFunc(func):
    @wraps(func)
    def wrapper(ctx, *args, **kwargs):
        return func(*args, **kwargs)

    return wrapper

_print = wrapPythonFunc(print)
_range = wrapPythonFunc(np.arange)
_range.func_name = 'range'

# OpenSCAD equivalent functions:

def _cos(ctx, n):
    return cos(radians(n))

def _sin(ctx, n):
    return sin(radians(n))

def _tan(ctx, n):
    return tan(radians(n))

def _acos(ctx, n):
    return degrees(acos(n))

def _asin(ctx, n):
    return degrees(asin(n))

def _atan(ctx, n):
    return degrees(atan(n))

def _atan2(ctx, x, y):
    return degrees(atan2(x, y))

_abs = wrapPythonFunc(abs)
_ceil = wrapPythonFunc(ceil)
_exp = wrapPythonFunc(exp)
_floor = wrapPythonFunc(floor)
_ln = wrapPythonFunc(log)
_len = wrapPythonFunc(len)
_log = wrapPythonFunc(log10)
_max = wrapPythonFunc(max)
_min = wrapPythonFunc(min)
_norm = wrapPythonFunc(np.linalg.norm)
_pow = wrapPythonFunc(pow)
_round = wrapPythonFunc(round)

def _sign(ctx, n):
    return 0 if n == 0 else copysign(1, n)

_sqrt = wrapPythonFunc(sqrt)

# Missing OpenSCAD functions: lookup, rands, str, search, import (for dxf)

def _read(ctx, path):
    shape = TopoDS_Shape()

    reader = StlAPI_Reader()
    reader.Read(shape, path)

    return Object3D(shape)


def makeTransformFunc(transformName):
    def transform(ctx, *args, **kwargs):
        block = kwargs.pop('block')

        for obj in block.run(ctx):
            # transform Object3Ds, leave everything else alone
            if isinstance(obj, Object3D):
                # transformName is also the method name
                method = getattr(obj, transformName)
                obj = method(ctx, *args, **kwargs)

            ctx.sendToBlock(obj)

    transform.func_name = transformName
    return transform

move = makeTransformFunc('move')
scale = makeTransformFunc('scale')
rotate = makeTransformFunc('rotate')


_builtinClasses = dict((c.__name__.lower(), c) for c in
    [Cube, Cylinder, Sphere, Polyhedron, Torus,
    Circle, Polygon, Square, Text])

builtins = dict((f.func_name.lstrip('_'), f)
    for f in [
        regPoly, regPrism, _read, _print, _range,

        _cos, _sin, _tan, _acos, _asin, _atan, _atan2,
        _abs, _ceil, _exp, _floor, _ln, _len, _log, _max, _min, _norm,
        _pow, _round, _sign, _sqrt,

        move, scale, rotate, extrude])
builtins.update(_builtinClasses)

builtins['add'] = partial(Combination.fromBlock, op='add')
builtins['sub'] = partial(Combination.fromBlock, op='sub')
builtins['mul'] = partial(Combination.fromBlock, op='mul')
builtins['pi'] = pi
builtins['e'] = e


def run(srcPath, parsedProgram, outputFilename):
    ctx = Context(outputFilename)
    _, obj = ctx.execProgram(srcPath, parsedProgram, moduleObjName='main')
    
    if obj.shape is None:
        with open(outputFilename, 'wb'):
            # create an empty file
            pass
    else:
        obj._tesselate(0.05)

        stl_writer = StlAPI_Writer()
        stl_writer.SetASCIIMode(False)
        stl_writer.Write(obj.shape, outputFilename)
