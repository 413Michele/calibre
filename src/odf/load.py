#!/usr/bin/env python
# Copyright (C) 2007-2008 Søren Roug, European Environment Agency
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Contributor(s):
#

# This script is to be embedded in opendocument.py later
# The purpose is to read an ODT/ODP/ODS file and create the datastructure
# in memory. The user should then be able to make operations and then save
# the structure again.


from xml.sax import handler

from .element import Element
from .namespaces import OFFICENS

#
# Parse the XML files
#


class LoadParser(handler.ContentHandler):
    ''' Extract headings from content.xml of an ODT file '''
    triggers = (
       (OFFICENS, 'automatic-styles'), (OFFICENS, 'body'),
       (OFFICENS, 'font-face-decls'), (OFFICENS, 'master-styles'),
       (OFFICENS, 'meta'), (OFFICENS, 'scripts'),
       (OFFICENS, 'settings'), (OFFICENS, 'styles'))

    def __init__(self, document):
        self.doc = document
        self.data = []
        self.level = 0
        self.parse = False

    def characters(self, data):
        if self.parse is False:
            return
        self.data.append(data)

    def startElementNS(self, tag, qname, attrs):
        if tag in self.triggers:
            self.parse = True
        if self.doc._parsing != 'styles.xml' and tag == (OFFICENS, 'font-face-decls'):
            self.parse = False
        if self.parse is False:
            return

        self.level = self.level + 1
        # Add any accumulated text content
        content = ''.join(self.data)
        if len(content.strip()) > 0:
            self.parent.addText(content, check_grammar=False)
            self.data = []
        # Create the element
        attrdict = {}
        for att,value in attrs.items():
            attrdict[att] = value
        try:
            e = Element(qname=tag, qattributes=attrdict, check_grammar=False)
            self.curr = e
        except AttributeError as v:
            print(f'Error: {v}')

        if tag == (OFFICENS, 'automatic-styles'):
            e = self.doc.automaticstyles
        elif tag == (OFFICENS, 'body'):
            e = self.doc.body
        elif tag == (OFFICENS, 'master-styles'):
            e = self.doc.masterstyles
        elif tag == (OFFICENS, 'meta'):
            e = self.doc.meta
        elif tag == (OFFICENS,'scripts'):
            e = self.doc.scripts
        elif tag == (OFFICENS,'settings'):
            e = self.doc.settings
        elif tag == (OFFICENS,'styles'):
            e = self.doc.styles
        elif self.doc._parsing == 'styles.xml' and tag == (OFFICENS, 'font-face-decls'):
            e = self.doc.fontfacedecls
        elif hasattr(self,'parent'):
            self.parent.addElement(e, check_grammar=False)
        self.parent = e

    def endElementNS(self, tag, qname):
        if self.parse is False:
            return
        self.level = self.level - 1
        # Changed by Kovid to deal with <span> tags with only whitespace
        # content.
        data = q = ''.join(self.data)
        tn = getattr(self.curr, 'tagName', '')
        try:
            do_strip = not tn.startswith('text:')
        except Exception:
            do_strip = True
        if do_strip:
            q = q.strip()
        if q:
            self.curr.addText(data, check_grammar=False)
        self.data = []
        self.curr = self.curr.parentNode
        self.parent = self.curr
        if tag in self.triggers:
            self.parse = False
