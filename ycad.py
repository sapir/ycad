#!/usr/bin/env python

from __future__ import absolute_import, print_function
import sys
import os
import argparse
import time
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
    
    startTime = time.time()

    print('Parsing...', file=sys.stderr)
    parsed = grammar.parseFile(args.filename)
    timeAfterParsing = time.time()
    print('Parse time: {0:.2f}s'.format(timeAfterParsing - startTime))

    print('Running...', file=sys.stderr)
    runtime.run(os.path.abspath(args.filename), parsed, args.output)
    endTime = time.time()
    
    print('Execution time: {0:.2f}s'.format(endTime - timeAfterParsing))
    print('Total time: {0:.2f}s'.format(endTime - startTime))
