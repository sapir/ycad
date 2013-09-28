#!/usr/bin/env python

import cairo
from OCC.gp import *
from OCC.TColgp import *
from OCC.BRepBuilderAPI import *
from OCC.GC import *
from OCC.Geom2dAPI import *
from OCC.TopAbs import *
from OCC.TopoDS import *



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

        elif instrType == cairo.PATH_LINE_TO:
            x, y = instrArgs[:2]

            if curPt is None:
                curPt = (x, y)
            else:
                p1 = gp_Pnt2d(curPt[0], curPt[1])
                p2 = gp_Pnt2d(x, y)
                edge = BRepBuilderAPI_MakeEdge2d(p1, p2).Edge()
                wireMaker.Add(edge)
                addedAnything = True

                curPt = (x, y)

        elif instrType == cairo.PATH_CURVE_TO:
            x1, y1, x2, y2, x3, y3 = instrArgs[:6]

            if curPt is None:
                curPt = (x1, y1)
                raise NotImplementedError

            x0, y0 = curPt
            pnts = [gp_Pnt2d(x0, y0), gp_Pnt2d(x1, y1), gp_Pnt2d(x2, y2),
                gp_Pnt2d(x3, y3)]
            
            pntArray = TColgp_Array1OfPnt2d(1, len(pnts))
            for i, p in enumerate(pnts):
                pntArray.SetValue(i + 1, p)
            curve = Geom2dAPI_PointsToBSpline(pntArray).Curve()

            edge = BRepBuilderAPI_MakeEdge2d(curve).Edge()
            wireMaker.Add(edge)
            addedAnything = True

        elif instrType == cairo.PATH_CLOSE_PATH:
            if startPt != curPt:
                p1 = gp_Pnt2d(*curPt)
                p2 = gp_Pnt2d(*startPt)
                edge = BRepBuilderAPI_MakeEdge2d(p1, p2).Edge()
                wireMaker.Add(edge)
                addedAnything = True
                curPt = startPt

            if addedAnything:
                yield wireMaker.Wire()

                # set up a new, empty wireMaker
                wireMaker = BRepBuilderAPI_MakeWire()

                addedAnything = False
                startPt = curPt = None
    
        if startPt is None:
            startPt = curPt

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
