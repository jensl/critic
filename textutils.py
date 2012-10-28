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

json_encode = json.dumps

def json_decode(s):
    def deunicode(v):
        if type(v) == unicode: return v.encode("utf-8")
        elif type(v) == list: return map(deunicode, v)
        elif type(v) == dict: return dict([(deunicode(a), deunicode(b)) for a, b in v.items()])
        else: return v

    return deunicode(json.loads(s))
