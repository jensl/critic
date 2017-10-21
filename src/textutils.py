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
import json
import unicodedata

try:
    import configuration

    DEFAULT_ENCODINGS = configuration.base.DEFAULT_ENCODINGS[:]
except ImportError:
    # This is the default set of default encodings.  We could fail to
    # import 'configuration' for two principal reasons:
    #
    #  1) There's some catastrophic problem with the system.  Ignoring
    #     the problem here won't make the least bit of difference.
    #
    #  2) We're trying to run unit tests without an installed system.
    #     This fallback is simply nice in that case.

    DEFAULT_ENCODINGS = ["utf-8"]

def reflow(text, line_length=80, indent=0):
    if line_length == 0: return text

    paragraphs = re.split("\n\n+", text.replace("\r", ""))
    spaces = " " * indent

    for paragraph_index, paragraph in enumerate(paragraphs):
        lines = paragraph.split("\n")
        for line_index, line in enumerate(lines):
            if (line and line[0] in " \t-*") or line_index < len(lines) - 1 and len(line) < 0.5 * line_length:
                if indent:
                    paragraphs[paragraph_index] = "\n".join([spaces + line for line in lines])
                break
        else:
            lines = []
            line = spaces
            words = re.split("(\s+)", paragraph)
            ws = ""
            for word in words:
                if not word.strip():
                    if "\n" in word: ws = " "
                    else: ws = word
                else:
                    if len(line) > indent and len(line) + len(ws) + len(word) > line_length:
                        lines.append(line)
                        line = spaces
                    if len(line) > indent: line += ws
                    line += word
            if line: lines.append(line)
            paragraphs[paragraph_index] = "\n".join(lines)

    text = "\n\n".join(paragraphs)

    if isinstance(text, unicode): return text.encode("utf-8")
    else: return text

def indent(string, width=4):
    prefix = " " * width
    return prefix + ("\n" + prefix).join(string.splitlines())

def summarize(string, max_length=80, as_html=False):
    if len(string) <= max_length:
        return string
    string = string[:max_length - 5]
    if as_html:
        import htmlutils
        return htmlutils.htmlify(string) + "[&#8230;]"
    else:
        return string + "[...]"

def escape(text):
    special = { "\a": "a",
                "\b": "b",
                "\t": "t",
                "\n": "n",
                "\v": "v",
                "\f": "f",
                "\r": "r" }

    def escape1(match):
        substring = match.group(0)

        if ord(substring) < 128:
            if substring in special:
                return "\\%s" % special[substring]
            elif ord(substring) < 32:
                return "\\x%02x" % ord(substring)
            else:
                return substring

        category = unicodedata.category(substring)
        if category[0] in "CZ" or category == "So":
            if ord(substring) < 256:
                return "\\x%02x" % ord(substring)
            elif ord(substring) < 65536:
                return "\\u%04x" % ord(substring)
            else:
                return "\\U%08x" % ord(substring)
        else:
            return substring

    text = decode(str(text))
    escaped = re.sub("\W", escape1, text, flags=re.UNICODE)

    return escaped.encode("utf-8")

json_encode = json.dumps

def deunicode(v):
    if isinstance(v, unicode): return v.encode("utf-8")
    elif isinstance(v, list): return list(map(deunicode, v))
    elif isinstance(v, dict): return dict([(deunicode(a), deunicode(b)) for a, b in v.items()])
    else: return v

def json_decode(s):
    return deunicode(json.loads(s))

def decode(text):
    if isinstance(text, unicode):
        return text

    text = str(text)

    for index, encoding in enumerate(DEFAULT_ENCODINGS):
        try:
            decoded = text.decode(encoding)
        except UnicodeDecodeError:
            continue
        except LookupError:
            del DEFAULT_ENCODINGS[index]
        else:
            # Replace characters in the surrogate pair range with U+FFFD since
            # PostgreSQL's UTF-8 decoder won't accept them.
            return re.sub(u"[\ud800-\udfff]", "\ufffd", decoded)

    return text.decode("ascii", errors="replace")

def encode(text):
    if isinstance(text, unicode):
        return text.encode("utf-8")
    return str(text)
