#!/usr/bin/python

from __future__ import print_function
from io import StringIO


class Expr(object):
    def eval(self, ctx):
        raise NotImplementedError

class LiteralExpr(Expr):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return repr(self.value)

    def eval(self, ctx):
        val = self.value

        if isinstance(val, Expr): # e.g. VectorExpr
            val = val.eval(ctx)

        return val

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

    def eval(self, ctx):
        return [expr.eval(ctx) for expr in self.exprs]

class CsgExpr(Expr):
    def __init__(self, opName, block):
        self.opName = opName
        self.block = block

    def __repr__(self):
        return '{0.opName} { {0.block} }'.format(self)

    def eval(self, ctx):
        ctx.startCombination(self.opName)
        self.block.exec_(ctx)
        return ctx.endCombination()

class MethodCallExpr(Expr):
    def __init__(self, expr, methodName, params):
        self.expr = expr
        self.methodName = methodName
        self.params = params

    def __repr__(self):
        return '{0}.{1}({2})'.format(repr(self.expr), repr(self.methodName),
            repr(self.params))

    def eval(self, ctx):
        baseObj = self.expr.eval(ctx)

        kwargs = dict((nameExpr.name, val.eval(ctx))
            for (nameExpr, val) in self.params)

        method = getattr(baseObj, self.methodName.name)

        return method(ctx, **kwargs)


class Stmt(object):
    def exec_(self, ctx):
        raise NotImplementedError

class BlockStmt(Stmt):
    def __init__(self, stmts):
        self.stmts = stmts

    def __repr__(self):
        return '{{\n\t{0}\n}}'.format(
            '\n\t'.join(
                repr(stmt) for stmt in self.stmts))

    def exec_(self,ctx):
        for stmt in self.stmts:
            stmt.exec_(ctx)

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
        print('if {0} {1}'.format(cond, repr(block)), file=output)

        for cond, block in self.condsAndBlocks[1:]:
            print('else if {0} {1}'.format(cond, repr(block)), file=output)

        if self.elseBlock is not None:
            print('else {0}'.format(self.elseBlock), file=output)

        return output.getvalue()

    def exec_(self, ctx):
        for cond, block in self.condsAndBlocks:
            condVal = cond.eval(ctx)
            if condVal:
                block.exec_(ctx)
                break

        else:
            if self.elseBlock is not None:
                self.elseBlock.exec_(ctx)

class ReturnException(BaseException):
    def __init__(self, value=None):
        self.value = value

class FuncDefStmt(Stmt):
    def __init__(self, funcName, paramsList, block):
        self.funcName = funcName.name
        self.paramsList = [(nameExpr.name, defaultExpr)
            for (nameExpr, defaultExpr) in paramsList]
        self.block = block

    def __repr__(self):
        return ('func {0.funcName}({0.paramsList}) {1}'
            .format(self, repr(self.block)))

    def exec_(self, ctx):
        def func(ctx, *args, **kwargs):
            assert len(args) + len(kwargs) <= self.paramsList, "Too many params!"

            paramsIter = iter(self.paramsList)
            
            # put args first in zip() so that when args ends before paramsIter,
            # we don't accidentally consume an extra param from paramsIter
            for arg, (name, _) in zip(args, paramsIter):
                # TODO: scope; new combination
                ctx.setVar(name, arg)

            namedParamsLeft = dict(paramsIter)
            for argName, val in kwargs.iteritems():
                namedParamsLeft.pop(argName)
                ctx.setVar(argName, val)

            for name, default in namedParamsLeft.iteritems():
                # default is a parsed expression, or None if no default value
                if default is not None:
                    ctx.setVar(name, default.eval(ctx))

            try:
                self.block.exec_(ctx)

            except ReturnException as e:
                return e.value

        func.func_name = self.funcName

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
            self.lvalue, self.iterableExpr, repr(self.block))

    def exec_(self, ctx):
        iterable = self.iterableExpr.eval(ctx)
        for i in iterable:
            ctx.setVar(self.lvalue, i.eval(ctx))
            self.block.exec_(ctx)
