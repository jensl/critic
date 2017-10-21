# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2012 Jens Lindström, Opera Software ASA
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License.  You may obtain a copy of
# the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  See the
# License for the specific language governing permissions and limitations under
# the License.

import re
import time
import os
import json
import urllib

import textutils

from io import StringIO

from linkify import ALL_LINKTYPES, Context

fragments = []
for linktype in ALL_LINKTYPES:
    if linktype.fragment:
        fragments.append(linktype.fragment)
re_linkify = re.compile("(?:^|\\b|(?=\\W))(" + "|".join(fragments) + ")([.,:;!?)]*(?:\\s|\\b|$))")

re_simple = re.compile("^[^ \t\r\n&<>/=`'\"]+$")
re_nonascii = re.compile("[^\t\n\r -\x7f]")
re_control = re.compile("[\x01-\x1f\x7f]")

def htmlify(text, attributeValue=False, pretty=False):
    if isinstance(text, unicode): text = re_nonascii.sub(lambda x: "&#%d;" % ord(x.group()), text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))
    else: text = str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if attributeValue:
        if not pretty and re_simple.match(text): return text
        elif "'" in text:
            if '"' not in text: text = '"' + text + '"'
            else: text = "'" + text.replace("'", '&apos;') + "'"
        else: text = "'" + text + "'"
        text = re_control.sub(lambda match: "&#%d;" % ord(match.group()), text)
    return text

def jsify(what, as_json=False):
    if what is None: return "null"
    elif isinstance(what, bool): return "true" if what else "false"
    elif isinstance(what, int): return str(what)
    else:
        what = textutils.decode(what)
        result = json.dumps(what)
        if not as_json:
            quote = result[0]
            return result.replace("</", "<%s+%s/" % (quote, quote)).replace("<!", "<%s+%s!" % (quote, quote))
        else:
            return result

re_tag = re.compile("<[^>]+>")

def tabify(line, tabwidth=8, indenttabsmode=True):
    index = 0
    length = len(line)
    column = 0
    result = ""

    try:
        leading = True
        while index < length:
            tabindex = line.index("\t", index)
            nontabbed = line[index:tabindex]
            nontabbed_length = len(re_tag.sub("", nontabbed))
            illegal = ""
            if leading:
                if nontabbed_length != 0:
                    leading = False
                elif not indenttabsmode:
                    illegal = " ill"
            width = tabwidth - (column + nontabbed_length) % tabwidth
            result += nontabbed + "<b class='t w%d%s'></b>" % (width, illegal)
            index = tabindex + 1
            column = column + nontabbed_length + width
    except:
        result += line[index:]

    return result

BLOCK_ELEMENTS = {"html", "head", "body", "section", "table", "thead", "tbody", "tfoot", "tr", "td", "th", "div", "p", "ol", "li", "label", "select", "option", "link", "script"}
EMPTY_ELEMENTS = {"br", "hr", "input", "link", "base", "col"}

def isBlockElement(name):
    return name in BLOCK_ELEMENTS

def isEmptyElement(name):
    return name in EMPTY_ELEMENTS

def mtime(path):
    try: return int(os.stat(path).st_mtime)
    except: raise

def base36(n):
    s = ""
    while n:
        s = "0123456789abcdefghijklmnopqrstuvwxyz"[n % 36] + s
        n = n // 36
    return s

def getStaticResourceURI(name):
    import configuration
    uri = "/static-resource/" + name
    ts = mtime(os.path.join(configuration.paths.INSTALL_DIR, "resources", name))
    if ts: uri += "?" + base36(ts)
    return uri

class URL(object):
    def __init__(self, path, fragment=None, **query):
        assert path.startswith("/")
        assert "?" not in path
        assert "#" not in path
        self.value = path
        if query:
            self.value += "?" + urllib.urlencode(
                [(name, str(value)) for name, value in query.items()])
        if fragment:
            self.value += "#" + fragment.lstrip("#")
    def __str__(self):
        return self.value

class MetaInformation(object):
    def __init__(self):
        self.__orderIndices = set()
        self.__externalStylesheetList = []
        self.__externalStylesheetSet = set()
        self.__internalStylesheetList = []
        self.__internalStylesheetSet = set()
        self.__externalScriptList = []
        self.__externalScriptSet = set()
        self.__internalScriptList = []
        self.__links = {}
        self.__title = None
        self.__finished = False
        self.__request = None
        self.__base = "/"

    def addExternalStylesheet(self, uri, use_static=True, order=0):
        if use_static:
            uri = getStaticResourceURI(uri.split("/", 1)[1])
        if uri not in self.__externalStylesheetSet:
            self.__orderIndices.add(order)
            self.__externalStylesheetList.append((order, uri))
            self.__externalStylesheetSet.add(uri)

    def addInternalStylesheet(self, text, order=0):
        if text not in self.__internalStylesheetSet:
            self.__orderIndices.add(order)
            self.__internalStylesheetList.append((order, text))
            self.__internalStylesheetSet.add(text)

    def addExternalScript(self, uri, use_static=True, order=0):
        if use_static:
            uri = getStaticResourceURI(uri.split("/", 1)[1])
        if uri not in self.__externalScriptSet:
            self.__orderIndices.add(order)
            self.__externalScriptList.append((order, uri))
            self.__externalScriptSet.add(uri)

    def addInternalScript(self, text, order=0):
        self.__orderIndices.add(order)
        self.__internalScriptList.append((order, text))

    def hasTitle(self):
        return self.__title is not None

    def setTitle(self, title):
        self.__title = title

    def setLink(self, rel, href):
        return self.__links.setdefault(rel, href)

    def setBase(self, base):
        self.__base = base

    def setRequest(self, req):
        self.__request = req

    def getRequest(self):
        return self.__request

    def render(self, target):
        import configuration

        if not self.__finished:
            if self.__title:
                target.title().text(self.__title)
            if self.__base:
                target.base(href=self.__base)
            for rel, href in self.__links.items():
                target.link(rel=rel, href=href)

            for index in sorted(self.__orderIndices):
                def filtered(items): return [data for order, data in items if order==index]

                for uri in filtered(self.__externalStylesheetList):
                    target.link(rel="stylesheet", type="text/css", href=uri)
                for uri in filtered(self.__externalScriptList):
                    target.script(type="text/javascript", src=uri)
                for text in filtered(self.__internalStylesheetList):
                    target.style(type="text/css").text(text.strip(), cdata=True)
                for text in filtered(self.__internalScriptList):
                    target.script(type="text/javascript").text(text.strip(), cdata=True)

            if configuration.debug.IS_DEVELOPMENT:
                favicon = "/static-resource/favicon-dev.png"
            else:
                favicon = "/static-resource/favicon.png"

            target.link(rel="icon", type="image/png", href=favicon)

            self.__finished = True

class PausedRendering: pass

class Fragment(object):
    def __init__(self, is_element=False, req=None):
        self.__children = []
        self.__metaInformation = not is_element and MetaInformation() or None

    def appendChild(self, child):
        self.__children.append(child)
        return child

    def insertChild(self, child, offset=0):
        self.__children.insert(offset, child)
        return child

    def removeChild(self, child):
        assert child in self.__children
        self.__children.remove(child)

    def metaInformation(self):
        return self.__metaInformation

    def __len__(self): return len(self.__children)
    def __getitem__(self, index): return self.__children[index]
    def __str__(self): return "".join(map(str, self.__children))

    def render(self, output, level=0, indent_before=True, stop=None, pretty=True):
        for child in self.__children:
            child.render(output, level, indent_before, stop=stop, pretty=pretty)
            if pretty: output.write("\n")

    def deleteChildren(self, count=None):
        if count is None: self.__children = []
        else: del self.__children[:count]

    def hasChildren(self):
        return bool(self.__children)

class Element(Fragment):
    def __init__(self, name):
        super(Element, self).__init__(True)
        self.__name = name
        self.__attributes = {}
        self.__empty = isEmptyElement(name)
        self.__preformatted = False
        self.__metaInformation = None
        self.__rendered = False
        self.__disabled = False

    def setAttribute(self, name, value):
        self.__attributes[name] = value

    def addClass(self, *names):
        classes = set(self.__attributes.get("class").split())
        classes.update(names)
        self.setAttribute("class", " ".join(classes))

    def setPreFormatted(self):
        self.__preformatted = True

    def setMetaInformation(self, metaInformation):
        self.__metaInformation = metaInformation

    def appendChild(self, child):
        assert not self.__empty
        return Fragment.appendChild(self, child)

    def remove(self):
        self.__disabled = True
    def removeIfEmpty(self):
        self.__disabled = not self.hasChildren()

    def __str__(self):
        attributes = "".join([(" %s=%s" % (name, htmlify(value, True))) for name, value in self.__attributes.items()])
        if isEmptyElement(self.__name):
            return "<%s%s>" % (self.__name, attributes)
        else:
            return "<%s%s>%s</%s>" % (self.__name, attributes, Fragment.__str__(self), self.__name)

    def render(self, output, level=0, indent_before=True, stop=None, pretty=True):
        if self.__disabled: return

        if self.__metaInformation: self.__metaInformation.render(Generator(self, None))

        if pretty: indent = "  " * level
        else: indent = ""

        if indent_before: startindent = indent
        else: startindent = ""

        for child in self:
            if isinstance(child, Element) and isBlockElement(child.__name) or (isinstance(child, Text) or isinstance(child, Comment)) and '\n' in str(child):
                linebreak = "\n"
                endindent = indent
                break
        else:
            indent_before = False
            linebreak = ""
            endindent = ""

        if not pretty or self.__preformatted:
            child_level = 0
            linebreak = ""
            endindent = ""
        else: child_level = level + 1

        attributes = "".join([(" %s=%s" % (name, htmlify(value, True, pretty))) for name, value in self.__attributes.items()])

        if self.__empty:
            if not self.__rendered:
                output.write("%s<%s%s>" % (startindent, self.__name, attributes))
            self.__rendered = True
        else:
            if not self.__rendered:
                output.write("%s<%s%s>%s" % (startindent, self.__name, attributes, linebreak))
            self.__rendered = True

            children_rendered = 0
            for child in self:
                if self.__preformatted: child.setPreFormatted()
                try:
                    child.render(output, child_level, indent_before, stop, pretty)
                    output.write(linebreak)
                    children_rendered += 1
                except PausedRendering:
                    self.deleteChildren(children_rendered)
                    raise

            self.deleteChildren()

            if self == stop: raise PausedRendering
            else: output.write("%s</%s>" % (endindent, self.__name))

    def empty(self):
        self.__empty = True

class Text(object):
    def __init__(self, value, preformatted=False, cdata=False):
        if cdata: self.__value = value
        elif value is None: self.__value = "&nbsp;"
        else: self.__value = htmlify(value)
        self.__preformatted = preformatted

    def setPreFormatted(self):
        self.__preformatted = True

    def render(self, output, level=0, indent_before=True, stop=None, pretty=True):
        if pretty and level and not self.__preformatted and '\n' in self.__value:
            indent = "  " * level
            if indent_before: startindent = indent
            else: startindent = ""
            output.write(startindent + ('\n' + indent).join([line for line in self.__value.strip().splitlines()]))
        else:
            output.write(self.__value)

    def __str__(self):
        return self.__value

class Comment(object):
    def __init__(self, value):
        self.__value = value.replace("--", "- -")

    def setPreFormatted(self):
        pass

    def render(self, output, level=0, indent_before=True, stop=None, pretty=True):
        if pretty and level and '\n' in self.__value:
            indent = "  " * level
            if indent_before: startindent = indent
            else: startindent = ""
            output.write(startindent + "<!-- " + ('\n' + indent + "     ").join(htmlify(self.__value).splitlines()) + " -->")
        else:
            output.write("<!-- " + self.__value + " -->")

    def __str__(self):
        return self.__value

class HTML(object):
    def __init__(self, value):
        self.__value = value

    def setPreFormatted(self):
        pass

    def render(self, output, level=0, indent_before=True, stop=None, pretty=True):
        output.write(self.__value)

    def __str__(self):
        return self.__value

def safestr(value):
    try: return str(value)
    except: return unicode(value)

class Generator(object):
    def __init__(self, target, metaInformation):
        self.__target = target
        self.__metaInformation = metaInformation

    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False

    def __eq__(self, other):
        return other == self.__target

    def __open(self, __name, **attributes):
        target = self.__target.appendChild(Element(__name))
        if "__generator__" in attributes:
            del attributes["__generator__"]
            generator = True
        else:
            generator = __name not in EMPTY_ELEMENTS
        for name, value in attributes.items():
            if value is not None:
                target.setAttribute(name.strip("_").replace("_", "-"), safestr(value))
        if not generator: return self
        else: return Generator(target, self.__metaInformation)

    def __getattr__(self, name):
        def open(*className, **attributes):
            assert len(className) == 0 or len(className) == 1
            if className: return self.__open(name, _class=className[0], **attributes)
            else: return self.__open(name, **attributes)
        return open

    def head(self, **attributes):
        target = self.__target.appendChild(Element("head"))
        for name, value in attributes.items():
            if value is not None:
                target.setAttribute(name.strip("_").replace("_", "-"), safestr(value))
        target.setMetaInformation(self.__metaInformation)
        return Generator(target, self.__metaInformation)

    def append(self, fragment):
        if fragment is not None:
            if isinstance(fragment, Generator): self.__target.appendChild(fragment.__target)
            else: self.__target.appendChild(fragment)

    def remove(self):
        self.__target.remove()
    def removeIfEmpty(self):
        self.__target.removeIfEmpty()

    def text(self, value=None, preformatted=False, cdata=False, linkify=False, repository=None, escape=False):
        if linkify:
            assert not cdata

            if isinstance(linkify, Context):
                context = linkify
            else:
                context = Context(repository=repository)

            for linktype in ALL_LINKTYPES:
                if linktype.match(value):
                    url = linktype.linkify(value, context)
                    if url:
                        self.a(href=url).text(value, escape=escape)
                        break
            else:
                for word in re_linkify.split(value):
                    if word:
                        for linktype in ALL_LINKTYPES:
                            if linktype.match(word):
                                url = linktype.linkify(word, context)
                                if url:
                                    self.a(href=url).text(word, escape=escape)
                                    break
                        else:
                            self.text(word, preformatted, escape=escape)
        else:
            if escape:
                value = textutils.escape(value)
            self.__target.appendChild(Text(value, preformatted, cdata))
        return self

    def comment(self, value):
        self.__target.appendChild(Comment(safestr(value)))
        return self

    def commentFirst(self, value):
        self.__target.insertChild(Comment(safestr(value)), offset=0)
        return self

    def innerHTML(self, value="&nbsp;"):
        self.__target.appendChild(HTML(safestr(value)))
        return self

    def setAttribute(self, name, value):
        self.__target.setAttribute(name, value)
        return self

    def addClass(self, *names):
        self.__target.addClass(*names)
        return self

    def render(self, output, level=0, stop=None, pretty=True):
        self.__target.render(output, level, stop=stop, pretty=pretty)

    def empty(self):
        self.__target.empty()
        return self

    def preformatted(self):
        self.__target.setPreFormatted()
        return self

    def addExternalStylesheet(self, uri, use_static=True, order=0):
        self.__metaInformation.addExternalStylesheet(uri, use_static, order=order)

    def addInternalStylesheet(self, text, order=0):
        self.__metaInformation.addInternalStylesheet(text, order=order)

    def addExternalScript(self, uri, use_static=True, order=0):
        self.__metaInformation.addExternalScript(uri, use_static, order=order)

    def addInternalScript(self, text, here=False, order=0):
        if here:
            self.script(type="text/javascript").text(text.strip().replace("</", "<\/"), cdata=True)
        else:
            self.__metaInformation.addInternalScript(text, order=order)

    def hasTitle(self):
        return self.__metaInformation.hasTitle()

    def setTitle(self, title):
        self.__metaInformation.setTitle(title)

    def setLink(self, rel, href):
        self.__metaInformation.setLink(rel, href)

    def setBase(self, base):
        self.__metaInformation.setBase(base)

    def getRequest(self):
        return self.__metaInformation.getRequest()

class Document(Generator):
    def __init__(self, req=None):
        self.__fragment = Fragment()
        Generator.__init__(self, self.__fragment, self.__fragment.metaInformation())
        self.__start = time.time()
        self.__generation = 0.0
        self.__rendering = 0.0
        self.__doctype = True

        if req: self.__fragment.metaInformation().setRequest(req)

    def render(self, plain=False, stop=None, pretty=True):
        self.__generation += time.time() - self.__start

        output = StringIO()
        if not plain and self.__doctype:
            output.write("<!DOCTYPE html>")
            self.__doctype = False

        before = time.time()
        try:
            Generator.render(self, output, stop=stop, pretty=pretty)
            finished = True
        except PausedRendering:
            finished = False
        after = time.time()

        self.__rendering += after - before

        if not plain and finished:
            output.write("\n<!-- generation: %.2f ms, rendering: %.2f ms -->" % (self.__generation * 1000, self.__rendering * 1000))

        self.__start = time.time()
        return output.getvalue()

    def __str__(self):
        return self.render()

def stripStylesheet(text, compact):
    if compact:
        text = re.sub(r"/\*(?:[^*]|\*[^/])*\*/", "", text)
        text = re.sub(r"\s*([,:;{}])\s*", lambda m: m.group(1), text)
        text = re.sub(r"\s+", " ", text)
    return text

if __name__ == "__main__":
    generator = Document()
    row = generator.html().body().table(border=1).tbody().tr()
    row.td(_class="left").div(id="foo").text("Column 1\nMore text")
    row.td(_class="right").text("text").comment("comment")
    print(generator.render())
