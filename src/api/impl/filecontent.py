# -*- mode: python; encoding: utf-8 -*-
#
# Copyright 2017 the Critic contributors, Opera Software ASA
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

import api
import api.impl
from api.impl import apiobject
import diff

class Filecontent(apiobject.APIObject):
    wrapper_class = api.filecontent.Filecontent

    def __init__(self, critic, repository, blob_sha1, file_obj):
        diffFile = diff.File(
            repository=repository._impl.getInternal(critic), path=file_obj.path,
            new_sha1=blob_sha1)
        diffFile.loadNewLines(
            highlighted=True, request_highlight=True, highlight_mode="json")
        self.__filecontents = diffFile.newLines(highlighted=True)

    def getLines(self, first_row, last_row):
        num_lines = len(self.__filecontents)

        actual_first_row = min(first_row, num_lines)
        if actual_first_row is None:
            actual_first_row = 1

        actual_last_row = min(max(last_row, actual_first_row), num_lines)
        if actual_last_row is None:
            actual_last_row = num_lines

        lines = []
        for offset in range(actual_first_row-1, actual_last_row):
            parts = api.impl.filediff.parts_from_html(self.__filecontents[offset])
            lines.append(api.filecontent.Line(parts, offset+1))

        return lines

def fetch(critic, repository, blob_sha1, file_obj):
    return Filecontent(critic, repository, blob_sha1, file_obj).wrap(critic)
