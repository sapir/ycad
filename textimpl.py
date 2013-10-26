#!/usr/bin/env python

import cairo
import networkx
import _ycad


def cairoPathToOccWiresAndPts(path):
    edgesInCurWire = []

    startPt = None
    curPt = None
    
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
                edgesInCurWire.append(_ycad.segment2D(curPt, (x, y)))

                curPt = (x, y)

        elif instrType == cairo.PATH_CURVE_TO:
            x1, y1, x2, y2, x3, y3 = instrArgs[:6]

            if curPt is None:
                curPt = (x1, y1)
                raise NotImplementedError

            curve = _ycad.BezierCurve(
                [curPt, (x1, y1), (x2, y2), (x3, y3)])
            edgesInCurWire.append(curve.makeEdge())
            curPt = (x3, y3)

        elif instrType == cairo.PATH_CLOSE_PATH:
            if startPt is not None and curPt is not None and startPt != curPt:
                edgesInCurWire.append(_ycad.segment2D(curPt, startPt))
                curPt = startPt

            if edgesInCurWire:
                assert startPt is not None
                yield (_ycad.wire(edgesInCurWire), startPt)

                # get ready for next wire
                edgesInCurWire = []
            
            startPt = None
    
    # we shouldn't have anything left that wasn't yielded, because the last
    # instr should have been a close_path
    assert instrType == cairo.PATH_CLOSE_PATH, \
        "Last path instruction should be a PATH_CLOSE_PATH!"
    assert not edgesInCurWire

def groupNonIntersectingWiresIntoFaces(wiresAndPts):
    # build directed graph of wires A->B where contains B
    containmentGraph = networkx.DiGraph()

    # add all wires, even those not participating in edges
    containmentGraph.add_nodes_from(wire for (wire, _) in wiresAndPts)

    containmentGraph.add_edges_from(
        (aWire, bWire)
        for (aWire, _) in wiresAndPts
        for (bWire, bPt) in wiresAndPts
        if aWire is not bWire and aWire.contains2DPoint(bPt))

    faces = []
    while True:
        # find wires that aren't contained in any other wires
        rootWires = [wire
            for (wire, inDeg) in containmentGraph.in_degree_iter()
            if inDeg == 0]

        if not rootWires:
            # we're done here
            break

        # build faces from the root wires + their inner loops. then remove
        # all of those, so that in the next iteration, any inner inner loops
        # can become root wires.
        for rootWire in rootWires:
            wires = [rootWire] + containmentGraph.successors(rootWire)
            containmentGraph.remove_nodes_from(wires)
            faces.append(_ycad.face(wires))

    return faces

def cairoPathToOccShape(path):
    wiresAndPts = list(cairoPathToOccWiresAndPts(path))
    faces = groupNonIntersectingWiresIntoFaces(wiresAndPts)
    return _ycad.compound(faces)



class TextShapeMaker(object):
    _SURFACE_SIZE = 1024

    def __init__(self):
        surface = cairo.SVGSurface(None, self._SURFACE_SIZE, self._SURFACE_SIZE)
        self.ctx = cairo.Context(surface)

    def make(self, text, fontName, fontSize, bold=False, italic=False):
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
