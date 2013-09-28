#!/usr/bin/env python

import cairo
from OCC.gp import *
from OCC.TColgp import *
from OCC.BRepBuilderAPI import *
from OCC.GC import *
from OCC.Geom2dAPI import *
from OCC.TopAbs import *
from OCC.TopoDS import *



def make2DLine(p1, p2):
    gpP1 = gp_Pnt2d(*p1)
    gpP2 = gp_Pnt2d(*p2)
    return BRepBuilderAPI_MakeEdge2d(gpP1, gpP2).Edge()

def makeArray1OfPnt2d(pnts):
    arr = TColgp_Array1OfPnt2d(1, len(pnts))
    for i, p in enumerate(pnts):
        arr.SetValue(i + 1, p)

    return arr

def make2DCurve(p0, p1, p2, p3):
    pnts = [gp_Pnt2d(*p) for p in [p0, p1, p2, p3]]
    pntArray = makeArray1OfPnt2d(pnts)
    curve = Geom2dAPI_PointsToBSpline(pntArray).Curve()
    return BRepBuilderAPI_MakeEdge2d(curve).Edge()

def cairoPathToOccWires(path):
    wireMaker = BRepBuilderAPI_MakeWire()

    startPt = None
    curPt = None
    addedAnything = False
    
    for pathInstr in path:
        instrType, instrArgs = pathInstr

        if instrType == cairo.PATH_MOVE_TO:
            x, y = instrArgs[:2]
            curPt = (x, y)
            startPt = curPt     # move_to begins a new sub-path

        elif instrType == cairo.PATH_LINE_TO:
            x, y = instrArgs[:2]

            if curPt is None:
                curPt = (x, y)
            else:
                wireMaker.Add(make2DLine(curPt, (x, y)))
                addedAnything = True

                curPt = (x, y)

        elif instrType == cairo.PATH_CURVE_TO:
            x1, y1, x2, y2, x3, y3 = instrArgs[:6]

            if curPt is None:
                curPt = (x1, y1)
                raise NotImplementedError

            wireMaker.Add(make2DCurve(curPt, (x1, y1), (x2, y2), (x3, y3)))
            addedAnything = True
            curPt = (x3, y3)

        elif instrType == cairo.PATH_CLOSE_PATH:
            if startPt is not None and curPt is not None and startPt != curPt:
                wireMaker.Add(make2DLine(curPt, startPt))
                addedAnything = True
                curPt = startPt

            if addedAnything:
                yield wireMaker.Wire()

                # set up a new, empty wireMaker
                wireMaker = BRepBuilderAPI_MakeWire()

                addedAnything = False
            
            startPt = None
    
    # we shouldn't have anything left that wasn't yielded, because the last
    # instr should have been a close_path
    assert instrType == cairo.PATH_CLOSE_PATH, \
        "Last path instruction should be a PATH_CLOSE_PATH!"

def cairoPathToOccShape(path):
    builder = TopoDS_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)

    for wire in cairoPathToOccWires(path):
        face = BRepBuilderAPI_MakeFace(wire).Face()
        builder.Add(compound, face)

    return compound



class TextWireMaker(object):
    _SURFACE_SIZE = 1024

    def __init__(self):
        surface = cairo.SVGSurface(None, self._SURFACE_SIZE, self._SURFACE_SIZE)
        self.ctx = cairo.Context(surface)

    def makeWire(self, text):
        # TODO: allow setting font options
        self.ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_NORMAL)
        self.ctx.set_font_size(40)

        path = self._getTextPath(text)
        return cairoPathToOccShape(path)

    def _getTextPath(self, text):
        self.ctx.new_path()
        self.ctx.text_path(text)
        return self.ctx.copy_path()
