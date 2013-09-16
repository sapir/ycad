#!/usr/bin/env python

from __future__ import print_function, division
from io import StringIO
import operator
import itertools
import grammar
from runtime import ReturnException, Module, Block, builtins


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
    def __init__(self, funcName, posParams, namedParams, block):
        self.funcName = funcName.name
        self.posParams = posParams
        self.namedParams = namedParams
        self.block = block

    @property
    def _paramsRepr(self):
        return ', '.join(itertools.chain(
            (repr(expr) for expr in self.posParams),
            ('{0}={1}'.format(nameExpr.name, repr(valExpr))
                for (nameExpr, valExpr) in self.namedParams)))
    
    def __repr__(self):
        s = '{0.funcName}({0._paramsRepr})'.format(self)
        if self.block is not None:
            s += ' ' + repr(self.block)
        return s

    def call(self, ctx, funcObj):
        """Evaluate params in context, and pass them to funcObj."""

        args = [expr.eval(ctx) for expr in self.posParams]

        kwargs = dict((nameExpr.name, valExpr.eval(ctx))
            for (nameExpr, valExpr) in self.namedParams)

        if self.block is None:
            return funcObj(ctx, *args, **kwargs)
        else:
            return funcObj(ctx, *args, block=Block(self.block), **kwargs)

    def eval(self, ctx):
        return self.call(ctx, ctx.getVar(self.funcName))

# no attributes yet:
#class AttrAccessExpr(Expr): pass

class VectorExpr(Expr):
    def __init__(self, exprs):
        self.exprs = exprs

    def eval(self, ctx):
        return [expr.eval(ctx) for expr in self.exprs]

class UnaryOpExpr(Expr):
    OPS = {
            '-' : operator.neg,
            'not' : operator.not_,
        }

    def __init__(self, op, expr):
        self.op = op
        self.expr = expr

    def eval(self, ctx):
        value = self.expr.eval(ctx)
        return (self.OPS[self.op])(value)

class BinaryOpExpr(Expr):
    OPS = {
            '^' :  operator.pow,
            '*' :  operator.mul,
            '/' :  operator.div,
            '%' :  operator.mod,
            '+' :  operator.add,
            '-' :  operator.sub,
            '<' :  operator.lt,
            '<=' : operator.le,
            '==' : operator.eq,
            '!=' : operator.ne,
            '>' :  operator.gt,
            '>=' : operator.ge,
            'and' : operator.and_,
            'or' : operator.or_,
        }

    def __init__(self, op, exprs):
        self.op = op
        self.exprs = exprs

    def eval(self, ctx):
        opFunc = self.OPS[self.op]
        values = [expr.eval(ctx) for expr in self.exprs]
        return reduce(opFunc, values)

class MethodCallExpr(Expr):
    def __init__(self, expr, funcCallExpr):
        self.expr = expr
        self.funcCallExpr = funcCallExpr

    def __repr__(self):
        return '{0}.{1}'.format(repr(self.expr), repr(self.funcCallExpr))

    def eval(self, ctx):
        baseObj = self.expr.eval(ctx)
        method = getattr(baseObj, self.funcCallExpr.funcName)
        return self.funcCallExpr.call(ctx, method)


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

    def exec_(self, ctx):
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
        ctx.sendToBlock(val)

class IfStmt(Stmt):
    def __init__(self, condsAndBlocks, elseBlock=None):
        self.condsAndBlocks = condsAndBlocks
        self.elseBlock = elseBlock

    def __repr__(self):
        output = StringIO()

        cond, block = self.condsAndBlocks[0]
        print(u'if {0} {1}'.format(repr(cond), repr(block)), file=output)

        for cond, block in self.condsAndBlocks[1:]:
            print(u'else if {0} {1}'.format(repr(cond), repr(block)), file=output)

        if self.elseBlock is not None:
            print(u'else {0}'.format(repr(self.elseBlock)), file=output)

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
        # create a new scope for the function
        ctx.pushScope()
        scopeChain = ctx.curScopeChain
        ctx.popScope()

        def func(ctx, *args, **kwargs):
            assert len(args) + len(kwargs) <= self.paramsList, "Too many params!"

            ctx.pushScope(scopeChain)

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
                if default is None:
                    raise ValueError(
                        "Parameter '{0}' got no value in call to func {1}!"
                        .format(name, self.funcName))

                ctx.setVar(name, default.eval(ctx))

            
            try:
                # run block with a default 'add' combination
                defaultResult = builtins['add'](ctx, block=Block(self.block))

            except ReturnException as e:
                return e.value

            finally:
                ctx.popScope()

            # if haven't returned anything else, return the combination
            return defaultResult


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
            ctx.setVar(self.lvalue, i)
            self.block.exec_(ctx)

class ImportStmt(Stmt):
    def __init__(self, pkgPath):
        self.pkgPath = pkgPath

        if len(pkgPath) > 1:
            raise NotImplementedError

    def __repr__(self):
        return 'import {0}'.format('.'.join(pkgPath))

    def exec_(self, ctx):
        assert len(self.pkgPath) == 1
        
        moduleName = self.pkgPath[0]
        
        try:
            return ctx.modules[moduleName]
        except KeyError:
            pass

        modulePath = ctx.findModuleInPath(moduleName)
        program = grammar.program.parseFile(modulePath)
        scope, moduleObj = ctx.execProgram(modulePath, program,
            moduleObjName='module.' + moduleName)
        module = Module(scope)
        ctx.setVar(moduleName, module)

        # cache for next time
        ctx.modules[moduleName] = module


class Program(BlockStmt):
    # essentially a block, but has a different __repr__

    def __repr__(self):
        return '\n\t'.join(repr(stmt) for stmt in self.stmts)
