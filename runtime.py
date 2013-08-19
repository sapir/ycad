#!/usr/bin/python

from ast_ import ReturnException
from itertools import count, chain
import brlcad


class Context:
    def __init__(self):
        self.scope = {}
        self.wdb = brlcad.wdb_fopen('temp.g')
        self.wdb.mk_id("ycad temp database")

    def __del__(self):
        self.wdb.close()

    def getVar(self, name):
        try:
            return self.scope[name]
        except LookupError:
            global builtins
            return builtins[name]

    def setVar(self, name, value):
        self.scope[name] = value


_autoNameCounter = count(1)
def _autoname():
    return 'autoname.{0}'.format(next(_autoNameCounter))

class BrlCadObject:
    def __init__(self):
        self._name = _autoname()

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


_builtinClasses = dict((c.__name__.lower(), c) for c in
    [Cube, Cylinder])

builtins = dict((f.func_name, f) for f in [])
builtins.update(_builtinClasses)


def run(parsedProgram):
    try:
        ctx = Context()
        for stmt in parsedProgram:
            stmt.exec_(ctx)

    except ReturnException:
        raise RuntimeError("return from main program!")
