#!/usr/bin/python

from ast_ import ReturnException
from itertools import count, chain
import numpy as np
import brlcad


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
        # ctx.wdb.apply_mat(self._name, mat)
        self._mat = np.dot(mat, self._mat)

    def move(self, ctx, x=0, y=0, z=0):
        mat = np.identity(4)
        brlcad.set_mat_deltas(mat, x, y, z)
        self._applyMatrix(ctx, mat)
        return self

    def scale(self, ctx, x=1, y=1, z=1):
        mat = np.identity(4)
        brlcad.set_mat_scale(mat, x, y, z)
        self._applyMatrix(ctx, mat)
        return self

    def rotate(self, ctx, angle, axis):
        mat = np.identity(4)
        brlcad.rotate_mat(mat, axis, np.deg2rad(angle))
        self._applyMatrix(ctx, mat)
        return self

class Cube(BrlCadObject):
    def __init__(self, ctx, s):
        BrlCadObject.__init__(self)

        assert isinstance(s, float)

        self.s = s
        ctx.wdb.mk_rpp(self._name, [0,0,0], [s,s,s])

class Cylinder(BrlCadObject):
    def __init__(self, ctx, h, d=None, d1=None, d2=None):
        BrlCadObject.__init__(self)
        
        assert isinstance(h, float)
        assert d is None or isinstance(d, float)
        assert d1 is None or isinstance(d1, float)
        assert d2 is None or isinstance(d2, float)
        assert (d is not None) ^ (d1 is not None and d2 is not None)
        
        if d is not None:
            ctx.wdb.mk_rcc(self._name, [0,0,0], [0,0,h], d/2.)
        elif d1 is not None and d2 is not None:
            ctx.wdb.mk_trc_h(self._name, [0,0,0], [0,0,h], d1/2., d2/2.)

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


_builtinClasses = dict((c.__name__.lower(), c) for c in
    [Cube, Cylinder])

builtins = dict((f.func_name, f) for f in [])
builtins.update(_builtinClasses)


def run(parsedProgram, outputFilename):
    try:
        ctx = Context(outputFilename)

        for stmt in parsedProgram:
            stmt.exec_(ctx)

        ctx.close()

    except ReturnException:
        raise RuntimeError("return from main program!")
