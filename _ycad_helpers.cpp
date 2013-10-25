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

// no need for this method - cython could handle it -
// but if write's here, then let's keep read here, too
void readSTL(TopoDS_Shape &shape, Standard_CString path)
{
    StlAPI_Reader reader;
    reader.Read(shape, path);
}
