#!/usr/bin/env python

import cairo
import networkx
from OCC.gp import *
from OCC.TColgp import *
from OCC.BRepBuilderAPI import *
from OCC.GC import *
from OCC.Geom2d import *
from OCC.TopAbs import *
from OCC.TopoDS import *
from OCC.BRepClass import *
from OCC.Precision import Precision_Confusion



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
    curve = Geom2d_BezierCurve(pntArray)
    return BRepBuilderAPI_MakeEdge2d(curve.GetHandle()).Edge()

def cairoPathToOccWiresAndPts(path):
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
                assert startPt is not None
                yield (wireMaker.Wire(), startPt)

                # set up a new, empty wireMaker
                wireMaker = BRepBuilderAPI_MakeWire()

                addedAnything = False
            
            startPt = None
    
    # we shouldn't have anything left that wasn't yielded, because the last
    # instr should have been a close_path
    assert instrType == cairo.PATH_CLOSE_PATH, \
        "Last path instruction should be a PATH_CLOSE_PATH!"

def isPointIn2DFace(point, face):
    classifier = BRepClass_FClassifier(BRepClass_FaceExplorer(face),
        gp_Pnt2d(*point), Precision_Confusion())

    return classifier.State() == TopAbs_IN

def isPointIn2DWire(point, wire):
    face = BRepBuilderAPI_MakeFace(wire).Face()
    return isPointIn2DFace(point, face)

def makeFaceFromWires(wires):
    wireIter = iter(wires)
    faceMaker = BRepBuilderAPI_MakeFace(next(wireIter))
    for wire in wireIter:
        faceMaker.Add(wire)

    return faceMaker.Face()

def groupNonIntersectingWiresIntoFaces(wiresAndPts):
    # build directed graph of wires A->B where contains B
    containmentGraph = networkx.DiGraph()

    # add all wires, even those not participating in edges
    containmentGraph.add_nodes_from(wire for (wire, _) in wiresAndPts)

    containmentGraph.add_edges_from(
        (aWire, bWire)
        for (aWire, _) in wiresAndPts
        for (bWire, bPt) in wiresAndPts
        if aWire is not bWire and isPointIn2DWire(bPt, aWire))

    # find wires that aren't contained in any other wires
    rootWires = [wire for (wire, inDeg) in containmentGraph.in_degree_iter()
        if inDeg == 0]

    # build faces starting with root wires
    faces = []
    for rootWire in rootWires:
        faceMaker = BRepBuilderAPI_MakeFace(rootWire)

        def _addWireToFace(wire, level):
            # the wire direction needs to be reversed for every other level,
            # to correctly bound the inside of the face
            wireToAdd = TopoDS_wire(wire.Reversed()) if level % 2 == 1 else wire
            faceMaker.Add(wireToAdd)

            for childWire in containmentGraph.successors(wire):
                _addWireToFace(childWire, level + 1)

        for childWire in containmentGraph.successors(rootWire):
            _addWireToFace(childWire, 1)

        faces.append(faceMaker.Face())

    return faces

def makeCompound(parts):
    builder = TopoDS_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)

    for part in parts:
        builder.Add(compound, part)

    return compound

def cairoPathToOccShape(path):
    wiresAndPts = list(cairoPathToOccWiresAndPts(path))
    faces = groupNonIntersectingWiresIntoFaces(wiresAndPts)
    return makeCompound(faces)



class TextWireMaker(object):
    _SURFACE_SIZE = 1024

    def __init__(self):
        surface = cairo.SVGSurface(None, self._SURFACE_SIZE, self._SURFACE_SIZE)
        self.ctx = cairo.Context(surface)

    def makeWire(self, text, fontName, fontSize, bold=False, italic=False):
        slant = cairo.FONT_SLANT_ITALIC if italic else cairo.FONT_SLANT_NORMAL
        weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
        self.ctx.select_font_face(fontName, slant, weight)
        self.ctx.set_font_size(fontSize)

        path = self._getTextPath(text)
        return cairoPathToOccShape(path)

    def _getTextPath(self, text):
        self.ctx.new_path()

        self.ctx.text_path(text)

        # invert y direction, to match coordinates used for 3D
        self.ctx.scale(1, -1)

        return self.ctx.copy_path()
