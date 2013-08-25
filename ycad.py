#!/usr/bin/python

from __future__ import absolute_import, print_function
from pyparsing import *
from ast_ import *
from runtime import *


def oneOfKeywords(keywords):
    return Or(map(Keyword, keywords.split()))

def surround(brackets, grammar):
    left, right = brackets
    return Suppress(left) + grammar + Suppress(right)


literal = Forward()

UNITS = {
    'mm' : 1,
    'cm' : 10,
    'm' : 1000,
    'inch' : 25.4,
}

unit = Or(
    CaselessLiteral(unitName).setName(unitName)
        .setParseAction(replaceWith(unitValue))
    for (unitName, unitValue)
    in UNITS.iteritems())

number = Combine(Word(nums) + Optional(Literal(".") + Word(nums))).setName("number")
number.setParseAction(lambda s,loc,toks: [ float(toks[0]) ])

numberWithUnit = (number + Optional(unit)).setName("number with optional unit")
numberWithUnit.setParseAction(lambda s,loc,toks: toks[0] if len(toks) == 1 else [toks[0]*toks[1]])

vectorLiteral = surround("[]", delimitedList(literal)).setName("vector literal")
vectorLiteral.setParseAction(lambda s,loc,toks: VectorExpr(toks.asList()))

boolLiteral = oneOfKeywords('true false').setName("boolean literal")
boolLiteral.setParseAction(lambda s,loc,toks: eval(toks[0].title()))

stringLiteral = QuotedString(quoteChar='"', escChar='\\', escQuote='\\"').setName("string literal")

literal << (numberWithUnit | vectorLiteral | boolLiteral | stringLiteral)
literal.setName("literal")
literal.setParseAction(lambda s,loc,toks: LiteralExpr(toks[0]))


expr = Forward()
stmt = Forward()

block = surround("{}", ZeroOrMore(stmt)).setName("block")
block.setParseAction(lambda s,loc,toks: BlockStmt(toks.asList()))


varName = Word(alphas + "_", alphanums + "_").setName("variable name")
varName.setParseAction(lambda s,loc,toks: VarNameExpr(toks[0]))

# TODO: attrAccess = varName + OneOrMore("." + varName)

vector = surround("[]", delimitedList(expr)).setName("vector expression")
vector.setParseAction(lambda s,loc,toks: VectorExpr(toks.asList()))

unaryOpParseAction = lambda s,loc,toks: UnaryOpExpr(toks[0][0], toks[0][1])

def binaryOpParseAction(s, loc, toks):
    toks = toks[0]      # toks are grouped. ignore it.

    expr = toks.pop(0)
    while toks:
        op = toks.pop(0)
        expr2 = toks.pop(0)
        expr = BinaryOpExpr(op, [expr, expr2])

    return expr

def compareOpParseAction(s, loc, toks):
    toks = toks[0]      # toks are grouped. ignore it.

    # comparison ops can be chained, i.e. x == y == z means (x == y) and (y == z)
    comparisons = []
    while len(toks) > 1:
        # consume a and op. leave b because it takes part in the next
        # comparison. the while condition means that we stop if b turns out
        # to be the last one, i.e. there is no "next comparison".
        a = toks.pop(0)
        op = toks.pop(0)
        b = toks[0]
        comparisons.append(BinaryOpExpr(op, [a, b]))

    return reduce(lambda a,b: BinaryOpExpr('and', [a,b]), comparisons)


mathExpr = operatorPrecedence(
    (varName | literal | vector),
    [
        ("^", 2, opAssoc.RIGHT, binaryOpParseAction),       # exponentiation
        ("-", 1, opAssoc.RIGHT, unaryOpParseAction),        # negation
        (oneOf("* /"), 2, opAssoc.LEFT, binaryOpParseAction),
        (oneOf("+ -"), 2, opAssoc.LEFT, binaryOpParseAction),
        (oneOf("< <= == != > >="), 2, opAssoc.LEFT, compareOpParseAction),
        ("not", 1, opAssoc.RIGHT, unaryOpParseAction),      # boolean negation
        ("and", 2, opAssoc.LEFT, binaryOpParseAction),
        ("or", 2, opAssoc.LEFT, binaryOpParseAction),
    ])
mathExpr.setName("math expression")

# TODO: allow named params but only after positional params
param = (varName("paramName") + Suppress("=") + expr("paramValue")).setName("parameter")
paramList = Group(Optional(delimitedList(Group(param)))).setName("parameter list")
funcCall = varName("funcName") + surround("()", paramList)("params")
funcCall.setName("function call")
funcCall.setParseAction(lambda s,loc,toks: FuncCallExpr(toks[0], toks[1].asList()))

csgExpr = oneOfKeywords("add sub mul")("op") + block("block")
csgExpr.setName("csg expression")
csgExpr.setParseAction(lambda s,loc,toks: CsgExpr(toks[0], toks[1]))

# binaryOp = expr + oneOf("* / + - == < > <= >=") + expr

parensExpr = surround("()", expr)

# allow method calls after an expression; use funcCall to parse them, but w/o
# its parse action
basicExpr = ((csgExpr | funcCall | mathExpr | parensExpr)
    + ZeroOrMore(Suppress(".") + funcCall.copy().setParseAction()))

def basicExprParseAction(s, loc, toks):
    finalExpr = toks.pop(0)
    
    while toks:
        varName = toks.pop(0)
        paramList = toks.pop(0).asList()
        finalExpr = MethodCallExpr(finalExpr, varName, paramList)
    
    return finalExpr

basicExpr.setParseAction(basicExprParseAction)

expr << basicExpr
expr.setName("expression")


assignment = varName("lvalue") + Suppress("=") + expr("rvalue")
assignment.setName("assignment statement")
assignment.setParseAction(lambda s,loc,toks: AssignStmt(toks[0], toks[1]))

# TODO: allow named params but only after positional params
paramDef = varName("paramName") + Optional(
    Literal("=").suppress() + literal("default"), default=None)
paramDef.setName("parameter definition")

funcDef = (Keyword("func").suppress() + varName("funcName")
    + Group(surround("()",
        Optional(delimitedList(Group(paramDef)))))("params")
    + block("block"))
funcDef.setName("func statement")
funcDef.setParseAction(lambda s,loc,toks: FuncDefStmt(toks[0], toks[1], toks[2]))


def _makeSimpleStmt(keyword, stmtCls):
    stmt = Keyword(keyword).suppress() + expr
    stmt.setName("{0} statement".format(keyword))
    stmt.setParseAction(lambda s,loc,toks: stmtCls(toks[0]))
    return stmt

returnStmt = _makeSimpleStmt('return', ReturnStmt)
simpleStmt = returnStmt

ifStmt = (Keyword("if").suppress() + expr + block
    + ZeroOrMore(Keyword("else").suppress() + Keyword("if").suppress() + expr + block)
    + Optional(Keyword("else").suppress() + block))
ifStmt.setName("if statement")

def ifStmtAction(s, loc, toks):
    elseBlock = toks.pop() if len(toks) % 2 == 1 else None
    condsAndBlocks = zip(*([iter(toks)] * 2))
    return IfStmt(condsAndBlocks, elseBlock)
ifStmt.setParseAction(ifStmtAction)

forStmt = (Keyword("for").suppress() + varName("iterator")
    + Keyword("in").suppress() + expr("iterable")
    + block("block"))
forStmt.setName("for statement")
forStmt.setParseAction(lambda s,loc,toks: ForStmt(toks[0], toks[1], toks[2]))

part = Keyword("part") + stringLiteral("partName") + block("block")
part.setName("part statement")

exprStmt = expr.copy().addParseAction(lambda s,loc,toks: ExprStmt(toks[0]))
exprStmt.setName("expression statement")

stmt << (block | funcDef | assignment | simpleStmt | ifStmt | forStmt | part | exprStmt)


program = ZeroOrMore(stmt)
program.setName("program")
program.ignore(pythonStyleComment)
program.ignore(cStyleComment)

if __name__ == '__main__':
    import sys
    import os
    from subprocess import check_call

    try:
        filename, outputName = sys.argv[1:]
    except:
        filename, = sys.argv[1:]
        outputName = os.path.splitext(filename)[0] + '.stl'

    dbName = 'temp.g'

    print('Parsing...', file=sys.stderr)
    parsed = program.parseFile(filename)
    print('Creating BRL-CAD database ({0})...'.format(dbName), file=sys.stderr)
    run(parsed, dbName)

    print('Converting to STL...', file=sys.stderr)
    check_call(['g-stl',
        '-b',          # binary STL
        '-a', '0.05',  # 0.05mm tolerance
        '-o', outputName,
        dbName,
        'main'])       # 'main' is name of main object in our DB

    print('OK!', file=sys.stderr)
