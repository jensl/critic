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

import diff
import diff.context

from changeset.utils import getCodeContext

def unified(db, changeset, context_lines=3):
    result = ""

    for file in changeset.files:
        file.loadOldLines()
        file.loadNewLines()

        try:
            lines = diff.context.ContextLines(file, file.chunks)

            file.macro_chunks = lines.getMacroChunks(context_lines, highlight=False)

            oldPath = file.path if not file.wasRemoved() else "dev/null"
            newPath = file.path if not file.wasAdded() else "dev/null"

            result += "--- a/%s\n+++ b/%s\n" % (oldPath, newPath)

            if file.isBinaryChanges():
                result += "  Binary file.\n"
                continue

            for chunk in file.macro_chunks:
                deleteOffset = chunk.lines[0].old_offset
                deleteCount = len(filter(lambda line: line.type != diff.Line.INSERTED, chunk.lines))
                insertOffset = chunk.lines[0].new_offset
                insertCount = len(filter(lambda line: line.type != diff.Line.DELETED, chunk.lines))

                chunkHeader = "@@ -%d,%d +%d,%d @@" % (deleteOffset, deleteCount, insertOffset, insertCount)

                if db: codeContext = getCodeContext(db, file.new_sha1, insertOffset, minimized=True)
                else: codeContext = None

                if codeContext: chunkHeader += " %s" % codeContext[:80 - len(chunkHeader)]

                result += chunkHeader + "\n"

                lines = iter(chunk.lines)
                line = lines.next()

                try:
                    while line:
                        while line.type == diff.Line.CONTEXT:
                            result += "  %s\n" % line.new_value
                            line = lines.next()

                        deleted = []
                        inserted = []

                        try:
                            while line.type != diff.Line.CONTEXT:
                                if line.type != diff.Line.INSERTED: deleted.append(line)
                                if line.type != diff.Line.DELETED: inserted.append(line)
                                line = lines.next()
                        except StopIteration:
                            line = None

                        for deletedLine in deleted:
                            result += "- %s\n" % deletedLine.old_value
                        for insertedLine in inserted:
                            result += "+ %s\n" % insertedLine.new_value
                except StopIteration:
                    pass
        finally:
            file.clean()

    return result
