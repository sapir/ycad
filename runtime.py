#!/usr/bin/env python

from __future__ import print_function
from itertools import count, chain
from collections import defaultdict, namedtuple
from functools import wraps, partial
from math import *
import copy
import os
import numpy as np
import textimpl
import operator
import _ycad


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

    def applyTransform(self, transform):
        if self.shape is None:
            return

        if isinstance(transform, _ycad.Transform):
            self.shape.applyTransform(transform)
        else:
            self.shape.applyGTransform(transform)

    def withTransform(self, transform):
        newObj = copy.copy(self)

        if isinstance(transform, _ycad.Transform):
            shape = self.shape.withTransform(transform)
        else:
            shape = self.shape.withGTransform(transform)

        newObj.shape = shape
        return newObj

    def _moveApply(self, vec):
        transform = _ycad.Transform()
        transform.setTranslation(vec)
        self.applyTransform(transform)

    def move(self, ctx, vec=None, x=0, y=0, z=0):
        if vec is None:
            vec = [x,y,z]
        elif len(vec) == 2:
            vec += [0]

        transform = _ycad.Transform()
        transform.setTranslation(vec)
        return self.withTransform(transform)

    def scale(self, ctx, size=None, x=1, y=1, z=1):
        if size is not None:
            if isinstance(size, float):
                x = y = z = size
            elif len(size) == 3:
                x, y, z = size
            elif len(size) == 2:
                x, y = size
                z = 1

        transform = _ycad.GenTransform()
        transform.setScale(x, y, z)
        return self.withTransform(transform)

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

        transform = _ycad.Transform()
        transform.setRotation(axis, radians(angle))
        return self.withTransform(transform)

    def extrude(self, ctx, *args, **kwargs):
        return LinearExtrusion(ctx, self, *args, **kwargs)

    def revolve(self, ctx, *args, **kwargs):
        return Revolution(ctx, self, *args, **kwargs)

    def _tesselate(self, tolerance):
        self.shape.tesselate(tolerance)

class Cube(Object3D):
    def __init__(self, ctx, s, center=False):
        Object3D.__init__(self, basename='cube')

        if isinstance(s, float):
            x = y = z = s
        else:
            x, y, z = s

        self.shape = _ycad.box(x, y, z)

        if center:
            self._moveApply([-x / 2., -y / 2., -z / 2.])

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
            self.shape = _ycad.cylinder(d/2., h)
        else:
            self.shape = _ycad.cone(d1/2., d2/2., h)

        if center:
            self._moveApply([0, 0, -h / 2.])

class Sphere(Object3D):
    def __init__(self, ctx, r=None, d=None):
        Object3D.__init__(self, basename='sphere')

        if d is not None:
            r = d / 2.

        assert isinstance(r, float)

        self.shape = _ycad.sphere(r)

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

        self.shape = _ycad.torus(*args)

class Combination(Object3D):
    def __init__(self, ctx, op, objs, name=None):
        Object3D.__init__(self, name=name, basename='comb')
        self.op = op
        self.objs = objs

        if self.objs:
            shapes = [obj.shape for obj in objs if obj.shape is not None]
            self.shape = self.makeShape(op, shapes)
        else:
            self.shape = None

    @staticmethod
    def makeShape(op, shapes):
        opFunc = getattr(operator, op)

        # # BRepAlgoAPI seems not to like handling compounds containing
        # # solids so we convert them to single solids. (docs say that
        # # compsolids aren't handled either, so we fix those, too).
        # def fixCompounds(shape):
        #     if shape.ShapeType() == TopAbs_COMPSOLID:
        #         return Combination.compSolidToSolid(compSolid)

        #     elif shape.ShapeType() == TopAbs_COMPOUND:
        #         compoundType = Combination._getCompoundType(shape)
        #         if compoundType == TopAbs_SOLID:
        #             return Combination.consolidateCompoundSolids(shape)

        #     return shape

        # fixedShapes = [fixCompounds(shape) for shape in shapes]
        return reduce(opFunc, shapes)

    @staticmethod
    def fromBlock(ctx, op, block, **kwargs):
        objs = [obj for obj in block.run(ctx) if isinstance(obj, Object3D)]
        return Combination(ctx, op, objs, **kwargs)

    @staticmethod
    def _getCompoundType(compound):
        assert compound.ShapeType() == TopAbs_COMPOUND

        hasSolids = False
        for obj in compound.descendants(_ycad.TopAbs_SOLID):
            hasSolids = True
            break

        hasExtraFaces = False
        # look for faces that aren't in solids
        for obj in compound.descendants(_ycad.TopAbs_FACE, _ycad.TopAbs_SOLID):
            hasExtraFaces = True
            break

        assert hasSolids ^ hasExtraFaces

        if hasSolids:
            return TopAbs_SOLID
        else:
            assert hasExtraFaces
            return TopAbs_FACE

    @staticmethod
    def consolidateCompoundSolids(compound):
        '''Assumes _getCompoundType(compound) is TopAbs_SOLID.'''

        builder = TopoDS_Builder()

        compSolid = TopoDS_CompSolid()
        builder.MakeCompSolid(compSolid)

        for solid in compound.descendants(_ycad.TopAbs_SOLID):
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

        self.shape = _ycad.circle(r)

class Polygon(Object3D):
    def __init__(self, ctx, points, paths=None):
        Object3D.__init__(self)

        if paths is None:
            paths = [range(len(points)) + [0]]
        else:
            # close loops and convert floats to ints
            paths = [map(int, p + [p[0]]) for p in paths]

        def pathPoints(path):
            return [points[pidx] for pidx in path]

        def makeWireFromPath(path):
            return _ycad.wire(
                _ycad.segment((x1, y1, 0), (x2, y2, 0))
                for ((x1, y1), (x2, y2))
                in zip(pathPoints(path), pathPoints(path[1:])))

        self.shape = _ycad.face(makeWireFromPath(path) for path in paths)


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
            self.shape = obj.shape.extrudeStraight(h)
        else:
            self._makeTwisted(obj.shape, h, twist)

        if center:
            self._moveApply([0, 0, -h / 2.])

    def _makeTwisted(self, baseShape, height, twist):
        faces = baseShape.descendants(_ycad.TopAbs_FACE)

        self.shape = _ycad.compound(
            self._twistFace(face, height, twist)
            for face in faces)

    def _twistFace(self, face, height, twist):
        # first sort face's wires into inner and outer wires.
        # baseShape should be contiguous and 2D, so there should be one
        # outer wire and possibly one or more inner wires.
        outerWires = []
        innerWires = []
        fwdFace = face.oriented(_ycad.TopAbs_FORWARD)
        for wire in fwdFace.descendants(_ycad.TopAbs_WIRE):
            if wire.isInnerWireOfFace(face):
                innerWires.append(wire)
            else:
                outerWires.append(wire)

        assert len(outerWires) == 1

        twistedOuter = self._twistProfileWire(outerWires[0], height, twist)
        if len(innerWires) > 0:
            twistedInners = [self._twistProfileWire(wire, height, twist)
                for wire in innerWires]

            return Combination.makeShape('sub', [twistedOuter] + twistedInners)
        else:
            return twistedOuter

    def _twistProfileWire(self, profile, height, twist):
        # split height into segments. each segment will twist no more than
        # 90 degrees.
        numTwistSegments = int(abs(twist) // 90 + 1)
        segmentHeight = float(height) / numTwistSegments
        segmentTwistRad = radians(float(twist) / numTwistSegments)

        auxSurfPts = [[None] * (numTwistSegments + 1) for i in xrange(2)]
        for i in xrange(numTwistSegments + 1):
            z = segmentHeight * i
            angle = segmentTwistRad * i
            auxSurfPts[0][i] = (0, 0, z)
            auxSurfPts[1][i] = (cos(angle), sin(angle), z)

        auxSurf = _ycad.BezierSurface(auxSurfPts)
        auxFace = auxSurf.makeFace(0, 1, 0, 1)
        spine = auxSurf.makeEdgeOnSurface((0, 0), (0, 1))
        return profile.extrudeAlongSurface(spine, auxFace)

class Revolution(Object3D):
    def __init__(self, ctx, obj, angle=360):
        Object3D.__init__(self)

        self.shape = obj.shape.revolve(radians(angle))

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
    return Object3D(_ycad.readSTL(path))


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

        move, scale, rotate, extrude, revolve])
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
        _ycad.writeSTL(obj.shape, outputFilename, 0.05)
