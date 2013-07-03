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

import gitutils
import htmlutils
import diff

from operation import Operation, OperationResult

class FetchLines(Operation):
    def __init__(self):
        Operation.__init__(self, { "repository_id": int,
                                   "path": str,
                                   "sha1": str,
                                   "ranges": [{ "offset": int,
                                                "count": int,
                                                "context": bool }],
                                   "tabify": bool },
                           accept_anonymous_user=True)

    def process(self, db, user, repository_id, path, sha1, ranges, tabify):
        repository = gitutils.Repository.fromId(db, repository_id)
        cursor = db.cursor()

        def getContext(offset):
            cursor.execute("""SELECT context
                                FROM codecontexts
                               WHERE sha1=%s
                                 AND %s BETWEEN first_line AND last_line
                            ORDER BY first_line DESC
                               LIMIT 1""",
                           (sha1, offset))

            row = cursor.fetchone()

            if row: return row[0]
            else: return None

        file = diff.File(repository=repository, path=path, new_sha1=sha1)
        file.loadNewLines(highlighted=True, request_highlight=True)

        if tabify:
            tabwidth = file.getTabWidth()
            indenttabsmode = file.getIndentTabsMode()

        def processRange(offset, count, context):
            if context: context = getContext(offset)
            else: context = None

            # Offset is a 1-based line number.
            start = offset - 1
            # If count is -1, fetch all lines.
            end = start + count if count > -1 else None

            lines = file.newLines(highlighted=True)[start:end]

            if tabify:
                lines = [htmlutils.tabify(line, tabwidth, indenttabsmode) for line in lines]

            return { "lines": lines, "context": context }

        return OperationResult(ranges=[processRange(**line_range) for line_range in ranges])
