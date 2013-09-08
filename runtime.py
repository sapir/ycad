#!/usr/bin/env python

from itertools import count, chain
import math
import copy
import numpy as np
import brlcad


class ReturnException(BaseException):
    def __init__(self, value=None):
        self.value = value

class Context:
    def __init__(self, outputFilename, dbTitle='ycad database'):
        self.scope = {}

        defComb = Combination(self, op='add', name='main')
        self.combinations = [defComb]

        self.wdb = brlcad.wdb_fopen(outputFilename)
        self.wdb.mk_id(dbTitle)

    def __del__(self):
        if self.wdb is not None:
            self.close()

    def close(self):
        # end default combination
        self.endCombination(asRegion=True)

        self.wdb.close()
        self.wdb = None

    def getVar(self, name):
        try:
            return self.scope[name]
        except LookupError:
            global builtins
            return builtins[name]

    def setVar(self, name, value):
        self.scope[name] = value

    @property
    def curCombination(self):
        return self.combinations[-1]

    def startCombination(self, op):
        self.combinations.append(Combination(self, op))

    def endCombination(self, asRegion=False):
        comb = self.combinations.pop()
        comb.make(self, asRegion=asRegion)
        return comb


_autoNameCounter = count(1)
def _autoname():
    return 'autoname.{0}'.format(next(_autoNameCounter))

class BrlCadObject(object):
    def __init__(self, name=None):
        self._name = _autoname() if name is None else name
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
        BrlCadObject.__init__(self)

        self.s = s

        if isinstance(s, float):
            ctx.wdb.mk_rpp(self._name, [0,0,0], [s,s,s])
        else:
            ctx.wdb.mk_rpp(self._name, [0,0,0], s)

class Cylinder(BrlCadObject):
    def __init__(self, ctx, h, d=None, d1=None, d2=None, r=None,
            r1=None, r2=None, center=False):

        BrlCadObject.__init__(self)

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
        BrlCadObject.__init__(self)

        if d is not None:
            r = d / 2.

        assert isinstance(r, float)

        ctx.wdb.mk_sph(self._name, [0,0,0], r)

class Polyhedron(BrlCadObject):
    def __init__(self, ctx, points, triangles):
        BrlCadObject.__init__(self)

        ctx.wdb.mk_bot(self._name, points, triangles)

class Combination(BrlCadObject):
    OPS = {
            'add' : brlcad.CombinationList.UNION,
            'sub' : brlcad.CombinationList.SUBTRACT,
            'mul' : brlcad.CombinationList.INTERSECT,
        }

    def __init__(self, ctx, op, name=None):
        BrlCadObject.__init__(self, name=name)
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


def run(parsedProgram, outputFilename):
    try:
        ctx = Context(outputFilename)

        for stmt in parsedProgram:
            stmt.exec_(ctx)

        ctx.close()

    except ReturnException:
        raise RuntimeError("return from main program!")
