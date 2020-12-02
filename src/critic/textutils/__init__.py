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
from typing import Collection, Optional, Set, Union


def reflow(text: str, line_length: int = 80, indent: int = 0, hanging_indent: int = 0):
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
            words = re.split(r"(\s+)", paragraph)
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


DEFAULT_ENCODINGS: Set[str] = set()


def decode(
    text: Union[bytes, str], *, default_encodings: Optional[Collection[str]] = None
) -> str:
    assert isinstance(text, (bytes, str))

    if isinstance(text, str):
        return text

    from critic import api

    if default_encodings is None:
        default_encodings = DEFAULT_ENCODINGS

    if not default_encodings:
        try:
            default_encodings = api.critic.settings().content.default_encodings
            assert default_encodings
            DEFAULT_ENCODINGS.update(default_encodings)
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


def filtercr(text: str) -> str:
    lines = text.splitlines(True)
    for index in range(len(lines)):
        _, _, lines[index] = lines[index].rpartition("\r")
    return "".join(lines)
