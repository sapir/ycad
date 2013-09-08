#!/usr/bin/env python

from __future__ import absolute_import, print_function
from pyparsing import *
from ast_ import *


# parse actions have no side effects or global variables, so we can enable
# packrat parsing for a great speedup
ParserElement.enablePackrat()


def oneOfKeywords(keywords):
    return MatchFirst(map(Keyword, keywords.split()))

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

unit = MatchFirst(
    CaselessKeyword(unitName).setName(unitName)
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


identifier = Word(alphas + "_", alphanums + "_").setName("identifier")

varName = identifier.copy()
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


namedParam = Group(varName("paramName") + Suppress("=") + expr("paramValue"))
namedParam.setName("named parameter")
posParam = expr + ~FollowedBy("=")
posParam.setName("positional parameter")
paramListWithoutPosParams = delimitedList(namedParam)("namedParams") + FollowedBy(")")
paramListWithPosParams = (delimitedList(posParam)("posParams")
    + ZeroOrMore(Suppress(",") + namedParam)("namedParams") + FollowedBy(")"))
paramList = Optional(paramListWithoutPosParams | paramListWithPosParams)
paramList.setName("parameter list")
funcCall = varName("funcName") + surround("()", paramList)
funcCall.setName("function call")
funcCall.setParseAction(
    lambda s,loc,toks: FuncCallExpr(toks.funcName, toks.get('posParams', []),
        toks.get('namedParams', [])))


mathAtom = ((literal | funcCall | varName | vector)
    + ZeroOrMore(Suppress(".") + funcCall))
mathAtom.setName("math atom")

def mathAtomParseAction(s, loc, toks):
    return reduce(MethodCallExpr, toks)

mathAtom.setParseAction(mathAtomParseAction)

mathExpr = operatorPrecedence(
    mathAtom,
    [
        ("^", 2, opAssoc.RIGHT, binaryOpParseAction),       # exponentiation
        ("-", 1, opAssoc.RIGHT, unaryOpParseAction),        # negation
        (oneOf("* / %"), 2, opAssoc.LEFT, binaryOpParseAction),
        (oneOf("+ -"), 2, opAssoc.LEFT, binaryOpParseAction),
        (oneOf("< <= == != > >="), 2, opAssoc.LEFT, compareOpParseAction),
        ("not", 1, opAssoc.RIGHT, unaryOpParseAction),      # boolean negation
        ("and", 2, opAssoc.LEFT, binaryOpParseAction),
        ("or", 2, opAssoc.LEFT, binaryOpParseAction),
    ])
mathExpr.setName("math expression")

csgExpr = oneOfKeywords("add sub mul")("op") + block("block")
csgExpr.setName("csg expression")
csgExpr.setParseAction(lambda s,loc,toks: CsgExpr(toks.op, toks.block))

expr << (csgExpr | mathExpr)
expr.setName("expression")



assignment = varName("lvalue") + Suppress("=") + expr("rvalue")
assignment.setName("assignment statement")
assignment.setParseAction(lambda s,loc,toks: AssignStmt(toks.lvalue, toks.rvalue))

# TODO: allow named params but only after positional params
paramDef = varName("paramName") + Optional(
    Literal("=").suppress() + literal("default"), default=None)
paramDef.setName("parameter definition")

funcDef = (Keyword("func").suppress() + varName("funcName")
    + surround("()",
        Optional(delimitedList(Group(paramDef)))("params"))
    + block("block"))
funcDef.setName("func statement")
funcDef.setParseAction(
    lambda s,loc,toks: FuncDefStmt(toks.funcName, toks.params, toks.block))


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
forStmt.setParseAction(
    lambda s,loc,toks: ForStmt(toks.iterator, toks.iterable, toks.block))

# TODO: implement
part = Keyword("part") + stringLiteral("partName") + block("block")
part.setName("part statement")

exprStmt = expr.copy().addParseAction(lambda s,loc,toks: ExprStmt(toks[0]))
exprStmt.setName("expression statement")

importStmt = Keyword("import").suppress() + delimitedList(identifier, delim='.')
importStmt.setParseAction(lambda s,loc,toks: ImportStmt(toks.asList()))

stmt << ~FollowedBy(Literal("}") | StringEnd()) + (block | funcDef
    | assignment | simpleStmt | ifStmt | forStmt | part | importStmt | exprStmt)
stmt.setName("statement")


program = ZeroOrMore(stmt) + StringEnd()
program.setName("program")
program.ignore(pythonStyleComment)
program.ignore(cStyleComment)
