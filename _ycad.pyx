ctypedef float Standard_Real
ctypedef char* Standard_CString

cdef extern from "gp_Pnt.hxx":
    cdef cppclass gp_Pnt:
        gp_Pnt()
        gp_Pnt(int, int, int)
        Standard_Real X()
        Standard_Real Y()
        Standard_Real Z()

cdef extern from "gp_Vec.hxx":
    cdef cppclass gp_Vec:
        gp_Vec()
        gp_Vec(Standard_Real, Standard_Real, Standard_Real)

cdef extern from "gp_Dir.hxx":
    cdef cppclass gp_Dir:
        gp_Dir()
        gp_Dir(gp_Vec)
        gp_Dir(gp_XYZ)
        gp_Dir(Standard_Real, Standard_Real, Standard_Real)

cdef extern from "gp_Mat.hxx":
    cdef cppclass gp_Mat:
        gp_Mat(Standard_Real, Standard_Real, Standard_Real,
            Standard_Real, Standard_Real, Standard_Real,
            Standard_Real, Standard_Real, Standard_Real)

cdef extern from "gp_Ax1.hxx":
    cdef cppclass gp_Ax1:
        gp_Ax1()
        gp_Ax1(gp_Pnt, gp_Dir)

cdef extern from "gp_XYZ.hxx":
    cdef cppclass gp_XYZ:
        gp_XYZ()

cdef extern from "gp_Trsf.hxx":
    cdef cppclass gp_Trsf:
        gp_Trsf()
        void SetRotation(gp_Ax1, Standard_Real)
        void SetTranslation(gp_Vec)

cdef extern from "gp_GTrsf.hxx":
    cdef cppclass gp_GTrsf:
        gp_GTrsf()
        gp_GTrsf(gp_Mat, gp_XYZ)
        void SetVectorialPart(gp_Mat)
        void SetTranslationPart(gp_XYZ)


cdef class Transform:
    cdef gp_Trsf obj

    def setTranslation(self, vec):
        x, y, z = vec
        self.obj.SetTranslation(gp_Vec(x, y, z))

    def setRotation(self, axis, float angle):
        ax, ay, az = axis
        self.obj.SetRotation(gp_Ax1(gp_Pnt(), gp_Dir(ax, ay, az)), angle)

cdef class GenTransform:
    cdef gp_GTrsf obj

    def setScale(self, sx, sy, sz):
        self.obj.SetVectorialPart(gp_Mat(
            sx, 0, 0,
            0, sy, 0,
            0, 0, sz))


cdef extern from "TopoDS_Shape.hxx":
    cdef cppclass TopoDS_Shape:
        pass

cdef extern from "BRepBuilderAPI_MakeShape.hxx":
    cdef cppclass BRepBuilderAPI_MakeShape:
        const TopoDS_Shape &Shape()



cdef extern from "BRepPrimAPI_MakeBox.hxx":
    cdef cppclass BRepPrimAPI_MakeBox(BRepBuilderAPI_MakeShape):
        BRepPrimAPI_MakeBox(Standard_Real, Standard_Real, Standard_Real)

def box(float x, float y, float z):
    return Shape().setFromMaker(BRepPrimAPI_MakeBox(x, y, z))


cdef extern from "BRepAlgoAPI_Fuse.hxx":
    cdef cppclass BRepAlgoAPI_Fuse(BRepBuilderAPI_MakeShape):
        BRepAlgoAPI_Fuse(TopoDS_Shape, TopoDS_Shape)

cdef extern from "BRepAlgoAPI_Cut.hxx":
    cdef cppclass BRepAlgoAPI_Cut(BRepBuilderAPI_MakeShape):
        BRepAlgoAPI_Cut(TopoDS_Shape, TopoDS_Shape)

cdef extern from "BRepAlgoAPI_Common.hxx":
    cdef cppclass BRepAlgoAPI_Common(BRepBuilderAPI_MakeShape):
        BRepAlgoAPI_Common(TopoDS_Shape, TopoDS_Shape)



cdef class Shape:
    cdef TopoDS_Shape obj

    cdef set_(self, TopoDS_Shape obj):
        self.obj = obj
        return self

    cdef setFromMaker(self, const BRepBuilderAPI_MakeShape &maker):
        self.obj = maker.Shape()
        return self

    def __add__(Shape self, Shape b):
        return Shape().setFromMaker(BRepAlgoAPI_Fuse(self.obj, b.obj))
    
    def __sub__(Shape self, Shape b):
        return Shape().setFromMaker(BRepAlgoAPI_Cut(self.obj, b.obj))

    def __mul__(Shape self, Shape b):
        return Shape().setFromMaker(BRepAlgoAPI_Common(self.obj, b.obj))


cdef extern from "_ycad_helpers.h":
    cdef extern void _writeSTL "writeSTL" (TopoDS_Shape, Standard_CString,
        Standard_Real)

def writeSTL(Shape shape, bytes path, double tol):
    _writeSTL(shape.obj, path, tol)
