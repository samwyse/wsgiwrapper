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
from importlib import import_module
from wsgiref.simple_server import make_server
import argparse, sys

# Python site libraries

# Python personal libraries
from . import wsgiwrapper

def mk_parser():
    """Build an argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-v', '--version', action='version',
                        version='%(prog)s '+__version__)
    parser.add_argument('-m', '--module', dest='mod', required=True,
            help='The command line program to run as a WSGI app.')
    parser.add_argument('-p', '--parser', default='mk_parser',
            help='''The function that returns an argparser object; default is %(default)s.
The parser will be invoked once during WSGI initialization.''')
    parser.add_argument('-r', '--run', dest='process', default='process',
            help='''The function to run when the form is submitted; default is %(default)s.
This procedure can be invoked multiple times during the lifetims of the WSGI app.''')
    parser.add_argument('-s', '--skip', action='append', default=[],
            metavar='GROUP', dest='skip_groups',
            help='''Specify any parser groups to skip when building the form.  Note that
'help' and 'version' actions generate special submission buttons and are visually removed
from their group(s).  If this results in an empty group, it is also not displayed.''')
    parser.add_argument('-x', '--prefix', default=None,
            help='''If set, adds prefixed "environ" and "start_response" to the wrapped
application\'s arguments. This provides a hint to the application that it is running as
a WSGI; this allows the application to, for example, format it's output as HTML.''')
    parser.add_argument('-H', '--host', default='0.0.0.0',
            help='The IP address to bind to the socket; default is %(default)s.')
    parser.add_argument('-P', '--port', type=int, default=8080,
            help='The port number to bind to the socket; default is %(default)s.')
    parser.add_argument('-U', action='store_true', dest='use_tables',
            help='Generate HTML using tables instead of "display=grid".')
    return parser

def real_process(args):
    """Process the arguments."""
    mod = import_module(args.mod)
    the_parser = getattr(mod, args.parser)()
    the_process = getattr(mod, args.process)
    the_app = wsgiwrapper(
        the_parser, the_process,
        form_name=args.mod,
        prefix=args.prefix,
        skip_groups=args.skip_groups,
        use_tables=args.use_tables,
        )
    srv = make_server(args.host, args.port, the_app)
    print('listening on %s:%d...' % srv.server_address)
    srv.serve_forever()

def process(args):
    print("""This is the result of using a fake 'process' function.
It exists so we can test this program against itself, without causing
the universe to explode or anything.""")
    print()
    print(repr(args))

def main(argv=None):
    # Cribbed from [Python main() functions](https://www.artima.com/weblogs/viewpost.jsp?thread=4829)
    if argv is None:
        argv = sys.argv[1:]
    parser = mk_parser()
    args = parser.parse_args(argv)
    return real_process(args)

if __name__ == '__main__':
    sys.exit(main())
