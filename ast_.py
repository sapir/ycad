#!/usr/bin/python

from pprint import *

class Expr:
    def eval(self, ctx):
        raise NotImplementedError

class LiteralExpr(Expr):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return repr(self.value)

    def eval(self, ctx):
        return self.value

class FuncCallExpr(Expr):
    def __init__(self, funcName, params):
        self.funcName = funcName
        self.params = params

    def __repr__(self):
        return '{0.funcName}({0.params})'.format(self)

    def eval(self, ctx):
        kwargs = dict((name, val.eval(ctx))
            for (name, val) in self.params)

        return ctx.getVar(self.funcName)(**kwargs)

# no attributes yet:
#class AttrAccessExpr(Expr): pass

class VectorExpr(Expr):
    def __init__(self, exprs):
        self.exprs = exprs



class Stmt:
    def exec_(self, ctx):
        raise NotImplementedError

class AssignStmt(Stmt):
    def __init__(self, lvalue, rvalue):
        self.lvalue = lvalue
        self.rvalue = rvalue

    def __repr__(self):
        return '{0.lvalue} = {0.rvalue}'.format(self)

    def exec_(self, ctx):
        if not isinstance(self.lvalue, basestring):
            raise NotImplementedError

        ctx.setVar(self.lvalue, self.rvalue.eval(ctx))

class ShowStmt(Stmt):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return 'show {0.value}'.format(self)

    def exec_(self, ctx):
        val = self.value.eval(ctx)
        print val
