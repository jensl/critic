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

import gitutils
import diff.analyze
import syntaxhighlight
import htmlutils

re_modeline = re.compile(r"-\*-\s*(.*?)\s*-\*-")
re_tabwidth = re.compile(r"(?:^|[ \t;])tab-width:\s*([0-9]+)(?:$|;)", re.I)
re_indent_tabs_mode = re.compile(r"(?:^|[ \t;])indent-tabs-mode:\s*(t|nil)(?:$|;)", re.I)
re_mode = re.compile(r"(?:^|[ \t;])mode:\s*([^;]+)(?:$|;)", re.I)

# Low-level chunk of difference between two versions of a file.  One chunk
# represents a possibly empty set of consecutive lines in the old version of the
# file being replaced by another possibly empty set of consecutive lines in the
# new version of the file.  (Both sets are never empty, of course.)
class Chunk:
    def __init__(self, delete_offset, delete_count, insert_offset, insert_count, **kwargs):
        # Primary information: identifying the line numbers of deleted lines and
        # the line numbers of inserted lines.  If lines are only inserted
        # delete_count is zero and delete_offset marks where, in the old version
        # of the file, this chunks adds its lines.  If lines are only deleted,
        # insert_count is zero and insert_offset marks where, in the new version
        # of the file, the deleted lines would have been.
        #
        # Line numbers are 1-based, that is, the first line is number 1.
        self.delete_offset = delete_offset
        self.delete_count = delete_count
        self.insert_offset = insert_offset
        self.insert_count = insert_count

        # Optional: the ID of the chunk.
        self.id = kwargs.get("id")

        # Optional: True if the chunk contains only white-space changes.
        self.is_whitespace = kwargs.get("is_whitespace")

        # Optional: the actual deleted and/or inserted lines.
        self.deleted_lines = kwargs.get("deleted_lines")
        self.inserted_lines = kwargs.get("inserted_lines")

        # Optional: chunk analysis, linking together "matching" lines within the
        # chunk and describing how such matching lines changed from the old
        # version to the new version.
        self.analysis = kwargs.get("analysis")

    def copy(self):
        return Chunk(self.delete_offset, self.delete_count,
                     self.insert_offset, self.insert_count,
                     deleted_lines=self.deleted_lines,
                     inserted_lines=self.inserted_lines,
                     analysis=self.analysis)

    def isBinary(self):
        return self.delete_count == self.insert_count == 0

    def analyze(self, file, last_chunk=False, reanalyze=False):
        if (reanalyze or not self.analysis) and self.delete_count != 0 and self.insert_count != 0:
            if not self.deleted_lines:
                file.loadOldLines()
                self.deleted_lines = file.getOldLines(self)

            if not self.inserted_lines:
                file.loadNewLines()
                self.inserted_lines = file.getNewLines(self)

            if self.is_whitespace:
                self.analysis = diff.analyze.analyzeWhiteSpaceChanges(self.deleted_lines, self.inserted_lines, last_chunk and self.delete_offset + self.delete_count + file.oldCount())
            else:
                self.analysis = diff.analyze.analyzeChunk(self.deleted_lines, self.inserted_lines)

    def deleteEnd(self):
        return self.delete_offset + self.delete_count

    def insertEnd(self):
        return self.insert_offset + self.insert_count

    def delta(self):
        return self.insert_count - self.delete_count

    def __str__(self):
        return "@@ -%d,%d +%d,%d @@" % (self.delete_offset, self.delete_count, self.insert_offset, self.insert_count)

    def __repr__(self):
        if self.analysis: analysis = ", analysis=%r" % self.analysis
        else: analysis = ""
        return "Chunk(delete_offset=%d, delete_count=%d, insert_offset=%d, insert_count=%d%s)" % (self.delete_offset, self.delete_count, self.insert_offset, self.insert_count, analysis)

    def __eq__(self, other):
        return self.delete_offset == other.delete_offset and self.insert_offset == other.insert_offset

    def getLines(self):
        assert not (self.deleted_lines is None or self.inserted_lines is None)

        lines = []
        terminator = "%d=%d" % (self.delete_count, self.insert_count)

        if self.analysis: analysis = self.analysis + ";" + terminator
        else: analysis = terminator

        mappings = analysis.split(";")
        old_offset = self.delete_offset
        new_offset = self.insert_offset

        for mapping in mappings:
            old_line, new_line = mapping.split(":")[0].split("=")
            old_line = self.delete_offset + int(old_line)
            new_line = self.insert_offset + int(new_line)

            while old_offset < old_line and new_offset < new_line:
                old_value = self.deleted_lines[old_offset - self.delete_offset]
                new_value = self.inserted_lines[new_offset - self.insert_offset]
                line_type = Line.CONTEXT if old_value == new_value else Line.REPLACED
                lines.append(Line(line_type, old_offset, old_value, new_offset, new_value))
                old_offset += 1
                new_offset += 1

            while old_offset < old_line:
                old_value = self.deleted_lines[old_offset - self.delete_offset]
                lines.append(Line(Line.DELETED, old_offset, old_value, new_offset, None))
                old_offset += 1

            while new_offset < new_line:
                new_value = self.inserted_lines[new_offset - self.insert_offset]
                lines.append(Line(Line.INSERTED, old_offset, None, new_offset, new_value))
                new_offset += 1

            if old_line == self.deleteEnd(): break

            old_value = self.deleted_lines[old_line - self.delete_offset]
            new_value = self.inserted_lines[new_line - self.insert_offset]
            lines.append(Line(Line.MODIFIED, old_line, old_value, new_line, new_value))
            old_offset += 1
            new_offset += 1

        return lines

re_conflict = re.compile("^(?:(?:&lt;){7}|={7}|(?:<b[^>]*>=</b>){7}|(?:&gt;){7})")

# Line in "macro chunk".  Representing either a context line, or a line that has
# been changed (modified, deleted or inserted.)
class Line:
    CONTEXT    = 1
    DELETED    = 2
    MODIFIED   = 3
    REPLACED   = 4
    INSERTED   = 5
    WHITESPACE = 6
    CONFLICT   = 7

    def __init__(self, type, old_offset, old_value, new_offset, new_value, **kwargs):
        # The type of line.  One of CONTEXT, MODIFIED, DELETED, INSERTED and
        # REPLACED.
        self.type = type

        # The line number of this line in the old and new versions of the file,
        # and the actual line value.  If the line represents an inserted line,
        # old_offset will be the line number of the next non-deleted line in the
        # old version of the file and old_value will be None.  If the line
        # represents a deleted line, new_offset will be the line number of the
        # next non-inserted line in the new version of the file and new_value
        # will be None.
        self.old_offset = old_offset
        self.old_value = old_value
        self.new_offset = new_offset
        self.new_value = new_value

        # The difference between old_value and new_value is only in white-space.
        self.is_whitespace = kwargs.get("is_whitespace", False)

    def __repr__(self):
        if self.type == Line.CONTEXT: type_string = "CONTEXT"
        elif self.type == Line.DELETED: type_string = "DELETED"
        elif self.type == Line.MODIFIED: type_string = "MODIFIED"
        elif self.type == Line.REPLACED: type_string = "REPLACED"
        elif self.type == Line.INSERTED: type_string = "INSERTED"
        return "Line(%s, %d:%d)" % (type_string, self.old_offset, self.new_offset)

    def isConflictMarker(self):
        return self.old_value and bool(re_conflict.match(self.old_value))

# Higher-level chunk of differences between two versions of a file.  Constructed
# by padding low-level chunks with a variable number of context lines.  Chunks
# whose contexts overlap are merged into a single "macro chunk."
class MacroChunk:
    def __init__(self, chunks, lines):
        # List of low-level chunks that make up this macro chunk.
        self.chunks = chunks

        # List of lines in the macro chunk.
        self.lines = lines

        # Line numbers and size of this macro chunk in the old and new versions
        # of the file.  Note that this includes the context lines, and thus does
        # not only represent actual changes.
        self.old_offset = lines[0].old_offset
        self.old_count = lines[-1].old_offset - lines[0].old_offset + 1
        self.new_offset = lines[0].new_offset
        self.new_count = lines[-1].new_offset - lines[0].new_offset + 1

# Container for difference information per file.
class File:
    def __init__(self, id=None, path=None, old_sha1=None, new_sha1=None, repository=None, **kwargs):
        self.id = id
        self.path = path
        self.old_sha1 = old_sha1
        self.new_sha1 = new_sha1
        self.old_mode = kwargs.get("old_mode")
        self.new_mode = kwargs.get("new_mode")
        self.repository = repository

        if isinstance(self.old_mode, int):
            self.old_mode = "%o" % self.old_mode
        if isinstance(self.new_mode, int):
            self.new_mode = "%o" % self.new_mode

        # List of low-level chunks affecting the file.
        self.chunks = kwargs.get("chunks")

        # List of macro chunks affecting the file.
        self.macro_chunks = kwargs.get("macro_chunks")

        # Lists of actual lines in the old and new versions of the file.  Each
        # line is a string, not including the linebreak character.
        self.old_plain = kwargs.get("old_plain")
        self.new_plain = kwargs.get("new_plain")
        self.old_highlighted = kwargs.get("old_highlighted")
        self.old_is_highlighted = bool(self.old_highlighted)
        self.new_highlighted = kwargs.get("new_highlighted")
        self.new_is_highlighted = bool(self.new_highlighted)

        # List of comment chains that apply to the whole file.
        self.file_comment_chains = []

        # List of comment chains that apply to the selected lines in the file.
        self.code_comment_chains = []

        self.move_source_file = kwargs.get("move_source_file")
        self.move_target_file = kwargs.get("move_target_file")

        self.modeline = {}
        self.interpreter = {}

    def clean(self):
        self.chunks = None
        self.macro_chunks = None
        self.old_plain = None
        self.new_plain = None
        self.old_highlighted = None
        self.new_highlighted = None

    def __hash__(self):
        return hash(self.id)

    def __int__(self):
        return self.id

    def __repr__(self):
        return "diff.File(id=%d, path=%r)" % (self.id or -1, self.path)

    def hasChanges(self):
        return self.old_sha1 is not None and self.new_sha1 is not None

    def isEmptyChanges(self):
        """Return true if empty diff information is recorded."""
        return self.hasChanges() \
            and len(self.chunks) == 1 \
            and self.chunks[0].delete_count == 0 \
            and self.chunks[0].insert_count == 0

    def isEmptyFile(self):
        """Return true if this is an added or deleted empty (zero-length) file."""
        if self.isEmptyChanges():
            if self.wasAdded() and self.newSize() == 0:
                return True
            elif self.wasRemoved() and self.oldSize() == 0:
                return True
        return False

    def isBinaryChanges(self):
        """Return true if this is a binary file."""
        return self.isEmptyChanges() and not self.isEmptyFile()

    def wasAdded(self):
        """Return true if this file was added."""
        return self.old_sha1 == '0' * 40

    def wasRemoved(self):
        """Return true if this file was deleted."""
        return self.new_sha1 == '0' * 40

    def oldSize(self):
        """Return size of old version of file, or None if file was deleted."""
        if self.old_sha1 != '0' * 40:
            return self.repository.fetch(self.old_sha1, fetchData=False).size
        else:
            return None

    def newSize(self):
        """Return size of new version of file, or None if file was deleted."""
        if self.new_sha1 != '0' * 40:
            return self.repository.fetch(self.new_sha1, fetchData=False).size
        else:
            return None

    def loadOldLines(self, highlighted=False, request_highlight=False):
        """Load the lines of the old version of the file, optionally highlighted."""

        from diff.parse import splitlines

        if self.old_sha1 is None or self.old_sha1 == '0' * 40:
            self.old_plain = []
            self.old_highlighted = []
            return
        elif self.old_mode and self.old_mode == "160000":
            self.old_plain = self.old_highlighted = ["Subproject commit %s" % self.old_sha1]
            return

        if highlighted:
            if self.old_highlighted and self.old_is_highlighted: return
            else:
                self.old_is_highlighted = True
                language = self.getLanguage(use_content="old")
                if language:
                    data = syntaxhighlight.readHighlight(self.repository, self.old_sha1, self.path, language, request=request_highlight)
                elif self.old_highlighted: return
                else:
                    data = htmlutils.htmlify(self.repository.fetch(self.old_sha1).data)
                self.old_highlighted = splitlines(data)
                self.old_eof_eol = data and data[-1] in "\n\r"
        else:
            if self.old_plain: return
            else:
                data = self.repository.fetch(self.old_sha1).data
                self.old_plain = splitlines(data)
                self.old_eof_eol = data and data[-1] in "\n\r"

    def loadNewLines(self, highlighted=False, request_highlight=False):
        """Load the lines of the new version of the file, optionally highlighted."""

        from diff.parse import splitlines

        if self.new_sha1 is None or self.new_sha1 == '0' * 40:
            self.new_plain = []
            self.new_highlighted = []
            return
        elif self.new_mode and self.new_mode == "160000":
            self.new_plain = self.new_highlighted = ["Subproject commit %s" % self.new_sha1]
            return

        if highlighted:
            if self.new_highlighted and self.new_is_highlighted: return
            else:
                self.new_is_highlighted = True
                language = self.getLanguage(use_content="new")
                if language:
                    data = syntaxhighlight.readHighlight(self.repository, self.new_sha1, self.path, language, request=request_highlight)
                elif self.new_highlighted: return
                else:
                    data = htmlutils.htmlify(self.repository.fetch(self.new_sha1).data)
                self.new_highlighted = splitlines(data)
                self.new_eof_eol = data and data[-1] in "\n\r"
        else:
            if self.new_plain: return
            else:
                data = self.repository.fetch(self.new_sha1).data
                self.new_plain = splitlines(data)
                self.new_eof_eol = data and data[-1] in "\n\r"

    def getOldLines(self, chunk, highlighted=False):
        begin = chunk.delete_offset - 1
        end = begin + chunk.delete_count
        return self.oldLines(highlighted)[begin:end]

    def getNewLines(self, chunk, highlighted=False):
        begin = chunk.insert_offset - 1
        end = begin + chunk.insert_count
        return self.newLines(highlighted)[begin:end]

    def oldLines(self, highlighted):
        if highlighted: return self.old_highlighted
        else: return self.old_plain

    def oldCount(self):
        if self.old_highlighted is not None: return len(self.old_highlighted)
        else: return len(self.old_plain)

    def newLines(self, highlighted):
        if highlighted: return self.new_highlighted
        else: return self.new_plain

    def newCount(self):
        if self.new_highlighted is not None: return len(self.new_highlighted)
        else: return len(self.new_plain)

    def canHighlight(self):
        return self.getLanguage() is not None

    def getLanguage(self, use_content=False):
        if (self.path.endswith(".h") or
            self.path.endswith(".c") or
            self.path.endswith(".cpp") or
            self.path.endswith(".hh") or
            self.path.endswith(".cc")):
            return "c++"
        elif (self.path.endswith(".py") or
              self.path.endswith(".gyp") or
              self.path.endswith(".gypi")):
            return "python"
        elif (self.path.endswith(".pl") or
              self.path.endswith(".pm")):
            return "perl"
        elif self.path.endswith(".java"):
            return "java"
        elif self.path.endswith(".rb"):
            return "ruby"
        elif self.path.endswith(".js"):
            return "javascript"
        elif self.path.endswith(".php"):
            return "php"
        elif (self.path.endswith(".mk") or
              self.path.endswith("/Makefile")):
            return "makefile"
        elif (self.path.endswith(".m") or
              self.path.endswith(".mm")):
            return "objective-c"
        elif self.path.endswith(".sql"):
            return "sql"
        # XML syntax highlighting is disabled due to issues (the pygments
        # lexer messes with the line-endings in the file.)
        #elif self.path.endswith(".xml"):
        #    return "xml"

        if use_content:
            interpreter = self.getInterpreter(use_content)
            if interpreter:
                executable = interpreter.split("/")[-1]
                if executable.startswith("python"):
                    return "python"
                elif executable.startswith("perl"):
                    return "perl"

            modeline = self.getModeLine(use_content)
            if modeline:
                match = re_mode.search(modeline)
                if match:
                    mode = match.group(1).strip()
                    if mode in ("c++", "python", "perl", "java", "ruby", "js", "php", "makefile"):
                        return mode

        return None

    def getInterpreter(self, side="new"):
        if side not in self.interpreter:
            if side == "new":
                self.loadNewLines()
                lines = self.new_plain
            else:
                self.loadOldLines()
                lines = self.old_plain
            self.interpreter[side] = ""
            for line in lines:
                if line.startswith("#!"):
                    words = line[2:].split()
                    if re.search("(^|/)env$", words[0]): self.interpreter[side] = words[1]
                    else: self.interpreter[side] = words[0]
                    break
        return self.interpreter[side]

    def getModeLine(self, side="new"):
        if side not in self.modeline:
            if side == "new":
                self.loadNewLines()
                lines = self.new_plain
            else:
                self.loadOldLines()
                lines = self.old_plain
            self.modeline[side] = ""
            for line in lines:
                if line.startswith("#!"): continue
                match = re_modeline.search(line)
                if match: self.modeline[side] = match.group(1)
                break
        return self.modeline[side]

    def getTabWidth(self, side="new", default=8):
        modeline = self.getModeLine(side)
        try: return int(re_tabwidth.search(modeline).group(1))
        except: return default

    def getIndentTabsMode(self, side="new", default=True):
        modeline = self.getModeLine(side)
        try: return re_indent_tabs_mode.search(modeline).group(1) == "t"
        except: return default

    @staticmethod
    def sorted(files, key=lambda file: file.path):
        def compareFilenames(a, b):
            def isSource(name): return name.endswith(".cpp") or name.endswith(".cc")
            def isHeader(name): return name.endswith(".h")

            if isHeader(a) and isSource(b) and a.rsplit(".", 1)[0] == b.rsplit(".", 1)[0]: return -1
            elif isSource(a) and isHeader(b) and a.rsplit(".", 1)[0] == b.rsplit(".", 1)[0]: return 1
            else: return cmp(a, b)

        return sorted(files, key=key, cmp=compareFilenames)

    @staticmethod
    def eliminateCommonPrefixes(files, text=False, getpath=None, setpath=None):
        assert (getpath is None) == (setpath is None)

        if getpath is None:
            def defaultGetPath(x): return x
            getpath = defaultGetPath
        if setpath is None:
            def defaultSetPath(x, p): files[index] = p
            setpath = defaultSetPath

        def commonPrefixLength(pathA, pathB):
            componentsA = pathA.split('/')
            componentsB = pathB.split('/')
            for index in range(min(len(componentsA), len(componentsB))):
                if componentsA[index] != componentsB[index]:
                    return sum(map(len, componentsA[:index])) + index

        if files:
            previous = getpath(files[0])
            for index in range(1, len(files)):
                length = commonPrefixLength(previous, getpath(files[index]))
                previous = getpath(files[index])
                if text and length > 4: setpath(files[index], " " * (length - 4) + ".../" + previous[length:])
                if not text and length > 2: setpath(files[index], " " * (length - 2) + "&#8230;/" + previous[length:])

        return files

class Changeset:
    def __init__(self, id, parent, child, type, files=None, commits=None):
        self.id = id
        self.parent = parent
        self.child = child
        self.type = type
        self.files = files
        self.conflicts = False

        self.__commits = commits if commits else [child] if type == "direct" else None
        self.__file_by_id = {}

    def __hash__(self): return hash(self.id)
    def __eq__(self, other): return self.id == other.id

    def commits(self, db):
        if self.__commits is None:
            iter = self.child
            self.__commits = [iter]
            while self.parent not in iter.parents:
                if len(iter.parents) != 1: return []
                iter = gitutils.Commit.fromSHA1(db, iter.repository, iter.parents[0])
                self.__commits.append(iter)
        return self.__commits

    def setCommits(self, commits):
        self.__commits = commits

    def getFile(self, file_id):
        if self.files and not self.__file_by_id:
            for file in self.files:
                self.__file_by_id[file.id] = file
        return self.__file_by_id.get(file_id)

    def getReviewFiles(self, db, user, review):
        files = {}

        if self.files and not self.__file_by_id:
            for file in self.files:
                self.__file_by_id[file.id] = file

        def process(cursor):
            for file_id, state, reviewer, is_reviewer, draft_from, draft_to in cursor:
                if file_id not in self.__file_by_id: continue
                if draft_from == state: state = draft_to
                if files.has_key(file_id):
                    existing = files[file_id]
                    reviewers = existing[2]
                    files[file_id] = (existing[0] or is_reviewer, state if existing[1] == state else "mixed", existing[2])
                else:
                    reviewers = set()
                    files[file_id] = (is_reviewer, state, reviewers)
                if reviewer is not None: reviewers.add(reviewer)

        if self.type in ("merge", "conflicts"):
            cursor = db.cursor()
            cursor.execute("""SELECT reviewfiles.file, reviewfiles.state, reviewfiles.reviewer, reviewuserfiles.uid IS NOT NULL, reviewfilechanges.from, reviewfilechanges.to
                                FROM reviewfiles
                     LEFT OUTER JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id AND reviewuserfiles.uid=%s)
                     LEFT OUTER JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id AND reviewfilechanges.uid=%s AND reviewfilechanges.state='draft')
                               WHERE reviewfiles.review=%s
                                 AND reviewfiles.changeset=%s""",
                           (user.id, user.id, review.id, self.id))
            process(cursor)
        elif self.__commits:
            cursor = db.cursor()
            cursor.execute("""SELECT reviewfiles.file, reviewfiles.state, reviewfiles.reviewer, reviewuserfiles.uid IS NOT NULL, reviewfilechanges.from, reviewfilechanges.to
                                FROM reviewfiles
                                JOIN changesets ON (changesets.id=reviewfiles.changeset)
                     LEFT OUTER JOIN reviewuserfiles ON (reviewuserfiles.file=reviewfiles.id AND reviewuserfiles.uid=%s)
                     LEFT OUTER JOIN reviewfilechanges ON (reviewfilechanges.file=reviewfiles.id AND reviewfilechanges.uid=%s AND reviewfilechanges.state='draft')
                               WHERE reviewfiles.review=%s
                                 AND changesets.child=ANY (%s)""",
                           (user.id, user.id, review.id, [commit.getId(db) for commit in self.__commits]))
            process(cursor)

        return files

    @staticmethod
    def fromId(db, repository, id):
        cursor = db.cursor()

        cursor.execute("SELECT parent, child, type FROM changesets WHERE id=%s", [id])
        parent_id, child_id, type = cursor.fetchone()

        parent = gitutils.Commit.fromId(db, repository, parent_id) if parent_id else None
        child = gitutils.Commit.fromId(db, repository, child_id)

        return Changeset(id, parent, child, type)
