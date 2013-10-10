#!/usr/bin/env python

from __future__ import absolute_import, print_function
import sys
import os
import argparse
import time


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

    print('Initializing...', file=sys.stderr)
    import grammar
    import runtime
    timeAfterInit = time.time()
    print('Initialization time: {0:.2f}s'.format(timeAfterInit - startTime))

    print('Parsing...', file=sys.stderr)
    try:
        parsed = grammar.parseFile(args.filename)
    finally:
        timeAfterParsing = time.time()
        print('Parse time: {0:.2f}s'.format(timeAfterParsing - timeAfterInit))

    print('Running...', file=sys.stderr)
    try:
        runtime.run(os.path.abspath(args.filename), parsed, args.output)
    finally:
        endTime = time.time()

        print('Execution time: {0:.2f}s'.format(endTime - timeAfterParsing))
        print('Total time: {0:.2f}s'.format(endTime - startTime))
