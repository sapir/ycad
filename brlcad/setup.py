from distutils.core import setup
from distutils.extension import Extension
from Cython.Distutils import build_ext
import os


BRLCAD_DIR = '/usr/brlcad'

setup(
    name='brlcad',
    cmdclass={'build_ext': build_ext},
    ext_modules=[
        Extension("brlcad", ["brlcad.pyx"],
            include_dirs=[
                os.path.join(BRLCAD_DIR, 'include'),
                os.path.join(BRLCAD_DIR, 'include', 'brlcad'),
            ],

            library_dirs=[
                os.path.join(BRLCAD_DIR, 'lib'),
            ],

            runtime_library_dirs=[
                os.path.join(BRLCAD_DIR, 'lib'),
            ],

            libraries=['bu', 'rt', 'wdb', 'm'],
        ),
    ]
)
