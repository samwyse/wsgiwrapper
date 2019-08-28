#! /usr/bin/env python

"""Useful utilities"""

# Insure maximum compatibility between Python 2 and 3
from __future__ import absolute_import, division, print_function

# Python standard libraries
from functools import partial, wraps
import os, sys
import struct, base64

# Python site libraries

# Python personal libraries

def setattrs(**kwargs):
    """\
Add arbitrary attributes to a function, allowing externally visible
values to be associated with a function without polluting the global
namespace.
"""
    def setter(f):
	for k, v in kwargs.items():
            setattr(f, k, v)
        return f
    return setter

def add_self(f):
    """\
Add a 'self' parameter to a function, pointing to the function itself,
allowing the function to access its attributes and otherwise appear
similar a class instance.
"""
    @wraps(f)
    def wrapper(*args, **kwargs):
	kwargs['self'] = f
        return f(*args, **kwargs)
    return wrapper

@add_self
@setattrs(cwd=os.getcwd(), home=os.path.expanduser('~'), stderr=sys.stderr)
def print_where(*args, **kwargs):
    from inspect import currentframe
    self = kwargs.pop('self')
    caller = currentframe()
    here = caller.f_code.co_filename
    while caller.f_code.co_filename == here:
        caller = caller.f_back
    fname = caller.f_code.co_filename
    if fname.startswith(self.cwd):
        fname = '.' + fname[len(self.cwd):]
    if fname.startswith(self.home):
        fname = '~' + fname[len(self.home):]
    print('File "%s", line %d:' % (fname, caller.f_lineno),
        *args, file=self.stderr)

# From https://cscheid.net/2017/12/11/minimal-tracing-decorator-python-3.html
def tracing(f):
    #from inspect import signature
    #sig = signature(f)
    @add_self
    @setattrs(indent=0)
    @wraps(f)
    def wrapper(*args, **kwargs):
        self = kwargs.pop('self')
        ws = ' ' * (self.indent * 2)
	fname = f.func_name
	code = f.func_code
	names = code.co_varnames[:code.co_argcount]
        print_where("%sENTER %s:" % (ws, fname))
	for name, value in zip(names, args):
	    print_where("%s    %s: %s" % (ws, name, repr(value)[:48]))
        #for ix, param in enumerate(sig.parameters.values()):
            #print_where("%s    %s: %s" % (ws, param.name, args[ix]))
        self.indent += 1
	try:
            result = f(*args, **kwargs)
	except Exception as err:
            self.indent -= 1
            print_where("%sEXCEPTION %s: %r" % (ws, fname, err))
            raise
	else:
            self.indent -= 1
            print_where("%sEXIT %s, returned %r" % (ws, fname, result))
        return result
    return wrapper

class b64id(object):
    def __init__(self):
        self.d1 = {}
        self.d2 = {}
    def register(self, obj):
        if obj in self.d1:
            return self.d1[obj]
        ticket = base64.b64encode(struct.pack('L', id(obj)))
        self.d1[obj] = ticket
        self.d2[ticket] = obj
        return ticket
    def redeem(self, ticket):
        return self.d2.get(ticket, ticket)

class Backstop(object):
    """This is a context manager to catch exceptions that would
otherwise cause problems is a WSGI app.  However, after reading
https://www.python.org/dev/peps/pep-0333/#error-handling I'm
thinking that a decorator might work better."""
    def __init__(self, environ, start_response):
        """Save start_response, and environ because, why not?""" 
        self.environ = environ
        self.start_response = start_response
    def __enter__(self):
        """Not much to do here..."""
        return self
    def __exit__(self, *args):
        """Intercept any exceptions that may have occurred."""
        if any(args):
            self.start_response(
                '500 Internal Error',
                [("content-type", "text/plain")],
                tuple(args))
        return True

if __name__ == '__main__':
    pass
