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
import textwrap
import unicodedata


def reflow(text, line_length=80, indent=0, hanging_indent=0):
    if line_length == 0:
        return text

    paragraphs = re.split("\n\n+", text.replace("\r", ""))
    spaces = " " * indent
    hanging_spaces = " " * (indent + hanging_indent)

    for paragraph_index, paragraph in enumerate(paragraphs):
        lines = paragraph.split("\n")
        for line_index, line in enumerate(lines):
            if (line and line[0] in " \t-*") or (
                line_index < len(lines) - 1 and len(line) < 0.5 * line_length
            ):
                if indent:
                    paragraphs[paragraph_index] = "\n".join(
                        spaces + line for line in lines
                    )
                break
        else:
            lines = []
            line = spaces
            words = re.split("(\s+)", paragraph)
            ws = ""
            for word in words:
                if not word.strip():
                    if "\n" in word:
                        ws = " "
                    else:
                        ws = word
                else:
                    if (
                        len(line) > indent
                        and len(line) + len(ws) + len(word) > line_length
                    ):
                        lines.append(line)
                        line = hanging_spaces
                    if len(line) > indent:
                        line += ws
                    line += word
            if line:
                lines.append(line)
            paragraphs[paragraph_index] = "\n".join(lines)

    text = "\n\n".join(paragraphs)

    return text


def indent(string, width=4):
    return textwrap.indent(string, " " * width)


def summarize(string, max_length=80, as_html=False):
    if len(string) <= max_length:
        return string
    string = string[: max_length - 5]
    if as_html:
        from critic import htmlutils

        return htmlutils.htmlify(string) + "[&#8230;]"
    else:
        return string + "[...]"


def escape(text):
    special = {
        "\a": "a",
        "\b": "b",
        "\t": "t",
        "\n": "n",
        "\v": "v",
        "\f": "f",
        "\r": "r",
    }

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

    return escaped


DEFAULT_ENCODINGS = None


def decode(text, *, default_encodings=None):
    global DEFAULT_ENCODINGS

    assert isinstance(text, (bytes, str))

    if isinstance(text, str):
        return text

    from critic import api

    if default_encodings is None:
        default_encodings = DEFAULT_ENCODINGS

    if default_encodings is None:
        try:
            default_encodings = api.critic.settings().content.default_encodings
            DEFAULT_ENCODINGS = default_encodings
        except api.critic.SessionNotInitialized:
            default_encodings = ["utf-8"]

    for encoding in default_encodings:
        try:
            decoded = text.decode(encoding)
        except UnicodeDecodeError:
            continue
        except LookupError:
            pass
        else:
            # Replace characters in the surrogate pair range with U+FFFD since
            # PostgreSQL's UTF-8 decoder won't accept them.
            # return re.sub("[\ud800-\udfff]", "\\ufffd", decoded)
            return decoded

    return text.decode("ascii", errors="replace")


def filtercr(text):
    lines = text.splitlines(True)
    for index in range(len(lines)):
        _, _, lines[index] = lines[index].rpartition("\r")
    return "".join(lines)
