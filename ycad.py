#!/usr/bin/env python

from __future__ import absolute_import, print_function
import sys
import os
import argparse
from subprocess import check_call

import grammar
import runtime


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("filename",
        help="source file (usually ends with '.ycad')")
    parser.add_argument("-o", "--output",
        help="STL output filename. defaults to source file with .stl extension")
    args = parser.parse_args()

    if not args.output:
        args.output = os.path.splitext(args.filename)[0] + '.stl'
    
    dbName = 'temp.g'

    print('Parsing...', file=sys.stderr)
    parsed = grammar.program.parseFile(args.filename)
    print('Creating BRL-CAD database ({0})...'.format(dbName), file=sys.stderr)
    runtime.run(os.path.abspath(args.filename), parsed, dbName)

    print('Converting to STL ({0})...'.format(args.output), file=sys.stderr)
    check_call(['g-stl',
        '-b',          # binary STL
        '-a', '0.05',  # 0.05mm tolerance
        '-o', args.output,
        dbName,
        'main'])       # 'main' is name of main object in our DB

    print('OK!', file=sys.stderr)
