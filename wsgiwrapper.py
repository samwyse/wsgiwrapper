#!/usr/bin/python

"""Turns a command-line program into a WSGI application."""

# Insure maximum compatibility between Python 2 and 3
from __future__ import absolute_import, division, print_function

# Metadate...
__author__ = "Samuel T. Denton, III <sam.denton@dell.com>"
__contributors__ = []
__copyright__ = "Copyright 2019 Samuel T. Denton, III"
__version__ = '0.5'

# Declutter our namespace
__all__ = ['wsgiwrapper']

# Python standard libraries
from functools import partial
from itertools import count
from importlib import import_module
from mimetypes import guess_type
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
from wsgiref.handlers import format_date_time
from wsgiref.headers import Headers
from wsgiref.simple_server import make_server
#from wsgiref.validate import validator
import argparse, cgi, copy, os, sys
import re, time

# Python site libraries
from pystache.renderer import Renderer  # TODO: decouple pystache

# Python personal libraries
from htmltags import *
from utils import b64id, Backstop, print_where, tracing

NL = '\n'
QUESTION_MARK = u'u\2753'
HEAVY_PLUS_SIGN = u'u\2795'
HEAVY_MINUS_SIGN = u'u\2796'

PlusButton = partial(Input, value="&#x2795;", type='button')
MinusButton = partial(Input, value="&#x2796;", type='button')

# common HTTP status codes
status200 = '200 OK'
status404 = '404 Not Found'
status500 = '500 Internal Server Error'

# MIME types of common types of content
IMAGE_ICON = [
    ('Content-Type', 'image/x-icon'),
    ('Cache-Control', 'public, max-age=31536000'),
    ]
TEXT_HTML = [('Content-Type', 'text/html')]
TEXT_PLAIN = [('Content-Type', 'text/plain')]

js_library = {
    ##### ----- ##### ----- ##### ----- #####
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
}''',
    ##### ----- ##### ----- ##### ----- #####
    'add_li': r'''
function add_li(name) {
    var ul = document.getElementById(name+'.ul'),
        li = document.getElementById(name+'.li');
    var copy = li.cloneNode(true);
    copy.removeAttribute('id');
    ul.appendChild(copy);
}''',
    ##### ----- ##### ----- ##### ----- #####
    'rm_li': r'''
function rm_li(node) {
    while(node.tagName != 'LI') {
        node = node.parentNode;
    }
    node.remove()
}''',
    ##### ----- ##### ----- ##### ----- #####
    'toggle': r'''
function toggle(node, name) {
    while(node.tagName != 'LI') {
        node = node.parentNode;
    }
    node.style.display = 'none';
    var that = document.getElementById(name);
    that.style.display = '';
}''',
    ##### ----- ##### ----- ##### ----- #####
    }


def get_placeholder(action):
    nargs = action.nargs
    metavars = (action.metavar or action.dest.upper(), )
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
        return '%s' % (1 * metavars)

def isrange(choices):
    # Determine if a list of choices can be represented as a range.
    if not all(isinstance(x, (int, float)) for x in choices):
        return None
    try:
        start, stop = choices[0], choices[-1]+1
        step = 1 if len(choices) < 2 else choices[1] - choices[0]
        return start, stop, step
    except:
        return None

def mk_select(action):
    """Create an HTML <select> element."""
    selct = Select()
    if action.nargs in (argparse.ZERO_OR_MORE, argparse.ONE_OR_MORE):
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

class wsgiwrapper(object):
    """\
Creates a WSGI application from a CLI program that uses ArgumentParser.

An HTTP GET request will return a form describing the parameters.
The form will contain a fieldset for each action group in the parser.
Each fieldset will contain an <input> element for each action.
Several buttons will be added.

An HTTP POST request will parse the data returned in the form, using it
to create an argparse.Namespace object.  That object will be passed to
the 'process()' function of the CLI program.
"""

    registry = b64id()

    defaults = {
        'form_name': '',
        'prefix': None,
        'hooks': {},
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

    def __init__(self, parser, runapp, **kwargs):
        self.parser = parser  # The argparse object to turn into an HTML form.
        self.runapp = runapp  # The app to run when the form is POSTed.
        for name, default in self.defaults.items():
            setattr(self, name, kwargs.get(name, default))
        self.renderer = Renderer()  # TODO: decouple pystache
        input_files, output_files = {}, {}
        self.script = set()
        self.toolbox = []

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
                    triplet = isrange(action.choices) if action.choices else False
                    if action.choices is not None and not triplet:
                        input = mk_select(action)
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
                            if triplet:
                                input.setAttribute('min', triplet[0])
                                input.setAttribute('max', triplet[1])
                                input.setAttribute('step', triplet[2])
                            if action.type == float:
                                input.setAttribute('step', 'any')
                    elif isinstance(action, argparse._AppendAction):
                        continue  # TODO: implement this
                    elif isinstance(action, argparse._AppendConstAction):
                        continue  # TODO: implement this
                    elif isinstance(action, argparse._CountAction):
                        input = Input(type='number', min=0)
                        if action.default:
                            input.setAttribute('value', cgi.escape(str(action.default)))
                    else:
                        continue  # TODO: can we ever get here?
                except TypeError as err:
                    from traceback import format_exc
                    input = Pre(format_exc())
                input.setAttribute('name', dest)
                input.setAttribute('placeholder', placeholder)
                if action.required:
                    input.setAttribute('required', None)
                handlers = self.hooks.get(dest+'.handlers', {})
                for event, jscmd in handlers.items():
                    input.setAttribute(event, jscmd % dest)
                    mobj = re.search(r'(\w+)\(', jscmd)
                    if mobj:
                        self.script.add(mobj.group(1))

                nargs = action.nargs
                if nargs is None:
                    item = input
                elif nargs == argparse.OPTIONAL:
                    item = Ul(id=dest+'.ul', Class='input-ul')
                    item += Li(PlusButton(onclick='toggle(this, "'+dest+'.li")'), id=dest+'.add')
                    item += Li(input, MinusButton(onclick='toggle(this, "'+dest+'.add")'), id=dest+'.li', style='display:none')
                    self.script.add('toggle')
                elif nargs == argparse.ZERO_OR_MORE:
                    item = Ul(id=dest+'.ul', Class='input-ul')
                    item += Li(PlusButton(onclick='add_li("'+dest+'")'), id=dest+'.add')
                    self.toolbox += Li(input, MinusButton(onclick='rm_li(this)'), id=dest+'.li')
                    self.script.add('add_li')
                    self.script.add('rm_li')
                elif nargs == argparse.ONE_OR_MORE:
                    first = copy.deepcopy(input)
                    first.setAttribute('required', None)
                    item = Ul(id=dest+'.ul', Class='input-ul')
                    item += Li(first, PlusButton(onclick='add_li("'+dest+'")'))
                    this_row = Li(id=dest+'.li')
                    this_row += input, MinusButton(onclick='rm_li(this)')
                    self.toolbox += this_row
                    self.script.add('add_li')
                    self.script.add('rm_li')
                elif nargs == argparse.REMAINDER:
                    raise NotImplementedError('nargs = %r' % nargs)
                elif nargs == argparse.PARSER:
                    raise NotImplementedError('nargs = %r' % nargs)
                else:
                    item = Ul(id=dest+'.ul', Class='input-ul')
                    for _ in range(nargs):
                        item += Li(copy.deepcopy(input))

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
            self.renderer.render_path(  # TODO: decouple pystache
                'wsgiwrapper.mustache',
                *context, **kwargs) ) ]

    def __call__(self, environ, start_response):
        """Display (GET) or processs (POST) our form."""
        self.environ = environ
        self.start_response = start_response
        parser = self.parser

        # Did we receive a GET or HEAD reques?
        # Display our form.
        # TODO: treat GET with query as a post?
        req_method = environ['REQUEST_METHOD']
        if req_method in {'GET', 'HEAD'}:
            path_info = environ['PATH_INFO']
            if path_info == '/favicon.ico':
                try:
                    with open(path_info[1:], 'rb') as favicon:
                        self.start_response(status200, IMAGE_ICON,)
                        return [favicon.read()]
                except:
                    pass
            if path_info != '/':
                self.start_response(status404, TEXT_PLAIN,)
                return ['Not found']
            headers, form_iter = self.mk_form(
                self.environ,
                script=[js_library[func] for func in self.script],
                toolbox=self.toolbox,
                form=self.form,
                )
            self.start_response(status200, headers)
            return [] if req_method == 'HEAD' else form_iter

        # The only other acceptable request is a POST.
        if req_method != 'POST':
            self.start_response('405 Method Not Allowed', TEXT_PLAIN)
            return []

        # Guard against errors while working...
        with Backstop(environ, self.start_response):

            # Parse the submitted data.
            #print_where('Parse the submitted data.')
            try:
                fieldstorage = cgi.FieldStorage(
                    fp=environ['wsgi.input'],
                    environ=environ,
                    keep_blank_values=True)
            except Exception:
                # The only error I've seen generated is when
                # wsgiref.validate is being used. See
                # http://python.6.x6.nabble.com/Revising-environ-wsgi-input-readline-in-the-WSGI-specification-td2211999.html#a2212023
                from traceback import format_exc
                #print_where(format_exc())
                return []

            # Did the user click on a button?
            #print_where('Did the user click on a button?')
            for action in self.buttons:
                if action.dest in fieldstorage:
                    if isinstance(action, argparse._HelpAction):
                        self.start_response(status200, TEXT_PLAIN)
                        return [ parser.format_help().encode() ]
                    elif isinstance(action, argparse._VersionAction):
                        formatter = parser.formatter_class(parser.prog)
                        formatter.add_text(action.version)
                        self.start_response(status200, TEXT_PLAIN)
                        return [ formatter.format_help().encode() ]
                    else:
                        self.start_response(status200, TEXT_PLAIN)
                        return [ str(action.__class__).encode() ]
                    return

            # Create an argparse.Namespace from the fieldstorage.
            #print_where('Create an argparse.Namespace from the fieldstorage.')
            new_args = argparse.Namespace()
            self.output_files = {}
            for action in parser._actions:
                #print_where('action =', action)
                if action in self.buttons:
                    continue
                dest = action.dest
                if isinstance(action, argparse._StoreConstAction):
                    # this is a checkbox, so ignore nargs
                    value = fieldstorage.getfirst(dest, action.default)
                    value = self.registry.redeem(value)
                elif action.nargs is None:
                    # no nargs means there can be only one
                    value = fieldstorage.getfirst(dest, action.default)
                else:
                    value = fieldstorage.getlist(dest) or [action.default]
                    if dest+'.split' in self.hooks:
                        value = value[0].split()
                #print_where('value =', repr(value)[:240])

                if action.type:
                    if isinstance(action.type, argparse.FileType):
                        field = fieldstorage[dest]
                        #print_where('field =', repr(field)[:240])
                        if 'r' in action.type._mode:
                            # need to read from a file-like object
                            filename = field.filename
                            #print_where('filename =', repr(filename)[:240])
                            if filename:
                                value = StringIO(field.value)
                                value.name = filename
                            else:
                                value = None
                            #print_where('value =', repr(value)[:240])
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
                #print_where('value =', repr(value)[:240])

                # add this to our Namespace object
                setattr(new_args, dest, value)

            if self.prefix is not None:
                # drop hints that we're a web app
                setattr(new_args, self.prefix+'environ', environ)
                setattr(new_args, self.prefix+'start_response', self.start_response)
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
                    script=[js_library[func] for func in self.script],
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
        from traceback import format_exc
        self.start_response(status200, TEXT_PLAIN)
        print_where(format_exc())
        return []

def mk_parser():
    """Build an argument parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-v', '--version', action='version',
                        version='%(prog)s '+__version__)
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

def real_process(args):
    """Process the arguments."""
    mod = import_module(args.mod)
    the_parser = getattr(mod, args.parser)()
    the_process = getattr(mod, args.process)
    the_app = wsgiwrapper(
        the_parser, the_process,
        form_name=args.mod,
        hooks={
            # TODO: https://stackoverflow.com/a/5849454/603136
            'csvfile.handlers': {
                'onblur': 'copy_v("%s","zipfile")',
                },
            'expansion.split': True,
            },
        prefix=args.prefix,
        skip_groups=args.skip_groups,
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
