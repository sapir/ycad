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

class VarNameExpr(Expr):
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name

    def eval(self, ctx):
        return ctx.getVar(self.name)

class FuncCallExpr(Expr):
    def __init__(self, funcName, params):
        self.funcName = funcName.name
        self.params = params

    def __repr__(self):
        return '{0.funcName}({0.params})'.format(self)

    def eval(self, ctx):
        kwargs = dict((nameExpr.name, val.eval(ctx))
            for (nameExpr, val) in self.params)

        return ctx.getVar(self.funcName)(ctx, **kwargs)

# no attributes yet:
#class AttrAccessExpr(Expr): pass

class VectorExpr(Expr):
    def __init__(self, exprs):
        self.exprs = exprs

class CsgExpr(Expr):
    def __init__(self, opName, block):
        self.opName = opName
        self.block = block

    def __repr__(self):
        return '{0.opName} { {0.block} }'.format(self)

    def eval(self, ctx):
        ctx.startCombination(self.opName)
        
        for stmt in self.block:
            stmt.exec_(ctx)

        return ctx.endCombination()


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
        if not isinstance(self.lvalue, VarNameExpr):
            raise NotImplementedError

        ctx.setVar(self.lvalue.name, self.rvalue.eval(ctx))

class ExprStmt(Stmt):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return repr(self.expr)

    def exec_(self, ctx):
        val = self.expr.eval(ctx)
        ctx.curCombination.add(val)

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

class ReturnException(BaseException):
    def __init__(self, value=None):
        self.value = value

class FuncDefStmt(Stmt):
    def __init__(self, funcName, paramsList, block):
        self.funcName = funcName.name
        self.paramsList = paramsList
        self.block = block

    def __repr__(self):
        return('func {0.funcName}({0.paramsList}) {1}'
            .format(self, _blockRepr(self.block)))

    def exec_(self, ctx):
        # TODO: params
        def func(ctx):
            try:
                for stmt in self.block:
                    stmt.exec_(ctx)

            except ReturnException as e:
                return e.value

        ctx.setVar(self.funcName, func)

class ReturnStmt(Stmt):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return 'return {0}'.format(self.expr)

    def exec_(self, ctx):
        raise ReturnException(self.expr.eval(ctx))

class ForStmt(Stmt):
    def __init__(self, lvalue, iterableExpr, block):
        self.lvalue = lvalue.name
        self.iterableExpr = iterableExpr
        self.block = block

    def __repr__(self):
        return 'for {0} in {1} {2}'.format(
            self.lvalue, self.iterableExpr, _blockRepr(self.block))

    def exec_(self, ctx):
        iterable = self.iterableExpr.eval(ctx)
        for i in iterable:
            ctx.setVar(self.lvalue, i.eval(ctx))

            for stmt in self.block:
                stmt.exec_(ctx)
