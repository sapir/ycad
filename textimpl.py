#!/usr/bin/env python

import cairo
from OCC.BRepBuilderAPI import *
from OCC.GC import *



def cairoPathToOccShape(path):
    raise NotImplementedError


class TextMaker(object):
    _SURFACE_SIZE = 1024

    def __init__(self):
        surface = cairo.SVGSurface(None, self._SURFACE_SIZE, self._SURFACE_SIZE)
        self.ctx = cairo.Context(surface)

    def makeWire(self, text):
        # TODO: allow setting font options
        ctx.select_font_face("Sans", cairo.FONT_SLANT_NORMAL,
            cairo.FONT_WEIGHT_NORMAL)
        ctx.set_font_size(40)

        path = self._getTextPath(text)
        return cairoPathToOccShape(path)

    def _getTextPath(self, text):
        self.ctx.new_path()
        self.ctx.text_path(text)
        return self.ctx.copy_path()
