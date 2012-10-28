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

import os
import os.path
import bz2

import htmlutils
import configuration

LANGUAGES = set()

def generateHighlightPath(sha1, language):
    return os.path.join(configuration.services.HIGHLIGHT["cache_dir"], sha1[:2], sha1[2:] + "." + language)

def isHighlighted(sha1, language):
    return os.path.exists(generateHighlightPath(sha1, language))

def readHighlight(repository, sha1, path, language, request=False):
    path = generateHighlightPath(sha1, language)

    if os.path.isfile(path):
        os.utime(path, None)
        source = open(path).read()
    elif os.path.isfile(path + ".bz2"):
        os.utime(path + ".bz2", None)
        source = bz2.BZ2File(path + ".bz2", "r").read()
    elif request:
        import request
        request.requestHighlights(repository, { sha1: (path, language) })
        return readHighlight(repository, sha1, path, language)
    else:
        source = None

    if not source:
        source = htmlutils.htmlify(repository.fetch(sha1)[2])

    return source.replace("\r", "")
