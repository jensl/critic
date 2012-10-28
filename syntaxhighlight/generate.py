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
import errno

import syntaxhighlight
import gitutils

def createHighlighter(language):
    import cpp
    highlighter = cpp.HighlightCPP.create(language)
    if highlighter: return highlighter

    import generic
    highlighter = generic.HighlightGeneric.create(language)
    if highlighter: return highlighter

def generateHighlight(repository_path, sha1, language, output_file=None):
    highlighter = createHighlighter(language)
    if not highlighter: return False

    source = gitutils.Repository.readObject(repository_path, "blob", sha1)

    if output_file:
        highlighter(source, output_file, None)
    else:
        output_path = syntaxhighlight.generateHighlightPath(sha1, language)

        try: os.makedirs(os.path.dirname(output_path))
        except OSError, error:
            if error.errno == errno.EEXIST: pass
            else: raise

        output_file = open(output_path + ".tmp", "w")
        contexts_path = output_path + ".ctx"

        highlighter(source, output_file, contexts_path)

        output_file.close()

        os.chmod(output_path + ".tmp", 0660)
        os.rename(output_path + ".tmp", output_path)

    return True
