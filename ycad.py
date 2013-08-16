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

number = Combine(Word(nums) + Optional(Literal(".") + Word(nums)))
number.setParseAction(lambda s,loc,toks: [ float(toks[0]) ])

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

numberWithUnit = number + unit
numberWithUnit.setParseAction(lambda s,loc,toks: [ toks[0]*toks[1] ])

vectorLiteral = Group(surround("[]", delimitedList(literal)))

boolLiteral = oneOfKeywords('true false')
boolLiteral.setParseAction(lambda s,loc,toks: eval(toks[0].title()))

stringLiteral = QuotedString(quoteChar='"', escChar='\\', escQuote='\\"')

literal << (numberWithUnit | number | vectorLiteral | boolLiteral | stringLiteral)
literal.setParseAction(lambda s,loc,toks: LiteralExpr(toks[0]))


expr = Forward()

varName = Word(alphas + "_", alphanums + "_")
varName.setParseAction(lambda s,loc,toks: VarNameExpr(toks[0]))

# TODO: allow named params but only after positional params
param = varName + Literal("=").suppress() + expr
paramList = Group(Optional(delimitedList(Group(param))))
funcCall = varName + surround("()", paramList)
funcCall.setParseAction(lambda s,loc,toks: FuncCallExpr(toks[0], toks[1].asList()))

attrAccess = varName + OneOrMore("." + varName)

vector = Group(surround("[]", delimitedList(expr)))

exprBlock = Literal("{") + ZeroOrMore(expr) + "}"
csgExpr = oneOfKeywords("union difference intersect add sub mul") + exprBlock

# binaryOp = expr + oneOf("* / + - == < > <= >=") + expr

transform = oneOfKeywords("translate rotate scale move") + expr + expr
shortTransform = oneOfKeywords("dx dy dz rot sx sy sz") + surround("()", expr) + expr

parensExpr = surround("()", expr)

expr << (csgExpr | transform | shortTransform | funcCall | attrAccess
    | literal | vector | varName | parensExpr)



stmt = Forward()

assignment = varName + Suppress("=") + expr
assignment.setParseAction(lambda s,loc,toks: AssignStmt(toks[0], toks[1]))

block = Group(surround("{}", ZeroOrMore(stmt)))

# TODO: allow named params but only after positional params
paramDef = varName + Optional(Literal("=").suppress() + literal)
funcDef = (Keyword("func").suppress() + varName
    + Group(surround("()",
        Group(Optional(delimitedList(Group(paramDef))))))
    + block)
funcDef.setParseAction(lambda s,loc,toks: FuncDefStmt(toks[0], toks[1], toks[2]))


def _makeSimpleStmt(keyword, stmtCls):
    stmt = Keyword(keyword).suppress() + expr
    stmt.setParseAction(lambda s,loc,toks: stmtCls(toks[0]))
    return stmt

showStmt = _makeSimpleStmt('show', ShowStmt)
returnStmt = _makeSimpleStmt('return', ReturnStmt)
simpleStmt = showStmt | returnStmt

ifStmt = (Keyword("if").suppress() + expr + block
    + ZeroOrMore(Keyword("else").suppress() + Keyword("if").suppress() + expr + block)
    + Optional(Keyword("else").suppress() + block))

def ifStmtAction(s, loc, toks):
    elseBlock = toks.pop() if len(toks) % 2 == 1 else None
    condsAndBlocks = zip(*([iter(toks)] * 2))
    return IfStmt(condsAndBlocks, elseBlock)
ifStmt.setParseAction(ifStmtAction)

forStmt = (Keyword("for").suppress() + varName
    + Keyword("in").suppress() + expr
    + block)
forStmt.setParseAction(lambda s,loc,toks: ForStmt(toks[0], toks[1], toks[2]))

part = Keyword("part") + stringLiteral + block

stmt << (block | funcDef | assignment | simpleStmt | ifStmt | forStmt | part)


program = ZeroOrMore(stmt)
program.ignore(Literal("#") + restOfLine)


import sys
filename, = sys.argv[1:]
parsed = program.parseFile(filename)
run(parsed)
