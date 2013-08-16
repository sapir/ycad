#!/usr/bin/python

from __future__ import print_function
from io import StringIO


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

        return ctx.getVar(self.funcName)(ctx, **kwargs)

# no attributes yet:
#class AttrAccessExpr(Expr): pass

class VectorExpr(Expr):
    def __init__(self, exprs):
        self.exprs = exprs



def _blockRepr(block):
    return '{{\n\t{0}\n}}'.format('\n\t'.join(repr(stmt) for stmt in block))

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
        print(val)

class IfStmt(Stmt):
    def __init__(self, condsAndBlocks, elseBlock=None):
        self.condsAndBlocks = condsAndBlocks
        self.elseBlock = elseBlock

    def __repr__(self):
        output = StringIO()

        cond, block = self.condsAndBlocks[0]
        print('if {0} {1}'.format(cond, _blockRepr(block)), file=output)

        for cond, block in self.condsAndBlocks[1:]:
            print('else if {0} {1}'.format(cond, _blockRepr(block)), file=output)

        if self.elseBlock is not None:
            print('else {0}'.format(self.elseBlock), file=output)

        return output.getvalue()

    def exec_(self, ctx):
        for cond, block in self.condsAndBlocks:
            condVal = cond.eval(ctx)
            if condVal:
                for stmt in block:
                    stmt.exec_(ctx)

                break

        else:
            if self.elseBlock is not None:
                for stmt in self.elseBlock:
                    stmt.exec_(ctx)

class FuncDefStmt(Stmt):
    def __init__(self, funcName, paramsList, block):
        self.funcName = funcName
        self.paramsList = paramsList
        self.block = block

    def __repr__(self):
        return('func {0.funcName}({0.paramsList}) {1}'
            .format(self, _blockRepr(self.block)))

    def exec_(self, ctx):
        # TODO: params
        def func(ctx):
            for stmt in self.block:
                stmt.exec_(ctx)

        ctx.setVar(self.funcName, func)
