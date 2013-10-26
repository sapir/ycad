from distutils.core import setup
from distutils.extension import Extension
from Cython.Build import cythonize

setup(
    name='ycad',
    ext_modules=cythonize([
        Extension(
            "_ycad",
            sources=["*.pyx", "_ycad_helpers.cpp"],
            language="c++",
            include_dirs=['/usr/local/include/oce'],
            libraries=['TK{0}'.format(lib)
                for lib in 'G3d BRep Prim Offset BO STL'.split()]
        ),
    ]))
