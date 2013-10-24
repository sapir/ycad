ctypedef float Standard_Real
ctypedef char* Standard_CString

cdef extern from "gp_Pnt.hxx":
    cdef cppclass gp_Pnt:
        gp_Pnt(int, int, int)
        Standard_Real X()
        Standard_Real Y()
        Standard_Real Z()

cdef extern from "TopoDS_Shape.hxx":
    cdef cppclass TopoDS_Shape:
        pass

cdef class Shape:
    cdef TopoDS_Shape obj



cdef extern from "BRepPrimAPI_MakeBox.hxx":
    cdef cppclass BRepPrimAPI_MakeBox:
        BRepPrimAPI_MakeBox(Standard_Real, Standard_Real, Standard_Real)
        const TopoDS_Shape &Shape()

def box(float x, float y, float z):
    s = Shape()
    s.obj = BRepPrimAPI_MakeBox(x, y, z).Shape()
    return s


cdef extern from "_ycad_helpers.h":
    cdef extern void _writeSTL "writeSTL" (TopoDS_Shape, Standard_CString,
        Standard_Real)

def writeSTL(Shape shape, bytes path, double tol):
    _writeSTL(shape.obj, path, tol)
