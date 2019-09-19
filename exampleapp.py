#! /usr/bin/env python

"""Documentation"""

# Insure maximum compatibility between Python 2 and 3
from __future__ import absolute_import, division, print_function

# Metadate...
__author__ = "Samuel T. Denton, III <sam.denton@dell.com>"
__contributors__ = []
__copyright__ = "Copyright 2019 Samuel T. Denton, III"
__version__ = '0.4'

# Python standard libraries
from wsgiref.simple_server import make_server
import argparse, sys

# Python site libraries

# Python personal libraries
from wsgiwrapper import wsgiwrapper

def mk_parser():
    """Build an argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-H', '--host', default='0.0.0.0',
            help='The IP address to bind to the socket; default is %(default)s.')
    parser.add_argument('-P', '--port', type=int, default=8080,
            help='The port number to bind to the socket; default is %(default)s.')
    return parser

def process(args):
    """Process the arguments."""
    import example
    app = wsgiwrapper(example.mk_parser(), example.process)
    srv = make_server(args.host, args.port, app)
    print('listening on %s:%d...' % srv.server_address)
    srv.serve_forever()

def main(argv=None):
    # Cribbed from [Python main() functions](https://www.artima.com/weblogs/viewpost.jsp?thread=4829)
    if argv is None:
        argv = sys.argv[1:]
    parser = mk_parser()
    args = parser.parse_args(argv)
    return process(args)

if __name__ == '__main__':
    sys.exit(main())
