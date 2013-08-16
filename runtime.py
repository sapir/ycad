#!/usr/bin/python

from ast_ import ReturnException


def cube(ctx, s):
    assert isinstance(s, float)
    return 'cube(size={0});'.format(s)

builtins = dict((f.func_name, f)
    for f in [cube])


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
