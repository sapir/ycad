#!/usr/bin/env python

from __future__ import print_function
from itertools import count, chain
from collections import defaultdict
from math import *
import copy
import os
import numpy as np
from OCC.gp import *
from OCC.BRepBuilderAPI import *
from OCC.BRepPrimAPI import *
from OCC.BRepAlgoAPI import *
from OCC.StlAPI import StlAPI_Writer


class ReturnException(BaseException):
    def __init__(self, value=None):
        self.value = value

class Module(object):
    def __init__(self, scope):
        self.scope = scope

    def __getattr__(self, name):
        return self.scope[name]

class Context:
    def __init__(self, outputFilename, dbTitle='ycad database'):
        self.scopeChains = [[builtins]]
        self.combinations = []

        self.modules = {}

    def execProgram(self, srcPath, parsedProgram, moduleObjName, asRegion):
        try:
            self.pushScope()
            self.startCombination('add', name=moduleObjName)
            self.setVar('__path', [os.path.dirname(srcPath)])

            for stmt in parsedProgram:
                stmt.exec_(self)

            # end default combination
            comb = self.endCombination(asRegion=asRegion)
            scope = self.popScope()
            return scope, comb

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
    def curCombination(self):
        return self.combinations[-1]

    def startCombination(self, op, name=None):
        self.combinations.append(Combination(self, op, name=name))

    def endCombination(self, asRegion=False):
        comb = self.combinations.pop()
        comb.make(self, asRegion=asRegion)
        return comb

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

class BrlCadObject(object):
    def __init__(self, name=None, basename='obj'):
        self._name = _autoname(basename) if name is None else name

    def applyTransform(self, transform, apiClass=BRepBuilderAPI_Transform,
            copy=False):

        self.brep = apiClass(self.brep.Shape(), transform, copy)

    def withTransform(self, transform, apiClass=BRepBuilderAPI_Transform):
        newObj = copy.copy(self)
        newObj.applyTransform(transform, apiClass, copy=True)
        return newObj

    def move(self, ctx, vec=None, x=0, y=0, z=0):
        if vec is None:
            vec = [x,y,z]

        transform = gp_Trsf()
        transform.SetTranslation(gp_Vec(*vec))
        return self.withTransform(transform)

    def scale(self, ctx, vec=None, x=1, y=1, z=1):
        if vec is not None:
            x, y, z = vec

        transform = gp_GTrsf(
            gp_Mat(
                x, 0, 0,
                0, y, 0,
                0, 0, z),
            gp_XYZ())
        return self.withTransform(transform, apiClass=BRepBuilderAPI_GTransform)

    def rotate(self, ctx, angle=None, axis=None, x=None, y=None, z=None):
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
        transform.SetRotation(gpAxis, angle)
        return self.withTransform(transform)

class Cube(BrlCadObject):
    def __init__(self, ctx, s):
        BrlCadObject.__init__(self, basename='cube')

        if isinstance(s, float):
            x = y = z = s
        else:
            x, y, z = s

        self.brep = BRepPrimAPI_MakeBox(x, y, z)

class Cylinder(BrlCadObject):
    def __init__(self, ctx, h, d=None, d1=None, d2=None, r=None,
            r1=None, r2=None, center=False):

        BrlCadObject.__init__(self, basename='cylinder')

        if r is not None: d = r * 2
        if r1 is not None: d1 = r1 * 2
        if r2 is not None: d2 = r2 * 2
        
        assert isinstance(h, float)
        assert d is None or isinstance(d, float)
        assert d1 is None or isinstance(d1, float)
        assert d2 is None or isinstance(d2, float)
        assert (d is not None) ^ (d1 is not None and d2 is not None)

        if d is not None:
            self.brep = BRepPrimAPI_MakeCylinder(d/2., h)
        else:
            self.brep = BRepPrimAPI_MakeCone(d1/2., d2/2., h)

        if center:
            transform = gp_Trsf()
            transform.SetTranslation(gp_Vec(0, 0, -h/2.))
            self.applyTransform(transform)

class Sphere(BrlCadObject):
    def __init__(self, ctx, r=None, d=None):
        BrlCadObject.__init__(self, basename='sphere')

        if d is not None:
            r = d / 2.

        assert isinstance(r, float)

        self.brep = BRepPrimAPI_MakeSphere(r)

class Polyhedron(BrlCadObject):
    def __init__(self, ctx, points, triangles):
        BrlCadObject.__init__(self, basename='polyhedron')

        raise NotImplementedError

class Combination(BrlCadObject):
    OP_CLASSES = {
            'add' : BRepAlgoAPI_Fuse,
            'sub' : BRepAlgoAPI_Cut,
            'mul' : BRepAlgoAPI_Common,
        }

    def __init__(self, ctx, op, name=None):
        BrlCadObject.__init__(self, name=name, basename='comb')
        self.op = op

        self._brepList = []
        self._opClass = self.OP_CLASSES[self.op]

    def add(self, obj):
        self._brepList.append(obj.brep)

    def make(self, ctx, asRegion):
        if not self._brepList:
            return

        self.brep = reduce(
            lambda a, b: self._opClass(a.Shape(), b.Shape()),
            self._brepList)


def regPrism(ctx, sides, r, h):
    # TODO: use BRL-CAD's arbn primitive, much simpler
    assert sides == int(sides)
    sides = int(sides)

    # angle to each of the vertices around the center
    angles = [i*2*pi/sides for i in xrange(sides)]

    origin = [0,0,0]
    bottomVertices = [[cos(a) * r, sin(a) * r, 0]
        for a in angles] + [origin]
    topVertices = [(x,y,z+h) for (x,y,z) in bottomVertices]

    vertices = bottomVertices + topVertices
    originIdx = len(bottomVertices) - 1     # index of origin vertex
    topIdx = len(bottomVertices)            # index of topVertices

    # build triangles out from origin
    bottomFaces = [[originIdx, i, (i + 1) % sides] for i in xrange(sides)]

    # again for top faces. vertex order is reversed from bottom,
    # because it's facing other way.
    topFaces = [[topIdx + originIdx, topIdx + (i + 1) % sides, topIdx + i]
        for i in xrange(sides)]

    # build quads connecting bottomVertices and topVertices
    connectingFaces1 = [[i, topIdx + i, (i + 1) % sides] for i in xrange(sides)]
    connectingFaces2 = [[topIdx + i, topIdx + (i + 1) % sides, (i + 1) % sides]
        for i in xrange(sides)]

    faces = bottomFaces + topFaces + connectingFaces1 + connectingFaces2

    return Polyhedron(ctx, points=vertices, triangles=faces)


def wrapPythonFunc(func):
    def wrapper(ctx, *args, **kwargs):
        return func(*args, **kwargs)

    return wrapper

_print = wrapPythonFunc(print)
_range = wrapPythonFunc(np.arange)

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

# Missing OpenSCAD functions: lookup, rands, str, search, import


_builtinClasses = dict((c.__name__.lower(), c) for c in
    [Cube, Cylinder, Sphere, Polyhedron])

builtins = dict((f.func_name.lstrip('_'), f)
    for f in [regPrism, _print, _range,
        _cos, _sin, _tan, _acos, _asin, _atan, _atan2,
        _abs, _ceil, _exp, _floor, _ln, _len, _log, _max, _min, _norm,
        _pow, _round, _sign, _sqrt])
builtins.update(_builtinClasses)


def run(srcPath, parsedProgram, outputFilename):
    ctx = Context(outputFilename)
    _, obj = ctx.execProgram(srcPath, parsedProgram, moduleObjName='main', asRegion=True)
    
    stl_writer = StlAPI_Writer()
    stl_writer.SetASCIIMode(False)
    stl_writer.Write(obj.brep.Shape(), outputFilename)
