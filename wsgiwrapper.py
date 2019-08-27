#!/usr/bin/python

"""Turns a command-line program in a WSGI application."""

# Insure maximum compatibility between Python 2 and 3
from __future__ import absolute_import, division, print_function

__version__ = 0.4
__copyright__ = "Copyright 2019 Samuel T. Denton, III"
__author__ = "Samuel T. Denton, III <sam.denton@emc.com>"
__contributors__ = []

# Python standard libraries
from functools import partial
from itertools import count
from importlib import import_module
from mimetypes import guess_type
from StringIO import StringIO
from wsgiref.handlers import format_date_time
from wsgiref.headers import Headers
from wsgiref.simple_server import make_server
import argparse, cgi, copy, os, sys
import time

# Python site libraries
#from pystache.renderer import Renderer

# Python personal libraries
from htmltags import *
from utils import b64id, Backstop, print_where

NL = '\n'
QUESTION_MARK = u'u\2753'
HEAVY_PLUS_SIGN = u'u\2795'
HEAVY_MINUS_SIGN = u'u\2796'

# common HTTP status codes
status200 = '200 OK'
status500 = '500 Internal Server Error'

# common HTTP types of content
TEXT_HTML = [('Content-Type', 'text/html')]
TEXT_PLAIN = [('Content-Type', 'text/plain')]

js_library = {
    'copy_v': r'''
function stripext(path) {
  var rsep = Math.max(path.lastIndexOf('\\'), path.lastIndexOf('/'));
  var rdot = path.lastIndexOf('.');
  var fname = rsep + 1;
  while (fname < rdot) {
    if (path.charAt(fname) != '.') {
      return path.slice(rsep + 1, rdot);
    }
    fname += 1;
  }
  return path.slice(rsep + 1)
}
function copy_v(srcid, dstid) {
    var src = document.getElementById(srcid),
        dst = document.getElementById(dstid);
    dst.value = stripext(src.value)+'.zip';
}'''
    }


def get_placeholder(action):
    nargs = action.nargs
    metavars = (action.metavar, )
    if nargs is None:
        return '%s' % (1 * metavars)
    elif nargs == argparse.OPTIONAL:
        return '[%s]' % (1 * metavars)
    elif nargs == argparse.ZERO_OR_MORE:
        return '[%s [%s ...]]' % (2 * metavars)
    elif nargs == argparse.ONE_OR_MORE:
        return '%s [%s ...]' % (2 * metavars)
    elif nargs == argparse.REMAINDER:
        return '...'
    elif nargs == argparse.PARSER:
        return '%s ...' % (1 * metavars)
    else:
        return ' '.join(nargs * metavars)

class wsgiwrapper(object):
    """\
Creates a WSGI application from CLI program that uses ArgumentParser.

An HTTP GET request will return a form describing the parameters.
The form will contain a fieldset for each action group in the parser.
Each fieldset will contain an <input> element for each action.
Several buttons will be added.

An HTTP POST request will parse the data returned in the form, returning
an argparse.Namespace object.  That object will be passed to the 'run()'
function of the CLI program.
"""

    registry = b64id()

    defaults = {
        'form_name': '',
        'prefix': None,
        'overrides': {},
        'skip_groups': [],
        'submit_actions': {
            argparse._HelpAction,
            argparse._VersionAction,
            }
        }

    type_lookup = {
        basestring: 'text',
        int: 'number',
        float: 'number',
        }

    def choices(self, action):
        """Create an HTML <select> element."""
        selct = Select()
        if action.nargs in ('*', '+'):
            selct.setAttribute('multiple', None)
        if action.required:
            selct.setAttribute('required', None)
        defaults = action.default if isinstance(action.default, (list, tuple)) else [action.default]
        for option in action.choices:
            if isinstance(action.choices, dict):
                option_str = str(action.choices[option])
            else:
                option_str = str(option).title()
            ticket = cgi.escape(str(option)) if isinstance(option, basestring) else self.registry.register(option)
            opt = Option(cgi.escape(option_str), value=ticket)
            if option in defaults:
                opt.setAttribute('selected', None)
            selct += opt
        return selct

    def __init__(self, parser, runapp, **kwargs):
        self.parser = parser
        self.renderer = Renderer()
        self.runapp = runapp
        self.classes = set()
        for name, default in self.defaults.items():
            setattr(self, name, kwargs.get(name, default))
        input_files, output_files = {}, {}
        self.scripts = set()
        form = Form(method='post', enctype='multipart/form-data', Class="form")
        if parser.description:
            form += P(parser.description, Class="description")
        button_bar = Div(Class="button_bar")
        self.buttons = []
        templates = Div(Style="display:none")

        for action_group in parser._action_groups:
            if not action_group._group_actions:
                continue
            fieldset = Fieldset(Class='fieldset', Style='display: grid;')
            row_counter = count()

            for action in action_group._group_actions:
                dest = action.dest
                placeholder = get_placeholder(action)

                try:
                    if isinstance(action, tuple(self.submit_actions)):
                        button_bar += Input(type="submit", name=dest,
                                value=cgi.escape(dest.title()),
                                formnovalidate=None)
                        self.buttons.append(action)
                        continue
                    elif action.choices is not None: 
                        input = self.choices(action)
                    elif isinstance(action, argparse._StoreConstAction):
                        ticket = self.registry.register(action.const)
                        input = Input(type='checkbox', value=cgi.escape(ticket))
                    elif isinstance(action, argparse._StoreAction):
                        if isinstance(action.type, argparse.FileType):
                            if 'r' in action.type._mode:
                                input = Input(type='file', id=dest)
                                input_files[dest] = input
                            else:
                                placeholder = 'Output file name'
                                input = Input(id=dest)
                                output_files[dest] = input
                        else:
                            input = Input(type=self.type_lookup.get(action.type, 'text'))
                            if action.default:
                                input.setAttribute('value', cgi.escape(str(action.default)))
                    elif isinstance(action, argparse._AppendAction):
                        continue  # TODO: implement this
                    elif isinstance(action, argparse._AppendConstAction):
                        continue  # TODO: implement this
                    elif isinstance(action, argparse._CountAction):
                        continue  # TODO: implement this
                    else:
                        continue  # TODO: can we ever get here?
                except TypeError as err:
                    from traceback import format_exc
                    input = Pre(format_exc())
                input.setAttribute('name', dest)
                input.setAttribute('placeholder', placeholder)
                if action.required or action.nargs == argparse.ONE_OR_MORE:
                    input.setAttribute('required', None)
                if dest+‘.onevent’ in overrides:
                    for event, jscmd in overrides[dest+‘.onevent’]:
                        input.setAttribute(event, jscmd % fest)
                        mobj = re.search(r’(\w+)\(‘)
                        if mobj:
                            self.scripts.add(mobj.group(1))
                if isinstance(action.nargs, int):
                    item = Div(id=dest+'.lst')
                    for _ in range(action.nargs+1):
                        item += Div(copy.copy(input))
                    templates += Div(input, id=dest+'.tmp')
                else:
                    item = input
                row = next(row_counter) + 1
                fieldset += NL, Label(
                    dest.replace('_', ' ').title(),
                    For=dest,
                    Style='grid-area:%d/1' % row,
                    Class='label')
                item.setAttribute('style', 'grid-area:%d/2' % row)
                fieldset += NL, item
                if action.help:
                    params = dict(vars(action), prog='XYZZY')
                    for key, value in list(params.items()):
                        if value == argparse.SUPPRESS:
                            del params[key]
                        elif hasattr(value, '__name__'):
                            params[name] = value.__name__
                        else:
                            pass
                    if params.get('choices') is not None:
                        params['choices'] = ', '.join([str(c) for c in params['choices']])
                    if isinstance(params.get('default'), list):
                        params['default'] = ', '.join([str(c) for c in params['default']])
                    fieldset += NL, Span(action.help % params, Style='grid-area:%d/3' % row)

            if next(row_counter) and action_group.title not in self.skip_groups:
                form += NL, fieldset 
            if action_group.title:
                legend = Legend(action_group.title,
                        Class='legend')
                if action_group.description:
                    legend += Br(), I(action_group.description)
                fieldset += legend

        assert len(output_files) < 2

        button_bar += Input(type="submit"), Input(type="reset")
        form += NL
        form += button_bar
        if parser.epilog:
            form += P(parser.epilog, Class="epilog")
        self.form = form

    def mk_form(self, *context, **kwargs):
        """Overridable method to generate our form.

Returns a list of headers and a generator for the actual form data,
which we can discard if we are processing, e.g., a HEAD request."""
        return TEXT_HTML, [ str(
            self.renderer.render_path(
                'wsgiwrapper.mustache',
                *context, **kwargs) ) ]

    def __call__(self, environ, start_response):
        """Display or processs our form."""
        self.environ = environ
        self.start_response = start_response
        parser = self.parser

        # Did we receive a GET or HEAD reques?
        # Display our form.
        # TODO: treat GET with query as a post?
        req_method = environ['REQUEST_METHOD']
        if req_method in {'GET', 'HEAD'}:
            headers, form_iter = self.mk_form(
                self.environ,
                scripts=self.scripts,
                form=self.form,
                )
            start_response(status200, headers)
            return [] if req_method == 'HEAD' else form_iter

        # The only other acceptable request is a POST.
        if req_method != 'POST':
            start_response('403 OK', TEXT_PLAIN)
            return

        # Guard against errors while working...
        with Backstop(environ, start_response):

            # Parse the submitted data.
            fieldstorage = cgi.FieldStorage(
                fp=environ['wsgi.input'],
                environ=environ,
                keep_blank_values=True)

            # Did the user click on a button?
            for action in self.buttons:
                if action.dest in fieldstorage:
                    if isinstance(action, argparse._HelpAction):
                        start_response(status200, TEXT_PLAIN)
                        return [ parser.format_help().encode() ]
                    elif isinstance(action, argparse._VersionAction):
                        start_response(status200, TEXT_PLAIN)
                        return [ action.version.encode() ]
                    else:
                        start_response(status200, TEXT_PLAIN)
                        return [ str(action.__class__).encode() ]
                    return

            # create an argparse.Namespace from the fieldstorage
            new_args = argparse.Namespace()
            self.output_files = {}
            for action in parser._actions:
                if action in self.buttons:
                    continue
                dest = action.dest
                if isinstance(action, argparse._StoreConstAction):
                    # this is a checkbox, so ignore nargs
                    value = fieldstorage.getfirst(dest, action.default)
                    value = self.registry.redeem(value)
                elif action.nargs is None:
                    value = fieldstorage.getfirst(dest, action.default)
                else:
                    value = fieldstorage.getlist(dest) or [action.default]
                    if dest+'.split' in self.overrides:
                        value = value[0].split()
                if action.type:
                    if isinstance(action.type, argparse.FileType):
                        field = fieldstorage[dest]
                        if 'r' in action.type._mode:
                            # need to read from a file-like object
                            try:
                                filename = field.filename
                            except:
                                filename = ''
                            if filename:
                                value = StringIO(field.value)
                                value.name = filename
                            else:
                                value = ''
                        else:
                            # create a file-like object from our text input
                            value = self.output_files[dest] = StringIO()
                            filename = field.value
                            if filename:
                                value.name = filename
                            else:
                                value = None
                    else:
                        try:
                            value = action.type(value)
                        except:
                            value = action.type()

                # add this to our Namespace object
                setattr(new_args, dest, value)

            if self.prefix is not None:
                # drop hints that we're a web app
                setattr(new_args, self.prefix+'environ', environ)
                setattr(new_args, self.prefix+'start_response', start_response)
            newout = StringIO()

        # build the rest of the execution environment
        try:
            try:
                _stdin, sys.stdin = sys.stdin, open(os.devnull, 'r')
                _stdout, sys.stdout = sys.stdout, newout
                _stderr, sys.stderr = sys.stderr, newout
                ### THEN THE MAGIC HAPPENS ###
                sys.exit(self.runapp(new_args))
            finally:
                sys.stdin = _stdin
                sys.stdout = _stdout
                sys.stderr = _stderr
        except SystemExit as err:
            return self.do_sys_exit(err, newout)
        except Exception as err:
            return self.do_exception(err)

    def do_sys_exit(self, err, newout):
        with Backstop(self.environ, self.start_response):
            buffer = newout.getvalue()
            if err.code:
                status = '400 Bad Request'
                headers, form_iter = self.mk_form(
                    self.environ,
                    scripts=self.scripts,
                    form=self.form,
                    errors=buffer
                    )
            elif self.output_files:
                status = status200
                assert len(self.output_files) == 1
                for outfile in self.output_files.values():
                    filename = outfile.name
                    content = outfile.getvalue()
                    content_length = len(content)
                    headers = [
                        ('Content-Length', str(content_length)),
                        ('Content-Disposition', 'attachment; filename="'+filename+'"'),
                        ('Last-Modified', format_date_time(time.time())),
                        ]
                    content_type, encoding = guess_type(filename)
                    if content_type:
                         headers.append(('Content-Type', content_type))
                    if encoding:
                         headers.append(('Content-Encoding', encoding))
                    form_iter = [ content ]
            else:
                status = status200
                headers = TEXT_PLAIN
                form_iter = [ buffer ]
        self.start_response(status, headers)
        return form_iter

    def do_exception(self, err):
        """Overridable method to handle miscellaeous exceptions."""
        self.start_response(status200, TEXT_PLAIN)
        yield repr(err)
        return

def mk_parser():
    """Build an argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-m', '--module', dest='mod', required=True,
            help='The command line program to run as a WSGI app.')
    parser.add_argument('-p', '--parser', default='mk_parser',
            help='The function that returns an argparser object; default is %(default)s.')
    parser.add_argument('-r', '--run', dest='process', default='process',
            help='The function to run when the form is submitted; default is %(default)s.')
    parser.add_argument('-x', '--prefix', default=None,
            help='If set, adds prefixed "environ" and "start_response" to the wrapped application\'s arguments')
    parser.add_argument('-H', '--host', default='0.0.0.0',
            help='The IP address to bind to the socket; default is %(default)s.')
    parser.add_argument('-P', '--port', type=int, default=8080,
            help='The port number to bind to the socket; default is %(default)s.')
    parser.add_argument('-s', '--skip', action='append', default=[],
            metavar='GROUP', dest='skip_groups',
            help='Specific parser groups to skip when building the form')
    return parser

def process(args):
    """Process the arguments."""
    mod = import_module(args.mod)
    the_parser = getattr(mod, args.parser)()
    the_process = getattr(mod, args.process)
    the_app = wsgiwrapper(the_parser, the_process,
        form_name=args.mod,
        overrides={
            # TODO: https://stackoverflow.com/a/5849454/603136
            ‘csvfile.onevent’: {
                ‘onblur‘: 'copy_v("%s","zipfile")',
                },
            ‘expansion.split’: True,
            },
        prefix=args.prefix,
        skip_groups=args.skip_groups,
        )
    srv = make_server(args.host, args.port, the_app)
    print('listening on %s:%d...' % srv.server_address)
    srv.serve_forever()

def main(args):
    parser = mk_parser()
    args = parser.parse_args(args)
    return process(args)

if __name__ == '__main__':
    main(['-h'])
