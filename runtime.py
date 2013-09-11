#!/usr/bin/env python

from itertools import count, chain
from collections import defaultdict
import math
import copy
import os
import numpy as np
import brlcad


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

        self.wdb = brlcad.wdb_fopen(outputFilename)
        self.wdb.mk_id(dbTitle)

        self.modules = {}

    def __del__(self):
        if self.wdb is not None:
            self.close()

    def close(self):
        self.wdb.close()
        self.wdb = None

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
        self._mat = np.identity(4)

    def _applyMatrix(self, ctx, mat):
        # switching to the commented line will break withMatrix():
        # ctx.wdb.apply_mat(self._name, mat)
        self._mat = np.dot(mat, self._mat)

    def withMatrix(self, ctx, mat):
        newObj = copy.copy(self)
        newObj._applyMatrix(ctx, mat)
        return newObj

    def move(self, ctx, vec=None, x=0, y=0, z=0):
        if vec is None:
            vec = [x,y,z]

        mat = np.identity(4)
        brlcad.set_mat_deltas(mat, *vec)
        return self.withMatrix(ctx, mat)

    def scale(self, ctx, vec=None, x=1, y=1, z=1):
        if vec is None:
            vec = [x,y,z]

        mat = np.identity(4)
        brlcad.set_mat_scale(mat, x, y, z)
        return self.withMatrix(ctx, mat)

    def rotate(self, ctx, angle, axis):
        mat = np.identity(4)
        brlcad.rotate_mat(mat, axis, np.deg2rad(angle))
        return self.withMatrix(ctx, mat)

class Cube(BrlCadObject):
    def __init__(self, ctx, s):
        BrlCadObject.__init__(self, basename='cube')

        self.s = s

        if isinstance(s, float):
            ctx.wdb.mk_rpp(self._name, [0,0,0], [s,s,s])
        else:
            ctx.wdb.mk_rpp(self._name, [0,0,0], s)

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
            ctx.wdb.mk_rcc(self._name, [0,0,0], [0,0,h], d/2.)
        elif d1 is not None and d2 is not None:
            ctx.wdb.mk_trc_h(self._name, [0,0,0], [0,0,h], d1/2., d2/2.)

        if center:
            self.move(ctx, z=-h/2)

class Sphere(BrlCadObject):
    def __init__(self, ctx, r=None, d=None):
        BrlCadObject.__init__(self, basename='sphere')

        if d is not None:
            r = d / 2.

        assert isinstance(r, float)

        ctx.wdb.mk_sph(self._name, [0,0,0], r)

class Polyhedron(BrlCadObject):
    def __init__(self, ctx, points, triangles):
        BrlCadObject.__init__(self, basename='polyhedron')

        ctx.wdb.mk_bot(self._name, points, triangles)

class Combination(BrlCadObject):
    OPS = {
            'add' : brlcad.CombinationList.UNION,
            'sub' : brlcad.CombinationList.SUBTRACT,
            'mul' : brlcad.CombinationList.INTERSECT,
        }

    def __init__(self, ctx, op, name=None):
        BrlCadObject.__init__(self, name=name, basename='comb')
        self.op = op

        self._objList = brlcad.CombinationList()
        self._opVal = self.OPS[self.op]

    def add(self, obj):
        self._objList.add_member(obj._name, self._opVal, obj._mat)

    def make(self, ctx, asRegion):
        ctx.wdb.mk_lfcomb(self._name, self._objList, asRegion)


def _range(ctx, stop):
    return np.arange(stop)

def regPrism(ctx, sides, r, h):
    # TODO: use BRL-CAD's arbn primitive, much simpler
    assert sides == int(sides)
    sides = int(sides)

    # angle to each of the vertices around the center
    angles = [i*2*math.pi/sides for i in xrange(sides)]

    origin = [0,0,0]
    bottomVertices = [[math.cos(a) * r, math.sin(a) * r, 0]
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


_builtinClasses = dict((c.__name__.lower(), c) for c in
    [Cube, Cylinder, Sphere, Polyhedron])

builtins = dict((f.func_name, f) for f in [regPrism])
builtins.update(_builtinClasses)
builtins['range'] = _range


def run(srcPath, parsedProgram, outputFilename):
    ctx = Context(outputFilename)
    ctx.execProgram(srcPath, parsedProgram, moduleObjName='main', asRegion=True)
    ctx.close()
