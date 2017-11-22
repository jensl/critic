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

from critic import textutils

re_simple = re.compile("^[^ \t\r\n&<>/=`'\"]+$")
re_nonascii = re.compile("[^\t\n\r -\x7f]")
re_control = re.compile("[\x01-\x1f\x7f]")


def htmlify(text, attributeValue=False, pretty=False):
    if isinstance(text, str):
        text = re_nonascii.sub(
            lambda x: "&#%d;" % ord(x.group()),
            text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
        )
    else:
        text = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    if attributeValue:
        if not pretty and re_simple.match(text):
            return text
        elif "'" in text:
            if '"' not in text:
                text = '"' + text + '"'
            else:
                text = "'" + text.replace("'", "&apos;") + "'"
        else:
            text = "'" + text + "'"
        text = re_control.sub(lambda match: "&#%d;" % ord(match.group()), text)
    return text


def jsify(what, as_json=False):
    if what is None:
        return "null"
    elif isinstance(what, bool):
        return "true" if what else "false"
    elif isinstance(what, int):
        return str(what)
    else:
        what = textutils.decode(what)
        result = json.dumps(what)
        if not as_json:
            quote = result[0]
            return result.replace("</", "<%s+%s/" % (quote, quote)).replace(
                "<!", "<%s+%s!" % (quote, quote)
            )
        else:
            return result
