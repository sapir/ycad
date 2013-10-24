#include "_ycad_helpers.h"


void writeSTL(const TopoDS_Shape &shape, Standard_CString path,
    Standard_Real deflection)
{
    StlAPI_Writer writer;
    writer.ASCIIMode() = false;
    writer.RelativeMode() = false;
    writer.SetDeflection(deflection);
    writer.Write(shape, path);
}
