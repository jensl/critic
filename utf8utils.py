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

def convertUTF8(text):
    # Check if it's already valid UTF-8 and return it unchanged if so.
    try:
        text.decode('utf-8')
        return text
    except: pass

    # Try to decode as latin-1.
    try: return text.decode('latin-1').encode('utf-8')
    except: pass

    # Fallback: just replace all non-ASCII characters with '?'.
    return re.sub("[\x80-\xff]", "?", text)
