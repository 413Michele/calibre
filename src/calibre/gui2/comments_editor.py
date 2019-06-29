#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import json
import os
import re
import weakref

from html5_parser import parse
from lxml import html
from PyQt5.Qt import (
    QAction, QApplication, QByteArray, QCheckBox, QColor, QColorDialog, QDialog,
    QDialogButtonBox, QFontInfo, QFormLayout, QHBoxLayout, QIcon, QKeySequence,
    QLabel, QLineEdit, QMenu, QPlainTextEdit, QPushButton, QSize, QSyntaxHighlighter,
    Qt, QTabWidget, QTextCursor, QTextEdit, QToolBar, QUrl, QVBoxLayout, QWidget,
    pyqtSignal, pyqtSlot
)

from calibre import prepare_string_for_xml, xml_replace_entities
from calibre.ebooks.chardet import xml_to_unicode
from calibre.gui2 import NO_URL_FORMATTING, choose_files, error_dialog, gprefs
from calibre.gui2.widgets import LineEditECM
from calibre.utils.config import tweaks
from calibre.utils.imghdr import what
from polyglot.builtins import unicode_type


class EditorWidget(QTextEdit, LineEditECM):  # {{{

    data_changed = pyqtSignal()

    @property
    def readonly(self):
        return self.isReadOnly()

    @readonly.setter
    def readonly(self, val):
        self.setReadOnly(bool(val))

    def __init__(self, parent=None):
        QTextEdit.__init__(self, parent)
        self.setTabChangesFocus(True)
        font = self.font()
        f = QFontInfo(font)
        delta = tweaks['change_book_details_font_size_by'] + 1
        if delta:
            font.setPixelSize(f.pixelSize() + delta)
            self.setFont(font)
        self.base_url = None
        self._parent = weakref.ref(parent)
        self.comments_pat = re.compile(r'<!--.*?-->', re.DOTALL)

        extra_shortcuts = {
            'bold': 'Bold',
            'italic': 'Italic',
            'underline': 'Underline',
        }

        for rec in (
            ('bold', 'format-text-bold', _('Bold'), True),
            ('italic', 'format-text-italic', _('Italic'), True),
            ('underline', 'format-text-underline', _('Underline'), True),
            ('strikethrough', 'format-text-strikethrough', _('Strikethrough'), True),
            ('superscript', 'format-text-superscript', _('Superscript'), True),
            ('subscript', 'format-text-subscript', _('Subscript'), True),
            ('ordered_list', 'format-list-ordered', _('Ordered list'), True),
            ('unordered_list', 'format-list-unordered', _('Unordered list'), True),

            ('align_left', 'format-justify-left', _('Align left'), ),
            ('align_center', 'format-justify-center', _('Align center'), ),
            ('align_right', 'format-justify-right', _('Align right'), ),
            ('align_justified', 'format-justify-fill', _('Align justified'), ),
            ('undo', 'edit-undo', _('Undo'), ),
            ('redo', 'edit-redo', _('Redo'), ),
            ('remove_format', 'edit-clear', _('Remove formatting'), ),
            ('copy', 'edit-copy', _('Copy'), ),
            ('paste', 'edit-paste', _('Paste'), ),
            ('cut', 'edit-cut', _('Cut'), ),
            ('indent', 'format-indent-more', _('Increase indentation'), ),
            ('outdent', 'format-indent-less', _('Decrease indentation'), ),
            ('select_all', 'edit-select-all', _('Select all'), ),

            ('color', 'format-text-color', _('Foreground color')),
            ('background', 'format-fill-color', _('Background color')),
            ('insert_link', 'insert-link', _('Insert link or image'),),
            ('insert_hr', 'format-text-hr', _('Insert separator'),),
            ('clear', 'trash', _('Clear')),
        ):
            name, icon, text = rec[:3]
            checkable = len(rec) == 4
            ac = QAction(QIcon(I(icon + '.png')), text, self)
            if checkable:
                ac.setCheckable(checkable)
            setattr(self, 'action_'+name, ac)
            ss = extra_shortcuts.get(name)
            if ss is not None:
                ac.setShortcut(QKeySequence(getattr(QKeySequence, ss)))
            ac.triggered.connect(getattr(self, 'do_' + name))

        self.action_block_style = QAction(QIcon(I('format-text-heading.png')),
                _('Style text block'), self)
        self.action_block_style.setToolTip(
                _('Style the selected text block'))
        self.block_style_menu = QMenu(self)
        self.action_block_style.setMenu(self.block_style_menu)
        h = _('Heading {0}')
        for text, name in (
            (_('Normal'), 'p'),
            (h.format(1), 'h1'),
            (h.format(2), 'h2'),
            (h.format(3), 'h3'),
            (h.format(4), 'h4'),
            (h.format(5), 'h5'),
            (h.format(6), 'h6'),
            (_('Pre-formatted'), 'pre'),
            (_('Blockquote'), 'blockquote'),
            (_('Address'), 'address'),
        ):
            ac = QAction(text, self)
            self.block_style_menu.addAction(ac)
            connect_lambda(ac.triggered, self, lambda self: self.do_format_block(name))

        self.setHtml('')
        self.textChanged.connect(self.data_changed)

    def set_readonly(self, what):
        self.readonly = what

    def focus_self(self):
        self.setFocus(Qt.TabFocusReason)

    def do_clear(self, *args):
        c = self.textCursor()
        c.beginEditBlock()
        c.movePosition(QTextCursor.Start, QTextCursor.MoveAnchor)
        c.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
        c.removeSelectedText()
        c.endEditBlock()
        self.focus_self()
    clear_text = do_clear

    def do_bold(self):
        raise NotImplementedError('TODO')

    def do_italic(self):
        raise NotImplementedError('TODO')

    def do_underline(self):
        raise NotImplementedError('TODO')

    def do_strikethrough(self):
        raise NotImplementedError('TODO')

    def do_superscript(self):
        raise NotImplementedError('TODO')

    def do_subscript(self):
        raise NotImplementedError('TODO')

    def do_ordered_list(self):
        raise NotImplementedError('TODO')

    def do_unordered_list(self):
        raise NotImplementedError('TODO')

    def do_align_left(self):
        raise NotImplementedError('TODO')

    def do_align_center(self):
        raise NotImplementedError('TODO')

    def do_align_right(self):
        raise NotImplementedError('TODO')

    def do_align_justified(self):
        raise NotImplementedError('TODO')

    def do_undo(self):
        self.undo()

    def do_redo(self):
        self.redo()

    def do_remove_format(self):
        raise NotImplementedError('TODO')

    def do_copy(self):
        self.copy()

    def do_paste(self):
        self.paste()

    def do_cut(self):
        self.cut()

    def do_indent(self):
        raise NotImplementedError('TODO')

    def do_outdent(self):
        raise NotImplementedError('TODO')

    def do_select_all(self):
        raise NotImplementedError('TODO')

    def do_format_block(self, name):
        raise NotImplementedError('TODO')

    def do_color(self):
        col = QColorDialog.getColor(Qt.black, self,
                _('Choose foreground color'), QColorDialog.ShowAlphaChannel)
        if col.isValid():
            raise NotImplementedError('TODO')
            self.exec_command('foreColor', unicode_type(col.name()))

    def do_background(self):
        col = QColorDialog.getColor(Qt.white, self,
                _('Choose background color'), QColorDialog.ShowAlphaChannel)
        if col.isValid():
            raise NotImplementedError('TODO')
            self.exec_command('hiliteColor', unicode_type(col.name()))

    def do_insert_hr(self, *args):
        raise NotImplementedError('TODO')

    def do_insert_link(self, *args):
        link, name, is_image = self.ask_link()
        if not link:
            return
        url = self.parse_link(link)
        if url.isValid():
            url = unicode_type(url.toString(NO_URL_FORMATTING))
            self.setFocus(Qt.OtherFocusReason)
            raise NotImplementedError('TODO')
            if is_image:
                self.exec_command('insertHTML',
                        '<img src="%s" alt="%s"></img>'%(prepare_string_for_xml(url, True),
                            prepare_string_for_xml(name or _('Image'), True)))
            elif name:
                self.exec_command('insertHTML',
                        '<a href="%s">%s</a>'%(prepare_string_for_xml(url, True),
                            prepare_string_for_xml(name)))
            else:
                self.exec_command('createLink', url)
        else:
            error_dialog(self, _('Invalid URL'),
                         _('The url %r is invalid') % link, show=True)

    def ask_link(self):
        d = QDialog(self)
        d.setWindowTitle(_('Create link'))
        l = QFormLayout()
        l.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        d.setLayout(l)
        d.url = QLineEdit(d)
        d.name = QLineEdit(d)
        d.treat_as_image = QCheckBox(d)
        d.setMinimumWidth(600)
        d.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        d.br = b = QPushButton(_('&Browse'))
        b.setIcon(QIcon(I('document_open.png')))

        def cf():
            files = choose_files(d, 'select link file', _('Choose file'), select_only_single_file=True)
            if files:
                path = files[0]
                d.url.setText(path)
                if path and os.path.exists(path):
                    with lopen(path, 'rb') as f:
                        q = what(f)
                    is_image = q in {'jpeg', 'png', 'gif'}
                    d.treat_as_image.setChecked(is_image)

        b.clicked.connect(cf)
        d.la = la = QLabel(_(
            'Enter a URL. If you check the "Treat the URL as an image" box '
            'then the URL will be added as an image reference instead of as '
            'a link. You can also choose to create a link to a file on '
            'your computer. '
            'Note that if you create a link to a file on your computer, it '
            'will stop working if the file is moved.'))
        la.setWordWrap(True)
        la.setStyleSheet('QLabel { margin-bottom: 1.5ex }')
        l.setWidget(0, l.SpanningRole, la)
        l.addRow(_('Enter &URL:'), d.url)
        l.addRow(_('Treat the URL as an &image'), d.treat_as_image)
        l.addRow(_('Enter &name (optional):'), d.name)
        l.addRow(_('Choose a file on your computer:'), d.br)
        l.addRow(d.bb)
        d.bb.accepted.connect(d.accept)
        d.bb.rejected.connect(d.reject)
        d.resize(d.sizeHint())
        link, name, is_image = None, None, False
        if d.exec_() == d.Accepted:
            link, name = unicode_type(d.url.text()).strip(), unicode_type(d.name.text()).strip()
            is_image = d.treat_as_image.isChecked()
        return link, name, is_image

    def parse_link(self, link):
        link = link.strip()
        if link and os.path.exists(link):
            return QUrl.fromLocalFile(link)
        has_schema = re.match(r'^[a-zA-Z]+:', link)
        if has_schema is not None:
            url = QUrl(link, QUrl.TolerantMode)
            if url.isValid():
                return url
        if os.path.exists(link):
            return QUrl.fromLocalFile(link)

        if has_schema is None:
            first, _, rest = link.partition('.')
            prefix = 'http'
            if first == 'ftp':
                prefix = 'ftp'
            url = QUrl(prefix +'://'+link, QUrl.TolerantMode)
            if url.isValid():
                return url

        return QUrl(link, QUrl.TolerantMode)

    def sizeHint(self):
        return QSize(150, 150)

    @property
    def html(self):
        ans = ''
        try:
            if not self.page().mainFrame().documentElement().findFirst('meta[name="calibre-dont-sanitize"]').isNull():
                # Bypass cleanup if special meta tag exists
                return unicode_type(self.page().mainFrame().toHtml())
            check = unicode_type(self.page().mainFrame().toPlainText()).strip()
            raw = unicode_type(self.page().mainFrame().toHtml())
            raw = xml_to_unicode(raw, strip_encoding_pats=True,
                                resolve_entities=True)[0]
            raw = self.comments_pat.sub('', raw)
            if not check and '<img' not in raw.lower():
                return ans

            try:
                root = html.fromstring(raw)
            except Exception:
                root = parse(raw, maybe_xhtml=False, sanitize_names=True)

            elems = []
            for body in root.xpath('//body'):
                if body.text:
                    elems.append(body.text)
                elems += [html.tostring(x, encoding='unicode') for x in body if
                    x.tag not in ('script', 'style')]

            if len(elems) > 1:
                ans = '<div>%s</div>'%(''.join(elems))
            else:
                ans = ''.join(elems)
                if not ans.startswith('<'):
                    ans = '<p>%s</p>'%ans
            ans = xml_replace_entities(ans)
        except Exception:
            import traceback
            traceback.print_exc()

        return ans

    @html.setter
    def html(self, val):
        self.setHtml(val)

    def set_base_url(self, qurl):
        self.base_url = qurl

    @pyqtSlot(int, 'QUrl', result='QVariant')
    def loadResource(self, rtype, qurl):
        if self.base_url:
            if qurl.isRelative():
                qurl = self.base_url.resolved(qurl)
            if qurl.isLocalFile():
                path = qurl.toLocalFile()
                try:
                    with lopen(path, 'rb') as f:
                        data = f.read()
                except EnvironmentError:
                    pass
                else:
                    return QByteArray(data)

    def set_html(self, val, allow_undo=True):
        if not allow_undo or self.readonly:
            self.html = val
            return
        mf = self.page().mainFrame()
        mf.evaluateJavaScript('document.execCommand("selectAll", false, null)')
        mf.evaluateJavaScript('document.execCommand("insertHTML", false, %s)' % json.dumps(unicode_type(val)))

    def text(self):
        return self.textCursor().selectedText()

    def setText(self, text):
        c = self.textCursor()
        c.insertText(text)
        self.setTextCursor(c)

    def contextMenuEvent(self, ev):
        menu = self.createStandardContextMenu()
        # paste = self.pageAction(QWebPage.Paste)
        for action in menu.actions():
            pass
            # if action == paste:
            #     menu.insertAction(action, self.pageAction(QWebPage.PasteAndMatchStyle))
        st = self.text()
        if st and st.strip():
            self.create_change_case_menu(menu)
        parent = self._parent()
        if hasattr(parent, 'toolbars_visible'):
            vis = parent.toolbars_visible
            menu.addAction(_('%s toolbars') % (_('Hide') if vis else _('Show')), parent.toggle_toolbars)
        menu.exec_(ev.globalPos())

# }}}

# Highlighter {{{


State_Text = -1
State_DocType = 0
State_Comment = 1
State_TagStart = 2
State_TagName = 3
State_InsideTag = 4
State_AttributeName = 5
State_SingleQuote = 6
State_DoubleQuote = 7
State_AttributeValue = 8


class Highlighter(QSyntaxHighlighter):

    def __init__(self, doc):
        QSyntaxHighlighter.__init__(self, doc)
        self.colors = {}
        self.colors['doctype']        = QColor(192, 192, 192)
        self.colors['entity']         = QColor(128, 128, 128)
        self.colors['tag']            = QColor(136,  18, 128)
        self.colors['comment']        = QColor(35, 110,  37)
        self.colors['attrname']       = QColor(153,  69,   0)
        self.colors['attrval']        = QColor(36,  36, 170)

    def highlightBlock(self, text):
        state = self.previousBlockState()
        len_ = len(text)
        start = 0
        pos = 0

        while pos < len_:

            if state == State_Comment:
                start = pos
                while pos < len_:
                    if text[pos:pos+3] == "-->":
                        pos += 3
                        state = State_Text
                        break
                    else:
                        pos += 1
                self.setFormat(start, pos - start, self.colors['comment'])

            elif state == State_DocType:
                start = pos
                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch == '>':
                        state = State_Text
                        break
                self.setFormat(start, pos - start, self.colors['doctype'])

            # at '<' in e.g. "<span>foo</span>"
            elif state == State_TagStart:
                start = pos + 1
                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch == '>':
                        state = State_Text
                        break
                    if not ch.isspace():
                        pos -= 1
                        state = State_TagName
                        break

            # at 'b' in e.g "<blockquote>foo</blockquote>"
            elif state == State_TagName:
                start = pos
                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch.isspace():
                        pos -= 1
                        state = State_InsideTag
                        break
                    if ch == '>':
                        state = State_Text
                        break
                self.setFormat(start, pos - start, self.colors['tag'])

            # anywhere after tag name and before tag closing ('>')
            elif state == State_InsideTag:
                start = pos

                while pos < len_:
                    ch = text[pos]
                    pos += 1

                    if ch == '/':
                        continue

                    if ch == '>':
                        state = State_Text
                        break

                    if not ch.isspace():
                        pos -= 1
                        state = State_AttributeName
                        break

            # at 's' in e.g. <img src=bla.png/>
            elif state == State_AttributeName:
                start = pos

                while pos < len_:
                    ch = text[pos]
                    pos += 1

                    if ch == '=':
                        state = State_AttributeValue
                        break

                    if ch in ('>', '/'):
                        state = State_InsideTag
                        break

                self.setFormat(start, pos - start, self.colors['attrname'])

            # after '=' in e.g. <img src=bla.png/>
            elif state == State_AttributeValue:
                start = pos

                # find first non-space character
                while pos < len_:
                    ch = text[pos]
                    pos += 1

                    # handle opening single quote
                    if ch == "'":
                        state = State_SingleQuote
                        break

                    # handle opening double quote
                    if ch == '"':
                        state = State_DoubleQuote
                        break

                    if not ch.isspace():
                        break

                if state == State_AttributeValue:
                    # attribute value without quote
                    # just stop at non-space or tag delimiter
                    start = pos
                    while pos < len_:
                        ch = text[pos]
                        if ch.isspace():
                            break
                        if ch in ('>', '/'):
                            break
                        pos += 1
                    state = State_InsideTag
                    self.setFormat(start, pos - start, self.colors['attrval'])

            # after the opening single quote in an attribute value
            elif state == State_SingleQuote:
                start = pos

                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch == "'":
                        break

                state = State_InsideTag

                self.setFormat(start, pos - start, self.colors['attrval'])

            # after the opening double quote in an attribute value
            elif state == State_DoubleQuote:
                start = pos

                while pos < len_:
                    ch = text[pos]
                    pos += 1
                    if ch == '"':
                        break

                state = State_InsideTag

                self.setFormat(start, pos - start, self.colors['attrval'])

            else:
                # State_Text and default
                while pos < len_:
                    ch = text[pos]
                    if ch == '<':
                        if text[pos:pos+4] == "<!--":
                            state = State_Comment
                        else:
                            if text[pos:pos+9].upper() == "<!DOCTYPE":
                                state = State_DocType
                            else:
                                state = State_TagStart
                        break
                    elif ch == '&':
                        start = pos
                        while pos < len_ and text[pos] != ';':
                            self.setFormat(start, pos - start,
                                    self.colors['entity'])
                            pos += 1

                    else:
                        pos += 1

        self.setCurrentBlockState(state)

# }}}


class Editor(QWidget):  # {{{

    toolbar_prefs_name = None
    data_changed = pyqtSignal()

    def __init__(self, parent=None, one_line_toolbar=False, toolbar_prefs_name=None):
        QWidget.__init__(self, parent)
        self.toolbar_prefs_name = toolbar_prefs_name or self.toolbar_prefs_name
        self.toolbar1 = QToolBar(self)
        self.toolbar2 = QToolBar(self)
        self.toolbar3 = QToolBar(self)
        for i in range(1, 4):
            t = getattr(self, 'toolbar%d'%i)
            t.setIconSize(QSize(18, 18))
        self.editor = EditorWidget(self)
        self.editor.data_changed.connect(self.data_changed)
        self.set_base_url = self.editor.set_base_url
        self.set_html = self.editor.set_html
        self.tabs = QTabWidget(self)
        self.tabs.setTabPosition(self.tabs.South)
        self.wyswyg = QWidget(self.tabs)
        self.code_edit = QPlainTextEdit(self.tabs)
        self.source_dirty = False
        self.wyswyg_dirty = True

        self._layout = QVBoxLayout(self)
        self.wyswyg.layout = l = QVBoxLayout(self.wyswyg)
        self.setLayout(self._layout)
        l.setContentsMargins(0, 0, 0, 0)
        if one_line_toolbar:
            tb = QHBoxLayout()
            l.addLayout(tb)
        else:
            tb = l
        tb.addWidget(self.toolbar1)
        tb.addWidget(self.toolbar2)
        tb.addWidget(self.toolbar3)
        l.addWidget(self.editor)
        self._layout.addWidget(self.tabs)
        self.tabs.addTab(self.wyswyg, _('N&ormal view'))
        self.tabs.addTab(self.code_edit, _('&HTML source'))
        self.tabs.currentChanged[int].connect(self.change_tab)
        self.highlighter = Highlighter(self.code_edit.document())
        self.layout().setContentsMargins(0, 0, 0, 0)
        if self.toolbar_prefs_name is not None:
            hidden = gprefs.get(self.toolbar_prefs_name)
            if hidden:
                self.hide_toolbars()

        # toolbar1 {{{
        self.toolbar1.addAction(self.editor.action_undo)
        self.toolbar1.addAction(self.editor.action_redo)
        self.toolbar1.addAction(self.editor.action_select_all)
        self.toolbar1.addAction(self.editor.action_remove_format)
        self.toolbar1.addAction(self.editor.action_clear)
        self.toolbar1.addSeparator()

        for x in ('copy', 'cut', 'paste'):
            ac = getattr(self.editor, 'action_'+x)
            self.toolbar1.addAction(ac)

        self.toolbar1.addSeparator()
        self.toolbar1.addAction(self.editor.action_background)
        # }}}

        # toolbar2 {{{
        for x in ('', 'un'):
            ac = getattr(self.editor, 'action_%sordered_list'%x)
            self.toolbar2.addAction(ac)
        self.toolbar2.addSeparator()
        for x in ('superscript', 'subscript', 'indent', 'outdent'):
            self.toolbar2.addAction(getattr(self.editor, 'action_' + x))
            if x in ('subscript', 'outdent'):
                self.toolbar2.addSeparator()

        self.toolbar2.addAction(self.editor.action_block_style)
        w = self.toolbar2.widgetForAction(self.editor.action_block_style)
        if hasattr(w, 'setPopupMode'):
            w.setPopupMode(w.InstantPopup)
        self.toolbar2.addAction(self.editor.action_insert_link)
        self.toolbar2.addAction(self.editor.action_insert_hr)
        # }}}

        # toolbar3 {{{
        for x in ('bold', 'italic', 'underline', 'strikethrough'):
            ac = getattr(self.editor, 'action_'+x)
            self.toolbar3.addAction(ac)
        self.toolbar3.addSeparator()

        for x in ('left', 'center', 'right', 'justified'):
            ac = getattr(self.editor, 'action_align_'+x)
            self.toolbar3.addAction(ac)
        self.toolbar3.addSeparator()
        self.toolbar3.addAction(self.editor.action_color)
        # }}}

        self.code_edit.textChanged.connect(self.code_dirtied)
        self.editor.data_changed.connect(self.wyswyg_dirtied)

    def set_minimum_height_for_editor(self, val):
        self.editor.setMinimumHeight(val)

    @property
    def html(self):
        self.tabs.setCurrentIndex(0)
        return self.editor.html

    @html.setter
    def html(self, v):
        self.editor.html = v

    def change_tab(self, index):
        # print 'reloading:', (index and self.wyswyg_dirty) or (not index and
        #        self.source_dirty)
        if index == 1:  # changing to code view
            if self.wyswyg_dirty:
                self.code_edit.setPlainText(self.editor.html)
                self.wyswyg_dirty = False
        elif index == 0:  # changing to wyswyg
            if self.source_dirty:
                self.editor.html = unicode_type(self.code_edit.toPlainText())
                self.source_dirty = False

    @property
    def tab(self):
        return 'code' if self.tabs.currentWidget() is self.code_edit else 'wyswyg'

    @tab.setter
    def tab(self, val):
        self.tabs.setCurrentWidget(self.code_edit if val == 'code' else self.wyswyg)

    def wyswyg_dirtied(self, *args):
        self.wyswyg_dirty = True

    def code_dirtied(self, *args):
        self.source_dirty = True

    def hide_toolbars(self):
        self.toolbar1.setVisible(False)
        self.toolbar2.setVisible(False)
        self.toolbar3.setVisible(False)

    def show_toolbars(self):
        self.toolbar1.setVisible(True)
        self.toolbar2.setVisible(True)
        self.toolbar3.setVisible(True)

    def toggle_toolbars(self):
        visible = self.toolbars_visible
        getattr(self, ('hide' if visible else 'show') + '_toolbars')()
        if self.toolbar_prefs_name is not None:
            gprefs.set(self.toolbar_prefs_name, visible)

    @property
    def toolbars_visible(self):
        return self.toolbar1.isVisible() or self.toolbar2.isVisible() or self.toolbar3.isVisible()

    @toolbars_visible.setter
    def toolbars_visible(self, val):
        getattr(self, ('show' if val else 'hide') + '_toolbars')()

    def set_readonly(self, what):
        self.editor.set_readonly(what)

    def hide_tabs(self):
        self.tabs.tabBar().setVisible(False)

# }}}


if __name__ == '__main__':
    app = QApplication([])
    w = Editor()
    w.resize(800, 600)
    w.show()
    w.html = '''<span style="background-color: rgb(0, 255, 255); ">He hadn't
    set out to have an <em>affair</em>, <span style="font-style:italic; background-color:red">much</span> less a long-term, devoted one.</span>'''
    app.exec_()
    # print w.html
