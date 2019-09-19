#!/usr/bin/python

"""Turns a command-line program into a WSGI application."""

# Insure maximum compatibility between Python 2 and 3
from __future__ import absolute_import, division, print_function

# Metadate...
__author__ = "Samuel T. Denton, III <sam.denton@dell.com>"
__contributors__ = []
__copyright__ = "Copyright 2019 Samuel T. Denton, III"
__version__ = '0.4'

# Declutter our namespace
#__all__ = ['wsgiwrapper']

# Python standard libraries
import argparse, sys

# Python site libraries

# Python personal libraries

def mk_parser():
    """Build an argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    grp = parser.add_argument_group('Interpretation of "nargs"')
    grp.add_argument('--none', metavar='ARG')
    grp.add_argument('--optional', metavar='ARG', nargs=argparse.OPTIONAL)
    grp.add_argument('--zero-or-more', metavar='ARG', nargs=argparse.ZERO_OR_MORE)
    grp.add_argument('--one-or-more', metavar='ARG', nargs=argparse.ONE_OR_MORE)
    for i in 1, 2, 3:
        grp.add_argument('--nargs-%d' % i, metavar='ARG', nargs=i)
    grp = parser.add_argument_group('Interpretation of "choices"')
    grp.add_argument('--a', choices='tom dick harry'.split())
    grp.add_argument('--b',
                     choices='mammals birds reptiles amphibians fish'.split(),
                     default='mammals birds'.split())
    grp.add_argument('--c', nargs=argparse.ONE_OR_MORE,
                     choices='tom dick harry'.split())
    grp.add_argument('--d', nargs=argparse.ONE_OR_MORE,
                     choices='mammals birds reptiles amphibians fish'.split(),
                     default='mammals birds'.split())
    grp.add_argument('--e', nargs=argparse.ZERO_OR_MORE,
                     choices='tom dick harry'.split())
    grp.add_argument('--f', nargs=argparse.ZERO_OR_MORE,
                     choices='mammals birds reptiles amphibians fish'.split(),
                     default='mammals birds'.split())
    return parser

def process(args):
    print(repr(args))

def main(argv=None):
    # Cribbed from [Python main() functions](https://www.artima.com/weblogs/viewpost.jsp?thread=4829)
    if argv is None:
        argv = sys.argv[1:]
    parser = mk_parser()
    args = parser.parse_args(argv)
    return process(args)

if __name__ == '__main__':
    sys.exit(main())
