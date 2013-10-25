#include <TopoDS_Shape.hxx>
#include <StlAPI_Writer.hxx>
#include <StlAPI_Reader.hxx>


void writeSTL(const TopoDS_Shape &shape, Standard_CString path,
    Standard_Real deflection);

void readSTL(TopoDS_Shape &shape, Standard_CString path);
