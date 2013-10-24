#include <TopoDS_Shape.hxx>
#include <StlAPI_Writer.hxx>


void writeSTL(const TopoDS_Shape &shape, Standard_CString path,
    Standard_Real deflection);
