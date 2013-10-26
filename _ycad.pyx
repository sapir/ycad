from libcpp cimport bool


ctypedef float Standard_Real
ctypedef char* Standard_CString


cdef extern from "gp_Pnt.hxx":
    cdef cppclass gp_Pnt:
        gp_Pnt()
        gp_Pnt(Standard_Real, Standard_Real, Standard_Real)
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

cdef extern from "gp_Ax2.hxx":
    cdef cppclass gp_Ax2:
        gp_Ax2()
        gp_Ax2(gp_Pnt P, gp_Dir N, gp_Dir Vx)

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

cdef extern from "TColgp_Array2OfPnt.hxx":
    cdef cppclass TColgp_Array2OfPnt:
        TColgp_Array2OfPnt(int, int, int, int)

cdef extern from "gp.hxx" namespace "gp":
    gp_Pnt Origin()
    gp_Dir DX()
    gp_Dir DY()
    gp_Dir DZ()
    gp_Ax1 OX()
    gp_Ax1 OY()
    gp_Ax1 OZ()
    gp_Ax2 XOY()
    gp_Ax2 ZOX()
    gp_Ax2 YOZ()


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


cdef extern from "gp_Circ.hxx":
    cdef cppclass gp_Circ:
        gp_Circ()
        gp_Circ(gp_Ax2, Standard_Real)

cdef extern from "Geom_Surface.hxx":
    cdef cppclass Geom_Surface:
        pass

cdef extern from "Geom_BezierSurface.hxx":
    cdef cppclass Geom_BezierSurface(Geom_Surface):
        Geom_BezierSurface(TColgp_Array2OfPnt)
        void SetPole(int, int, gp_Pnt)

cdef extern from "Handle_Geom_Surface.hxx":
    cdef cppclass Handle_Geom_Surface:
        Handle_Geom_Surface()
        void Set "operator=" (Geom_Surface*)

cdef class BezierSurface:
    cdef Geom_BezierSurface *thisptr

    def __cinit__(self, pnts):
        cdef int rows = len(pnts)
        cdef int cols = len(pnts[0])
        cdef float x, y, z
        
        if not all(len(row) == cols for row in pnts):
            raise ValueError("pnts parameter must be a rectangular array")
        
        self.thisptr = new Geom_BezierSurface(
            TColgp_Array2OfPnt(0, rows - 1, 0, cols - 1))
        for i in xrange(rows):
            for j in xrange(cols):
                x, y, z = pnts[i][j]
                self.thisptr.SetPole(i, j, gp_Pnt(x, y, z))

    def __dealloc__(self):
        del self.thisptr

    def makeFace(self, float umin, float umax, float vmin, float vmax,
        float tolDegen):

        cdef Handle_Geom_Surface handle
        handle.Set(self.thisptr)

        return Shape().setFromMaker(BRepBuilderAPI_MakeFace(
            handle, umin, umax, vmin, vmax, tolDegen))


cdef extern from "TopoDS_Shape.hxx":
    cdef cppclass TopoDS_Shape:
        pass

cdef extern from "TopoDS_Edge.hxx":
    cdef cppclass TopoDS_Edge(TopoDS_Shape):
        pass

cdef extern from "TopoDS_Wire.hxx":
    cdef cppclass TopoDS_Wire(TopoDS_Shape):
        pass

cdef extern from "TopoDS_Face.hxx":
    cdef cppclass TopoDS_Face(TopoDS_Shape):
        pass

cdef extern from "TopoDS.hxx" namespace "TopoDS":
    cdef TopoDS_Edge Edge(TopoDS_Shape)
    cdef TopoDS_Wire Wire(TopoDS_Shape)
    cdef TopoDS_Face Face(TopoDS_Shape)


cdef extern from "BRepBuilderAPI_MakeShape.hxx":
    cdef cppclass BRepBuilderAPI_MakeShape:
        const TopoDS_Shape &Shape()

cdef extern from "BRepBuilderAPI_MakeEdge.hxx":
    cdef cppclass BRepBuilderAPI_MakeEdge(BRepBuilderAPI_MakeShape):
        BRepBuilderAPI_MakeEdge(gp_Pnt, gp_Pnt)
        BRepBuilderAPI_MakeEdge(gp_Circ)
        TopoDS_Edge Edge()

cdef extern from "BRepBuilderAPI_MakeWire.hxx":
    cdef cppclass BRepBuilderAPI_MakeWire(BRepBuilderAPI_MakeShape):
        BRepBuilderAPI_MakeWire()
        BRepBuilderAPI_MakeWire(TopoDS_Edge)
        TopoDS_Wire Wire()

        void Add(TopoDS_Edge)

cdef extern from "BRepBuilderAPI_MakeFace.hxx":
    cdef cppclass BRepBuilderAPI_MakeFace(BRepBuilderAPI_MakeShape):
        BRepBuilderAPI_MakeFace()
        BRepBuilderAPI_MakeFace(TopoDS_Wire)
        BRepBuilderAPI_MakeFace(Handle_Geom_Surface, Standard_Real, Standard_Real,
            Standard_Real, Standard_Real, Standard_Real)
        TopoDS_Face Face()

        void Add(TopoDS_Wire)


cdef extern from "BRepAlgoAPI_Fuse.hxx":
    cdef cppclass BRepAlgoAPI_Fuse(BRepBuilderAPI_MakeShape):
        BRepAlgoAPI_Fuse(TopoDS_Shape, TopoDS_Shape)

cdef extern from "BRepAlgoAPI_Cut.hxx":
    cdef cppclass BRepAlgoAPI_Cut(BRepBuilderAPI_MakeShape):
        BRepAlgoAPI_Cut(TopoDS_Shape, TopoDS_Shape)

cdef extern from "BRepAlgoAPI_Common.hxx":
    cdef cppclass BRepAlgoAPI_Common(BRepBuilderAPI_MakeShape):
        BRepAlgoAPI_Common(TopoDS_Shape, TopoDS_Shape)

cdef extern from "BRepBuilderAPI_Transform.hxx":
    cdef cppclass BRepBuilderAPI_Transform(BRepBuilderAPI_MakeShape):
        BRepBuilderAPI_Transform(TopoDS_Shape, gp_Trsf, bool)

cdef extern from "BRepBuilderAPI_GTransform.hxx":
    cdef cppclass BRepBuilderAPI_GTransform(BRepBuilderAPI_MakeShape):
        BRepBuilderAPI_GTransform(TopoDS_Shape, gp_GTrsf, bool)


cdef extern from "BRepPrimAPI_MakeRevol.hxx":
    cdef cppclass BRepPrimAPI_MakeRevol(BRepBuilderAPI_MakeShape):
        BRepPrimAPI_MakeRevol(TopoDS_Shape, gp_Ax1, Standard_Real D,
            bool Copy)
        BRepPrimAPI_MakeRevol(TopoDS_Shape, gp_Ax1, bool Copy)

cdef extern from "BRepPrimAPI_MakePrism.hxx":
    cdef cppclass BRepPrimAPI_MakePrism(BRepBuilderAPI_MakeShape):
        BRepPrimAPI_MakePrism(TopoDS_Shape, gp_Vec, bool Copy)


cdef class Shape:
    cdef TopoDS_Shape obj

    cdef set_(self, TopoDS_Shape obj):
        self.obj = obj
        return self

    cdef setFromMaker(self, const BRepBuilderAPI_MakeShape &maker):
        self.obj = maker.Shape()
        return self

    cdef TopoDS_Edge edge(self):
        return Edge(self.obj)

    cdef TopoDS_Wire wire(self):
        return Wire(self.obj)

    cdef TopoDS_Face face(self):
        return Face(self.obj)

    def __add__(Shape self, Shape b):
        return Shape().setFromMaker(BRepAlgoAPI_Fuse(self.obj, b.obj))
    
    def __sub__(Shape self, Shape b):
        return Shape().setFromMaker(BRepAlgoAPI_Cut(self.obj, b.obj))

    def __mul__(Shape self, Shape b):
        return Shape().setFromMaker(BRepAlgoAPI_Common(self.obj, b.obj))

    def applyTransform(Shape self, Transform transform):
        self.setFromMaker(BRepBuilderAPI_Transform(
            # False = don't copy
            self.obj, transform.obj, False))

    def applyGTransform(Shape self, GenTransform gtransform):
        self.setFromMaker(BRepBuilderAPI_GTransform(
            # False = don't copy
            self.obj, gtransform.obj, False))

    def withTransform(Shape self, Transform transform):
        return Shape().setFromMaker(BRepBuilderAPI_Transform(
            # True = make a copy
            self.obj, transform.obj, True))

    def withGTransform(Shape self, GenTransform gtransform):
        return Shape().setFromMaker(BRepBuilderAPI_GTransform(
            # True = make a copy
            self.obj, gtransform.obj, True))

    def revolve(Shape self, float angle):
        return Shape().setFromMaker(BRepPrimAPI_MakeRevol(
            self.obj, OY(), angle, True))

    def extrudeStraight(Shape self, float h):
        return Shape().setFromMaker(BRepPrimAPI_MakePrism(
            self.obj, gp_Vec(0, 0, h), True))


def segment(p1, p2):
    cdef float x1, y1, z1
    cdef float x2, y2, z2
    x1, y1, z1 = p1
    x2, y2, z2 = p2
    return Shape().setFromMaker(BRepBuilderAPI_MakeEdge(
        gp_Pnt(x1, y1, z1), gp_Pnt(x2, y2, z2)))

def wire(edges):
    cdef BRepBuilderAPI_MakeWire maker
    for edgeShape in edges:
        maker.Add((<Shape?>edgeShape).edge())
    return Shape().setFromMaker(maker)

def face(wires):
    wireIter = iter(wires)
    # first wire has to be passed directly to constructor,
    # otherwise a segfault occurs for some reason
    cdef TopoDS_Wire firstWire = (<Shape?>next(wireIter)).wire()
    cdef BRepBuilderAPI_MakeFace maker = BRepBuilderAPI_MakeFace(firstWire)
    for wireShape in wireIter:
        maker.Add((<Shape?>wireShape).wire())
    return Shape().setFromMaker(maker)


def circle(float r):
    cdef gp_Circ circ = gp_Circ(gp_Ax2(), r)
    cdef TopoDS_Edge edge = BRepBuilderAPI_MakeEdge(circ).Edge()
    cdef TopoDS_Wire wire = BRepBuilderAPI_MakeWire(edge).Wire()
    cdef TopoDS_Face face = BRepBuilderAPI_MakeFace(wire).Face()
    return Shape().set_(face)


cdef extern from "BRepPrimAPI_MakeBox.hxx":
    cdef cppclass BRepPrimAPI_MakeBox(BRepBuilderAPI_MakeShape):
        BRepPrimAPI_MakeBox(Standard_Real, Standard_Real, Standard_Real)

def box(float x, float y, float z):
    return Shape().setFromMaker(BRepPrimAPI_MakeBox(x, y, z))


cdef extern from "BRepPrimAPI_MakeCylinder.hxx":
    cdef cppclass BRepPrimAPI_MakeCylinder(BRepBuilderAPI_MakeShape):
        BRepPrimAPI_MakeCylinder(Standard_Real, Standard_Real)

def cylinder(float r, float h):
    return Shape().setFromMaker(BRepPrimAPI_MakeCylinder(r, h))


cdef extern from "BRepPrimAPI_MakeCone.hxx":
    cdef cppclass BRepPrimAPI_MakeCone(BRepBuilderAPI_MakeShape):
        BRepPrimAPI_MakeCone(Standard_Real, Standard_Real, Standard_Real)

def cone(float r1, float r2, float h):
    return Shape().setFromMaker(BRepPrimAPI_MakeCone(r1, r2, h))


cdef extern from "BRepPrimAPI_MakeSphere.hxx":
    cdef cppclass BRepPrimAPI_MakeSphere(BRepBuilderAPI_MakeShape):
        BRepPrimAPI_MakeSphere(Standard_Real)

def sphere(float r):
    return Shape().setFromMaker(BRepPrimAPI_MakeSphere(r))


cdef extern from "BRepPrimAPI_MakeTorus.hxx":
    cdef cppclass BRepPrimAPI_MakeTorus(BRepBuilderAPI_MakeShape):
        BRepPrimAPI_MakeTorus(Standard_Real R1, Standard_Real R2)
        BRepPrimAPI_MakeTorus(Standard_Real R1, Standard_Real R2,
            Standard_Real angle)
        BRepPrimAPI_MakeTorus(Standard_Real R1, Standard_Real R2,
            Standard_Real angle1, Standard_Real angle2)
        BRepPrimAPI_MakeTorus(Standard_Real R1, Standard_Real R2,
            Standard_Real angle1, Standard_Real angle2, Standard_Real angle)

def torus(*args):
    if len(args) == 2:
        r1, r2 = args
        return Shape().setFromMaker(BRepPrimAPI_MakeTorus(r1, r2))

    elif len(args) == 3:
        r1, r2, angle = args
        return Shape().setFromMaker(BRepPrimAPI_MakeTorus(r1, r2, angle))


cdef extern from "_ycad_helpers.h":
    cdef extern void _writeSTL "writeSTL" (TopoDS_Shape, Standard_CString,
        Standard_Real)

    cdef extern void _readSTL "readSTL" (TopoDS_Shape &, Standard_CString)

def writeSTL(Shape shape, bytes path, double tol):
    _writeSTL(shape.obj, path, tol)

def readSTL(bytes path):
    s = Shape()
    _readSTL(s.obj, path)
    return s
