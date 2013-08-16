#!/usr/bin/python

from ast_ import ReturnException


def cube(ctx, s):
    assert isinstance(s, float)
    return 'cube(size={0});'.format(s)

def cylinder(ctx, h, d, d1=None, d2=None):
    assert isinstance(h, float)
    assert d is None or isinstance(d, float)
    assert d1 is None or isinstance(d1, float)
    assert d2 is None or isinstance(d2, float)
    assert (d is not None) ^ (d1 is not None and d2 is not None)
    
    if d is not None:
        return 'cylinder(h={0}, r={1});'.format(h, d/2.)
    elif d1 is not None and d2 is not None:
        return 'cylinder(h={0}, r1={1}, r2={2});'.format(h, d1/2., d2/2.)

builtins = dict((f.func_name, f)
    for f in [cube, cylinder])


class Context:
    def __init__(self):
        self.scope = {}

    def getVar(self, name):
        try:
            return self.scope[name]
        except LookupError:
            return builtins[name]

    def setVar(self, name, value):
        self.scope[name] = value


def run(parsedProgram):
    try:
        ctx = Context()
        for stmt in parsedProgram:
            stmt.exec_(ctx)

    except ReturnException:
        raise RuntimeError("return from main program!")
