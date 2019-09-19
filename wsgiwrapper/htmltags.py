#!/usr/bin/python

# Insure maximum compatibility between Python 2 and 3
from __future__ import absolute_import, division, print_function

__version__ = 1.1
__copyright__ = "Copyright 2015 Samuel T. Denton, III"
__author__ = "Samuel T. Denton, III <sam.denton@emc.com>"
__contributors__ = []

__license__ = """
Copyright (c) 2015 Samuel T. Denton, III, <sam.denton@emc.com>
Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

# Python standard libraries
from functools import partial

# Python site libraries

# Python personal libraries

__all__ = [ 'Element', 'EmptyElement' ]


def import_all(cls, globals=globals()):
    '''Class decorator that creates partial objects and adds them to the module's __all__ list.'''
    try:
        for tagName in cls.__all__:
            globals.setdefault(tagName, partial(cls, tagName.lower()))
        __all__.extend(cls.__all__)
    except AttributeError:
        pass
    return cls


@import_all
class EmptyElement(object):
    '''An HTML element that does not have a closing element and thus cannot contain sub-elements.'''

    __all__ = [
        'Area', 'Base', 'BaseFont', 'Br', 'Col', 'Frame', 'HR', 'Img',
        'Input', 'IsIndex', 'Link', 'Meta', 'Param']

    def __init__(self, tagName, **attributes):
        self.tagName = tagName.upper()
        self.attributes = attributes
        super(EmptyElement, self).__init__()

    def __iter__(self):
        yield '<' + self.tagName.lower()
        for key, value in self.attributes.items():
            yield ' ' + key.lower()
            if value is not None:
                yield '=' + repr(value)
        yield '>'

    def __str__(self):
        return ''.join(self)

    def __bytes__(self):
        return str(self).encode()

    def getAttribute(self, name):
        return self.attributes.get(name.lower())

    def hasAttribute(self, name):
        return name.lower() in self.attributes

    def removeAttribute(self, name):
        try:
            del self.attributes[name.lower()]
        except:
            pass

    def setAttribute(self, name, value):
        self.attributes[name.lower()] = value


@import_all
class Element(EmptyElement):
    '''An HTML element that can contain sub-elements.'''

    __all__ = [
        'A', 'Abbr', 'Acronym', 'Address', 'Applet', 'B', 'Bdo', 'Big',
        'Blockquote', 'Body', 'Button', 'Caption', 'Center', 'Cite',
        'Code', 'Colgroup', 'Dd', 'Del', 'Dfn', 'Dir', 'Div', 'Dl',
        'Dt', 'Em', 'Fieldset', 'Font', 'Form', 'Frameset', 'H1', 'H2',
        'H3', 'H4', 'H5', 'H6', 'Head', 'Html', 'I', 'Iframe', 'Ins',
        'Kbd', 'Label', 'Legend', 'Li', 'Map', 'Menu', 'Noframes',
        'Noscript', 'Object', 'Ol', 'Optgroup', 'Option', 'P', 'Pre',
        'Q', 'S', 'Samp', 'Script', 'Select', 'Small', 'Span', 'Strike',
        'Strong', 'Style', 'Sub', 'Sup', 'Table', 'Tbody', 'Td',
        'Textarea', 'Tfoot', 'Th', 'Thead', 'Title', 'Tr', 'Tt', 'U',
        'Ul', 'Var']
    
    def __init__(self, tagName, *childNodes, **attributes):
        self.childNodes = list(childNodes)
        super(Element, self).__init__(tagName, **attributes)
        
    def __iadd__(self, item):
        if isinstance(item, tuple):
            self.childNodes.extend(item)
        else:
            self.childNodes.append(item)
        return self
    
    def __iter__(self):
        yield '<' + self.tagName.lower()
        for key, value in self.attributes.items():
            yield ' ' + key.lower()
            if value is not None:
                yield '=' + repr(value)
        if not self.childNodes:
            yield ' />'
        else:
            yield '>'
            for item in self.childNodes:
                yield str(item)
            yield '</' + self.tagName+'>'

if __name__ == '__main__':
    xyzzy = Element('xyzzy', foo='bar')
    xyzzy += 'this'
    xyzzy += 'a', 'b', 'c'
    print(xyzzy)
